import os
import shutil
import subprocess

from . import build_ops
from . import errors


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, env=env)


def build_demo(
    repo_root: str,
    demo_name: str,
    version: str,
    configure: bool,
    cmake_minimum_version: str,
    cmake_package_name: str,
    sdk_dependencies: list[tuple[str, str]],
    build_jobs: int,
    build_static: bool,
    build_shared: bool,
    build_testing: bool,
    env: dict[str, str],
    demo_order: list[str],
    core_vcpkg_prefix: str | None,
    core_vcpkg_triplet: str,
) -> None:
    core_build_dir = os.path.join(repo_root, "build", version)
    core_sdk_prefix = os.path.join(core_build_dir, "sdk")
    build_ops.validate_sdk_prefix(core_sdk_prefix, cmake_package_name)

    source_dir = build_ops.resolve_demo_source_dir(repo_root, demo_name)
    build_dir = os.path.join(repo_root, "demo", demo_name, "build", version)
    install_prefix = os.path.join(build_dir, "sdk")

    prefix_entries: list[str] = [core_sdk_prefix]
    if core_vcpkg_prefix is not None:
        if not os.path.isdir(core_vcpkg_prefix):
            errors.die(f"missing vcpkg triplet prefix: {core_vcpkg_prefix}")
        prefix_entries.append(core_vcpkg_prefix)
    for _, dependency_prefix in sdk_dependencies:
        if dependency_prefix not in prefix_entries:
            prefix_entries.append(dependency_prefix)
    for dependency_demo in demo_order:
        dependency_sdk = os.path.join(repo_root, "demo", dependency_demo, "build", version, "sdk")
        if os.path.isdir(dependency_sdk) and dependency_sdk not in prefix_entries:
            prefix_entries.append(dependency_sdk)
    runtime_rpath_dirs = build_ops.runtime_library_dirs(prefix_entries)

    cmake_args = [
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DKTOOLS_CMAKE_MINIMUM_VERSION={cmake_minimum_version}",
        f"-DKTOOLS_DEMO_BUILD_STATIC={'ON' if build_static else 'OFF'}",
        f"-DKTOOLS_DEMO_BUILD_SHARED={'ON' if build_shared else 'OFF'}",
        f"-DBUILD_TESTING={'ON' if build_testing else 'OFF'}",
        f"-DCMAKE_PREFIX_PATH={';'.join(prefix_entries)}",
        "-DCMAKE_FIND_PACKAGE_PREFER_CONFIG=ON",
        f"-D{cmake_package_name}_DIR={build_ops.package_dir(core_sdk_prefix, cmake_package_name)}",
    ]
    if runtime_rpath_dirs:
        cmake_args.append(f"-DKTOOLS_RUNTIME_RPATH_DIRS={';'.join(runtime_rpath_dirs)}")
    for package_name, dependency_prefix in sdk_dependencies:
        cmake_args.append(f"-D{package_name}_DIR={build_ops.package_dir(dependency_prefix, package_name)}")
    message = f"Demo build -> dir={build_dir} | demo={demo_name} | sdk={core_sdk_prefix}"
    if core_vcpkg_triplet:
        message = f"{message} | triplet={core_vcpkg_triplet}"
    print(message, flush=True)

    if not configure:
        cache_path = os.path.join(build_dir, "CMakeCache.txt")
        if not os.path.isfile(cache_path):
            errors.die(
                f"--cmake-no-configure requires an existing CMakeCache.txt in the build directory ({build_dir})",
                code=1,
            )
    else:
        os.makedirs(build_dir, exist_ok=True)
        _run(["cmake", "-S", source_dir, "-B", build_dir, *cmake_args], env=env)

    _run(["cmake", "--build", build_dir, f"-j{build_jobs}"], env=env)
    if build_ops.build_dir_has_install_rules(build_dir):
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
        return

    if os.path.islink(install_prefix) or os.path.isfile(install_prefix):
        os.remove(install_prefix)
    elif os.path.isdir(install_prefix):
        shutil.rmtree(install_prefix)
    print(f"Build complete -> dir={build_dir} | sdk=<none>")
