import os
import subprocess
import sys

from . import config_ops
from . import errors


def _canonical_path(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _load_batch_repo_tokens(repo_root: str, inline_repo_tokens: list[str]) -> list[str]:
    if inline_repo_tokens:
        return inline_repo_tokens

    config_repo_tokens = config_ops.load_batch_repos(repo_root)
    if config_repo_tokens:
        return config_repo_tokens

    errors.die(
        "no batch repos were specified.\n"
        "Provide repo paths after '--batch' or define 'batch.repos' in the kbuild config.",
        code=1,
    )


def _resolve_batch_targets(repo_root: str, repo_tokens: list[str]) -> list[tuple[str, str]]:
    repo_root_canonical = _canonical_path(repo_root)
    resolved_targets: list[tuple[str, str]] = []

    for repo_token in repo_tokens:
        repo_abs = os.path.abspath(os.path.join(repo_root, repo_token))
        repo_canonical = _canonical_path(repo_abs)
        if repo_canonical != repo_root_canonical and not repo_canonical.startswith(repo_root_canonical + os.sep):
            errors.die(
                f"batch repo path resolves outside the current repo root:\n"
                f"  token: {repo_token}\n"
                f"  resolved: {repo_abs}",
                code=1,
            )
        if not os.path.isdir(repo_abs):
            errors.die(
                f"batch repo path does not exist or is not a directory:\n"
                f"  token: {repo_token}\n"
                f"  resolved: {repo_abs}",
                code=1,
            )

        local_config_path = os.path.join(repo_abs, config_ops.LOCAL_KBUILD_CONFIG_FILENAME)
        if not os.path.isfile(local_config_path):
            errors.die(
                f"batch repo is missing './{config_ops.LOCAL_KBUILD_CONFIG_FILENAME}':\n"
                f"  token: {repo_token}\n"
                f"  resolved: {repo_abs}",
                code=1,
            )
        resolved_targets.append((repo_token, repo_abs))

    return resolved_targets


def run_batch(
    repo_root: str,
    forwarded_args: list[str],
    inline_repo_tokens: list[str],
    *,
    entrypoint_path: str,
) -> int:
    repo_tokens = _load_batch_repo_tokens(repo_root, inline_repo_tokens)
    targets = _resolve_batch_targets(repo_root, repo_tokens)

    for index, (repo_token, repo_abs) in enumerate(targets, start=1):
        print(f"[batch {index}/{len(targets)}] {repo_token}", flush=True)
        result = subprocess.run(
            [sys.executable, entrypoint_path, *forwarded_args],
            cwd=repo_abs,
            check=False,
        )
        if result.returncode != 0:
            errors.emit_error(
                f"batch command failed in '{repo_token}' with exit code {result.returncode}"
            )
            return result.returncode

    print("Batch complete.", flush=True)
    return 0
