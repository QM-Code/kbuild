if(NOT DEFINED KTOOLS_CMAKE_MINIMUM_VERSION OR KTOOLS_CMAKE_MINIMUM_VERSION STREQUAL "")
    set(KTOOLS_CMAKE_MINIMUM_VERSION "{{CMAKE_MINIMUM_VERSION}}")
endif()
cmake_minimum_required(VERSION ${KTOOLS_CMAKE_MINIMUM_VERSION})

project({{LIBRARY_ID}} VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(KTOOLS_DEMO_BUILD_STATIC "Build demo static library target" ON)
option(KTOOLS_DEMO_BUILD_SHARED "Build demo shared library target" ON)

if(NOT KTOOLS_DEMO_BUILD_STATIC AND NOT KTOOLS_DEMO_BUILD_SHARED)
    message(FATAL_ERROR "Demo SDK requires at least one of KTOOLS_DEMO_BUILD_STATIC or KTOOLS_DEMO_BUILD_SHARED to be ON.")
endif()

function(ktools_apply_runtime_rpath target_name)
    if(NOT TARGET "${target_name}")
        return()
    endif()
    if(NOT DEFINED KTOOLS_RUNTIME_RPATH_DIRS OR KTOOLS_RUNTIME_RPATH_DIRS STREQUAL "")
        return()
    endif()
    set_target_properties("${target_name}" PROPERTIES
        BUILD_RPATH "${KTOOLS_RUNTIME_RPATH_DIRS}"
    )
endfunction()

if(NOT TARGET {{PROJECT_ID}}::sdk_shared)
    find_package({{SDK_PACKAGE_NAME}} CONFIG REQUIRED)
endif()
include(CMakePackageConfigHelpers)

set(_{{LIBRARY_ID}}_sdk_static_dep {{PROJECT_ID}}::sdk_static)
if(NOT TARGET {{PROJECT_ID}}::sdk_static)
    set(_{{LIBRARY_ID}}_sdk_static_dep {{PROJECT_ID}}::sdk)
endif()

set(_{{LIBRARY_ID}}_sdk_shared_dep {{PROJECT_ID}}::sdk_shared)
if(NOT TARGET {{PROJECT_ID}}::sdk_shared)
    set(_{{LIBRARY_ID}}_sdk_shared_dep {{PROJECT_ID}}::sdk)
endif()

set(_{{LIBRARY_ID}}_install_targets)

if(KTOOLS_DEMO_BUILD_STATIC)
    add_library({{LIBRARY_ID}}_sdk_static STATIC
        src/main.cpp
    )
    add_library({{LIBRARY_ID}}::sdk_static ALIAS {{LIBRARY_ID}}_sdk_static)

    target_include_directories({{LIBRARY_ID}}_sdk_static
        PUBLIC
            $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
            $<INSTALL_INTERFACE:include>
    )

    target_link_libraries({{LIBRARY_ID}}_sdk_static PUBLIC ${_{{LIBRARY_ID}}_sdk_static_dep})

    set_target_properties({{LIBRARY_ID}}_sdk_static PROPERTIES
        OUTPUT_NAME {{LIBRARY_ID}}
        EXPORT_NAME sdk_static
    )
    list(APPEND _{{LIBRARY_ID}}_install_targets {{LIBRARY_ID}}_sdk_static)
endif()

if(KTOOLS_DEMO_BUILD_SHARED)
    add_library({{LIBRARY_ID}}_sdk_shared SHARED
        src/main.cpp
    )
    add_library({{LIBRARY_ID}}::sdk_shared ALIAS {{LIBRARY_ID}}_sdk_shared)

    target_include_directories({{LIBRARY_ID}}_sdk_shared
        PUBLIC
            $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
            $<INSTALL_INTERFACE:include>
    )

    target_link_libraries({{LIBRARY_ID}}_sdk_shared PUBLIC ${_{{LIBRARY_ID}}_sdk_shared_dep})

    set_target_properties({{LIBRARY_ID}}_sdk_shared PROPERTIES
        OUTPUT_NAME {{LIBRARY_ID}}
        EXPORT_NAME sdk_shared
    )
    ktools_apply_runtime_rpath({{LIBRARY_ID}}_sdk_shared)
    list(APPEND _{{LIBRARY_ID}}_install_targets {{LIBRARY_ID}}_sdk_shared)
endif()

if(TARGET {{LIBRARY_ID}}_sdk_shared)
    add_library({{LIBRARY_ID}}::sdk ALIAS {{LIBRARY_ID}}_sdk_shared)
elseif(TARGET {{LIBRARY_ID}}_sdk_static)
    add_library({{LIBRARY_ID}}::sdk ALIAS {{LIBRARY_ID}}_sdk_static)
endif()

install(TARGETS ${_{{LIBRARY_ID}}_install_targets}
    EXPORT {{LIBRARY_PACKAGE_NAME}}Targets
    ARCHIVE DESTINATION lib COMPONENT {{LIBRARY_PACKAGE_NAME}}
    LIBRARY DESTINATION lib COMPONENT {{LIBRARY_PACKAGE_NAME}}
    RUNTIME DESTINATION bin COMPONENT {{LIBRARY_PACKAGE_NAME}}
    INCLUDES DESTINATION include
)

install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/include/
    DESTINATION include
    COMPONENT {{LIBRARY_PACKAGE_NAME}}
    FILES_MATCHING PATTERN "*.hpp"
)

install(EXPORT {{LIBRARY_PACKAGE_NAME}}Targets
    FILE {{LIBRARY_PACKAGE_NAME}}Targets.cmake
    NAMESPACE {{LIBRARY_ID}}::
    DESTINATION lib/cmake/{{LIBRARY_PACKAGE_NAME}}
    COMPONENT {{LIBRARY_PACKAGE_NAME}}
)

configure_package_config_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/cmake/{{LIBRARY_PACKAGE_NAME}}Config.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/{{LIBRARY_PACKAGE_NAME}}Config.cmake
    INSTALL_DESTINATION lib/cmake/{{LIBRARY_PACKAGE_NAME}}
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/{{LIBRARY_PACKAGE_NAME}}ConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/{{LIBRARY_PACKAGE_NAME}}Config.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/{{LIBRARY_PACKAGE_NAME}}ConfigVersion.cmake
    DESTINATION lib/cmake/{{LIBRARY_PACKAGE_NAME}}
    COMPONENT {{LIBRARY_PACKAGE_NAME}}
)

include(CTest)
if(BUILD_TESTING AND EXISTS "${CMAKE_CURRENT_LIST_DIR}/cmake/tests/CMakeLists.txt")
    add_subdirectory(cmake/tests)
endif()
