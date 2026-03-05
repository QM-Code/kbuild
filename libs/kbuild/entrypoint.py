import os
from . import engine


def run(
    *,
    repo_root: str,
    argv: list[str],
    kbuild_root: str,
    program_name: str = "kbuild.py",
    bootstrap_root_override: str | None = None,
) -> int:
    templates_root = os.path.join(kbuild_root, "templates")
    return engine.main(
        repo_root=repo_root,
        args=list(argv),
        templates_root=templates_root,
        program_name=program_name,
        bootstrap_root_override=bootstrap_root_override,
    )
