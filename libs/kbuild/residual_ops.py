import os

from . import backend_ops
from . import errors
from .config_ops import KbuildConfig


def _format_repo_path(path: str, repo_root: str) -> str:
    relative = os.path.relpath(path, repo_root).replace("\\", "/")
    return f"./{relative}"


def ensure_repo_hygiene(
    *,
    repo_root: str,
    config: KbuildConfig,
    operation: str,
) -> None:
    finding = backend_ops.find_unexpected_residuals(repo_root=repo_root, config=config)
    if finding is None:
        return

    artifact_label, paths = finding
    formatted_paths = "\n".join(
        f"  {_format_repo_path(path, repo_root)}"
        for path in paths
    )
    errors.die(
        f"refusing to {operation}: found {artifact_label} outside build/.\n"
        "kbuild requires generated artifacts to stay under build/ directories.\n"
        "Remove or relocate the following paths before retrying:\n"
        f"{formatted_paths}"
    )
