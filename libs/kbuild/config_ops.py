import json
import os
import re
import sys

from . import errors

PRIMARY_KBUILD_CONFIG_FILENAME = "kbuild.json"
LOCAL_KBUILD_CONFIG_FILENAME = ".kbuild.json"
VALID_BUILD_TYPES = {"static", "shared", "both"}
ALLOWED_TOP_LEVEL_KEYS = {"project", "git", "cmake", "vcpkg", "build", "batch"}


def default_build_type_for_host() -> str:
    platform_name = sys.platform.lower()
    if (
        platform_name.startswith("linux")
        or platform_name.startswith("darwin")
        or platform_name.startswith("win")
        or platform_name.startswith("cygwin")
        or platform_name.startswith("msys")
    ):
        return "shared"
    return "static"


def parse_build_type(*, value: object, key_path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.die(f"kbuild config key '{key_path}' must be a non-empty string")
    build_type = value.strip().lower()
    if build_type not in VALID_BUILD_TYPES:
        allowed = ", ".join(sorted(VALID_BUILD_TYPES))
        errors.die(f"kbuild config key '{key_path}' must be one of: {allowed}")
    return build_type


def _load_json_object(path: str, *, required: bool) -> dict[str, object] | None:
    if not os.path.isfile(path):
        if required:
            errors.die(f"missing required JSON file: {path}")
        return None

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        errors.die(f"could not parse {path}: {exc}")

    if not isinstance(payload, dict):
        errors.die(f"{path} must be a JSON object")
    return payload


def _deep_merge(base: object, overlay: object) -> object:
    if isinstance(base, dict) and isinstance(overlay, dict):
        merged = dict(base)
        for key, overlay_value in overlay.items():
            if key in merged:
                merged[key] = _deep_merge(merged[key], overlay_value)
            else:
                merged[key] = overlay_value
        return merged
    return overlay


def load_shared_kbuild_payload(repo_root: str, *, require_shared: bool) -> dict[str, object]:
    shared_path = os.path.join(repo_root, PRIMARY_KBUILD_CONFIG_FILENAME)
    shared_payload = _load_json_object(shared_path, required=require_shared)
    if shared_payload is None:
        return {}
    return shared_payload


def load_local_kbuild_payload(repo_root: str, *, require_local: bool) -> dict[str, object]:
    local_path = os.path.join(repo_root, LOCAL_KBUILD_CONFIG_FILENAME)
    local_payload = _load_json_object(local_path, required=require_local)
    if local_payload is None:
        return {}
    return local_payload


def load_effective_kbuild_payload(
    repo_root: str,
    *,
    require_local: bool,
) -> dict[str, object]:
    shared_payload = load_shared_kbuild_payload(repo_root, require_shared=False)
    local_payload = load_local_kbuild_payload(repo_root, require_local=require_local)
    merged = _deep_merge(shared_payload, local_payload)
    if not isinstance(merged, dict):  # pragma: no cover
        errors.die("internal error while merging kbuild config payloads")
    return merged


def load_kbuild_config(
    repo_root: str,
) -> tuple[
    str,
    bool,
    str,
    str,
    bool,
    bool,
    bool,
    list[str],
    list[str],
    int,
    str,
    list[tuple[str, str]],
]:
    raw = load_effective_kbuild_payload(repo_root, require_local=True)

    for key in raw:
        if key not in ALLOWED_TOP_LEVEL_KEYS:
            errors.die(f"unexpected key in kbuild config: '{key}'")

    project_raw = raw.get("project")
    if not isinstance(project_raw, dict):
        errors.die("kbuild config key 'project' must be an object")
    project_title_raw = project_raw.get("title")
    if not isinstance(project_title_raw, str) or not project_title_raw.strip():
        errors.die("kbuild config key 'project.title' must be a non-empty string")
    project_id_raw = project_raw.get("id")
    if not isinstance(project_id_raw, str) or not project_id_raw.strip():
        errors.die("kbuild config key 'project.id' must be a non-empty string")
    project_id = project_id_raw.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", project_id):
        errors.die("kbuild config key 'project.id' must be a valid C/C++ identifier")

    git_raw = raw.get("git")
    if not isinstance(git_raw, dict):
        errors.die("kbuild config key 'git' must be an object")
    git_url_raw = git_raw.get("url")
    if not isinstance(git_url_raw, str) or not git_url_raw.strip():
        errors.die("kbuild config key 'git.url' must be a non-empty string")
    git_auth_raw = git_raw.get("auth")
    if not isinstance(git_auth_raw, str) or not git_auth_raw.strip():
        errors.die("kbuild config key 'git.auth' must be a non-empty string")

    has_cmake = False
    cmake_minimum_version = "3.20"
    cmake_package_name = ""
    configure_by_default = True
    build_testing = True
    sdk_dependencies: list[tuple[str, str]] = []
    cmake_raw = raw.get("cmake")
    if cmake_raw is not None:
        if not isinstance(cmake_raw, dict):
            errors.die("kbuild config key 'cmake' must be an object")
        has_cmake = True

        allowed_cmake = {"minimum_version", "configure_by_default", "tests", "sdk", "dependencies"}
        for key in cmake_raw:
            if key not in allowed_cmake:
                errors.die(f"unexpected key in kbuild config 'cmake': '{key}'")

        if "minimum_version" in cmake_raw:
            cmake_minimum_version_raw = cmake_raw.get("minimum_version")
            if not isinstance(cmake_minimum_version_raw, str) or not cmake_minimum_version_raw.strip():
                errors.die("kbuild config key 'cmake.minimum_version' must be a non-empty string")
            cmake_minimum_version = cmake_minimum_version_raw.strip()

        configure_by_default_raw = cmake_raw.get("configure_by_default", True)
        if not isinstance(configure_by_default_raw, bool):
            errors.die("kbuild config key 'cmake.configure_by_default' must be a boolean")
        configure_by_default = configure_by_default_raw

        build_testing_raw = cmake_raw.get("tests", True)
        if not isinstance(build_testing_raw, bool):
            errors.die("kbuild config key 'cmake.tests' must be a boolean")
        build_testing = build_testing_raw

        if "sdk" in cmake_raw:
            sdk_raw = cmake_raw.get("sdk")
            if not isinstance(sdk_raw, dict):
                errors.die("kbuild config key 'cmake.sdk' must be an object when defined")
            allowed_sdk = {"package_name"}
            for key in sdk_raw:
                if key not in allowed_sdk:
                    errors.die(f"unexpected key in kbuild config 'cmake.sdk': '{key}'")
            package_name_raw = sdk_raw.get("package_name")
            if not isinstance(package_name_raw, str) or not package_name_raw.strip():
                errors.die("kbuild config key 'cmake.sdk.package_name' must be a non-empty string")
            cmake_package_name = package_name_raw.strip()

        dependencies_raw = cmake_raw.get("dependencies", {})
        if not isinstance(dependencies_raw, dict):
            errors.die("kbuild config key 'cmake.dependencies' must be an object when defined")

        for dependency_name_raw, dependency_raw in dependencies_raw.items():
            if not isinstance(dependency_name_raw, str) or not dependency_name_raw.strip():
                errors.die("kbuild config key 'cmake.dependencies' has an invalid package name")
            dependency_name = dependency_name_raw.strip()
            if cmake_package_name and dependency_name == cmake_package_name:
                errors.die(
                    f"kbuild config cmake dependency '{dependency_name}' cannot match root cmake.sdk.package_name"
                )
            if not isinstance(dependency_raw, dict):
                errors.die(f"kbuild config key 'cmake.dependencies.{dependency_name}' must be an object")

            allowed_dependency = {"prefix"}
            for key in dependency_raw:
                if key not in allowed_dependency:
                    errors.die(
                        f"unexpected key in kbuild config 'cmake.dependencies.{dependency_name}': '{key}'"
                    )

            prefix_raw = dependency_raw.get("prefix")
            if not isinstance(prefix_raw, str) or not prefix_raw.strip():
                errors.die(
                    f"kbuild config key 'cmake.dependencies.{dependency_name}.prefix' must be a non-empty string"
                )
            sdk_dependencies.append((dependency_name, prefix_raw.strip()))

    has_vcpkg = False
    vcpkg_raw = raw.get("vcpkg")
    if vcpkg_raw is not None:
        if not isinstance(vcpkg_raw, dict):
            errors.die("kbuild config key 'vcpkg' must be an object")
        has_vcpkg = True
        allowed_vcpkg = {"dependencies"}
        for key in vcpkg_raw:
            if key not in allowed_vcpkg:
                errors.die(f"unexpected key in kbuild config 'vcpkg': '{key}'")
        dependencies_raw = vcpkg_raw.get("dependencies", [])
        if not isinstance(dependencies_raw, list):
            errors.die("kbuild config key 'vcpkg.dependencies' must be an array")
        for idx, dep in enumerate(dependencies_raw):
            if not isinstance(dep, str) or not dep.strip():
                errors.die(f"kbuild config key 'vcpkg.dependencies[{idx}]' must be a non-empty string")

    build_demos: list[str] = []
    default_build_demos: list[str] = []
    build_jobs = 4
    build_type = default_build_type_for_host()
    build_raw = raw.get("build")
    if build_raw is not None:
        if not isinstance(build_raw, dict):
            errors.die("kbuild config key 'build' must be an object")
        allowed_build = {"jobs", "type", "demos", "defaults"}
        for key in build_raw:
            if key not in allowed_build:
                errors.die(f"unexpected key in kbuild config 'build': '{key}'")

        if "jobs" in build_raw:
            jobs_raw = build_raw.get("jobs")
            if not isinstance(jobs_raw, int) or isinstance(jobs_raw, bool) or jobs_raw < 1:
                errors.die("kbuild config key 'build.jobs' must be a positive integer")
            build_jobs = jobs_raw

        if "type" in build_raw:
            build_type = parse_build_type(value=build_raw.get("type"), key_path="build.type")

        demos_raw = build_raw.get("demos", [])
        if not isinstance(demos_raw, list):
            errors.die("kbuild config key 'build.demos' must be an array when defined")
        for idx, item in enumerate(demos_raw):
            if not isinstance(item, str) or not item.strip():
                errors.die(f"kbuild config key 'build.demos[{idx}]' must be a non-empty string")
            build_demos.append(item.strip())

        defaults_raw = build_raw.get("defaults", {})
        if not isinstance(defaults_raw, dict):
            errors.die("kbuild config key 'build.defaults' must be an object when defined")
        allowed_build_defaults = {"demos"}
        for key in defaults_raw:
            if key not in allowed_build_defaults:
                errors.die(f"unexpected key in kbuild config 'build.defaults': '{key}'")

        default_demos_raw = defaults_raw.get("demos", [])
        if not isinstance(default_demos_raw, list):
            errors.die("kbuild config key 'build.defaults.demos' must be an array when defined")
        for idx, item in enumerate(default_demos_raw):
            if not isinstance(item, str) or not item.strip():
                errors.die(f"kbuild config key 'build.defaults.demos[{idx}]' must be a non-empty string")
            default_build_demos.append(item.strip())

    return (
        project_id,
        has_cmake,
        cmake_minimum_version,
        cmake_package_name,
        configure_by_default,
        has_vcpkg,
        build_testing,
        build_demos,
        default_build_demos,
        build_jobs,
        build_type,
        sdk_dependencies,
    )


def load_batch_repos(repo_root: str) -> list[str]:
    raw = load_effective_kbuild_payload(repo_root, require_local=True)

    for key in raw:
        if key not in ALLOWED_TOP_LEVEL_KEYS:
            errors.die(f"unexpected key in kbuild config: '{key}'")

    batch_raw = raw.get("batch")
    if batch_raw is None:
        return []
    if not isinstance(batch_raw, dict):
        errors.die("kbuild config key 'batch' must be an object")

    allowed_batch = {"repos"}
    for key in batch_raw:
        if key not in allowed_batch:
            errors.die(f"unexpected key in kbuild config 'batch': '{key}'")

    repos_raw = batch_raw.get("repos", [])
    if not isinstance(repos_raw, list):
        errors.die("kbuild config key 'batch.repos' must be an array when defined")

    repos: list[str] = []
    for idx, item in enumerate(repos_raw):
        if not isinstance(item, str) or not item.strip():
            errors.die(f"kbuild config key 'batch.repos[{idx}]' must be a non-empty string")
        repo_token = item.strip()
        if os.path.isabs(repo_token):
            errors.die(f"kbuild config key 'batch.repos[{idx}]' must be a relative path")
        repos.append(repo_token)
    return repos


def _write_json_object(path: str, payload: dict[str, object]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def create_kbuild_config_template(repo_root: str) -> int:
    config_path = os.path.join(repo_root, LOCAL_KBUILD_CONFIG_FILENAME)
    if os.path.exists(config_path):
        errors.emit_error(f"'./{LOCAL_KBUILD_CONFIG_FILENAME}' already exists.")
        return 2

    payload = {
        "project": {
            "title": "My Project Title",
            "id": "myproject",
        },
        "git": {
            "url": "https://github.com/your-org/your-repo",
            "auth": "git@github.com:your-org/your-repo.git",
        },
        "cmake": {
            "minimum_version": "3.20",
            "configure_by_default": True,
            "tests": True,
            "sdk": {
                "package_name": "MyPackageNameSDK",
            },
            "dependencies": {},
        },
        "build": {
            "jobs": 4,
            "type": default_build_type_for_host(),
            "demos": [],
            "defaults": {
                "demos": [],
            },
        },
    }
    _write_json_object(config_path, payload)
    print(f"Created ./{LOCAL_KBUILD_CONFIG_FILENAME} template.", flush=True)
    print(f"Edit ./{LOCAL_KBUILD_CONFIG_FILENAME}, then run 'kbuild --kbuild-init'.", flush=True)
    return 0
