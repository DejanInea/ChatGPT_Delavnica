cmake_minimum_required(VERSION 3.15)
project(WaterFlowVisualization LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(WATER_FLOW_USE_OPENCV "Enable live preview window using OpenCV" OFF)

find_package(ImageMagick COMPONENTS Magick++ REQUIRED)

if(WATER_FLOW_USE_OPENCV)
    find_package(OpenCV REQUIRED)
endif()

add_executable(water_flow_cpp water_flow_visualization.cpp)

target_include_directories(water_flow_cpp PRIVATE ${ImageMagick_INCLUDE_DIRS})
target_link_libraries(water_flow_cpp PRIVATE ${ImageMagick_LIBRARIES})

target_compile_definitions(water_flow_cpp PRIVATE ${ImageMagick_DEFINITIONS})

if(WATER_FLOW_USE_OPENCV)
    target_compile_definitions(water_flow_cpp PRIVATE USE_OPENCV)
    target_include_directories(water_flow_cpp PRIVATE ${OpenCV_INCLUDE_DIRS})
    target_link_libraries(water_flow_cpp PRIVATE ${OpenCV_LIBS})
endif()

if(MSVC)
    target_compile_options(water_flow_cpp PRIVATE /permissive- /W4)
else()
    target_compile_options(water_flow_cpp PRIVATE -Wall -Wextra -Wpedantic)
endif()
