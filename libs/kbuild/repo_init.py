import json
import os
import re

from . import errors


def _load_json_object(path: str) -> dict[str, object]:
    if not os.path.isfile(path):
        errors.die(f"missing required JSON file: {path}")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        errors.die(f"could not parse {path}: {exc}")
    if not isinstance(payload, dict):
        errors.die(f"expected JSON object in {path}")
    return payload


def load_initialize_repo_config(repo_root: str) -> dict[str, object]:
    config_path = os.path.join(repo_root, "kbuild.json")
    if not os.path.isfile(config_path):
        errors.die("missing required config file './kbuild.json'")

    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        errors.die(f"could not parse {config_path}: {exc}")

    if not isinstance(raw, dict):
        errors.die("kbuild.json must be a JSON object")

    project_raw = raw.get("project")
    if not isinstance(project_raw, dict):
        errors.die("kbuild.json key 'project' must be an object")

    project_title_raw = project_raw.get("title")
    if not isinstance(project_title_raw, str) or not project_title_raw.strip():
        errors.die("kbuild.json key 'project.title' must be a non-empty string")
    project_title = project_title_raw.strip()

    project_id_raw = project_raw.get("id")
    if not isinstance(project_id_raw, str) or not project_id_raw.strip():
        errors.die("kbuild.json key 'project.id' must be a non-empty string")
    project_id = project_id_raw.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", project_id):
        errors.die("kbuild.json key 'project.id' must be a valid C/C++ identifier")

    git_raw = raw.get("git")
    if not isinstance(git_raw, dict):
        errors.die("kbuild.json key 'git' must be an object")
    git_url_raw = git_raw.get("url")
    if not isinstance(git_url_raw, str) or not git_url_raw.strip():
        errors.die("kbuild.json key 'git.url' must be a non-empty string")
    git_auth_raw = git_raw.get("auth")
    if not isinstance(git_auth_raw, str) or not git_auth_raw.strip():
        errors.die("kbuild.json key 'git.auth' must be a non-empty string")
    git_url = git_url_raw.strip()
    git_auth = git_auth_raw.strip()

    cmake_raw = raw.get("cmake")
    cmake_enabled = cmake_raw is not None
    cmake_minimum_version = "3.20"
    cmake_dependency_packages: list[str] = []
    sdk_enabled = False
    sdk_package_name = ""
    if cmake_raw is not None:
        if not isinstance(cmake_raw, dict):
            errors.die("kbuild.json key 'cmake' must be an object")

        cmake_minimum_version_raw = cmake_raw.get("minimum_version", "3.20")
        if not isinstance(cmake_minimum_version_raw, str) or not cmake_minimum_version_raw.strip():
            errors.die("kbuild.json key 'cmake.minimum_version' must be a non-empty string")
        cmake_minimum_version = cmake_minimum_version_raw.strip()

        if "sdk" in cmake_raw:
            sdk_raw = cmake_raw.get("sdk")
            if not isinstance(sdk_raw, dict):
                errors.die("kbuild.json key 'cmake.sdk' must be an object when defined")
            sdk_package_name_raw = sdk_raw.get("package_name")
            if not isinstance(sdk_package_name_raw, str) or not sdk_package_name_raw.strip():
                errors.die("kbuild.json key 'cmake.sdk.package_name' must be a non-empty string")
            sdk_enabled = True
            sdk_package_name = sdk_package_name_raw.strip()

        dependencies_raw = cmake_raw.get("dependencies", {})
        if not isinstance(dependencies_raw, dict):
            errors.die("kbuild.json key 'cmake.dependencies' must be an object when defined")
        for dependency_name_raw, dependency_value_raw in dependencies_raw.items():
            if not isinstance(dependency_name_raw, str) or not dependency_name_raw.strip():
                errors.die("kbuild.json key 'cmake.dependencies' has an invalid package name")
            dependency_name = dependency_name_raw.strip()
            if not isinstance(dependency_value_raw, dict):
                errors.die(f"kbuild.json key 'cmake.dependencies.{dependency_name}' must be an object")
            cmake_dependency_packages.append(dependency_name)

    vcpkg_raw = raw.get("vcpkg")
    vcpkg_dependencies: list[str] = []
    if vcpkg_raw is not None:
        if not isinstance(vcpkg_raw, dict):
            errors.die("kbuild.json key 'vcpkg' must be an object")

        dependencies_raw = vcpkg_raw.get("dependencies", [])
        if not isinstance(dependencies_raw, list):
            errors.die("kbuild.json key 'vcpkg.dependencies' must be an array")
        for idx, dep in enumerate(dependencies_raw):
            if not isinstance(dep, str) or not dep.strip():
                errors.die(f"kbuild.json key 'vcpkg.dependencies[{idx}]' must be a non-empty string")
            vcpkg_dependencies.append(dep.strip())

    return {
        "project_title": project_title,
        "project_id": project_id,
        "git_url": git_url,
        "git_auth": git_auth,
        "cmake_enabled": cmake_enabled,
        "cmake_minimum_version": cmake_minimum_version,
        "cmake_dependency_packages": cmake_dependency_packages,
        "sdk_enabled": sdk_enabled,
        "sdk_package_name": sdk_package_name,
        "vcpkg_dependencies": vcpkg_dependencies,
    }


def format_path_for_output(path: str, repo_root: str) -> str:
    rel = os.path.relpath(path, repo_root).replace("\\", "/").strip("/")
    return f"./{rel}"


def ensure_directory_for_init(path: str) -> bool:
    if os.path.isdir(path):
        return False
    if os.path.exists(path):
        errors.die(f"expected directory path is occupied by a non-directory: {path}")
    os.makedirs(path, exist_ok=True)
    return True


def ensure_initialize_repo_root_empty(repo_root: str) -> None:
    allowed_entries = {"kbuild.py", "kbuild.json"}
    unexpected_entries = sorted(entry for entry in os.listdir(repo_root) if entry not in allowed_entries)
    if not unexpected_entries:
        return

    details = "\n".join(f"  {entry}" for entry in unexpected_entries)
    errors.die(
        "--initialize-repo must be run from an empty directory "
        "(other than kbuild.json and kbuild.py).\n"
        "Found:\n"
        f"{details}"
    )


def write_file_for_init(path: str, content: str) -> None:
    if os.path.isdir(path):
        errors.die(f"expected file path is occupied by a directory: {path}")
    if os.path.exists(path):
        errors.die(f"refusing to overwrite existing file: {path}")
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def load_template(templates_root: str, template_name: str) -> str:
    path = os.path.join(templates_root, template_name)
    if not os.path.isfile(path):
        errors.die(f"missing required template: {path}")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        errors.die(f"could not read template {path}: {exc}")


def render_template(templates_root: str, template_name: str, values: dict[str, str]) -> str:
    text = load_template(templates_root, template_name)
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def build_cmake_dependency_finds(packages: list[str]) -> str:
    if not packages:
        return "# No explicit dependencies defined in kbuild.json cmake.dependencies."
    return "\n".join(f"find_package({package_name} CONFIG REQUIRED)" for package_name in packages)


def initialize_repo_layout(repo_root: str, templates_root: str) -> int:
    config = load_initialize_repo_config(repo_root)
    ensure_initialize_repo_root_empty(repo_root)

    project_title = str(config["project_title"])
    project_id = str(config["project_id"])
    project_id_upper = project_id.upper()
    project_sources_var = f"{project_id_upper}_SOURCES"
    cmake_enabled = bool(config["cmake_enabled"])
    cmake_minimum_version = str(config["cmake_minimum_version"])
    cmake_dependency_packages = list(config["cmake_dependency_packages"])
    sdk_enabled = bool(config["sdk_enabled"])
    sdk_package_name = str(config["sdk_package_name"])
    vcpkg_dependencies = list(config["vcpkg_dependencies"])
    demo_library_ids = ["alpha", "beta", "gamma"]

    option_build_shared = ""
    include_install_export = ""
    if sdk_enabled:
        option_build_shared = (
            f'option({project_id_upper}_BUILD_SHARED "Build {project_id} as a shared library" OFF)'
        )
        include_install_export = (
            'if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/cmake/50_install_export.cmake")\n'
            '    include("${CMAKE_CURRENT_LIST_DIR}/cmake/50_install_export.cmake")\n'
            "endif()"
        )

    created_dirs: list[str] = []
    created_files: list[str] = []

    directory_order = [
        os.path.join(repo_root, "agent"),
        os.path.join(repo_root, "agent", "projects"),
        os.path.join(repo_root, "cmake"),
        os.path.join(repo_root, "demo"),
        os.path.join(repo_root, "src"),
        os.path.join(repo_root, "tests"),
        os.path.join(repo_root, "vcpkg"),
    ]
    if cmake_enabled:
        directory_order.append(os.path.join(repo_root, "cmake", "tests"))
    if sdk_enabled:
        directory_order.extend(
            [
                os.path.join(repo_root, "demo", "bootstrap"),
                os.path.join(repo_root, "demo", "bootstrap", "cmake"),
                os.path.join(repo_root, "demo", "bootstrap", "cmake", "tests"),
                os.path.join(repo_root, "demo", "bootstrap", "src"),
                os.path.join(repo_root, "demo", "libraries"),
                os.path.join(repo_root, "demo", "libraries", "alpha"),
                os.path.join(repo_root, "demo", "libraries", "alpha", "cmake"),
                os.path.join(repo_root, "demo", "libraries", "alpha", "cmake", "tests"),
                os.path.join(repo_root, "demo", "libraries", "alpha", "include"),
                os.path.join(repo_root, "demo", "libraries", "alpha", "include", "alpha"),
                os.path.join(repo_root, "demo", "libraries", "alpha", "src"),
                os.path.join(repo_root, "demo", "libraries", "beta"),
                os.path.join(repo_root, "demo", "libraries", "beta", "cmake"),
                os.path.join(repo_root, "demo", "libraries", "beta", "cmake", "tests"),
                os.path.join(repo_root, "demo", "libraries", "beta", "include"),
                os.path.join(repo_root, "demo", "libraries", "beta", "include", "beta"),
                os.path.join(repo_root, "demo", "libraries", "beta", "src"),
                os.path.join(repo_root, "demo", "libraries", "gamma"),
                os.path.join(repo_root, "demo", "libraries", "gamma", "cmake"),
                os.path.join(repo_root, "demo", "libraries", "gamma", "cmake", "tests"),
                os.path.join(repo_root, "demo", "libraries", "gamma", "include"),
                os.path.join(repo_root, "demo", "libraries", "gamma", "include", "gamma"),
                os.path.join(repo_root, "demo", "libraries", "gamma", "src"),
                os.path.join(repo_root, "demo", "executable"),
                os.path.join(repo_root, "demo", "executable", "cmake"),
                os.path.join(repo_root, "demo", "executable", "cmake", "tests"),
                os.path.join(repo_root, "demo", "executable", "src"),
                os.path.join(repo_root, "include"),
                os.path.join(repo_root, "include", project_id),
            ]
        )

    for path in directory_order:
        if ensure_directory_for_init(path):
            created_dirs.append(path)

    cmake_lists_content = render_template(
        templates_root,
        "CMakeLists.txt.tpl",
        {
            "CMAKE_MINIMUM_VERSION": cmake_minimum_version,
            "PROJECT_ID": project_id,
            "OPTION_BUILD_SHARED": option_build_shared,
            "INCLUDE_INSTALL_EXPORT": include_install_export,
        },
    )

    readme_build_section = ""
    readme_demos_section = ""
    if sdk_enabled:
        readme_build_section = (
            "## Build SDK\n\n"
            "```bash\n"
            "./kbuild.py\n"
            "```\n\n"
            "SDK output:\n"
            "- `build/latest/sdk/include`\n"
            "- `build/latest/sdk/lib`\n"
            f"- `build/latest/sdk/lib/cmake/{sdk_package_name}`\n\n"
        )
        readme_demos_section = (
            "## Build and Test Demos\n\n"
            "```bash\n"
            "# Builds SDK plus kbuild.json \"build.defaults.demos\".\n"
            "./kbuild.py\n\n"
            "# Explicit demo-only run (uses build.demos when no args are provided).\n"
            "./kbuild.py --build-demos\n\n"
            "./demo/executable/build/latest/test\n"
            "```\n\n"
            "Demos:\n"
            "- Bootstrap compile/link check: `demo/bootstrap/`\n"
            "- Libraries: `demo/libraries/{alpha,beta,gamma}`\n"
            "- Executable: `demo/executable/`\n\n"
            "Demo builds are orchestrated by the root `kbuild.py`.\n\n"
        )
    elif cmake_enabled:
        readme_build_section = (
            "## Build\n\n"
            "```bash\n"
            "./kbuild.py\n"
            "```\n\n"
            "Build output:\n"
            "- `build/latest/`\n\n"
        )
    else:
        readme_build_section = (
            "## Build\n\n"
            "This scaffold does not define a CMake project yet.\n"
            "Add `cmake` settings to `kbuild.json` before running `./kbuild.py`.\n\n"
        )

    readme_content = render_template(
        templates_root,
        "README.md.tpl",
        {
            "PROJECT_TITLE": project_title,
            "README_BUILD_SECTION": readme_build_section,
            "README_DEMOS_SECTION": readme_demos_section,
        },
    )

    bootstrap_content = render_template(templates_root, "agent_BOOTSTRAP.md.tpl", {})
    cmake_tests_content = render_template(templates_root, "cmake_tests_CMakeLists.txt.tpl", {})
    cmake_toolchain_content = render_template(templates_root, "cmake_00_toolchain.cmake.tpl", {})
    cmake_dependencies_content = render_template(
        templates_root,
        "cmake_10_dependencies.cmake.tpl",
        {"DEPENDENCY_FINDS": build_cmake_dependency_finds(cmake_dependency_packages)},
    )
    cmake_targets_content = render_template(
        templates_root,
        "cmake_20_targets_sdk.cmake.tpl" if sdk_enabled else "cmake_20_targets_app.cmake.tpl",
        {
            "PROJECT_ID": project_id,
            "PROJECT_ID_UPPER": project_id_upper,
            "PROJECT_SOURCES_VAR": project_sources_var,
        },
    )
    cmake_install_export_content = ""
    if sdk_enabled:
        cmake_install_export_content = render_template(
            templates_root,
            "cmake_50_install_export.cmake.tpl",
            {
                "PROJECT_ID": project_id,
                "SDK_PACKAGE_NAME": sdk_package_name,
            },
        )
    demo_bootstrap_cmake_content = ""
    demo_bootstrap_readme_content = ""
    demo_bootstrap_src_content = ""
    demo_executable_cmake_content = ""
    demo_executable_readme_content = ""
    demo_executable_src_content = ""
    demo_bootstrap_tests_cmake_content = ""
    demo_executable_tests_cmake_content = ""
    demo_library_tests_cmake_content = ""
    demo_library_contents: list[dict[str, str]] = []
    if sdk_enabled:
        demo_bootstrap_cmake_content = render_template(
            templates_root,
            "demo_bootstrap_CMakeLists.txt.tpl",
            {
                "CMAKE_MINIMUM_VERSION": cmake_minimum_version,
                "PROJECT_ID": project_id,
                "SDK_PACKAGE_NAME": sdk_package_name,
            },
        )
        demo_bootstrap_readme_content = render_template(
            templates_root,
            "demo_bootstrap_README.md.tpl",
            {
                "SDK_PACKAGE_NAME": sdk_package_name,
            },
        )
        demo_bootstrap_src_content = render_template(
            templates_root,
            "demo_bootstrap_src_main.cpp.tpl",
            {
                "PROJECT_ID": project_id,
            },
        )
        demo_executable_cmake_content = render_template(
            templates_root,
            "demo_executable_CMakeLists.txt.tpl",
            {
                "CMAKE_MINIMUM_VERSION": cmake_minimum_version,
                "PROJECT_ID": project_id,
                "SDK_PACKAGE_NAME": sdk_package_name,
            },
        )
        demo_executable_readme_content = render_template(
            templates_root,
            "demo_executable_README.md.tpl",
            {
                "SDK_PACKAGE_NAME": sdk_package_name,
            },
        )
        demo_executable_src_content = render_template(
            templates_root,
            "demo_executable_src_main.cpp.tpl",
            {
                "PROJECT_ID": project_id,
                "PROJECT_ID_UPPER": project_id_upper,
            },
        )
        demo_bootstrap_tests_cmake_content = render_template(
            templates_root,
            "demo_bootstrap_cmake_tests_CMakeLists.txt.tpl",
            {},
        )
        demo_executable_tests_cmake_content = render_template(
            templates_root,
            "demo_executable_cmake_tests_CMakeLists.txt.tpl",
            {},
        )
        demo_library_tests_cmake_content = render_template(
            templates_root,
            "demo_libraries_cmake_tests_CMakeLists.txt.tpl",
            {},
        )
        for library_id in demo_library_ids:
            library_package_name = f"{library_id.capitalize()}SDK"
            demo_library_contents.append(
                {
                    "library_id": library_id,
                    "library_package_name": library_package_name,
                    "cmake": render_template(
                        templates_root,
                        "demo_libraries_CMakeLists.txt.tpl",
                        {
                            "CMAKE_MINIMUM_VERSION": cmake_minimum_version,
                            "PROJECT_ID": project_id,
                            "SDK_PACKAGE_NAME": sdk_package_name,
                            "LIBRARY_ID": library_id,
                            "LIBRARY_PACKAGE_NAME": library_package_name,
                        },
                    ),
                    "readme": render_template(
                        templates_root,
                        "demo_libraries_README.md.tpl",
                        {
                            "PROJECT_ID": project_id,
                            "SDK_PACKAGE_NAME": sdk_package_name,
                            "LIBRARY_ID": library_id,
                            "LIBRARY_PACKAGE_NAME": library_package_name,
                        },
                    ),
                    "config": render_template(
                        templates_root,
                        "demo_libraries_config.cmake.in.tpl",
                        {
                            "SDK_PACKAGE_NAME": sdk_package_name,
                            "LIBRARY_PACKAGE_NAME": library_package_name,
                        },
                    ),
                    "header": render_template(
                        templates_root,
                        "demo_libraries_sdk.hpp.tpl",
                        {
                            "PROJECT_ID": project_id,
                            "LIBRARY_ID": library_id,
                        },
                    ),
                    "source": render_template(
                        templates_root,
                        "demo_libraries_src_main.cpp.tpl",
                        {
                            "PROJECT_ID": project_id,
                            "LIBRARY_ID": library_id,
                        },
                    ),
                    "tests": demo_library_tests_cmake_content,
                }
            )

    optional_include = ""
    if sdk_enabled:
        optional_include = f"#include <{project_id}.hpp>\n\n"
    src_cpp_content = render_template(
        templates_root,
        "src_project.cpp.tpl",
        {
            "OPTIONAL_INCLUDE": optional_include,
            "PROJECT_ID": project_id,
        },
    )

    if sdk_enabled:
        vcpkg_json_payload: dict[str, object] = {
            "name": project_id,
            "dependencies": vcpkg_dependencies,
        }
    else:
        vcpkg_json_payload = {
            "dependencies": vcpkg_dependencies,
        }
    vcpkg_json_content = f"{json.dumps(vcpkg_json_payload, indent=2)}\\n"

    vcpkg_configuration_payload = {
        "default-registry": {
            "kind": "builtin",
        }
    }
    vcpkg_configuration_content = f"{json.dumps(vcpkg_configuration_payload, indent=2)}\\n"
    gitignore_content = render_template(templates_root, "gitignore.tpl", {})

    files_to_write: list[tuple[str, str]] = [
        (os.path.join(repo_root, "CMakeLists.txt"), cmake_lists_content),
        (os.path.join(repo_root, "README.md"), readme_content),
        (os.path.join(repo_root, ".gitignore"), gitignore_content),
        (os.path.join(repo_root, "agent", "BOOTSTRAP.md"), bootstrap_content),
        (os.path.join(repo_root, "src", f"{project_id}.cpp"), src_cpp_content),
        (os.path.join(repo_root, "vcpkg", "vcpkg.json"), vcpkg_json_content),
        (
            os.path.join(repo_root, "vcpkg", "vcpkg-configuration.json"),
            vcpkg_configuration_content,
        ),
    ]
    if cmake_enabled:
        files_to_write.extend(
            [
                (
                    os.path.join(repo_root, "cmake", "00_toolchain.cmake"),
                    cmake_toolchain_content,
                ),
                (
                    os.path.join(repo_root, "cmake", "10_dependencies.cmake"),
                    cmake_dependencies_content,
                ),
                (
                    os.path.join(repo_root, "cmake", "20_targets.cmake"),
                    cmake_targets_content,
                ),
                (
                    os.path.join(repo_root, "cmake", "tests", "CMakeLists.txt"),
                    cmake_tests_content,
                ),
            ]
        )
        if sdk_enabled:
            files_to_write.append(
                (
                    os.path.join(repo_root, "cmake", "50_install_export.cmake"),
                    cmake_install_export_content,
                )
            )

    if sdk_enabled:
        include_header_content = render_template(
            templates_root,
            "include_project.hpp.tpl",
            {
                "PROJECT_ID": project_id,
            },
        )
        sdk_config_content = render_template(
            templates_root,
            "package_config.cmake.in.tpl",
            {
                "SDK_PACKAGE_NAME": sdk_package_name,
            },
        )
        files_to_write.extend(
            [
                (os.path.join(repo_root, "include", f"{project_id}.hpp"), include_header_content),
                (
                    os.path.join(repo_root, "cmake", f"{sdk_package_name}Config.cmake.in"),
                    sdk_config_content,
                ),
                (
                    os.path.join(repo_root, "demo", "bootstrap", "CMakeLists.txt"),
                    demo_bootstrap_cmake_content,
                ),
                (
                    os.path.join(repo_root, "demo", "bootstrap", "README.md"),
                    demo_bootstrap_readme_content,
                ),
                (
                    os.path.join(repo_root, "demo", "bootstrap", "src", "main.cpp"),
                    demo_bootstrap_src_content,
                ),
                (
                    os.path.join(repo_root, "demo", "bootstrap", "cmake", "tests", "CMakeLists.txt"),
                    demo_bootstrap_tests_cmake_content,
                ),
                (
                    os.path.join(repo_root, "demo", "executable", "CMakeLists.txt"),
                    demo_executable_cmake_content,
                ),
                (
                    os.path.join(repo_root, "demo", "executable", "README.md"),
                    demo_executable_readme_content,
                ),
                (
                    os.path.join(repo_root, "demo", "executable", "src", "main.cpp"),
                    demo_executable_src_content,
                ),
                (
                    os.path.join(repo_root, "demo", "executable", "cmake", "tests", "CMakeLists.txt"),
                    demo_executable_tests_cmake_content,
                ),
            ]
        )
        for entry in demo_library_contents:
            library_id = entry["library_id"]
            library_package_name = entry["library_package_name"]
            files_to_write.extend(
                [
                    (
                        os.path.join(repo_root, "demo", "libraries", library_id, "CMakeLists.txt"),
                        entry["cmake"],
                    ),
                    (
                        os.path.join(repo_root, "demo", "libraries", library_id, "README.md"),
                        entry["readme"],
                    ),
                    (
                        os.path.join(
                            repo_root,
                            "demo",
                            "libraries",
                            library_id,
                            "cmake",
                            "tests",
                            "CMakeLists.txt",
                        ),
                        entry["tests"],
                    ),
                    (
                        os.path.join(
                            repo_root,
                            "demo",
                            "libraries",
                            library_id,
                            "cmake",
                            f"{library_package_name}Config.cmake.in",
                        ),
                        entry["config"],
                    ),
                    (
                        os.path.join(
                            repo_root,
                            "demo",
                            "libraries",
                            library_id,
                            "include",
                            library_id,
                            "sdk.hpp",
                        ),
                        entry["header"],
                    ),
                    (
                        os.path.join(repo_root, "demo", "libraries", library_id, "src", "main.cpp"),
                        entry["source"],
                    ),
                ]
            )

    for path, content in files_to_write:
        write_file_for_init(path, content)
        created_files.append(path)

    print("Initialized repository scaffold:")
    if created_dirs:
        print("  Directories:")
        for path in created_dirs:
            print(f"    + {format_path_for_output(path, repo_root)}/")
    if created_files:
        print("  Files:")
        for path in created_files:
            print(f"    + {format_path_for_output(path, repo_root)}")

    return 0
