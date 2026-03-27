import os
import re
import shutil
from . import errors


def format_dir_for_output(path: str, repo_root: str) -> str:
    rel = os.path.relpath(path, repo_root).replace("\\", "/").strip("/")
    return f"./{rel}/"


def collect_build_version_dirs(repo_root: str) -> list[str]:
    output: list[str] = []
    core_build_root = os.path.join(repo_root, "build")
    if os.path.isdir(core_build_root):
        for entry in sorted(os.listdir(core_build_root)):
            path = os.path.join(core_build_root, entry)
            if os.path.isdir(path):
                output.append(path)

    demo_root = os.path.join(repo_root, "demo")
    if os.path.isdir(demo_root):
        for current_root, dirnames, _ in os.walk(demo_root):
            dirnames.sort()
            if "build" not in dirnames:
                continue

            demo_build_root = os.path.join(current_root, "build")
            for entry in sorted(os.listdir(demo_build_root)):
                path = os.path.join(demo_build_root, entry)
                if os.path.isdir(path):
                    output.append(path)

            dirnames.remove("build")
    return output


def list_build_dirs(repo_root: str) -> int:
    output = collect_build_version_dirs(repo_root)
    for line in output:
        print(format_dir_for_output(line, repo_root))
    return 0


def is_safe_latest_build_dir(path: str, repo_root: str) -> bool:
    if os.path.basename(os.path.abspath(path).rstrip("/\\")) != "latest":
        return False
    return is_safe_version_build_dir(path, repo_root)


def is_safe_version_build_dir(path: str, repo_root: str) -> bool:
    path_abs = os.path.abspath(path)
    repo_root_abs = os.path.abspath(repo_root)
    rel = os.path.relpath(path_abs, repo_root_abs).replace("\\", "/")
    if rel == ".." or rel.startswith("../"):
        return False

    parts = [part for part in rel.split("/") if part not in ("", ".")]
    if len(parts) == 2 and parts[0] == "build":
        return True
    if len(parts) >= 4 and parts[0] == "demo" and parts[-2] == "build":
        return True
    return False


def remove_version_build_dir(path: str, repo_root: str) -> bool:
    target = os.path.abspath(path)
    if not os.path.exists(target):
        return False
    if not os.path.isdir(target):
        errors.die(f"expected build directory path is not a directory: {target}", code=1)
    if os.path.islink(target):
        errors.die(f"refusing to remove symlinked build directory: {target}", code=1)
    if not is_safe_version_build_dir(target, repo_root):
        errors.die(f"refusing to remove unexpected build directory: {target}", code=1)

    shutil.rmtree(target)
    print(f"removed {format_dir_for_output(target, repo_root)}")
    return True


def remove_latest_build_dirs(repo_root: str) -> int:
    removed = 0
    for path in collect_build_version_dirs(repo_root):
        if os.path.basename(path.rstrip("/\\")) != "latest":
            continue
        if not is_safe_latest_build_dir(path, repo_root):
            errors.die(f"refusing to remove unexpected latest directory: {path}", code=1)
        if remove_version_build_dir(path, repo_root):
            removed += 1

    if removed == 0:
        print("no build/latest/ directories found")
    return 0


def remove_build_dirs_for_slot(repo_root: str, version: str) -> int:
    removed = 0
    for path in collect_build_version_dirs(repo_root):
        if os.path.basename(path.rstrip("/\\")) != version:
            continue
        if remove_version_build_dir(path, repo_root):
            removed += 1

    if removed == 0:
        print(f"no build directories found for slot '{version}'")
    return 0


def remove_all_build_dirs(repo_root: str) -> int:
    removed = 0
    for path in collect_build_version_dirs(repo_root):
        if remove_version_build_dir(path, repo_root):
            removed += 1

    if removed == 0:
        print("no build directories found")
    return 0


def resolve_prefix(path_arg: str, repo_root: str) -> str:
    if os.path.isabs(path_arg):
        return os.path.abspath(path_arg)
    return os.path.abspath(os.path.join(repo_root, path_arg))


def package_config_path(prefix: str, cmake_package_name: str) -> str:
    return os.path.join(
        prefix,
        "lib",
        "cmake",
        cmake_package_name,
        f"{cmake_package_name}Config.cmake",
    )


def package_dir(prefix: str, cmake_package_name: str) -> str:
    return os.path.join(prefix, "lib", "cmake", cmake_package_name)


def clean_sdk_install_prefix(prefix: str) -> None:
    if os.path.isfile(prefix):
        errors.die(f"SDK install prefix is a file, expected directory: {prefix}")

    os.makedirs(prefix, exist_ok=True)
    for entry in ("include", "lib", "bin", "share"):
        path = os.path.join(prefix, entry)
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)


def validate_core_build_dir_layout(build_dir: str) -> None:
    normalized = build_dir.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if len(parts) < 2 or parts[0] != "build" or any(part == ".." for part in parts):
        errors.die("build directory must be under 'build/' (example: build/test/)", code=1)


def validate_version_slot(version: str, *, option_name: str = "--build") -> str:
    token = version.strip()
    if not token:
        errors.die(f"{option_name} requires a non-empty value", code=1)
    if "/" in token or "\\" in token or token in (".", "..") or ".." in token:
        errors.die(
            f"{option_name} must be a simple slot name (for example: latest or 0.1)",
            code=1,
        )
    return token


def validate_sdk_prefix(prefix: str, cmake_package_name: str) -> None:
    if not os.path.isdir(prefix):
        errors.die(
            "SDK prefix must point to an existing directory.\n"
            f"Provided:\n  {prefix}"
        )

    include_dir = os.path.join(prefix, "include")
    lib_dir = os.path.join(prefix, "lib")
    missing_dirs: list[str] = []
    if not os.path.isdir(include_dir):
        missing_dirs.append("include/")
    if not os.path.isdir(lib_dir):
        missing_dirs.append("lib/")
    if missing_dirs:
        errors.die(
            "SDK prefix is invalid; required SDK directories are missing.\n"
            f"Provided:\n  {prefix}\n"
            f"Missing:\n  {', '.join(missing_dirs)}"
        )

    config_path = os.path.join(
        prefix,
        "lib",
        "cmake",
        cmake_package_name,
        f"{cmake_package_name}Config.cmake",
    )
    if os.path.isfile(config_path):
        return
    errors.die(
        "SDK prefix is missing package config.\n"
        f"Expected:\n  {config_path}\n"
        "Build/install SDK from a core build first (for example: kbuild --build test)."
    )


def normalize_demo_name(demo_token: str) -> str:
    value = demo_token.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    if value.startswith("demo/"):
        value = value[5:]
    if not value:
        errors.die(f"invalid demo '{demo_token}'", code=1)
    if value.startswith("/") or ".." in value.split("/"):
        errors.die(f"invalid demo '{demo_token}'", code=1)
    return value


def resolve_demo_source_dir(repo_root: str, demo_name: str) -> str:
    source_dir = os.path.join(repo_root, "demo", demo_name)
    cmake_lists = os.path.join(source_dir, "CMakeLists.txt")
    if not os.path.isfile(cmake_lists):
        errors.die(f"demo source directory is missing CMakeLists.txt: {source_dir}", code=1)
    return source_dir


def build_dir_has_install_rules(build_dir: str) -> bool:
    install_script = os.path.join(build_dir, "cmake_install.cmake")
    if not os.path.isfile(install_script):
        return False
    try:
        with open(install_script, "r", encoding="utf-8") as handle:
            for line in handle:
                if re.match(r"\s*file\(INSTALL\b", line):
                    return True
    except OSError:
        return False
    return False


def resolve_sdk_dependencies(
    repo_root: str,
    version: str,
    dependency_specs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    resolved: list[tuple[str, str]] = []

    for package_name, prefix_template in dependency_specs:
        if not isinstance(package_name, str) or not isinstance(prefix_template, str):
            errors.die("internal sdk dependency validation failure")

        raw_path = prefix_template.replace("{version}", version)
        candidate_prefix = resolve_prefix(raw_path, repo_root)
        config_path = package_config_path(candidate_prefix, package_name)
        if not os.path.isfile(config_path):
            errors.die(
                "sdk dependency package config not found.\n"
                f"Package:\n  {package_name}\n"
                "Checked SDK prefix:\n"
                f"  {candidate_prefix}"
            )

        validate_sdk_prefix(candidate_prefix, package_name)
        resolved.append((package_name, candidate_prefix))

    return resolved


def runtime_library_dirs(prefixes: list[str]) -> list[str]:
    dirs: list[str] = []
    for prefix in prefixes:
        lib_dir = os.path.join(prefix, "lib")
        if not os.path.isdir(lib_dir):
            continue
        if lib_dir in dirs:
            continue
        dirs.append(lib_dir)
    return dirs
