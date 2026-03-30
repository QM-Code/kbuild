import os
import subprocess
import sys

from . import config_ops
from . import errors


def _canonical_path(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _load_batch_target_tokens(project_root: str, inline_target_tokens: list[str]) -> list[str]:
    if inline_target_tokens:
        return inline_target_tokens

    config_target_tokens = config_ops.load_batch_targets(project_root)
    if config_target_tokens:
        return config_target_tokens

    errors.die(
        "no batch targets were specified.\n"
        "Provide target paths after '--batch' or define 'batch.targets' in the kbuild config.",
        code=1,
    )


def _resolve_batch_targets(project_root: str, target_tokens: list[str]) -> list[tuple[str, str]]:
    project_root_canonical = _canonical_path(project_root)
    resolved_targets: list[tuple[str, str]] = []

    for target_token in target_tokens:
        target_abs = os.path.abspath(os.path.join(project_root, target_token))
        target_canonical = _canonical_path(target_abs)
        if target_canonical != project_root_canonical and not target_canonical.startswith(project_root_canonical + os.sep):
            errors.die(
                f"batch target path resolves outside the current project root:\n"
                f"  token: {target_token}\n"
                f"  resolved: {target_abs}",
                code=1,
            )
        if not os.path.isdir(target_abs):
            errors.die(
                f"batch target path does not exist or is not a directory:\n"
                f"  token: {target_token}\n"
                f"  resolved: {target_abs}",
                code=1,
            )

        local_config_path = os.path.join(target_abs, config_ops.LOCAL_KBUILD_CONFIG_FILENAME)
        if not os.path.isfile(local_config_path):
            errors.die(
                f"batch target is missing './{config_ops.LOCAL_KBUILD_CONFIG_FILENAME}':\n"
                f"  token: {target_token}\n"
                f"  resolved: {target_abs}",
                code=1,
            )
        resolved_targets.append((target_token, target_abs))

    return resolved_targets


def run_batch(
    project_root: str,
    forwarded_args: list[str],
    inline_target_tokens: list[str],
    *,
    entrypoint_path: str,
) -> int:
    target_tokens = _load_batch_target_tokens(project_root, inline_target_tokens)
    targets = _resolve_batch_targets(project_root, target_tokens)

    for index, (target_token, target_abs) in enumerate(targets, start=1):
        print(f"[batch {index}/{len(targets)}] {target_token}", flush=True)
        result = subprocess.run(
            [sys.executable, entrypoint_path, *forwarded_args],
            cwd=target_abs,
            check=False,
        )
        if result.returncode != 0:
            errors.emit_error(
                f"batch command failed in '{target_token}' with exit code {result.returncode}"
            )
            return result.returncode

    print("Batch complete.", flush=True)
    return 0
