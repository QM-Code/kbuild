import glob
import json
import os
import shutil
import subprocess

from . import build_ops
from . import config_ops
from . import errors


def find_unexpected_residuals(repo_root: str) -> tuple[str, list[str]] | None:
    findings: list[str] = []
    for current_root, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = sorted(
            dirname
            for dirname in dirnames
            if dirname not in (".git", "build", "node_modules")
        )
        for filename in sorted(filenames):
            candidate_path = os.path.join(current_root, filename)
            if filename == "kbuild-javascript-sdk.json" or _looks_like_generated_launcher(candidate_path):
                findings.append(candidate_path)

    if not findings:
        return None
    return ("JavaScript kbuild artifacts", findings)


def _load_javascript_config(
    repo_root: str,
) -> tuple[str, str, list[str], list[tuple[str, str]], dict[str, tuple[str, str]]]:
    raw = config_ops.load_effective_kbuild_payload(repo_root, require_local=True)
    javascript_raw = raw.get("javascript")
    if not isinstance(javascript_raw, dict):
        errors.die("kbuild config key 'javascript' must be an object")

    allowed_javascript = {"package", "sdk_dir", "test_globs", "dependencies", "demos"}
    for key in javascript_raw:
        if key not in allowed_javascript:
            errors.die(f"unexpected key in kbuild config 'javascript': '{key}'")

    package_raw = javascript_raw.get("package")
    if not isinstance(package_raw, str) or not package_raw.strip():
        errors.die("kbuild config key 'javascript.package' must be a non-empty string")
    package_name = package_raw.strip()

    sdk_dir_raw = javascript_raw.get("sdk_dir")
    if not isinstance(sdk_dir_raw, str) or not sdk_dir_raw.strip():
        errors.die("kbuild config key 'javascript.sdk_dir' must be a non-empty string")
    sdk_dir = sdk_dir_raw.strip().replace("\\", "/")

    test_globs_raw = javascript_raw.get("test_globs", [])
    if not isinstance(test_globs_raw, list):
        errors.die("kbuild config key 'javascript.test_globs' must be an array when defined")
    test_globs: list[str] = []
    for idx, item in enumerate(test_globs_raw):
        if not isinstance(item, str) or not item.strip():
            errors.die(f"kbuild config key 'javascript.test_globs[{idx}]' must be a non-empty string")
        test_globs.append(item.strip().replace("\\", "/"))

    dependencies_raw = javascript_raw.get("dependencies", {})
    if not isinstance(dependencies_raw, dict):
        errors.die("kbuild config key 'javascript.dependencies' must be an object when defined")
    dependency_specs: list[tuple[str, str]] = []
    for dependency_name_raw, dependency_raw in dependencies_raw.items():
        if not isinstance(dependency_name_raw, str) or not dependency_name_raw.strip():
            errors.die("kbuild config key 'javascript.dependencies' has an invalid dependency name")
        dependency_name = dependency_name_raw.strip()
        if not isinstance(dependency_raw, dict):
            errors.die(f"kbuild config key 'javascript.dependencies.{dependency_name}' must be an object")
        allowed_dependency = {"prefix"}
        for key in dependency_raw:
            if key not in allowed_dependency:
                errors.die(
                    f"unexpected key in kbuild config 'javascript.dependencies.{dependency_name}': '{key}'"
                )
        prefix_raw = dependency_raw.get("prefix")
        if not isinstance(prefix_raw, str) or not prefix_raw.strip():
            errors.die(
                f"kbuild config key 'javascript.dependencies.{dependency_name}.prefix' must be a non-empty string"
            )
        dependency_specs.append((dependency_name, prefix_raw.strip()))

    demos_raw = javascript_raw.get("demos", {})
    if not isinstance(demos_raw, dict):
        errors.die("kbuild config key 'javascript.demos' must be an object when defined")
    demo_specs: dict[str, tuple[str, str]] = {}
    for demo_name_raw, demo_raw in demos_raw.items():
        if not isinstance(demo_name_raw, str) or not demo_name_raw.strip():
            errors.die("kbuild config key 'javascript.demos' has an invalid demo name")
        demo_name = build_ops.normalize_demo_name(demo_name_raw.strip())
        if not isinstance(demo_raw, dict):
            errors.die(f"kbuild config key 'javascript.demos.{demo_name}' must be an object")
        allowed_demo = {"entry", "output"}
        for key in demo_raw:
            if key not in allowed_demo:
                errors.die(f"unexpected key in kbuild config 'javascript.demos.{demo_name}': '{key}'")
        entry_raw = demo_raw.get("entry")
        if not isinstance(entry_raw, str) or not entry_raw.strip():
            errors.die(f"kbuild config key 'javascript.demos.{demo_name}.entry' must be a non-empty string")
        output_raw = demo_raw.get("output")
        if output_raw is None:
            output_name = "bootstrap" if demo_name == "bootstrap" else "test"
        else:
            if not isinstance(output_raw, str) or not output_raw.strip():
                errors.die(f"kbuild config key 'javascript.demos.{demo_name}.output' must be a non-empty string")
            output_name = output_raw.strip()
        demo_specs[demo_name] = (entry_raw.strip().replace("\\", "/"), output_name)

    return package_name, sdk_dir, test_globs, dependency_specs, demo_specs


def _prepare_dir(path: str) -> None:
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)


def _copy_sdk_snapshot(repo_root: str, sdk_dir_token: str, install_prefix: str, package_name: str) -> None:
    source_path = os.path.join(repo_root, sdk_dir_token)
    if not os.path.exists(source_path):
        errors.die(f"javascript sdk_dir does not exist: {source_path}")

    _prepare_dir(install_prefix)
    destination_path = os.path.join(install_prefix, sdk_dir_token)
    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    if os.path.isdir(source_path):
        shutil.copytree(source_path, destination_path, dirs_exist_ok=True)
    else:
        shutil.copy2(source_path, destination_path)

    metadata = {
        "package": package_name,
        "sdk_dir": sdk_dir_token,
    }
    metadata_path = os.path.join(install_prefix, "share", "kbuild-javascript-sdk.json")
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(metadata, handle, indent=2)
        handle.write("\n")


def _resolve_dependency_sdk_roots(
    repo_root: str,
    version: str,
    dependency_specs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    resolved: list[tuple[str, str]] = []
    for dependency_name, prefix_template in dependency_specs:
        raw_path = prefix_template.replace("{version}", version)
        candidate_path = os.path.abspath(os.path.join(repo_root, raw_path))
        if not os.path.isdir(candidate_path):
            errors.die(
                "JavaScript dependency SDK directory does not exist.\n"
                f"Dependency: {dependency_name}\n"
                f"Expected:\n  {candidate_path}\n"
                "Build the dependency repo first for the same slot."
            )
        candidate_src = os.path.join(candidate_path, "src", dependency_name)
        if not os.path.isdir(candidate_src):
            errors.die(
                "JavaScript dependency SDK directory is missing staged package sources.\n"
                f"Dependency: {dependency_name}\n"
                f"Expected:\n  {candidate_src}"
            )
        resolved.append((dependency_name, candidate_path))
    return resolved


def _javascript_sdk_env_key(package_name: str) -> str:
    normalized = "".join(char if char.isalnum() else "_" for char in package_name.upper())
    return f"KTOOLS_JS_SDK_ROOT_{normalized}"


def _looks_like_generated_launcher(path: str) -> bool:
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > 32 * 1024:
            return False
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return False
    return (
        text.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")
        and "KTOOLS_JS_SDK_ROOT_" in text
        and "exec node " in text
    )


def _run_node_test(test_globs: list[str], *, repo_root: str, env: dict[str, str]) -> None:
    if not test_globs:
        return
    expanded_tests: list[str] = []
    for pattern in test_globs:
        matches = sorted(glob.glob(os.path.join(repo_root, pattern), recursive=True))
        if not matches:
            errors.die(
                "javascript test glob did not match any files.\n"
                f"Pattern:\n  {pattern}"
            )
        expanded_tests.extend(os.path.relpath(match, repo_root) for match in matches)
    cmd = ["node", "--test", *expanded_tests]
    try:
        subprocess.run(cmd, cwd=repo_root, check=True, env=env)
    except FileNotFoundError:
        errors.die(
            "node executable was not found on PATH.\n"
            "Install Node.js before running JavaScript workspace builds."
        )
    except subprocess.CalledProcessError as exc:
        errors.die(
            "node test command failed.\n"
            f"Command:\n  {' '.join(cmd)}\n"
            f"Exit code:\n  {exc.returncode}",
            code=exc.returncode or 1,
        )


def _write_test_launcher(path: str, *, repo_root: str, test_globs: list[str], env: dict[str, str]) -> None:
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    exports = "".join(
        f'export {key}="{value}"\n'
        for key, value in env.items()
        if key.startswith("KTOOLS_JS_SDK_ROOT_")
    )
    glob_tokens = " ".join(test_globs)
    payload = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'cd "{repo_root}"\n'
        f"{exports}"
        f"exec node --test {glob_tokens} \"$@\"\n"
    )
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
    os.chmod(path, 0o755)


def _write_demo_launcher(path: str, *, entry_abs: str, env: dict[str, str]) -> None:
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    exports = "".join(
        f'export {key}="{value}"\n'
        for key, value in env.items()
        if key.startswith("KTOOLS_JS_SDK_ROOT_")
    )
    payload = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"{exports}"
        f'exec node "{entry_abs}" "$@"\n'
    )
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
    os.chmod(path, 0o755)


def build_repo(
    *,
    repo_root: str,
    version: str,
    build_demos: bool,
    requested_demos: list[str],
    config_build_demos: list[str],
    config_default_build_demos: list[str],
) -> int:
    package_name, sdk_dir, test_globs, dependency_specs, demo_specs = _load_javascript_config(repo_root)
    dependency_sdk_roots = _resolve_dependency_sdk_roots(repo_root, version, dependency_specs)

    demo_order: list[str] = []
    if build_demos:
        if requested_demos:
            demo_order = [build_ops.normalize_demo_name(token) for token in requested_demos]
        else:
            if not config_build_demos:
                errors.die("config must define 'build.demos' for --build-demos with no demo arguments")
            demo_order = [build_ops.normalize_demo_name(token) for token in config_build_demos]
    elif config_default_build_demos:
        demo_order = [build_ops.normalize_demo_name(token) for token in config_default_build_demos]

    build_dir = os.path.join(repo_root, "build", version)
    sdk_dir_abs = os.path.join(build_dir, "sdk")
    tests_dir = os.path.join(build_dir, "tests")
    os.makedirs(build_dir, exist_ok=True)

    _copy_sdk_snapshot(repo_root, sdk_dir, sdk_dir_abs, package_name)

    env = os.environ.copy()
    env[_javascript_sdk_env_key(package_name)] = sdk_dir_abs
    for dependency_name, dependency_sdk_root in dependency_sdk_roots:
        env[_javascript_sdk_env_key(dependency_name)] = dependency_sdk_root

    _run_node_test(test_globs, repo_root=repo_root, env=env)
    if test_globs:
        _write_test_launcher(
            os.path.join(tests_dir, "run-tests"),
            repo_root=repo_root,
            test_globs=test_globs,
            env=env,
        )

    print(f"Build complete -> dir=build/{version} | sdk={sdk_dir_abs}", flush=True)

    for demo_name in demo_order:
        demo_spec = demo_specs.get(demo_name)
        if demo_spec is None:
            errors.die(
                "javascript demo is not defined in config.\n"
                f"Demo:\n  {demo_name}\n"
                "Add it under 'javascript.demos' first."
            )
        entry_token, output_name = demo_spec
        entry_abs = os.path.abspath(os.path.join(repo_root, entry_token))
        if not os.path.isfile(entry_abs):
            errors.die(
                "javascript demo entry script does not exist.\n"
                f"Demo:\n  {demo_name}\n"
                f"Expected:\n  {entry_abs}"
            )
        demo_build_dir = os.path.join(repo_root, "demo", demo_name, "build", version)
        os.makedirs(demo_build_dir, exist_ok=True)
        print(f"Demo build -> dir={demo_build_dir} | demo={demo_name} | sdk={sdk_dir_abs}", flush=True)
        _write_demo_launcher(
            os.path.join(demo_build_dir, output_name),
            entry_abs=entry_abs,
            env=env,
        )
        print(f"Build complete -> dir={demo_build_dir} | sdk=<none>", flush=True)

    return 0
