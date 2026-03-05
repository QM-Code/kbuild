include(CMakePackageConfigHelpers)

set(KTOOLS_INSTALL_CMAKEDIR "lib/cmake/{{SDK_PACKAGE_NAME}}")

set(_{{PROJECT_ID}}_install_targets)
if(TARGET {{PROJECT_ID}}_sdk_static)
    list(APPEND _{{PROJECT_ID}}_install_targets {{PROJECT_ID}}_sdk_static)
endif()
if(TARGET {{PROJECT_ID}}_sdk_shared)
    list(APPEND _{{PROJECT_ID}}_install_targets {{PROJECT_ID}}_sdk_shared)
endif()

install(TARGETS ${_{{PROJECT_ID}}_install_targets}
    EXPORT {{SDK_PACKAGE_NAME}}Targets
    ARCHIVE DESTINATION lib COMPONENT {{SDK_PACKAGE_NAME}}
    LIBRARY DESTINATION lib COMPONENT {{SDK_PACKAGE_NAME}}
    RUNTIME DESTINATION bin COMPONENT {{SDK_PACKAGE_NAME}}
    INCLUDES DESTINATION include
)

install(DIRECTORY ${PROJECT_SOURCE_DIR}/include/
    DESTINATION include
    COMPONENT {{SDK_PACKAGE_NAME}}
    FILES_MATCHING PATTERN "*.hpp"
)

install(EXPORT {{SDK_PACKAGE_NAME}}Targets
    FILE {{SDK_PACKAGE_NAME}}Targets.cmake
    NAMESPACE {{PROJECT_ID}}::
    DESTINATION ${KTOOLS_INSTALL_CMAKEDIR}
    COMPONENT {{SDK_PACKAGE_NAME}}
)

configure_package_config_file(
    ${PROJECT_SOURCE_DIR}/cmake/{{SDK_PACKAGE_NAME}}Config.cmake.in
    ${PROJECT_BINARY_DIR}/{{SDK_PACKAGE_NAME}}Config.cmake
    INSTALL_DESTINATION ${KTOOLS_INSTALL_CMAKEDIR}
)

write_basic_package_version_file(
    ${PROJECT_BINARY_DIR}/{{SDK_PACKAGE_NAME}}ConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${PROJECT_BINARY_DIR}/{{SDK_PACKAGE_NAME}}Config.cmake
    ${PROJECT_BINARY_DIR}/{{SDK_PACKAGE_NAME}}ConfigVersion.cmake
    DESTINATION ${KTOOLS_INSTALL_CMAKEDIR}
    COMPONENT {{SDK_PACKAGE_NAME}}
)
