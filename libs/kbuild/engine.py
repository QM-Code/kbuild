#!/usr/bin/env python3

import os
import subprocess
import sys

from . import build_ops
from . import config_ops
from . import demo_ops
from . import errors
from . import git_ops
from . import repo_init
from . import vcpkg_ops


PROGRAM_NAME = "kbuild.py"


def print_build_usage(*, file: object) -> None:
    print("Build options:", file=file)
    print(
        "  --build [version]       build a version slot under build/; with no version prints this section",
        file=file,
    )
    print("  --build-latest          build the latest slot", file=file)
    print(
        "  --build-demos [demo ...]  build demos in order; with no args uses kbuild.json build.demos",
        file=file,
    )
    print("  --build-type <t>        build type: static|shared|both", file=file)
    print("  --build-jobs <n>        number of parallel jobs for cmake --build", file=file)
    print("  --build-list            list existing build version directories", file=file)


def print_clean_usage(*, file: object) -> None:
    print("Clean options:", file=file)
    print(
        "  --clean [version]       remove a specific build version; with no version prints this section",
        file=file,
    )
    print("  --clean-latest          remove every build/latest/ directory", file=file)
    print("  --clean-all             remove every build version directory", file=file)


def usage(exit_code: int = 1) -> None:
    prog = PROGRAM_NAME
    print(f"Usage: {prog} <options>", file=sys.stderr)
    print("", file=sys.stderr)
    print("Initialization options:", file=sys.stderr)
    print(
        "  --kbuild-root <dir>     validate a shared kbuild checkout and update ./.kbuild.json",
        file=sys.stderr,
    )
    print("  --kbuild-config         create a starter kbuild.json template", file=sys.stderr)
    print("  --kbuild-init           scaffold this repo from ./kbuild.json", file=sys.stderr)
    print("", file=sys.stderr)
    print_build_usage(file=sys.stderr)
    print("", file=sys.stderr)
    print("CMake options:", file=sys.stderr)
    print("  --cmake-configure       force cmake configure step", file=sys.stderr)
    print("  --cmake-no-configure    skip cmake configure step", file=sys.stderr)
    print("", file=sys.stderr)
    print("Git options:", file=sys.stderr)
    print(
        "  --git-initialize        verify remote, initialize local git repo, commit, and push main",
        file=sys.stderr,
    )
    print("  --git-sync <msg>        git add . && git commit -m <msg> && git push", file=sys.stderr)
    print("", file=sys.stderr)
    print("VCpkg options:", file=sys.stderr)
    print(
        "  --vcpkg-install         clone/bootstrap local vcpkg under ./vcpkg, sync baseline, then build",
        file=sys.stderr,
    )
    print(
        "  --vcpkg-sync-baseline   set baseline fields from ./vcpkg/src HEAD",
        file=sys.stderr,
    )
    print("", file=sys.stderr)
    print_clean_usage(file=sys.stderr)
    raise SystemExit(exit_code)


def usage_build(exit_code: int = 0) -> None:
    print(f"Usage: {PROGRAM_NAME} --build [version] [build options]", file=sys.stderr)
    print_build_usage(file=sys.stderr)
    raise SystemExit(exit_code)


def usage_clean(exit_code: int = 0) -> None:
    print(f"Usage: {PROGRAM_NAME} --clean [version] [clean options]", file=sys.stderr)
    print_clean_usage(file=sys.stderr)
    raise SystemExit(exit_code)


def fail(message: str) -> None:
    errors.die_with_usage(message, usage, code=1)


def ensure_shared_config_exists(repo_root: str) -> None:
    config_path = os.path.join(repo_root, config_ops.PRIMARY_KBUILD_CONFIG_FILENAME)
    if os.path.isfile(config_path):
        return
    errors.die(
        "missing required config file './kbuild.json'.\n"
        "Run './kbuild.py --kbuild-config' first.",
        code=1,
    )


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, env=env)


def enforce_script_directory() -> str:
    repo_root = os.path.abspath(os.path.dirname(__file__))
    cwd = os.path.abspath(os.getcwd())
    repo_root_cmp = os.path.normcase(os.path.realpath(repo_root))
    cwd_cmp = os.path.normcase(os.path.realpath(cwd))
    if cwd_cmp != repo_root_cmp:
        errors.die(
            "kbuild.py must be run from the directory it is in.\n"
            "Run `./kbuild.py` from that directory."
        )
    return repo_root


def main(
    *,
    repo_root: str,
    args: list[str],
    templates_root: str,
    program_name: str = "kbuild.py",
) -> int:
    global PROGRAM_NAME
    PROGRAM_NAME = program_name

    if not args:
        usage(0)

    version = "latest"
    version_explicit = False
    build_requested = False
    configure_override: bool | None = None
    configure_flag_seen = False
    create_config = False
    install_vcpkg = False
    sync_vcpkg_baseline_only = False
    build_demos = False
    list_builds = False
    clean_requested = False
    clean_version: str | None = None
    clean_latest = False
    clean_all = False
    initialize_repo = False
    initialize_git = False
    git_sync_requested = False
    git_sync_message = ""
    build_jobs_override: int | None = None
    build_type_override: str | None = None
    requested_demos: list[str] = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-h", "--help"):
            usage(0)
        elif arg == "--kbuild-config":
            create_config = True
        elif arg == "--build-list":
            list_builds = True
        elif arg == "--clean-latest":
            clean_latest = True
        elif arg == "--clean-all":
            clean_all = True
        elif arg == "--clean":
            clean_requested = True
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                i += 1
                clean_version = build_ops.validate_version_slot(args[i], option_name="--clean")
        elif arg == "--kbuild-init":
            initialize_repo = True
        elif arg == "--git-initialize":
            initialize_git = True
        elif arg == "--git-sync":
            git_sync_requested = True
            i += 1
            if i >= len(args):
                fail("missing value for '--git-sync'")
            git_sync_message = args[i].strip()
            if not git_sync_message:
                fail("--git-sync requires a non-empty commit message")
        elif arg == "--vcpkg-sync-baseline":
            sync_vcpkg_baseline_only = True
        elif arg == "--build":
            build_requested = True
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                i += 1
                version = build_ops.validate_version_slot(args[i], option_name="--build")
                version_explicit = True
        elif arg == "--build-latest":
            build_requested = True
            version = "latest"
            version_explicit = True
        elif arg == "--build-jobs":
            build_requested = True
            i += 1
            if i >= len(args):
                fail("missing value for '--build-jobs'")
            try:
                parsed_jobs = int(args[i].strip())
            except ValueError:
                fail("--build-jobs requires a positive integer")
            if parsed_jobs < 1:
                fail("--build-jobs requires a positive integer")
            build_jobs_override = parsed_jobs
        elif arg == "--build-type":
            build_requested = True
            i += 1
            if i >= len(args):
                fail("missing value for '--build-type'")
            parsed_build_type = args[i].strip().lower()
            if parsed_build_type not in config_ops.VALID_BUILD_TYPES:
                fail("--build-type must be one of: static, shared, both")
            build_type_override = parsed_build_type
        elif arg == "--build-demos":
            build_requested = True
            build_demos = True
            i += 1
            while i < len(args) and not args[i].startswith("-"):
                requested_demos.append(args[i])
                i += 1
            continue
        elif arg == "--cmake-configure":
            build_requested = True
            configure_override = True
            configure_flag_seen = True
        elif arg == "--cmake-no-configure":
            build_requested = True
            configure_override = False
            configure_flag_seen = True
        elif arg == "--vcpkg-install":
            build_requested = True
            install_vcpkg = True
        elif arg.startswith("-"):
            fail(f"unknown option '{arg}'")
        else:
            fail(f"unexpected positional argument '{arg}'; use --build <name>")
        i += 1

    build_help_requested = build_requested and not (
        version_explicit
        or build_demos
        or build_jobs_override is not None
        or build_type_override is not None
        or configure_flag_seen
        or install_vcpkg
    )
    clean_help_requested = clean_requested and clean_version is None and not clean_latest and not clean_all

    if build_help_requested:
        usage_build(0)
    if clean_help_requested:
        usage_clean(0)

    clean_target_count = int(clean_version is not None) + int(clean_latest) + int(clean_all)
    if clean_target_count > 1:
        fail("use only one clean target: --clean <version>, --clean-latest, or --clean-all")

    build_mode = build_requested or version_explicit or build_demos or build_jobs_override is not None or build_type_override is not None or configure_flag_seen or install_vcpkg
    clean_mode = clean_target_count > 0

    if create_config and (
        list_builds
        or clean_mode
        or initialize_repo
        or initialize_git
        or git_sync_requested
        or sync_vcpkg_baseline_only
        or build_mode
    ):
        fail("--kbuild-config cannot be combined with other options")

    if list_builds and (clean_mode or initialize_repo or initialize_git or git_sync_requested or sync_vcpkg_baseline_only or build_mode):
        fail("--build-list cannot be combined with other options")
    if clean_mode and (initialize_repo or initialize_git or git_sync_requested or sync_vcpkg_baseline_only or build_mode or list_builds):
        fail("clean options cannot be combined with build, git, or kbuild init/config options")
    if initialize_repo and (list_builds or clean_mode or initialize_git or git_sync_requested or sync_vcpkg_baseline_only or build_mode):
        fail("--kbuild-init cannot be combined with other options")
    if initialize_git and (
        list_builds
        or clean_mode
        or initialize_repo
        or git_sync_requested
        or sync_vcpkg_baseline_only
        or build_mode
        or create_config
    ):
        fail("--git-initialize cannot be combined with other options")
    if git_sync_requested and (
        list_builds
        or clean_mode
        or initialize_repo
        or initialize_git
        or sync_vcpkg_baseline_only
        or build_mode
        or create_config
    ):
        fail("--git-sync cannot be combined with other options")
    if sync_vcpkg_baseline_only and (
        list_builds
        or clean_mode
        or initialize_repo
        or initialize_git
        or git_sync_requested
        or build_mode
        or create_config
    ):
        fail("--vcpkg-sync-baseline cannot be combined with other options")

    if not create_config:
        ensure_shared_config_exists(repo_root)

    if initialize_repo:
        return repo_init.initialize_repo_layout(repo_root, templates_root)
    if create_config:
        return config_ops.create_kbuild_config_template(repo_root)
    if initialize_git:
        git_url, git_auth = git_ops.load_git_urls(repo_root)
        return git_ops.initialize_git_repo(repo_root, git_url, git_auth)
    if git_sync_requested:
        return git_ops.git_sync(repo_root, git_sync_message)
    if list_builds:
        return build_ops.list_build_dirs(repo_root)
    if clean_latest:
        return build_ops.remove_latest_build_dirs(repo_root)
    if clean_all:
        return build_ops.remove_all_build_dirs(repo_root)
    if clean_version is not None:
        return build_ops.remove_build_dirs_for_slot(repo_root, clean_version)

    (
        project_id,
        has_cmake,
        cmake_minimum_version,
        cmake_package_name,
        configure_by_default,
        has_vcpkg,
        config_build_demos,
        config_default_build_demos,
        config_build_jobs,
        config_build_type,
        config_sdk_dependencies,
    ) = config_ops.load_kbuild_config(repo_root)

    if sync_vcpkg_baseline_only:
        if not has_vcpkg:
            print("Nothing to do.")
            return 0
        vcpkg_ops.sync_vcpkg_baseline(repo_root)
        return 0

    if install_vcpkg and has_vcpkg:
        vcpkg_ops.install_local_vcpkg(repo_root)
        vcpkg_ops.sync_vcpkg_baseline(repo_root)

    if not has_cmake:
        print("Nothing to do.")
        return 0

    sdk_dependencies = build_ops.resolve_sdk_dependencies(repo_root, version, config_sdk_dependencies)
    build_jobs = config_build_jobs if build_jobs_override is None else build_jobs_override
    build_type = config_build_type if build_type_override is None else build_type_override
    build_static = build_type in {"static", "both"}
    build_shared = build_type in {"shared", "both"}
    configure = configure_by_default if configure_override is None else configure_override
    demo_order: list[str] = []
    if build_demos:
        if requested_demos:
            demo_order = [build_ops.normalize_demo_name(token) for token in requested_demos]
        else:
            if not config_build_demos:
                fail("config must define 'build.demos' for --build-demos with no demo arguments")
            demo_order = [build_ops.normalize_demo_name(token) for token in config_build_demos]
    elif config_default_build_demos:
        demo_order = [build_ops.normalize_demo_name(token) for token in config_default_build_demos]

    if demo_order:
        if not cmake_package_name:
            fail(
                "demo builds require SDK metadata; define cmake.sdk.package_name in config"
            )
        for demo_name in demo_order:
            build_ops.resolve_demo_source_dir(repo_root, demo_name)

    build_dir = os.path.join("build", version)

    source_dir = repo_root
    project_id_upper = project_id.upper()
    cmake_args = [
        "-DCMAKE_BUILD_TYPE=Release",
        f"-D{project_id_upper}_BUILD_STATIC={'ON' if build_static else 'OFF'}",
        f"-D{project_id_upper}_BUILD_SHARED={'ON' if build_shared else 'OFF'}",
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
    if has_vcpkg:
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
            fail("--cmake-no-configure requires an existing CMakeCache.txt in the build directory")
    else:
        os.makedirs(build_dir, exist_ok=True)
        run(["cmake", "-S", source_dir, "-B", build_dir, *cmake_args], env=env)

    run(["cmake", "--build", build_dir, f"-j{build_jobs}"], env=env)

    install_prefix = os.path.abspath(os.path.join(build_dir, "sdk"))
    build_ops.clean_sdk_install_prefix(install_prefix)
    run(
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

    if demo_order:
        for demo_name in demo_order:
            demo_ops.build_demo(
                repo_root=repo_root,
                demo_name=demo_name,
                version=version,
                configure=configure,
                cmake_minimum_version=cmake_minimum_version,
                cmake_package_name=cmake_package_name,
                sdk_dependencies=sdk_dependencies,
                build_jobs=build_jobs,
                build_static=build_static,
                build_shared=build_shared,
                env=env,
                demo_order=demo_order,
            )

    return 0


if __name__ == "__main__":
    repo = enforce_script_directory()
    raise SystemExit(
        main(
            repo_root=repo,
            args=sys.argv[1:],
            templates_root=os.path.join(repo, "templates"),
            program_name=os.path.basename(sys.argv[0]),
        )
    )
