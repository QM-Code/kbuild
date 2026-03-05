if(NOT DEFINED KTOOLS_CMAKE_MINIMUM_VERSION OR KTOOLS_CMAKE_MINIMUM_VERSION STREQUAL "")
    set(KTOOLS_CMAKE_MINIMUM_VERSION "{{CMAKE_MINIMUM_VERSION}}")
endif()
cmake_minimum_required(VERSION ${KTOOLS_CMAKE_MINIMUM_VERSION})

project({{PROJECT_ID}}_demo_executable LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT TARGET {{PROJECT_ID}}::sdk)
    find_package({{SDK_PACKAGE_NAME}} CONFIG REQUIRED)
endif()
if(NOT TARGET alpha::sdk)
    find_package(AlphaSDK CONFIG REQUIRED)
endif()
if(NOT TARGET beta::sdk)
    find_package(BetaSDK CONFIG REQUIRED)
endif()
if(NOT TARGET gamma::sdk)
    find_package(GammaSDK CONFIG REQUIRED)
endif()

add_executable({{PROJECT_ID}}_demo_executable
    src/main.cpp
)

target_compile_definitions({{PROJECT_ID}}_demo_executable PRIVATE KTRACE_NAMESPACE="{{PROJECT_ID}}_demo")

target_link_libraries({{PROJECT_ID}}_demo_executable PRIVATE
    {{PROJECT_ID}}::sdk
    alpha::sdk
    beta::sdk
    gamma::sdk
)

set_target_properties({{PROJECT_ID}}_demo_executable PROPERTIES
    OUTPUT_NAME test
)

include(CTest)
if(BUILD_TESTING AND EXISTS "${CMAKE_CURRENT_LIST_DIR}/cmake/tests/CMakeLists.txt")
    add_subdirectory(cmake/tests)
endif()
