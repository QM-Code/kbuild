import json
import os
import shutil
import subprocess

from . import build_ops
from . import config_ops
from . import errors


def is_enabled(repo_root: str) -> bool:
    raw = config_ops.load_effective_kbuild_payload(repo_root, require_local=True)
    return raw.get("swift") is not None


def find_unexpected_residuals(repo_root: str) -> tuple[str, list[str]] | None:
    findings: list[str] = []
    for current_root, dirnames, _ in os.walk(repo_root):
        next_dirnames: list[str] = []
        for dirname in sorted(dirnames):
            if dirname in (".git", "build"):
                continue
            if dirname == ".build":
                findings.append(os.path.join(current_root, dirname))
                continue
            next_dirnames.append(dirname)
        dirnames[:] = next_dirnames

    if not findings:
        return None
    return ("SwiftPM build directories", findings)


def _load_swift_config(repo_root: str) -> tuple[str, str, dict[str, tuple[str, str]]]:
    raw = config_ops.load_effective_kbuild_payload(repo_root, require_local=True)
    swift_raw = raw.get("swift")
    if not isinstance(swift_raw, dict):
        errors.die("kbuild config key 'swift' must be an object")

    allowed_swift = {"package_path", "demo_package_path", "demo_products"}
    for key in swift_raw:
        if key not in allowed_swift:
            errors.die(f"unexpected key in kbuild config 'swift': '{key}'")

    package_path_raw = swift_raw.get("package_path")
    if not isinstance(package_path_raw, str) or not package_path_raw.strip():
        errors.die("kbuild config key 'swift.package_path' must be a non-empty string")
    package_path = package_path_raw.strip().replace("\\", "/")

    demo_package_path_raw = swift_raw.get("demo_package_path", package_path)
    if not isinstance(demo_package_path_raw, str) or not demo_package_path_raw.strip():
        errors.die("kbuild config key 'swift.demo_package_path' must be a non-empty string")
    demo_package_path = demo_package_path_raw.strip().replace("\\", "/")

    demo_products: dict[str, tuple[str, str]] = {}
    demo_products_raw = swift_raw.get("demo_products", {})
    if not isinstance(demo_products_raw, dict):
        errors.die("kbuild config key 'swift.demo_products' must be an object when defined")

    for demo_name_raw, demo_config_raw in demo_products_raw.items():
        if not isinstance(demo_name_raw, str) or not demo_name_raw.strip():
            errors.die("kbuild config key 'swift.demo_products' has an invalid demo name")
        demo_name = build_ops.normalize_demo_name(demo_name_raw.strip())
        if not isinstance(demo_config_raw, dict):
            errors.die(f"kbuild config key 'swift.demo_products.{demo_name}' must be an object")

        allowed_demo = {"product", "kind"}
        for key in demo_config_raw:
            if key not in allowed_demo:
                errors.die(f"unexpected key in kbuild config 'swift.demo_products.{demo_name}': '{key}'")

        product_raw = demo_config_raw.get("product")
        if not isinstance(product_raw, str) or not product_raw.strip():
            errors.die(
                f"kbuild config key 'swift.demo_products.{demo_name}.product' must be a non-empty string"
            )
        kind_raw = demo_config_raw.get("kind")
        if not isinstance(kind_raw, str) or not kind_raw.strip():
            errors.die(
                f"kbuild config key 'swift.demo_products.{demo_name}.kind' must be a non-empty string"
            )
        kind = kind_raw.strip().lower()
        if kind not in {"library", "executable"}:
            errors.die(
                f"kbuild config key 'swift.demo_products.{demo_name}.kind' must be 'library' or 'executable'"
            )
        demo_products[demo_name] = (product_raw.strip(), kind)

    return package_path, demo_package_path, demo_products


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    try:
        subprocess.run(cmd, check=True, env=env)
    except FileNotFoundError:
        errors.die(
            "swift executable was not found on PATH.\n"
            "Install a Swift toolchain before running Swift workspace builds."
        )
    except subprocess.CalledProcessError as exc:
        errors.die(
            "swift command failed.\n"
            f"Command:\n  {' '.join(cmd)}\n"
            f"Exit code:\n  {exc.returncode}",
            code=exc.returncode or 1,
        )


def _prepare_dir(path: str) -> None:
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)


def _write_text(path: str, content: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def _write_launcher(
    path: str,
    package_dir: str,
    build_dir: str,
    product: str,
    local_dirs: dict[str, str],
) -> None:
    payload = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'if [ -f "${SWIFTLY_HOME_DIR:-$HOME/.local/share/swiftly}/env.sh" ]; then\n'
        '  . "${SWIFTLY_HOME_DIR:-$HOME/.local/share/swiftly}/env.sh"\n'
        "  hash -r\n"
        "fi\n"
        f'export XDG_CACHE_HOME="{local_dirs["xdg_cache"]}"\n'
        f'export CLANG_MODULE_CACHE_PATH="{local_dirs["clang_module_cache"]}"\n'
        f'export SWIFT_OVERLOAD_PREBUILT_MODULE_CACHE_PATH="{local_dirs["prebuilt_module_cache"]}"\n'
        f'exec swift run --package-path "{package_dir}" --build-path "{build_dir}" '
        f'--cache-path "{local_dirs["cache"]}" --config-path "{local_dirs["config"]}" '
        f'--security-path "{local_dirs["security"]}" --manifest-cache local -c release "{product}" "$@"\n'
    )
    _write_text(path, payload)
    os.chmod(path, 0o755)


def _write_test_launcher(
    path: str,
    package_dir: str,
    build_dir: str,
    local_dirs: dict[str, str],
) -> None:
    payload = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'if [ -f "${SWIFTLY_HOME_DIR:-$HOME/.local/share/swiftly}/env.sh" ]; then\n'
        '  . "${SWIFTLY_HOME_DIR:-$HOME/.local/share/swiftly}/env.sh"\n'
        "  hash -r\n"
        "fi\n"
        f'export XDG_CACHE_HOME="{local_dirs["xdg_cache"]}"\n'
        f'export CLANG_MODULE_CACHE_PATH="{local_dirs["clang_module_cache"]}"\n'
        f'export SWIFT_OVERLOAD_PREBUILT_MODULE_CACHE_PATH="{local_dirs["prebuilt_module_cache"]}"\n'
        f'exec swift test --package-path "{package_dir}" --build-path "{build_dir}" '
        f'--cache-path "{local_dirs["cache"]}" --config-path "{local_dirs["config"]}" '
        f'--security-path "{local_dirs["security"]}" --manifest-cache local -c release "$@"\n'
    )
    _write_text(path, payload)
    os.chmod(path, 0o755)


def _swift_local_dirs(build_root: str) -> dict[str, str]:
    root = os.path.join(build_root, "_swift")
    paths = {
        "root": root,
        "cache": os.path.join(root, "cache"),
        "config": os.path.join(root, "config"),
        "security": os.path.join(root, "security"),
        "xdg_cache": os.path.join(root, "xdg-cache"),
        "clang_module_cache": os.path.join(root, "clang-module-cache"),
        "prebuilt_module_cache": os.path.join(root, "prebuilt-module-cache"),
    }
    for path in paths.values():
        os.makedirs(path, exist_ok=True)
    return paths


def _swift_shared_options(local_dirs: dict[str, str]) -> list[str]:
    return [
        "--cache-path",
        local_dirs["cache"],
        "--config-path",
        local_dirs["config"],
        "--security-path",
        local_dirs["security"],
        "--manifest-cache",
        "local",
    ]


def _swift_env(local_dirs: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env["XDG_CACHE_HOME"] = local_dirs["xdg_cache"]
    env["CLANG_MODULE_CACHE_PATH"] = local_dirs["clang_module_cache"]
    env["SWIFT_OVERLOAD_PREBUILT_MODULE_CACHE_PATH"] = local_dirs["prebuilt_module_cache"]
    return env


def _snapshot_package_sdk(
    package_dir: str,
    sdk_dir: str,
    *,
    product: str | None,
    package_snapshot_name: str,
) -> None:
    _prepare_dir(sdk_dir)
    source_snapshot = os.path.join(sdk_dir, package_snapshot_name)
    shutil.copytree(
        package_dir,
        source_snapshot,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".build", "build"),
    )
    metadata = {
        "package_path": package_snapshot_name,
        "product": product or "",
        "kind": "swiftpm-source-snapshot",
    }
    _write_text(os.path.join(sdk_dir, "swift-sdk.json"), json.dumps(metadata, indent=2) + "\n")


def build_repo(
    *,
    repo_root: str,
    version: str,
    build_demos: bool,
    requested_demos: list[str],
    config_build_demos: list[str],
    config_default_build_demos: list[str],
) -> int:
    package_path, demo_package_path, demo_products = _load_swift_config(repo_root)
    package_dir = os.path.join(repo_root, package_path)
    package_snapshot_name = os.path.basename(package_dir.rstrip("/\\"))
    if not package_snapshot_name:
        errors.die(f"Swift package path must resolve to a named directory: {package_path}")
    package_manifest = os.path.join(package_dir, "Package.swift")
    if not os.path.isfile(package_manifest):
        errors.die(f"Swift package manifest not found: {package_manifest}")

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

    build_root = os.path.join(repo_root, "build", version)
    swift_build_dir = os.path.join(build_root, "swiftpm")
    sdk_dir = os.path.join(build_root, "sdk")
    tests_dir = os.path.join(build_root, "tests")
    local_dirs = _swift_local_dirs(build_root)
    shared_options = _swift_shared_options(local_dirs)
    env = _swift_env(local_dirs)
    demo_package_dir = os.path.join(repo_root, demo_package_path)
    demo_package_snapshot_name = os.path.basename(demo_package_dir.rstrip("/\\"))

    os.makedirs(build_root, exist_ok=True)
    _run(
        [
            "swift",
            "build",
            "--package-path",
            package_dir,
            "--build-path",
            swift_build_dir,
            *shared_options,
            "-c",
            "release",
        ],
        env=env,
    )
    _snapshot_package_sdk(
        package_dir,
        sdk_dir,
        product=None,
        package_snapshot_name=package_snapshot_name,
    )

    tests_root = os.path.join(package_dir, "Tests")
    if os.path.isdir(tests_root):
        os.makedirs(tests_dir, exist_ok=True)
        _write_test_launcher(os.path.join(tests_dir, "run-tests"), package_dir, swift_build_dir, local_dirs)

    print(f"Build complete -> dir=build/{version} | sdk={sdk_dir}")

    demo_swift_build_dir = swift_build_dir
    if demo_order:
        if not demo_package_snapshot_name:
            errors.die(f"Swift demo package path must resolve to a named directory: {demo_package_path}")
        demo_package_manifest = os.path.join(demo_package_dir, "Package.swift")
        if not os.path.isfile(demo_package_manifest):
            errors.die(f"Swift demo package manifest not found: {demo_package_manifest}")

        if os.path.normpath(demo_package_dir) != os.path.normpath(package_dir):
            demo_swift_build_dir = os.path.join(build_root, "swiftpm-demo")
            _run(
                [
                    "swift",
                    "build",
                    "--package-path",
                    demo_package_dir,
                    "--build-path",
                    demo_swift_build_dir,
                    *shared_options,
                    "-c",
                    "release",
                ],
                env=env,
            )

    for demo_name in demo_order:
        if demo_name not in demo_products:
            errors.die(
                f"swift demo '{demo_name}' is not mapped in config key 'swift.demo_products'"
            )
        product, kind = demo_products[demo_name]
        demo_build_dir = os.path.join(repo_root, "demo", demo_name, "build", version)
        print(f"Demo build -> dir={demo_build_dir} | demo={demo_name} | sdk={sdk_dir}", flush=True)

        if kind == "library":
            _snapshot_package_sdk(
                demo_package_dir,
                os.path.join(demo_build_dir, "sdk"),
                product=product,
                package_snapshot_name=demo_package_snapshot_name,
            )
            print(f"Build complete -> dir={demo_build_dir} | sdk={os.path.join(demo_build_dir, 'sdk')}")
            continue

        os.makedirs(demo_build_dir, exist_ok=True)
        launcher_name = "bootstrap" if demo_name == "bootstrap" else "test"
        _write_launcher(
            os.path.join(demo_build_dir, launcher_name),
            demo_package_dir,
            demo_swift_build_dir,
            product,
            local_dirs,
        )
        print(f"Build complete -> dir={demo_build_dir} | sdk=<none>")

    return 0
