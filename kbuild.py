#!/usr/bin/env python3

import os
import sys


LOCAL_CONFIG_FILENAME = ".kbuild.json"


def fail(message: str, *, exit_code: int = 2) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def load_core_runner(kbuild_root: str):
    libs_dir = os.path.join(kbuild_root, "libs")
    package_init = os.path.join(libs_dir, "kbuild", "__init__.py")
    if not os.path.isfile(package_init):
        raise ValueError(f"required shared library package is missing: {package_init}")

    if libs_dir not in sys.path:
        sys.path.insert(0, libs_dir)

    try:
        from kbuild import run as run_core
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"failed to load shared kbuild library from {libs_dir}: {exc}") from exc

    return run_core


def resolve_kbuild_root() -> str:
    script_path = os.path.realpath(__file__)
    root_abs = os.path.abspath(os.path.dirname(script_path))
    if not os.path.isdir(root_abs):
        raise ValueError(f"kbuild root does not exist: {root_abs}")
    return root_abs


def ensure_local_repo_config_exists(repo_root: str) -> None:
    local_path = os.path.join(repo_root, LOCAL_CONFIG_FILENAME)
    if os.path.isfile(local_path):
        return
    if os.path.exists(local_path):
        fail(f"expected './{LOCAL_CONFIG_FILENAME}' to be a regular file", exit_code=1)
    fail(
        "current directory is not a valid kbuild repo root.\n"
        f"Missing required file './{LOCAL_CONFIG_FILENAME}'.\n"
        "Run 'kbuild --kbuild-config' from the repo root first.",
        exit_code=1,
    )


def main() -> int:
    repo_root = os.path.abspath(os.getcwd())
    raw_args = list(sys.argv[1:])
    create_config_requested = "--kbuild-config" in raw_args

    if not create_config_requested:
        ensure_local_repo_config_exists(repo_root)

    try:
        kbuild_root = resolve_kbuild_root()
        run_core = load_core_runner(kbuild_root)
    except ValueError as exc:
        fail(str(exc), exit_code=1)

    return run_core(
        repo_root=repo_root,
        argv=raw_args,
        kbuild_root=kbuild_root,
        program_name=os.path.basename(sys.argv[0]) or "kbuild",
    )


if __name__ == "__main__":
    raise SystemExit(main())
