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


def usage(exit_code: int = 1) -> None:
    prog = PROGRAM_NAME
    print(f"Usage: {prog} <options>", file=sys.stderr)
    print("  --list-builds       list existing build version directories", file=sys.stderr)
    print("  --remove-latest     remove every build/latest/ directory", file=sys.stderr)
    print("  --version <name>    build version slot under build/ (default: latest)", file=sys.stderr)
    print(
        "  --build-demos [demo ...]  build demos in order; with no args uses kbuild.json build.demos",
        file=sys.stderr,
    )
    print("  --rebuild          remove existing build directory/directories before building", file=sys.stderr)
    print("  --configure         force cmake configure step", file=sys.stderr)
    print("  --no-configure      skip cmake configure step", file=sys.stderr)
    print("  --create-config     create a starter kbuild.json template", file=sys.stderr)
    print("                     (requires wrapper bootstrap option: --kbuild-root <path>)", file=sys.stderr)
    print("  --initialize-repo   scaffold this repo from kbuild.json metadata", file=sys.stderr)
    print(
        "  --initialize-git    verify remote, initialize local git repo, commit, and push main",
        file=sys.stderr,
    )
    print("  --git-sync <msg>    git add . && git commit -m <msg> && git push", file=sys.stderr)
    print("  --sync-vcpkg-baseline  set baseline fields from ./vcpkg/src HEAD", file=sys.stderr)
    print(
        "  --install-vcpkg     clone/bootstrap local vcpkg under ./vcpkg, sync baseline, then build",
        file=sys.stderr,
    )
    raise SystemExit(exit_code)


def fail(message: str) -> None:
    errors.die_with_usage(message, usage, code=1)


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
    bootstrap_root_override: str | None = None,
) -> int:
    global PROGRAM_NAME
    PROGRAM_NAME = program_name

    version = "latest"
    version_explicit = False
    configure_override: bool | None = None
    configure_flag_seen = False
    create_config = False
    install_vcpkg = False
    sync_vcpkg_baseline_only = False
    build_demos = False
    rebuild = False
    list_builds = False
    remove_latest_builds = False
    initialize_repo = False
    initialize_git = False
    git_sync_requested = False
    git_sync_message = ""
    requested_demos: list[str] = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-h", "--help"):
            usage(0)
        elif arg == "--create-config":
            create_config = True
        elif arg == "--list-builds":
            list_builds = True
        elif arg == "--remove-latest":
            remove_latest_builds = True
        elif arg == "--initialize-repo":
            initialize_repo = True
        elif arg == "--initialize-git":
            initialize_git = True
        elif arg == "--git-sync":
            git_sync_requested = True
            i += 1
            if i >= len(args):
                fail("missing value for '--git-sync'")
            git_sync_message = args[i].strip()
            if not git_sync_message:
                fail("--git-sync requires a non-empty commit message")
        elif arg == "--sync-vcpkg-baseline":
            sync_vcpkg_baseline_only = True
        elif arg == "--version":
            i += 1
            if i >= len(args):
                fail("missing value for '--version'")
            version = build_ops.validate_version_slot(args[i])
            version_explicit = True
        elif arg == "--build-demos":
            build_demos = True
            i += 1
            while i < len(args) and not args[i].startswith("-"):
                requested_demos.append(args[i])
                i += 1
            continue
        elif arg == "--rebuild":
            rebuild = True
        elif arg == "--configure":
            configure_override = True
            configure_flag_seen = True
        elif arg == "--no-configure":
            configure_override = False
            configure_flag_seen = True
        elif arg == "--install-vcpkg":
            install_vcpkg = True
        elif arg.startswith("-"):
            fail(f"unknown option '{arg}'")
        else:
            fail(f"unexpected positional argument '{arg}'; use --version <name>")
        i += 1

    build_mode_flags: list[str] = []
    if version_explicit:
        build_mode_flags.append("--version")
    if build_demos:
        build_mode_flags.append("--build-demos")
    if configure_flag_seen:
        build_mode_flags.append("--configure/--no-configure")
    if rebuild:
        build_mode_flags.append("--rebuild")
    if install_vcpkg:
        build_mode_flags.append("--install-vcpkg")

    if create_config and (
        list_builds
        or remove_latest_builds
        or initialize_repo
        or initialize_git
        or git_sync_requested
        or sync_vcpkg_baseline_only
        or bool(build_mode_flags)
    ):
        fail("--create-config cannot be combined with other options")

    if list_builds and remove_latest_builds:
        fail("--list-builds and --remove-latest cannot be combined")
    if list_builds and build_mode_flags:
        fail("--list-builds cannot be combined with build options")
    if remove_latest_builds and build_mode_flags:
        fail("--remove-latest cannot be combined with build options")
    if initialize_repo and (list_builds or remove_latest_builds or build_mode_flags):
        fail("--initialize-repo cannot be combined with other options")
    if initialize_git and (
        list_builds
        or remove_latest_builds
        or initialize_repo
        or git_sync_requested
        or sync_vcpkg_baseline_only
        or bool(build_mode_flags)
    ):
        fail("--initialize-git cannot be combined with other options")
    if git_sync_requested and (
        list_builds
        or remove_latest_builds
        or initialize_repo
        or initialize_git
        or sync_vcpkg_baseline_only
        or bool(build_mode_flags)
    ):
        fail("--git-sync cannot be combined with other options")
    if sync_vcpkg_baseline_only and (
        list_builds
        or remove_latest_builds
        or initialize_repo
        or initialize_git
        or git_sync_requested
        or build_mode_flags
    ):
        fail("--sync-vcpkg-baseline cannot be combined with other options")

    if create_config and bootstrap_root_override is None:
        fail("--create-config requires wrapper bootstrap option --kbuild-root <path>")

    config_path = os.path.join(repo_root, "kbuild.json")
    if not os.path.isfile(config_path):
        if create_config:
            return config_ops.create_kbuild_config_template(repo_root, bootstrap_root_override)
        errors.die(
            "'kbuild.json' does not exist.\n"
            "Run `./kbuild.py --kbuild-root <path> --create-config` to create a template."
        )
    if create_config:
        errors.die("'./kbuild.json' already exists.")

    if initialize_repo:
        return repo_init.initialize_repo_layout(repo_root, templates_root)
    if initialize_git:
        git_url, git_auth = git_ops.load_git_urls(repo_root)
        return git_ops.initialize_git_repo(repo_root, git_url, git_auth)
    if git_sync_requested:
        return git_ops.git_sync(repo_root, git_sync_message)
    if remove_latest_builds:
        return build_ops.remove_latest_build_dirs(repo_root)
    if list_builds:
        return build_ops.list_build_dirs(repo_root)

    (
        has_cmake,
        cmake_package_name,
        configure_by_default,
        has_vcpkg,
        config_build_demos,
        config_default_build_demos,
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
    configure = configure_by_default if configure_override is None else configure_override
    if rebuild:
        if configure_override is False:
            fail("--rebuild cannot be combined with --no-configure")
        configure = True

    demo_order: list[str] = []
    if build_demos:
        if requested_demos:
            demo_order = [build_ops.normalize_demo_name(token) for token in requested_demos]
        else:
            if not config_build_demos:
                fail("kbuild.json must define 'build.demos' for --build-demos with no demo arguments")
            demo_order = [build_ops.normalize_demo_name(token) for token in config_build_demos]
    elif config_default_build_demos:
        demo_order = [build_ops.normalize_demo_name(token) for token in config_default_build_demos]

    if demo_order:
        if not cmake_package_name:
            fail(
                "demo builds require SDK metadata; define cmake.sdk.package_name in kbuild.json"
            )
        for demo_name in demo_order:
            build_ops.resolve_demo_source_dir(repo_root, demo_name)

    if rebuild:
        removed = 0
        core_build_dir = os.path.join(repo_root, "build", version)
        if build_ops.remove_version_build_dir(core_build_dir, repo_root):
            removed += 1
        for demo_name in demo_order:
            demo_build_dir = os.path.join(repo_root, "demo", demo_name, "build", version)
            if build_ops.remove_version_build_dir(demo_build_dir, repo_root):
                removed += 1
        if removed == 0:
            print(f"no existing build directories found for --rebuild (version={version})")

    build_dir = os.path.join("build", version)

    source_dir = repo_root
    cmake_args = ["-DCMAKE_BUILD_TYPE=Release"]
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
            fail("--no-configure requires an existing CMakeCache.txt in the build directory")
    else:
        os.makedirs(build_dir, exist_ok=True)
        run(["cmake", "-S", source_dir, "-B", build_dir, *cmake_args], env=env)

    run(["cmake", "--build", build_dir, "-j4"], env=env)

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
                cmake_package_name=cmake_package_name,
                sdk_dependencies=sdk_dependencies,
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
