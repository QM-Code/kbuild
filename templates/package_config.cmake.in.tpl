@PACKAGE_INIT@

include("${CMAKE_CURRENT_LIST_DIR}/{{SDK_PACKAGE_NAME}}Targets.cmake")
check_required_components({{SDK_PACKAGE_NAME}})
