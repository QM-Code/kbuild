cmake_minimum_required(VERSION {{CMAKE_MINIMUM_VERSION}})

if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/cmake/00_toolchain.cmake")
    include("${CMAKE_CURRENT_LIST_DIR}/cmake/00_toolchain.cmake")
endif()

project({{PROJECT_ID}} VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

{{OPTION_BUILD_VARIANTS}}

if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/cmake/10_dependencies.cmake")
    include("${CMAKE_CURRENT_LIST_DIR}/cmake/10_dependencies.cmake")
endif()
if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/cmake/20_targets.cmake")
    include("${CMAKE_CURRENT_LIST_DIR}/cmake/20_targets.cmake")
endif()

include(CTest)
if(BUILD_TESTING AND EXISTS "${CMAKE_CURRENT_LIST_DIR}/cmake/tests/CMakeLists.txt")
    add_subdirectory(cmake/tests)
endif()

{{INCLUDE_INSTALL_EXPORT}}
