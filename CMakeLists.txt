cmake_minimum_required(VERSION 3.15)
project(TheiaMCR_C VERSION 3.5.1 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ==============================================================================
# Dependencies
# ==============================================================================
# We now include the lightweight header-only spdlog library directly inside 
# the 'include/' folder of the repository. This guarantees offline, 
# platform-agnostic, and lightning-fast builds on all development 
# machines and CI/CD servers.
#
# If spdlog is built as a header-only library, we define its target properties:
add_library(spdlog INTERFACE)
target_include_directories(spdlog INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_compile_definitions(spdlog INTERFACE 
    SPDLOG_ACTIVE_LEVEL=SPDLOG_LEVEL_INFO
    $<$<CXX_COMPILER_ID:MSVC>:_SECURE_SCL=0>
)

# Map spdlog::spdlog alias to maintain backward compatibility with project files
add_library(spdlog::spdlog ALIAS spdlog)

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
    target_link_libraries(TheiaMCR_C PRIVATE setupapi spdlog)
else()
    target_link_libraries(TheiaMCR_C PRIVATE spdlog)
endif()

# ==============================================================================
# Install rules (required for standard cmake --install)
# ==============================================================================
include(GNUInstallDirs)

install(TARGETS TheiaMCR_C
    EXPORT TheiaMCR_CTargets
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
)

# Installs all files in include/ (including spdlog headers)
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
# ==============================================================================
option(ENABLE_PYTHON_BINDINGS "Build pybind11 Python bindings" OFF)

if(ENABLE_PYTHON_BINDINGS)
    find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
    
    # Try to find pybind11, if not found, fetch it automatically
    find_package(pybind11 CONFIG QUIET)
    if(NOT pybind11_FOUND)
        message(STATUS "pybind11 not found, fetching from GitHub...")
        include(FetchContent)
        FetchContent_Declare(
            pybind11
            GIT_REPOSITORY https://github.com/pybind/pybind11.git
            GIT_TAG        v2.13.6
        )
        FetchContent_MakeAvailable(pybind11)
    endif()

    pybind11_add_module(TheiaMCR_py
        src/TheiaMCR_pybind11.cpp
        src/TheiaMCR.cpp
        src/SimpleSerial.cpp
    )

    target_include_directories(TheiaMCR_py PRIVATE include)

    if(MSVC)
        target_link_libraries(TheiaMCR_py PRIVATE setupapi spdlog)
    else()
        target_link_libraries(TheiaMCR_py PRIVATE spdlog)
    endif()

    install(TARGETS TheiaMCR_py
        LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
        RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    )
endif()

# ==============================================================================
# C++ Examples (optional)
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
        target_link_libraries(Example_3.5 PRIVATE setupapi spdlog)
    else()
        target_link_libraries(Example_3.5 PRIVATE spdlog)
    endif()
endif()
