set({{PROJECT_SOURCES_VAR}}
    ${PROJECT_SOURCE_DIR}/src/{{PROJECT_ID}}.cpp
)

if(NOT {{PROJECT_ID_UPPER}}_BUILD_STATIC AND NOT {{PROJECT_ID_UPPER}}_BUILD_SHARED)
    message(FATAL_ERROR "{{PROJECT_ID}} requires at least one of {{PROJECT_ID_UPPER}}_BUILD_STATIC or {{PROJECT_ID_UPPER}}_BUILD_SHARED to be ON.")
endif()

if({{PROJECT_ID_UPPER}}_BUILD_STATIC)
    add_library({{PROJECT_ID}}_sdk_static STATIC ${{{PROJECT_SOURCES_VAR}}})
    add_library({{PROJECT_ID}}::sdk_static ALIAS {{PROJECT_ID}}_sdk_static)

    target_include_directories({{PROJECT_ID}}_sdk_static
        PUBLIC
            $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>
            $<INSTALL_INTERFACE:include>
    )

    # Add link dependencies here when needed.
    # target_link_libraries({{PROJECT_ID}}_sdk_static PUBLIC spdlog::spdlog)

    set_target_properties({{PROJECT_ID}}_sdk_static PROPERTIES
        OUTPUT_NAME {{PROJECT_ID}}
        EXPORT_NAME sdk_static
    )
endif()

if({{PROJECT_ID_UPPER}}_BUILD_SHARED)
    add_library({{PROJECT_ID}}_sdk_shared SHARED ${{{PROJECT_SOURCES_VAR}}})
    add_library({{PROJECT_ID}}::sdk_shared ALIAS {{PROJECT_ID}}_sdk_shared)

    target_include_directories({{PROJECT_ID}}_sdk_shared
        PUBLIC
            $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>
            $<INSTALL_INTERFACE:include>
    )

    # Add link dependencies here when needed.
    # target_link_libraries({{PROJECT_ID}}_sdk_shared PUBLIC spdlog::spdlog)

    set_target_properties({{PROJECT_ID}}_sdk_shared PROPERTIES
        OUTPUT_NAME {{PROJECT_ID}}
        EXPORT_NAME sdk_shared
    )
endif()

if(TARGET {{PROJECT_ID}}_sdk_shared)
    add_library({{PROJECT_ID}}::sdk ALIAS {{PROJECT_ID}}_sdk_shared)
elseif(TARGET {{PROJECT_ID}}_sdk_static)
    add_library({{PROJECT_ID}}::sdk ALIAS {{PROJECT_ID}}_sdk_static)
endif()
