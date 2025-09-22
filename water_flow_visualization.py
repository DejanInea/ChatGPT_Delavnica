#!/usr/bin/env python3
"""Visualize procedural water flow in real time and export an animated GIF."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np

try:
    import imageio.v2 as imageio  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    imageio = None


@dataclass
class SimulationConfig:
    resolution: int = 512
    steps: int = 180
    dt: float = 0.6
    strength: float = 1.4
    output_dir: Path = Path("output_frames")
    gif_name: str = "water_flow.gif"
    live_view: bool = True
    fps: int = 60


def build_grid(resolution: int) -> Tuple[np.ndarray, np.ndarray]:
    """Return normalized meshgrid coordinates in [0, 1)."""
    axis = np.linspace(0.0, 1.0, resolution, endpoint=False)
    return np.meshgrid(axis, axis, indexing="ij")


def stream_function(x: np.ndarray, y: np.ndarray, t: float) -> np.ndarray:
    """Time varying stream function whose curl yields a divergence-free field."""
    base = np.sin(2 * np.pi * (3 * x + 0.7 * t)) * np.sin(2 * np.pi * (3 * y - 0.5 * t))
    swirl = np.cos(2 * np.pi * (2 * x - 0.3 * t)) * np.cos(2 * np.pi * (2 * y + 0.4 * t))
    ripple = np.sin(2 * np.pi * (4 * x + y + 0.2 * t))
    return base + 0.6 * swirl + 0.25 * ripple


def velocity_field(resolution: int, t: float, strength: float) -> np.ndarray:
    """Compute a divergence-free velocity field from the stream function."""
    x, y = build_grid(resolution)
    psi = stream_function(x, y, t)
    dpsi_dy = np.gradient(psi, axis=0)
    dpsi_dx = np.gradient(psi, axis=1)

    u = dpsi_dy * strength * resolution  # horizontal component
    v = -dpsi_dx * strength * resolution  # vertical component
    velocity = np.stack((u, v), axis=-1)

    # Slight smoothing keeps the motion fluid without losing curls.
    velocity = gaussian_blur(velocity, sigma=1.0)
    return velocity


def gaussian_blur(field: np.ndarray, sigma: float = 1.0) -> np.ndarray:
    """Lightweight separable Gaussian blur implemented with numpy only."""
    if sigma <= 0:
        return field

    radius = int(max(1, sigma * 3))
    offsets = np.arange(-radius, radius + 1)
    weights = np.exp(-(offsets**2) / (2 * sigma**2))
    weights /= weights.sum()

    blurred = field.copy()
    for axis in range(2):
        blurred = np.apply_along_axis(
            lambda m: np.convolve(m, weights, mode="same"), axis, blurred
        )
    return blurred


def bilinear_sample(field: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Sample ``field`` at fractional coordinates (x, y) using bilinear interpolation."""
    h, w = field.shape[:2]
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)

    x0 = np.clip(x0, 0, w - 1)
    y0 = np.clip(y0, 0, h - 1)

    fx = x - x0
    fy = y - y0

    top = field[y0, x0] * (1 - fx)[..., None] + field[y0, x1] * fx[..., None]
    bottom = field[y1, x0] * (1 - fx)[..., None] + field[y1, x1] * fx[..., None]
    return top * (1 - fy)[..., None] + bottom * fy[..., None]


def advect(field: np.ndarray, velocity: np.ndarray, dt: float) -> np.ndarray:
    """Semi-Lagrangian advection step for a 3-channel field."""
    h, w = field.shape[:2]
    y, x = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")

    x_back = x - dt * velocity[..., 0]
    y_back = y - dt * velocity[..., 1]

    x_back = np.clip(x_back, 0, w - 1)
    y_back = np.clip(y_back, 0, h - 1)

    return bilinear_sample(field, x_back, y_back)


def create_initial_dye(resolution: int) -> np.ndarray:
    """Create a blue-ish dye field with subtle turbulence."""
    rng = np.random.default_rng(42)
    base_color = np.array([30, 90, 180], dtype=np.float32)
    dye = np.full((resolution, resolution, 3), base_color, dtype=np.float32)

    turbulence = rng.normal(0.0, 20.0, size=(resolution, resolution, 3))
    dye += turbulence

    vignette = np.hypot(*np.meshgrid(np.linspace(-1, 1, resolution),
                                      np.linspace(-1, 1, resolution)))
    vignette = np.clip(1.0 - 0.8 * vignette, 0.2, 1.0)
    dye *= vignette[..., None]

    return np.clip(dye, 0, 255)


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run_simulation(config: SimulationConfig) -> List[np.ndarray]:
    """Run the fluid advection simulation, streaming frames if requested."""
    base_dye = create_initial_dye(config.resolution)
    dye = base_dye.copy()
    frames: List[np.ndarray] = []

    fig = ax = im = None
    pause_time = max(0.0005, 1.0 / config.fps)

    if config.live_view:
        plt.ion()
        fig, ax = plt.subplots(figsize=(6, 6))
        im = ax.imshow(np.clip(dye, 0, 255).astype(np.uint8))
        ax.set_title("Procedural Water Flow")
        ax.axis("off")
        plt.show(block=False)

    for step in range(config.steps):
        t = step / config.steps * 6.0
        vel = velocity_field(config.resolution, t, config.strength)
        dye = advect(dye, vel, config.dt)

        # Gentle dissipation and color balancing keeps the palette vibrant.
        dye = 0.995 * dye + 0.005 * base_dye
        frame = np.clip(dye, 0, 255).astype(np.uint8)
        frames.append(frame)

        if config.live_view and im is not None:
            im.set_data(frame)
            fig.canvas.draw_idle()
            fig.canvas.flush_events()
            plt.pause(pause_time)

    if config.live_view:
        plt.ioff()
        plt.show()

    return frames


def save_gif(frames: List[np.ndarray], config: SimulationConfig) -> None:
    if imageio is None:
        print("imageio not available; skipping GIF export. Use `pip install imageio` to enable it.")
        return

    ensure_output_dir(config.output_dir)
    output_path = config.output_dir / config.gif_name
    imageio.mimsave(output_path, frames, fps=config.fps)
    print(f"Saved animation to {output_path}")


def apply_cli_overrides(config: SimulationConfig, args: List[str]) -> SimulationConfig:
    """Allow simple key=value overrides without argparse."""
    for raw in args:
        if not raw.startswith("--"):
            print(f"Ignoring argument '{raw}'. Use --key=value format or --no-live-view.")
            continue

        key = raw[2:]
        if key == "no-live-view":
            config.live_view = False
            continue

        if "=" not in key:
            print(f"Ignoring argument '--{key}'. Expected --key=value format or --no-live-view.")
            continue

        opt, value = key.split("=", 1)
        try:
            if opt == "steps":
                config.steps = int(value)
            elif opt == "resolution":
                config.resolution = int(value)
            elif opt == "dt":
                config.dt = float(value)
            elif opt == "strength":
                config.strength = float(value)
            elif opt == "gif-name":
                config.gif_name = value
            elif opt == "output-dir":
                config.output_dir = Path(value)
            elif opt == "fps":
                config.fps = int(value)
            else:
                print(f"Unknown option '--{opt}'.")
        except ValueError as exc:
            print(f"Failed to parse value for '--{opt}': {exc}")
    return config


def main() -> None:
    config = SimulationConfig()
    config = apply_cli_overrides(config, sys.argv[1:])
    frames = run_simulation(config)
    save_gif(frames, config)


if __name__ == "__main__":
    main()
