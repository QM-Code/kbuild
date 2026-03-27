import json
import os
import re

from . import config_ops
from . import errors


def _default_project_title(repo_root: str) -> str:
    dirname = os.path.basename(os.path.abspath(repo_root)).strip()
    if dirname:
        return dirname
    return "My Project Title"


def _default_project_id(repo_root: str) -> str:
    dirname = os.path.basename(os.path.abspath(repo_root)).strip().lower()
    token = re.sub(r"[^a-z0-9_]+", "_", dirname)
    token = re.sub(r"_+", "_", token).strip("_")
    if not token:
        token = "myproject"
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token):
        token = f"_{token}"
    return token


def load_initialize_repo_config(repo_root: str) -> dict[str, object]:
    raw = config_ops.load_effective_kbuild_payload(repo_root, require_local=True)

    allowed_top = {"project", "git", "cmake", "vcpkg", "build", "batch"}
    for key in raw:
        if key not in allowed_top:
            errors.die(f"unexpected key in config payload: '{key}'")

    project_raw = raw.get("project", {})
    if project_raw is None:
        project_raw = {}
    if not isinstance(project_raw, dict):
        errors.die("config key 'project' must be an object when defined")

    project_title_raw = project_raw.get("title", _default_project_title(repo_root))
    if not isinstance(project_title_raw, str) or not project_title_raw.strip():
        errors.die("config key 'project.title' must be a non-empty string when defined")
    project_title = project_title_raw.strip()

    project_id_raw = project_raw.get("id", _default_project_id(repo_root))
    if not isinstance(project_id_raw, str) or not project_id_raw.strip():
        errors.die("config key 'project.id' must be a non-empty string when defined")
    project_id = project_id_raw.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", project_id):
        errors.die("config key 'project.id' must be a valid C/C++ identifier")

    git_raw = raw.get("git", {})
    if git_raw is None:
        git_raw = {}
    if not isinstance(git_raw, dict):
        errors.die("config key 'git' must be an object when defined")
    git_url_raw = git_raw.get("url", "https://github.com/your-org/your-repo")
    if not isinstance(git_url_raw, str) or not git_url_raw.strip():
        errors.die("config key 'git.url' must be a non-empty string when defined")
    git_auth_raw = git_raw.get("auth", "git@github.com:your-org/your-repo.git")
    if not isinstance(git_auth_raw, str) or not git_auth_raw.strip():
        errors.die("config key 'git.auth' must be a non-empty string when defined")
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
            errors.die("config key 'cmake' must be an object when defined")

        cmake_minimum_version_raw = cmake_raw.get("minimum_version", "3.20")
        if not isinstance(cmake_minimum_version_raw, str) or not cmake_minimum_version_raw.strip():
            errors.die("config key 'cmake.minimum_version' must be a non-empty string when defined")
        cmake_minimum_version = cmake_minimum_version_raw.strip()

        if "sdk" in cmake_raw:
            sdk_raw = cmake_raw.get("sdk")
            if not isinstance(sdk_raw, dict):
                errors.die("config key 'cmake.sdk' must be an object when defined")
            sdk_package_name_raw = sdk_raw.get("package_name")
            if not isinstance(sdk_package_name_raw, str) or not sdk_package_name_raw.strip():
                errors.die("config key 'cmake.sdk.package_name' must be a non-empty string")
            sdk_enabled = True
            sdk_package_name = sdk_package_name_raw.strip()

        dependencies_raw = cmake_raw.get("dependencies", {})
        if not isinstance(dependencies_raw, dict):
            errors.die("config key 'cmake.dependencies' must be an object when defined")
        for dependency_name_raw, dependency_value_raw in dependencies_raw.items():
            if not isinstance(dependency_name_raw, str) or not dependency_name_raw.strip():
                errors.die("config key 'cmake.dependencies' has an invalid package name")
            dependency_name = dependency_name_raw.strip()
            if not isinstance(dependency_value_raw, dict):
                errors.die(f"config key 'cmake.dependencies.{dependency_name}' must be an object")
            cmake_dependency_packages.append(dependency_name)

    vcpkg_raw = raw.get("vcpkg")
    has_vcpkg = vcpkg_raw is not None
    vcpkg_dependencies: list[str] = []
    if vcpkg_raw is not None:
        if not isinstance(vcpkg_raw, dict):
            errors.die("config key 'vcpkg' must be an object when defined")

        dependencies_raw = vcpkg_raw.get("dependencies", [])
        if not isinstance(dependencies_raw, list):
            errors.die("config key 'vcpkg.dependencies' must be an array")
        for idx, dep in enumerate(dependencies_raw):
            if not isinstance(dep, str) or not dep.strip():
                errors.die(f"config key 'vcpkg.dependencies[{idx}]' must be a non-empty string")
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
        "has_vcpkg": has_vcpkg,
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
    allowed_entries = {"kbuild.json", ".kbuild.json"}
    unexpected_entries = sorted(entry for entry in os.listdir(repo_root) if entry not in allowed_entries)
    if not unexpected_entries:
        return

    details = "\n".join(f"  {entry}" for entry in unexpected_entries)
    errors.die(
        "--kbuild-init must be run from an empty directory "
        "(other than kbuild.json and .kbuild.json).\n"
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
        return "# No explicit dependencies defined in config cmake.dependencies."
    return "\n".join(f"find_package({package_name} CONFIG REQUIRED)" for package_name in packages)


def initialize_repo_layout(
    repo_root: str,
    templates_root: str,
) -> int:
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
    has_vcpkg = bool(config["has_vcpkg"])
    vcpkg_dependencies = list(config["vcpkg_dependencies"])
    demo_library_ids = ["alpha", "beta", "gamma"]
    demo_executable_specs = [
        {
            "demo_id": "core",
            "demo_title": "Core",
            "demo_title_lower": "core",
            "demo_purpose": "basic end-to-end",
            "demo_trace_namespace": f"{project_id}_demo_core",
        },
        {
            "demo_id": "omega",
            "demo_title": "Omega",
            "demo_title_lower": "omega",
            "demo_purpose": "full-featured",
            "demo_trace_namespace": f"{project_id}_demo_omega",
        },
    ]

    option_build_variants = ""
    include_install_export = ""
    if sdk_enabled:
        option_build_variants = (
            f'option({project_id_upper}_BUILD_STATIC "Build {project_id} static library target" ON)\n'
            f'option({project_id_upper}_BUILD_SHARED "Build {project_id} shared library target" ON)'
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
    ]
    if has_vcpkg:
        directory_order.append(os.path.join(repo_root, "vcpkg"))
    if cmake_enabled:
        directory_order.append(os.path.join(repo_root, "cmake", "tests"))
    if sdk_enabled:
        directory_order.extend(
            [
                os.path.join(repo_root, "demo", "bootstrap"),
                os.path.join(repo_root, "demo", "bootstrap", "cmake"),
                os.path.join(repo_root, "demo", "bootstrap", "cmake", "tests"),
                os.path.join(repo_root, "demo", "bootstrap", "src"),
                os.path.join(repo_root, "demo", "sdk"),
                os.path.join(repo_root, "demo", "sdk", "alpha"),
                os.path.join(repo_root, "demo", "sdk", "alpha", "cmake"),
                os.path.join(repo_root, "demo", "sdk", "alpha", "cmake", "tests"),
                os.path.join(repo_root, "demo", "sdk", "alpha", "include"),
                os.path.join(repo_root, "demo", "sdk", "alpha", "include", "alpha"),
                os.path.join(repo_root, "demo", "sdk", "alpha", "src"),
                os.path.join(repo_root, "demo", "sdk", "beta"),
                os.path.join(repo_root, "demo", "sdk", "beta", "cmake"),
                os.path.join(repo_root, "demo", "sdk", "beta", "cmake", "tests"),
                os.path.join(repo_root, "demo", "sdk", "beta", "include"),
                os.path.join(repo_root, "demo", "sdk", "beta", "include", "beta"),
                os.path.join(repo_root, "demo", "sdk", "beta", "src"),
                os.path.join(repo_root, "demo", "sdk", "gamma"),
                os.path.join(repo_root, "demo", "sdk", "gamma", "cmake"),
                os.path.join(repo_root, "demo", "sdk", "gamma", "cmake", "tests"),
                os.path.join(repo_root, "demo", "sdk", "gamma", "include"),
                os.path.join(repo_root, "demo", "sdk", "gamma", "include", "gamma"),
                os.path.join(repo_root, "demo", "sdk", "gamma", "src"),
                os.path.join(repo_root, "demo", "exe"),
                os.path.join(repo_root, "demo", "exe", "core"),
                os.path.join(repo_root, "demo", "exe", "core", "cmake"),
                os.path.join(repo_root, "demo", "exe", "core", "cmake", "tests"),
                os.path.join(repo_root, "demo", "exe", "core", "src"),
                os.path.join(repo_root, "demo", "exe", "omega"),
                os.path.join(repo_root, "demo", "exe", "omega", "cmake"),
                os.path.join(repo_root, "demo", "exe", "omega", "cmake", "tests"),
                os.path.join(repo_root, "demo", "exe", "omega", "src"),
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
            "OPTION_BUILD_VARIANTS": option_build_variants,
            "INCLUDE_INSTALL_EXPORT": include_install_export,
        },
    )

    readme_build_section = ""
    readme_demos_section = ""
    if sdk_enabled:
        readme_build_section = (
            "## Build SDK\n\n"
            "```bash\n"
            "kbuild --build-latest\n"
            "```\n\n"
            "SDK output:\n"
            "- `build/latest/sdk/include`\n"
            "- `build/latest/sdk/lib`\n"
            f"- `build/latest/sdk/lib/cmake/{sdk_package_name}`\n\n"
        )
        readme_demos_section = (
            "## Build and Test Demos\n\n"
            "```bash\n"
            "# Builds SDK plus config \"build.defaults.demos\".\n"
            "kbuild --build-latest\n\n"
            "# Explicit demo-only run (uses build.demos when no args are provided).\n"
            "kbuild --build-demos\n\n"
            "./demo/exe/core/build/latest/test\n"
            "```\n\n"
            "Demos:\n"
            "- Bootstrap compile/link check: `demo/bootstrap/`\n"
            "- SDKs: `demo/sdk/{alpha,beta,gamma}`\n"
            "- Executables: `demo/exe/{core,omega}`\n\n"
            "Demo builds are orchestrated by the root `kbuild` command.\n\n"
        )
    elif cmake_enabled:
        readme_build_section = (
            "## Build\n\n"
            "```bash\n"
            "kbuild --build-latest\n"
            "```\n\n"
            "Build output:\n"
            "- `build/latest/`\n\n"
        )
    else:
        readme_build_section = (
            "## Build\n\n"
            "This scaffold does not define a CMake project yet.\n"
            "Add `cmake` settings to your kbuild config before running `kbuild --build-latest`.\n\n"
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
    demo_bootstrap_tests_cmake_content = ""
    demo_executable_tests_cmake_content = ""
    demo_library_tests_cmake_content = ""
    demo_library_contents: list[dict[str, str]] = []
    demo_executable_contents: list[dict[str, str]] = []
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
        for demo_spec in demo_executable_specs:
            demo_executable_contents.append(
                {
                    "demo_id": demo_spec["demo_id"],
                    "cmake": render_template(
                        templates_root,
                        "demo_executable_CMakeLists.txt.tpl",
                        {
                            "CMAKE_MINIMUM_VERSION": cmake_minimum_version,
                            "PROJECT_ID": project_id,
                            "SDK_PACKAGE_NAME": sdk_package_name,
                            "DEMO_ID": demo_spec["demo_id"],
                            "DEMO_TITLE": demo_spec["demo_title"],
                            "DEMO_TITLE_LOWER": demo_spec["demo_title_lower"],
                            "DEMO_TRACE_NAMESPACE": demo_spec["demo_trace_namespace"],
                        },
                    ),
                    "readme": render_template(
                        templates_root,
                        "demo_executable_README.md.tpl",
                        {
                            "SDK_PACKAGE_NAME": sdk_package_name,
                            "DEMO_TITLE": demo_spec["demo_title"],
                            "DEMO_PURPOSE": demo_spec["demo_purpose"],
                        },
                    ),
                    "source": render_template(
                        templates_root,
                        "demo_executable_src_main.cpp.tpl",
                        {
                            "PROJECT_ID": project_id,
                            "PROJECT_ID_UPPER": project_id_upper,
                            "DEMO_TITLE_LOWER": demo_spec["demo_title_lower"],
                        },
                    ),
                    "tests": demo_executable_tests_cmake_content,
                }
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
                            "LIBRARY_ID": library_id,
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

    gitignore_content = render_template(templates_root, "gitignore.tpl", {})

    files_to_write: list[tuple[str, str]] = [
        (os.path.join(repo_root, "CMakeLists.txt"), cmake_lists_content),
        (os.path.join(repo_root, "README.md"), readme_content),
        (os.path.join(repo_root, ".gitignore"), gitignore_content),
        (os.path.join(repo_root, "agent", "BOOTSTRAP.md"), bootstrap_content),
        (os.path.join(repo_root, "src", f"{project_id}.cpp"), src_cpp_content),
    ]
    if has_vcpkg:
        if sdk_enabled:
            vcpkg_json_payload: dict[str, object] = {
                "name": project_id,
                "dependencies": vcpkg_dependencies,
            }
        else:
            vcpkg_json_payload = {
                "dependencies": vcpkg_dependencies,
            }
        vcpkg_json_payload["configuration"] = {
            "default-registry": {
                "kind": "builtin",
            }
        }
        vcpkg_json_content = f"{json.dumps(vcpkg_json_payload, indent=2)}\\n"
        files_to_write.append((os.path.join(repo_root, "vcpkg", "vcpkg.json"), vcpkg_json_content))
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
                "PROJECT_ID": project_id,
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
            ]
        )
        for entry in demo_executable_contents:
            demo_id = entry["demo_id"]
            files_to_write.extend(
                [
                    (
                        os.path.join(repo_root, "demo", "exe", demo_id, "CMakeLists.txt"),
                        entry["cmake"],
                    ),
                    (
                        os.path.join(repo_root, "demo", "exe", demo_id, "README.md"),
                        entry["readme"],
                    ),
                    (
                        os.path.join(repo_root, "demo", "exe", demo_id, "src", "main.cpp"),
                        entry["source"],
                    ),
                    (
                        os.path.join(repo_root, "demo", "exe", demo_id, "cmake", "tests", "CMakeLists.txt"),
                        entry["tests"],
                    ),
                ]
            )
        for entry in demo_library_contents:
            library_id = entry["library_id"]
            library_package_name = entry["library_package_name"]
            files_to_write.extend(
                [
                    (
                        os.path.join(repo_root, "demo", "sdk", library_id, "CMakeLists.txt"),
                        entry["cmake"],
                    ),
                    (
                        os.path.join(repo_root, "demo", "sdk", library_id, "README.md"),
                        entry["readme"],
                    ),
                    (
                        os.path.join(
                            repo_root,
                            "demo",
                            "sdk",
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
                            "sdk",
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
                            "sdk",
                            library_id,
                            "include",
                            library_id,
                            "sdk.hpp",
                        ),
                        entry["header"],
                    ),
                    (
                        os.path.join(repo_root, "demo", "sdk", library_id, "src", "main.cpp"),
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
