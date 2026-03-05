import os
import shutil
import subprocess

from . import build_ops
from . import errors
from . import vcpkg_ops


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, env=env)


def build_demo(
    repo_root: str,
    demo_name: str,
    version: str,
    configure: bool,
    cmake_package_name: str,
    sdk_dependencies: list[tuple[str, str]],
    env: dict[str, str],
    demo_order: list[str],
) -> None:
    core_build_dir = os.path.join(repo_root, "build", version)
    core_sdk_prefix = os.path.join(core_build_dir, "sdk")
    build_ops.validate_sdk_prefix(core_sdk_prefix, cmake_package_name)

    demo_vcpkg_installed_dir, demo_vcpkg_triplet = vcpkg_ops.resolve_demo_vcpkg_context(
        core_sdk_prefix, repo_root
    )
    demo_vcpkg_prefix = os.path.join(demo_vcpkg_installed_dir, demo_vcpkg_triplet)
    if not os.path.isdir(demo_vcpkg_prefix):
        errors.die(f"missing vcpkg triplet prefix: {demo_vcpkg_prefix}")

    source_dir = build_ops.resolve_demo_source_dir(repo_root, demo_name)
    build_dir = os.path.join(repo_root, "demo", demo_name, "build", version)
    install_prefix = os.path.join(build_dir, "sdk")

    prefix_entries: list[str] = [core_sdk_prefix, demo_vcpkg_prefix]
    for _, dependency_prefix in sdk_dependencies:
        if dependency_prefix not in prefix_entries:
            prefix_entries.append(dependency_prefix)
    for dependency_demo in demo_order:
        dependency_sdk = os.path.join(repo_root, "demo", dependency_demo, "build", version, "sdk")
        if os.path.isdir(dependency_sdk) and dependency_sdk not in prefix_entries:
            prefix_entries.append(dependency_sdk)

    cmake_args = [
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_PREFIX_PATH={';'.join(prefix_entries)}",
        "-DCMAKE_FIND_PACKAGE_PREFER_CONFIG=ON",
        f"-D{cmake_package_name}_DIR={build_ops.package_dir(core_sdk_prefix, cmake_package_name)}",
    ]
    for package_name, dependency_prefix in sdk_dependencies:
        cmake_args.append(f"-D{package_name}_DIR={build_ops.package_dir(dependency_prefix, package_name)}")
    print(
        f"Demo build -> dir={build_dir} | demo={demo_name} | sdk={core_sdk_prefix} | triplet={demo_vcpkg_triplet}",
        flush=True,
    )

    if not configure:
        cache_path = os.path.join(build_dir, "CMakeCache.txt")
        if not os.path.isfile(cache_path):
            errors.die(
                f"--no-configure requires an existing CMakeCache.txt in the build directory ({build_dir})",
                code=1,
            )
    else:
        os.makedirs(build_dir, exist_ok=True)
        _run(["cmake", "-S", source_dir, "-B", build_dir, *cmake_args], env=env)

    _run(["cmake", "--build", build_dir, "-j4"], env=env)
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
