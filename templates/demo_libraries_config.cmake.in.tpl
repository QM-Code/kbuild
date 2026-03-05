@PACKAGE_INIT@

include(CMakeFindDependencyMacro)
find_dependency({{SDK_PACKAGE_NAME}} CONFIG REQUIRED)

include("${CMAKE_CURRENT_LIST_DIR}/{{LIBRARY_PACKAGE_NAME}}Targets.cmake")

if(NOT TARGET {{LIBRARY_ID}}::sdk)
    if(TARGET {{LIBRARY_ID}}::sdk_shared)
        add_library({{LIBRARY_ID}}::sdk INTERFACE IMPORTED)
        set_property(TARGET {{LIBRARY_ID}}::sdk PROPERTY
            INTERFACE_LINK_LIBRARIES {{LIBRARY_ID}}::sdk_shared
        )
    elseif(TARGET {{LIBRARY_ID}}::sdk_static)
        add_library({{LIBRARY_ID}}::sdk INTERFACE IMPORTED)
        set_property(TARGET {{LIBRARY_ID}}::sdk PROPERTY
            INTERFACE_LINK_LIBRARIES {{LIBRARY_ID}}::sdk_static
        )
    endif()
endif()

check_required_components({{LIBRARY_PACKAGE_NAME}})
