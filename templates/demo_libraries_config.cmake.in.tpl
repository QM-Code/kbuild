@PACKAGE_INIT@

include(CMakeFindDependencyMacro)
find_dependency({{SDK_PACKAGE_NAME}} CONFIG REQUIRED)

include("${CMAKE_CURRENT_LIST_DIR}/{{LIBRARY_PACKAGE_NAME}}Targets.cmake")
check_required_components({{LIBRARY_PACKAGE_NAME}})
