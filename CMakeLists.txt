cmake_minimum_required(VERSION 3.15)
project(TheiaMCR_C VERSION 3.5.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ==============================================================================
# Dependencies
# ==============================================================================
# Try CONFIG mode first (vcpkg supplies this); fall back to MODULE for non-vcpkg builds
find_package(spdlog CONFIG QUIET)
if(NOT spdlog_FOUND)
    message(STATUS "spdlog not found via CONFIG, trying MODULE mode")
    find_package(spdlog REQUIRED MODULE)
endif()

# ==============================================================================
# Core shared library
# ==============================================================================
set(SOURCES
    src/SimpleSerial.cpp
    src/TheiaMCR.cpp
    src/TheiaMCR_C.cpp
)

add_library(TheiaMCR_C SHARED ${SOURCES})

target_include_directories(TheiaMCR_C PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

set_target_properties(TheiaMCR_C PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 1
    POSITION_INDEPENDENT_CODE ON
)

if(MSVC)
    target_compile_definitions(TheiaMCR_C PRIVATE "THEIAMCR_C_EXPORTS")
    target_link_libraries(TheiaMCR_C PRIVATE setupapi spdlog::spdlog)
else()
    target_link_libraries(TheiaMCR_C PRIVATE spdlog::spdlog)
endif()

# ==============================================================================
# Install rules (required for vcpkg and standard cmake --install)
# ==============================================================================
include(GNUInstallDirs)

install(TARGETS TheiaMCR_C
    EXPORT TheiaMCR_CTargets
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
)

# Installs SimpleSerial.h, TheiaMCR_C.h, and TheiaMCR.h
install(DIRECTORY include/
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(EXPORT TheiaMCR_CTargets
    FILE TheiaMCR_CTargets.cmake
    NAMESPACE TheiaMCR_C::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/TheiaMCR_C
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/cmake/TheiaMCR_CConfig.cmake.in"
    "${CMAKE_CURRENT_BINARY_DIR}/TheiaMCR_CConfig.cmake"
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/TheiaMCR_C
)

write_basic_package_version_file(
    "${CMAKE_CURRENT_BINARY_DIR}/TheiaMCR_CConfigVersion.cmake"
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    "${CMAKE_CURRENT_BINARY_DIR}/TheiaMCR_CConfig.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/TheiaMCR_CConfigVersion.cmake"
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/TheiaMCR_C
)
# ==============================================================================
# pybind11 Integration (optional)
# Enabled by vcpkg when the "python" feature is requested, or manually with
# -DENABLE_PYTHON_BINDINGS=ON
# ==============================================================================
option(ENABLE_PYTHON_BINDINGS "Build pybind11 Python bindings" OFF)

if(ENABLE_PYTHON_BINDINGS)
    find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
    find_package(pybind11 CONFIG REQUIRED)

    pybind11_add_module(TheiaMCR_py
        src/TheiaMCR_pybind11.cpp
        src/TheiaMCR.cpp
        src/SimpleSerial.cpp
    )

    target_include_directories(TheiaMCR_py PRIVATE include)

    if(MSVC)
        target_link_libraries(TheiaMCR_py PRIVATE setupapi spdlog::spdlog)
    else()
        target_link_libraries(TheiaMCR_py PRIVATE spdlog::spdlog)
    endif()

    install(TARGETS TheiaMCR_py
        LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
        RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    )
endif()

# ==============================================================================
# C++ Examples (optional)
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