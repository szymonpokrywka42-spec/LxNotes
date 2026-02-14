cmake_minimum_required(VERSION 3.16)
project(lxcharset_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(lxcharset_core STATIC
    src/detector.cpp
)

target_include_directories(lxcharset_core
    PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include
)
