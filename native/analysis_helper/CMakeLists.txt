cmake_minimum_required(VERSION 3.20)

project(tm_analysis_helper LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(TM_ANALYSIS_HELPER_ENABLE_ESSENTIA "Build the helper with Essentia integration" OFF)

add_executable(tm-analysis-helper
    src/essentia_pipeline.cpp
    src/json_io.cpp
    src/main.cpp
)

target_include_directories(tm-analysis-helper
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

if(TM_ANALYSIS_HELPER_ENABLE_ESSENTIA)
    target_compile_definitions(tm-analysis-helper PRIVATE TM_ANALYSIS_HELPER_ENABLE_ESSENTIA=1)
    message(STATUS "Essentia integration is expected to be provided by a future CMake update.")
endif()

if(MSVC)
    target_compile_options(tm-analysis-helper PRIVATE /W4 /permissive-)
else()
    target_compile_options(tm-analysis-helper PRIVATE -Wall -Wextra -Wpedantic)
endif()
