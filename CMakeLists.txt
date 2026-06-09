cmake_minimum_required(VERSION 3.15)
project(TheiaMCR_C VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Source files
set(SOURCES
    src/SimpleSerial.cpp
    src/TheiaMCR.cpp
    src/TheiaMCR_C.cpp
)

# Core shared library compilation
add_library(TheiaMCR_C SHARED ${SOURCES})

# Include directories
target_include_directories(TheiaMCR_C PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

# Set library properties for shared library
set_target_properties(TheiaMCR_C PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 1
    POSITION_INDEPENDENT_CODE ON
)

# On Windows, we need to export symbols
if(MSVC)
    target_compile_definitions(TheiaMCR_C PRIVATE "THEIAMCR_C_EXPORTS")
    # Link with setupapi (required for Windows serial APIs)
    target_link_libraries(TheiaMCR_C PRIVATE setupapi spdlog::spdlog)
else()
    target_link_libraries(TheiaMCR_C PRIVATE spdlog::spdlog)
endif()


# ==============================================================================
# pybind11 Integration
# ==============================================================================
# Prefer Python 3.13 over other installed versions (e.g. Windows Store Python 3.11)
set(Python3_ROOT_DIR "$ENV{LOCALAPPDATA}/Programs/Python/Python313")
find_package(Python3 3.13 EXACT COMPONENTS Interpreter Development REQUIRED)

# FetchContent automatically downloads pybind11 during configure-time
include(FetchContent)
FetchContent_Declare(
  pybind11
  GIT_REPOSITORY https://github.com/pybind/pybind11.git
  GIT_TAG        v2.11.1
)
FetchContent_Declare(
  spdlog
  GIT_REPOSITORY https://github.com/gabime/spdlog.git
  GIT_TAG        v1.14.1
)
FetchContent_MakeAvailable(pybind11 spdlog)

# Compile native Python bindings
pybind11_add_module(TheiaMCR_py
    src/TheiaMCR_pybind11.cpp
    src/TheiaMCR.cpp
    src/SimpleSerial.cpp
)

# Include directories for python bindings
target_include_directories(TheiaMCR_py PRIVATE include)

if(MSVC)
    target_link_libraries(TheiaMCR_py PRIVATE setupapi spdlog::spdlog)
else()
    target_link_libraries(TheiaMCR_py PRIVATE spdlog::spdlog)
endif()


# ==============================================================================
# C++ Example (optional — disabled by default to keep normal builds fast)
# Enable with: cmake -DBUILD_EXAMPLES=ON ..
# ==============================================================================
option(BUILD_EXAMPLES "Build C++ example executables" OFF)
if(BUILD_EXAMPLES)
    add_executable(Example_3.5
        Examples/cpp/Example_3.5.cpp
        src/SimpleSerial.cpp
        src/TheiaMCR.cpp
    )
    target_include_directories(Example_3.5 PRIVATE include)
    if(MSVC)
        target_link_libraries(Example_3.5 PRIVATE setupapi spdlog::spdlog)
    else()
        target_link_libraries(Example_3.5 PRIVATE spdlog::spdlog)
    endif()
endif()
