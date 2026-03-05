set({{PROJECT_SOURCES_VAR}}
    ${PROJECT_SOURCE_DIR}/src/{{PROJECT_ID}}.cpp
)

if({{PROJECT_ID_UPPER}}_BUILD_SHARED)
    set(_{{PROJECT_ID}}_library_type SHARED)
else()
    set(_{{PROJECT_ID}}_library_type STATIC)
endif()

add_library({{PROJECT_ID}}_sdk ${_{{PROJECT_ID}}_library_type} ${{{PROJECT_SOURCES_VAR}}})
add_library({{PROJECT_ID}}::sdk ALIAS {{PROJECT_ID}}_sdk)

target_include_directories({{PROJECT_ID}}_sdk
    PUBLIC
        $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

# Add link dependencies here when needed.
# target_link_libraries({{PROJECT_ID}}_sdk PUBLIC spdlog::spdlog)

set_target_properties({{PROJECT_ID}}_sdk PROPERTIES
    OUTPUT_NAME {{PROJECT_ID}}
    EXPORT_NAME sdk
)
