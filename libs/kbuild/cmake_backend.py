import os
import subprocess

from . import build_ops
from . import demo_ops
from . import errors
from . import vcpkg_ops
from .config_ops import KbuildConfig

_RESIDUAL_DIR_NAMES = {
    "CMakeFiles",
    "Testing",
}

_RESIDUAL_FILE_NAMES = {
    ".ninja_deps",
    ".ninja_log",
    "build.ninja",
    "CMakeCache.txt",
    "cmake_install.cmake",
    "compile_commands.json",
    "CPackConfig.cmake",
    "CPackSourceConfig.cmake",
    "CTestTestfile.cmake",
    "install_manifest.txt",
    "Makefile",
    "rules.ninja",
}


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, env=env)


def find_unexpected_residuals(repo_root: str) -> tuple[str, list[str]] | None:
    findings: list[str] = []
    for current_root, dirnames, filenames in os.walk(repo_root):
        kept_dirnames: list[str] = []
        for dirname in sorted(dirnames):
            if dirname in (".git", "build"):
                continue
            if dirname in _RESIDUAL_DIR_NAMES:
                findings.append(os.path.join(current_root, dirname))
                continue
            kept_dirnames.append(dirname)
        dirnames[:] = kept_dirnames

        for filename in sorted(filenames):
            if filename in _RESIDUAL_FILE_NAMES:
                findings.append(os.path.join(current_root, filename))

    if not findings:
        return None
    return ("CMake build artifacts", findings)


def build_repo(
    *,
    repo_root: str,
    config: KbuildConfig,
    version: str,
    build_demos: bool,
    requested_demos: list[str],
    configure_override: bool | None,
    cmake_jobs_override: int | None,
    cmake_linkage_override: str | None,
) -> int:
    sdk_dependencies = build_ops.resolve_sdk_dependencies(repo_root, version, config.sdk_dependencies)
    build_jobs = config.build_jobs if cmake_jobs_override is None else cmake_jobs_override
    build_type = config.build_type if cmake_linkage_override is None else cmake_linkage_override
    build_static = build_type in {"static", "both"}
    build_shared = build_type in {"shared", "both"}
    configure = config.configure_by_default if configure_override is None else configure_override

    demo_order: list[str] = []
    if build_demos:
        if requested_demos:
            demo_order = [build_ops.normalize_demo_name(token) for token in requested_demos]
        else:
            if not config.build_demos:
                errors.die("config must define 'build.demos' for --build-demos with no demo arguments")
            demo_order = [build_ops.normalize_demo_name(token) for token in config.build_demos]
    elif config.default_build_demos:
        demo_order = [build_ops.normalize_demo_name(token) for token in config.default_build_demos]

    if demo_order:
        if not config.cmake_package_name:
            errors.die("demo builds require SDK metadata; define cmake.sdk.package_name in config")
        for demo_name in demo_order:
            build_ops.resolve_demo_source_dir(repo_root, demo_name)

    build_dir = os.path.join("build", version)
    source_dir = repo_root
    project_id_upper = config.project_id.upper()
    cmake_args = [
        "-DCMAKE_BUILD_TYPE=Release",
        f"-D{project_id_upper}_BUILD_STATIC={'ON' if build_static else 'OFF'}",
        f"-D{project_id_upper}_BUILD_SHARED={'ON' if build_shared else 'OFF'}",
        f"-DBUILD_TESTING={'ON' if config.build_testing else 'OFF'}",
    ]
    if sdk_dependencies:
        prefix_entries = [dependency_prefix for _, dependency_prefix in sdk_dependencies]
        cmake_args.extend(
            [
                f"-DCMAKE_PREFIX_PATH={';'.join(prefix_entries)}",
                "-DCMAKE_FIND_PACKAGE_PREFER_CONFIG=ON",
            ]
        )
        for package_name, dependency_prefix in sdk_dependencies:
            cmake_args.append(f"-D{package_name}_DIR={build_ops.package_dir(dependency_prefix, package_name)}")
    runtime_rpath_dirs = build_ops.runtime_library_dirs([dependency_prefix for _, dependency_prefix in sdk_dependencies])
    if runtime_rpath_dirs:
        cmake_args.append(f"-DKTOOLS_RUNTIME_RPATH_DIRS={';'.join(runtime_rpath_dirs)}")

    build_ops.validate_core_build_dir_layout(build_dir)

    env = os.environ.copy()
    if config.has_vcpkg:
        local_vcpkg_root, local_toolchain, local_vcpkg_downloads, local_vcpkg_binary_cache = (
            vcpkg_ops.ensure_local_vcpkg(repo_root)
        )
        env["VCPKG_ROOT"] = local_vcpkg_root
        if not env.get("VCPKG_DOWNLOADS", "").strip():
            env["VCPKG_DOWNLOADS"] = local_vcpkg_downloads
        if not env.get("VCPKG_DEFAULT_BINARY_CACHE", "").strip():
            env["VCPKG_DEFAULT_BINARY_CACHE"] = local_vcpkg_binary_cache
        cmake_args.append(f"-DCMAKE_TOOLCHAIN_FILE={local_toolchain}")

    if not configure:
        cache_path = os.path.join(build_dir, "CMakeCache.txt")
        if not os.path.isfile(cache_path):
            errors.die("--cmake-no-configure requires an existing CMakeCache.txt in the build directory", code=1)
    else:
        os.makedirs(build_dir, exist_ok=True)
        _run(["cmake", "-S", source_dir, "-B", build_dir, *cmake_args], env=env)

    _run(["cmake", "--build", build_dir, f"-j{build_jobs}"], env=env)

    install_prefix = os.path.abspath(os.path.join(build_dir, "sdk"))
    build_ops.clean_sdk_install_prefix(install_prefix)
    _run(
        [
            "cmake",
            "--install",
            build_dir,
            "--prefix",
            install_prefix,
        ],
        env=env,
    )

    print(f"Build complete -> dir={build_dir} | sdk={install_prefix}")

    core_vcpkg_prefix: str | None = None
    core_vcpkg_triplet = ""
    if demo_order and config.has_vcpkg:
        core_vcpkg_installed_dir, core_vcpkg_triplet = vcpkg_ops.resolve_build_vcpkg_context(build_dir, repo_root)
        core_vcpkg_prefix = os.path.join(core_vcpkg_installed_dir, core_vcpkg_triplet)

    if demo_order:
        for demo_name in demo_order:
            demo_ops.build_demo(
                repo_root=repo_root,
                demo_name=demo_name,
                version=version,
                configure=configure,
                cmake_minimum_version=config.cmake_minimum_version,
                cmake_package_name=config.cmake_package_name,
                sdk_dependencies=sdk_dependencies,
                build_jobs=build_jobs,
                build_static=build_static,
                build_shared=build_shared,
                build_testing=config.build_testing,
                env=env,
                demo_order=demo_order,
                core_vcpkg_prefix=core_vcpkg_prefix,
                core_vcpkg_triplet=core_vcpkg_triplet,
            )

    return 0
