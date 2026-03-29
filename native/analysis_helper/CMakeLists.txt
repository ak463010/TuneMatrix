cmake_minimum_required(VERSION 3.20)

project(tm_analysis_helper LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(TM_ANALYSIS_HELPER_ENABLE_ESSENTIA "Build the helper with Essentia integration" OFF)
set(
    TM_ANALYSIS_HELPER_ESSENTIA_ROOT
    "$ENV{ESSENTIA_ROOT}"
    CACHE PATH
    "Root directory of the Essentia installation"
)

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
    find_path(
        TM_ANALYSIS_HELPER_ESSENTIA_INCLUDE_DIR
        NAMES
            essentia/algorithmfactory.h
            essentia/essentia.h
        HINTS
            ${TM_ANALYSIS_HELPER_ESSENTIA_ROOT}
        PATH_SUFFIXES
            include
    )
    find_library(
        TM_ANALYSIS_HELPER_ESSENTIA_LIBRARY
        NAMES
            essentia
            libessentia
        HINTS
            ${TM_ANALYSIS_HELPER_ESSENTIA_ROOT}
        PATH_SUFFIXES
            lib
            lib64
            build
            build\Release
            build\Debug
    )

    if(NOT TM_ANALYSIS_HELPER_ESSENTIA_INCLUDE_DIR OR NOT TM_ANALYSIS_HELPER_ESSENTIA_LIBRARY)
        message(
            FATAL_ERROR
            "Essentia was requested but not found. Set TM_ANALYSIS_HELPER_ESSENTIA_ROOT or ESSENTIA_ROOT to an Essentia install containing include/essentia and the Essentia library."
        )
    endif()

    target_compile_definitions(tm-analysis-helper PRIVATE TM_ANALYSIS_HELPER_ENABLE_ESSENTIA=1)
    target_include_directories(
        tm-analysis-helper
        PRIVATE
            ${TM_ANALYSIS_HELPER_ESSENTIA_INCLUDE_DIR}
    )
    target_link_libraries(
        tm-analysis-helper
        PRIVATE
            ${TM_ANALYSIS_HELPER_ESSENTIA_LIBRARY}
    )

    message(STATUS "Essentia include dir: ${TM_ANALYSIS_HELPER_ESSENTIA_INCLUDE_DIR}")
    message(STATUS "Essentia library: ${TM_ANALYSIS_HELPER_ESSENTIA_LIBRARY}")
endif()

if(MSVC)
    target_compile_definitions(tm-analysis-helper PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
    target_compile_options(tm-analysis-helper PRIVATE /W4 /permissive-)
else()
    target_compile_options(tm-analysis-helper PRIVATE -Wall -Wextra -Wpedantic)
endif()
