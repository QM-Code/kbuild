@PACKAGE_INIT@

include("${CMAKE_CURRENT_LIST_DIR}/{{SDK_PACKAGE_NAME}}Targets.cmake")

if(NOT TARGET {{PROJECT_ID}}::sdk)
    if(TARGET {{PROJECT_ID}}::sdk_shared)
        add_library({{PROJECT_ID}}::sdk INTERFACE IMPORTED)
        set_property(TARGET {{PROJECT_ID}}::sdk PROPERTY
            INTERFACE_LINK_LIBRARIES {{PROJECT_ID}}::sdk_shared
        )
    elseif(TARGET {{PROJECT_ID}}::sdk_static)
        add_library({{PROJECT_ID}}::sdk INTERFACE IMPORTED)
        set_property(TARGET {{PROJECT_ID}}::sdk PROPERTY
            INTERFACE_LINK_LIBRARIES {{PROJECT_ID}}::sdk_static
        )
    endif()
endif()

check_required_components({{SDK_PACKAGE_NAME}})
