import json
import os
import shutil
import subprocess

from . import build_ops
from . import errors
from .config_ops import KbuildConfig
from .config_ops import CargoDemoTarget


def _run(cmd: list[str], *, cwd: str, env: dict[str, str]) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, env=env)


def _resolve_manifest(repo_root: str, manifest_path: str) -> tuple[str, str]:
    manifest_abs = build_ops.resolve_prefix(manifest_path, repo_root)
    if not os.path.isfile(manifest_abs):
        errors.die(
            "cargo manifest was not found.\n"
            f"Expected:\n  {manifest_abs}"
        )
    manifest_dir = os.path.dirname(manifest_abs)
    return manifest_abs, manifest_dir


def _copy_sdk_snapshot(
    manifest_dir: str,
    install_prefix: str,
    sdk_include: list[str],
    *,
    project_id: str,
    manifest_path: str,
) -> None:
    shutil.rmtree(install_prefix, ignore_errors=True)
    os.makedirs(install_prefix, exist_ok=True)

    metadata = {
        "project_id": project_id,
        "manifest": manifest_path,
        "sdk_include": list(sdk_include),
    }
    metadata_path = os.path.join(install_prefix, "share", "kbuild-cargo-sdk.json")
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(metadata, handle, indent=2)
        handle.write("\n")

    for relative_path in sdk_include:
        source_path = os.path.join(manifest_dir, relative_path)
        if not os.path.exists(source_path):
            continue

        destination_path = os.path.join(install_prefix, relative_path)
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        if os.path.isdir(source_path):
            if os.path.exists(destination_path):
                shutil.rmtree(destination_path)
            shutil.copytree(source_path, destination_path)
        else:
            shutil.copy2(source_path, destination_path)


def _build_demo_target(
    *,
    repo_root: str,
    manifest_abs: str,
    manifest_dir: str,
    env: dict[str, str],
    build_jobs: int,
    version: str,
    demo_target: CargoDemoTarget,
    package_name: str,
) -> None:
    cmd = [
        "cargo",
        "build",
        "--manifest-path",
        manifest_abs,
        f"-j{build_jobs}",
    ]
    if package_name:
        cmd.extend(["--package", package_name])
    cmd.extend([f"--{demo_target.kind}", demo_target.target_name])
    _run(cmd, cwd=manifest_dir, env=env)

    target_dir = env["CARGO_TARGET_DIR"]
    binary_root = os.path.join(target_dir, "debug")
    if demo_target.kind == "example":
        binary_root = os.path.join(binary_root, "examples")

    executable_name = demo_target.target_name
    if os.name == "nt":
        executable_name += ".exe"
    source_binary = os.path.join(binary_root, executable_name)
    if not os.path.isfile(source_binary):
        errors.die(
            "cargo demo target was built but the executable was not found.\n"
            f"Expected:\n  {source_binary}"
        )

    demo_build_dir = os.path.join(repo_root, "demo", demo_target.demo_name, "build", version)
    os.makedirs(demo_build_dir, exist_ok=True)
    destination_binary = os.path.join(demo_build_dir, executable_name)
    shutil.copy2(source_binary, destination_binary)
    print(
        f"Demo complete -> demo={demo_target.demo_name} | dir={build_ops.format_dir_for_output(demo_build_dir, repo_root)}",
        flush=True,
    )


def build_cargo_repo(
    *,
    repo_root: str,
    project_id: str,
    version: str,
    manifest_path: str,
    package_name: str,
    build_tests: bool,
    build_jobs: int,
    demo_order: list[str],
    demo_targets: dict[str, CargoDemoTarget],
    sdk_include: list[str],
) -> int:
    manifest_abs, manifest_dir = _resolve_manifest(repo_root, manifest_path)
    target_dir = os.path.abspath(os.path.join(repo_root, "build", version))
    os.makedirs(target_dir, exist_ok=True)

    env = os.environ.copy()
    env["CARGO_TARGET_DIR"] = target_dir
    if not env.get("CARGO_HOME", "").strip():
        cargo_home = os.path.join(repo_root, ".cargo-home")
        os.makedirs(cargo_home, exist_ok=True)
        env["CARGO_HOME"] = cargo_home

    build_cmd = [
        "cargo",
        "build",
        "--manifest-path",
        manifest_abs,
        f"-j{build_jobs}",
    ]
    if package_name:
        build_cmd.extend(["--package", package_name])
    _run(build_cmd, cwd=manifest_dir, env=env)

    if build_tests:
        test_cmd = [
            "cargo",
            "test",
            "--manifest-path",
            manifest_abs,
            "--no-run",
            f"-j{build_jobs}",
        ]
        if package_name:
            test_cmd.extend(["--package", package_name])
        _run(test_cmd, cwd=manifest_dir, env=env)

    install_prefix = os.path.abspath(os.path.join(target_dir, "sdk"))
    _copy_sdk_snapshot(
        manifest_dir,
        install_prefix,
        sdk_include,
        project_id=project_id,
        manifest_path=manifest_path,
    )
    print(f"Build complete -> dir=build/{version} | sdk={install_prefix}", flush=True)

    for demo_name in demo_order:
        demo_target = demo_targets.get(demo_name)
        if demo_target is None:
            errors.die(
                "cargo demo is not defined in config.\n"
                f"Demo:\n  {demo_name}\n"
                "Add it under 'cargo.demos' first."
            )
        _build_demo_target(
            repo_root=repo_root,
            manifest_abs=manifest_abs,
            manifest_dir=manifest_dir,
            env=env,
            build_jobs=build_jobs,
            version=version,
            demo_target=demo_target,
            package_name=package_name,
        )

    return 0


def build_repo(
    *,
    repo_root: str,
    config: KbuildConfig,
    version: str,
    build_demos: bool,
    requested_demos: list[str],
) -> int:
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

    return build_cargo_repo(
        repo_root=repo_root,
        project_id=config.project_id,
        version=version,
        manifest_path=config.cargo_manifest,
        package_name=config.cargo_package,
        build_tests=config.cargo_build_tests,
        build_jobs=config.build_jobs,
        demo_order=demo_order,
        demo_targets=config.cargo_demo_targets,
        sdk_include=config.cargo_sdk_include,
    )
