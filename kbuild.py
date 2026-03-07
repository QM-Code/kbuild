#!/usr/bin/env python3

import json
import os
import sys
from collections.abc import Callable


WRAPPER_API = "1"
LOCAL_CONFIG_FILENAME = ".kbuild.json"


def fail(message: str, *, exit_code: int = 2) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def enforce_script_directory() -> str:
    repo_root = os.path.abspath(os.path.dirname(__file__))
    cwd = os.path.abspath(os.getcwd())
    repo_root_cmp = os.path.normcase(os.path.realpath(repo_root))
    cwd_cmp = os.path.normcase(os.path.realpath(cwd))
    if cwd_cmp != repo_root_cmp:
        fail("kbuild.py must be run from the directory it is in. Run `./kbuild.py` from that directory.")
    return repo_root


def parse_bootstrap_root_arg(args: list[str]) -> tuple[str | None, list[str]]:
    root_override: str | None = None
    passthrough: list[str] = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--kbuild-root":
            i += 1
            if i >= len(args):
                fail("missing value for '--kbuild-root'", exit_code=1)
            value = args[i].strip()
            if not value:
                fail("--kbuild-root requires a non-empty value", exit_code=1)
            if root_override is not None:
                fail("--kbuild-root cannot be specified more than once", exit_code=1)
            root_override = value
        else:
            passthrough.append(arg)
        i += 1

    return root_override, passthrough


def _load_json_object(path: str, *, display_name: str) -> dict[str, object]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"could not parse ./{display_name}: {exc}")
    if not isinstance(payload, dict):
        fail(f"{display_name} must be a JSON object")
    return payload


def _write_json_object(path: str, payload: dict[str, object]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _load_local_config(repo_root: str) -> dict[str, object]:
    local_path = os.path.join(repo_root, LOCAL_CONFIG_FILENAME)
    if not os.path.isfile(local_path):
        fail(
            "missing required local config file './.kbuild.json'. "
            "Run './kbuild.py --kbuild-root <path>' first."
        )
    return _load_json_object(local_path, display_name=LOCAL_CONFIG_FILENAME)


def _write_local_root_override(repo_root: str, root_token: str) -> None:
    local_path = os.path.join(repo_root, LOCAL_CONFIG_FILENAME)
    payload: dict[str, object] = {}
    if os.path.isfile(local_path):
        payload = _load_json_object(local_path, display_name=LOCAL_CONFIG_FILENAME)
    elif os.path.exists(local_path):
        fail("./.kbuild.json exists but is not a regular file")

    kbuild_raw = payload.get("kbuild")
    if not isinstance(kbuild_raw, dict):
        kbuild_raw = {}

    kbuild_raw["root"] = root_token
    kbuild_raw["api"] = WRAPPER_API
    payload["kbuild"] = kbuild_raw
    _write_json_object(local_path, payload)


def load_config_root_token(repo_root: str) -> str:
    payload = _load_local_config(repo_root)
    kbuild_raw = payload.get("kbuild")
    if not isinstance(kbuild_raw, dict):
        fail("kbuild.root is required in .kbuild.json. Run './kbuild.py --kbuild-root <path>' first.")

    root_raw = kbuild_raw.get("root")
    if not isinstance(root_raw, str) or not root_raw.strip():
        fail("kbuild.root is required in .kbuild.json. Run './kbuild.py --kbuild-root <path>' first.")

    api_raw = kbuild_raw.get("api")
    if api_raw is not None:
        if isinstance(api_raw, str):
            api_token = api_raw.strip()
        elif isinstance(api_raw, int) and not isinstance(api_raw, bool):
            api_token = str(api_raw)
        else:
            fail("kbuild.api must be a non-empty string or integer when defined")
        if not api_token:
            fail("kbuild.api must be a non-empty string or integer when defined")
        if api_token != WRAPPER_API:
            fail(
                f"kbuild.api mismatch: config={api_token} wrapper={WRAPPER_API}. "
                "Run './kbuild.py --kbuild-root <path>' to refresh local bootstrap config."
            )

    return root_raw.strip()


def resolve_rootdir(repo_root: str, root_token: str) -> str:
    if os.path.isabs(root_token):
        root_abs = os.path.abspath(root_token)
    else:
        root_abs = os.path.abspath(os.path.join(repo_root, root_token))

    if not os.path.isdir(root_abs):
        fail(
            f"kbuild.root resolves to '{root_abs}' but does not exist. "
            "Run './kbuild.py --kbuild-root <path>' with a valid kbuild directory."
        )

    return root_abs


def load_core_runner(root_abs: str) -> Callable[..., int]:
    libs_dir = os.path.join(root_abs, "libs")
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


def main() -> int:
    repo_root = enforce_script_directory()
    raw_args = sys.argv[1:]

    root_override, passthrough_args = parse_bootstrap_root_arg(raw_args)

    if root_override is not None:
        if passthrough_args:
            fail(
                "--kbuild-root cannot be combined with other options. "
                "Run './kbuild.py --kbuild-root <path>' by itself.",
                exit_code=1,
            )
        root_abs = resolve_rootdir(repo_root, root_override)
        try:
            load_core_runner(root_abs)
        except ValueError as exc:
            fail(f"--kbuild-root path is not a valid kbuild directory: {exc}", exit_code=1)
        _write_local_root_override(repo_root, root_override)
        print(f"Updated ./.kbuild.json with kbuild.root='{root_override}'", flush=True)
        return 0

    root_token = load_config_root_token(repo_root)
    root_abs = resolve_rootdir(repo_root, root_token)
    try:
        run_core = load_core_runner(root_abs)
    except ValueError as exc:
        fail(
            "could not bootstrap from ./.kbuild.json: "
            f"{exc}. Run './kbuild.py --kbuild-root <path>' first."
        )

    return run_core(
        repo_root=repo_root,
        argv=raw_args,
        kbuild_root=root_abs,
        program_name=os.path.basename(sys.argv[0]),
    )


if __name__ == "__main__":
    raise SystemExit(main())
