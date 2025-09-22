#include <algorithm>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <random>
#include <string>
#include <vector>

#include <Magick++.h>

#ifdef USE_OPENCV
#include <opencv2/highgui.hpp>
#include <opencv2/imgproc.hpp>
#endif

struct Config {
    int resolution = 512;
    int steps = 180;
    float dt = 0.6f;
    float strength = 1.4f;
    std::filesystem::path outputDir = "output_frames";
    std::string gifName = "water_flow.gif";
    bool liveView = true;
    int fps = 60;
};

static float streamFunction(float x, float y, float t) {
    constexpr float pi = 3.14159265358979323846f;
    const float base = std::sin(2.0f * pi * (3.0f * x + 0.7f * t)) * std::sin(2.0f * pi * (3.0f * y - 0.5f * t));
    const float swirl = std::cos(2.0f * pi * (2.0f * x - 0.3f * t)) * std::cos(2.0f * pi * (2.0f * y + 0.4f * t));
    const float ripple = std::sin(2.0f * pi * (4.0f * x + y + 0.2f * t));
    return base + 0.6f * swirl + 0.25f * ripple;
}

static void buildVelocityField(const Config& cfg, float t, std::vector<float>& velocity) {
    const int n = cfg.resolution;
    std::vector<float> psi(n * n);
    for (int y = 0; y < n; ++y) {
        for (int x = 0; x < n; ++x) {
            const float fx = static_cast<float>(x) / static_cast<float>(n);
            const float fy = static_cast<float>(y) / static_cast<float>(n);
            psi[y * n + x] = streamFunction(fx, fy, t);
        }
    }

    velocity.resize(n * n * 2);
    const float scale = cfg.strength * static_cast<float>(n) * 0.5f;

    for (int y = 0; y < n; ++y) {
        for (int x = 0; x < n; ++x) {
            const int idx = y * n + x;
            const int xp = std::min(x + 1, n - 1);
            const int xm = std::max(x - 1, 0);
            const int yp = std::min(y + 1, n - 1);
            const int ym = std::max(y - 1, 0);

            const float dpsi_dx = (psi[y * n + xp] - psi[y * n + xm]);
            const float dpsi_dy = (psi[yp * n + x] - psi[ym * n + x]);

            velocity[2 * idx + 0] = dpsi_dy * scale;
            velocity[2 * idx + 1] = -dpsi_dx * scale;
        }
    }
}

static void gaussianBlur(std::vector<float>& data, int width, int height, int channels, float sigma) {
    if (sigma <= 0.0f) {
        return;
    }
    const int radius = std::max(1, static_cast<int>(sigma * 3.0f));
    const int kernelSize = 2 * radius + 1;
    std::vector<float> kernel(kernelSize);
    float sum = 0.0f;
    for (int i = -radius; i <= radius; ++i) {
        const float value = std::exp(-(i * i) / (2.0f * sigma * sigma));
        kernel[i + radius] = value;
        sum += value;
    }
    for (float& v : kernel) {
        v /= sum;
    }

    std::vector<float> temp(data.size());

    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            for (int c = 0; c < channels; ++c) {
                float accum = 0.0f;
                for (int k = -radius; k <= radius; ++k) {
                    const int xi = std::clamp(x + k, 0, width - 1);
                    accum += data[(y * width + xi) * channels + c] * kernel[k + radius];
                }
                temp[(y * width + x) * channels + c] = accum;
            }
        }
    }

    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            for (int c = 0; c < channels; ++c) {
                float accum = 0.0f;
                for (int k = -radius; k <= radius; ++k) {
                    const int yi = std::clamp(y + k, 0, height - 1);
                    accum += temp[(yi * width + x) * channels + c] * kernel[k + radius];
                }
                data[(y * width + x) * channels + c] = accum;
            }
        }
    }
}

static std::vector<float> createInitialDye(const Config& cfg) {
    const int n = cfg.resolution;
    std::vector<float> dye(n * n * 3);
    std::mt19937 rng(42);
    std::normal_distribution<float> noise(0.0f, 20.0f);

    for (int y = 0; y < n; ++y) {
        for (int x = 0; x < n; ++x) {
            const int idx = (y * n + x) * 3;
            dye[idx + 0] = 30.0f + noise(rng);
            dye[idx + 1] = 90.0f + noise(rng);
            dye[idx + 2] = 180.0f + noise(rng);
        }
    }

    for (int y = 0; y < n; ++y) {
        for (int x = 0; x < n; ++x) {
            const int idx = (y * n + x) * 3;
            const float nx = (static_cast<float>(x) / (n - 1)) * 2.0f - 1.0f;
            const float ny = (static_cast<float>(y) / (n - 1)) * 2.0f - 1.0f;
            const float vignette = std::clamp(1.0f - 0.8f * std::hypot(nx, ny), 0.2f, 1.0f);
            dye[idx + 0] = std::clamp(dye[idx + 0] * vignette, 0.0f, 255.0f);
            dye[idx + 1] = std::clamp(dye[idx + 1] * vignette, 0.0f, 255.0f);
            dye[idx + 2] = std::clamp(dye[idx + 2] * vignette, 0.0f, 255.0f);
        }
    }

    return dye;
}

static void advect(const std::vector<float>& field, const std::vector<float>& velocity, int width, int height, float dt, std::vector<float>& out) {
    out.resize(field.size());
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            const int idx = y * width + x;
            float xBack = static_cast<float>(x) - dt * velocity[2 * idx + 0];
            float yBack = static_cast<float>(y) - dt * velocity[2 * idx + 1];

            xBack = std::clamp(xBack, 0.0f, static_cast<float>(width - 1));
            yBack = std::clamp(yBack, 0.0f, static_cast<float>(height - 1));

            const int x0 = static_cast<int>(std::floor(xBack));
            const int y0 = static_cast<int>(std::floor(yBack));
            const int x1 = std::min(x0 + 1, width - 1);
            const int y1 = std::min(y0 + 1, height - 1);

            const float fx = xBack - static_cast<float>(x0);
            const float fy = yBack - static_cast<float>(y0);

            for (int c = 0; c < 3; ++c) {
                const float top = field[(y0 * width + x0) * 3 + c] * (1.0f - fx) + field[(y0 * width + x1) * 3 + c] * fx;
                const float bottom = field[(y1 * width + x0) * 3 + c] * (1.0f - fx) + field[(y1 * width + x1) * 3 + c] * fx;
                out[idx * 3 + c] = top * (1.0f - fy) + bottom * fy;
            }
        }
    }
}

static Config applyOverrides(Config cfg, const std::vector<std::string>& args) {
    for (const auto& raw : args) {
        if (raw.rfind("--", 0) != 0) {
            std::cerr << "Ignoring argument '" << raw << "'. Use --key=value format or --no-live-view.\n";
            continue;
        }
        const std::string keyValue = raw.substr(2);
        if (keyValue == "no-live-view") {
            cfg.liveView = false;
            continue;
        }
        const auto pos = keyValue.find('=');
        if (pos == std::string::npos) {
            std::cerr << "Ignoring argument '--" << keyValue << "'. Expected --key=value format or --no-live-view.\n";
            continue;
        }
        const std::string key = keyValue.substr(0, pos);
        const std::string value = keyValue.substr(pos + 1);
        try {
            if (key == "steps") {
                cfg.steps = std::stoi(value);
            } else if (key == "resolution") {
                cfg.resolution = std::stoi(value);
            } else if (key == "dt") {
                cfg.dt = std::stof(value);
            } else if (key == "strength") {
                cfg.strength = std::stof(value);
            } else if (key == "gif-name") {
                cfg.gifName = value;
            } else if (key == "output-dir") {
                cfg.outputDir = value;
            } else if (key == "fps") {
                cfg.fps = std::stoi(value);
            } else {
                std::cerr << "Unknown option '--" << key << "'.\n";
            }
        } catch (const std::exception& ex) {
            std::cerr << "Failed to parse value for '--" << key << "': " << ex.what() << "\n";
        }
    }
    return cfg;
}

static void ensureOutputDir(const std::filesystem::path& dir) {
    if (!dir.empty()) {
        std::filesystem::create_directories(dir);
    }
}

int main(int argc, char** argv) {
    Magick::InitializeMagick(nullptr);

    Config cfg;
    std::vector<std::string> args;
    for (int i = 1; i < argc; ++i) {
        args.emplace_back(argv[i]);
    }
    cfg = applyOverrides(cfg, args);

    const int n = cfg.resolution;
    std::vector<float> baseDye = createInitialDye(cfg);
    std::vector<float> dye = baseDye;
    std::vector<float> tempDye(dye.size());
    std::vector<float> velocity;

    ensureOutputDir(cfg.outputDir);
    const std::string gifPath = (cfg.outputDir / cfg.gifName).string();

    std::vector<unsigned char> rgbBuffer(n * n * 3);

#ifdef USE_OPENCV
    cv::Mat display;
    std::vector<unsigned char> displayBuffer(n * n * 3);
    const double pauseSeconds = 1.0 / static_cast<double>(std::max(1, cfg.fps));
    const int pauseMs = std::max(1, static_cast<int>(pauseSeconds * 1000.0));
    if (cfg.liveView) {
        cv::namedWindow("Procedural Water Flow", cv::WINDOW_AUTOSIZE);
    }
#endif

    std::vector<Magick::Image> frames;
    frames.reserve(cfg.steps);
    const size_t delayCs = std::max<size_t>(1, static_cast<size_t>(std::round(100.0 / std::max(1, cfg.fps))));

    for (int step = 0; step < cfg.steps; ++step) {
        const float t = static_cast<float>(step) / static_cast<float>(cfg.steps) * 6.0f;
        buildVelocityField(cfg, t, velocity);
        gaussianBlur(velocity, n, n, 2, 1.0f);
        advect(dye, velocity, n, n, cfg.dt, tempDye);

        for (size_t i = 0; i < dye.size(); ++i) {
            dye[i] = 0.995f * tempDye[i] + 0.005f * baseDye[i];
        }

        for (int i = 0; i < n * n; ++i) {
            const float r = std::clamp(dye[3 * i + 0], 0.0f, 255.0f);
            const float g = std::clamp(dye[3 * i + 1], 0.0f, 255.0f);
            const float b = std::clamp(dye[3 * i + 2], 0.0f, 255.0f);
            rgbBuffer[3 * i + 0] = static_cast<unsigned char>(r);
            rgbBuffer[3 * i + 1] = static_cast<unsigned char>(g);
            rgbBuffer[3 * i + 2] = static_cast<unsigned char>(b);
#ifdef USE_OPENCV
            if (cfg.liveView) {
                displayBuffer[3 * i + 0] = static_cast<unsigned char>(b);
                displayBuffer[3 * i + 1] = static_cast<unsigned char>(g);
                displayBuffer[3 * i + 2] = static_cast<unsigned char>(r);
            }
#endif
        }

        Magick::Image frame;
        frame.size(Magick::Geometry(n, n));
        frame.depth(8);
        frame.magick("RGB");
        frame.read(n, n, "RGB", Magick::CharPixel, rgbBuffer.data());
        frame.animationDelay(static_cast<size_t>(delayCs));
        frames.emplace_back(std::move(frame));

#ifdef USE_OPENCV
        if (cfg.liveView) {
            display = cv::Mat(n, n, CV_8UC3, displayBuffer.data()).clone();
            cv::imshow("Procedural Water Flow", display);
            const int key = cv::waitKey(pauseMs);
            if (key == 27) {
                std::cout << "Stopping simulation (ESC pressed).\n";
                break;
            }
        }
#endif
    }

    try {
        Magick::writeImages(frames.begin(), frames.end(), gifPath);
        std::cout << "Saved animation to " << gifPath << "\n";
    } catch (const Magick::Exception& err) {
        std::cerr << "Failed to write GIF: " << err.what() << "\n";
        return 1;
    }

#ifdef USE_OPENCV
    if (cfg.liveView) {
        cv::destroyWindow("Procedural Water Flow");
    }
#endif

    return 0;
}
