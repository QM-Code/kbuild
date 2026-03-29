import os


def is_enabled(repo_root: str) -> bool:
    for root_name in ("src", "tests", "demo"):
        source_root = os.path.join(repo_root, root_name)
        if not os.path.isdir(source_root):
            continue
        for current_root, dirnames, filenames in os.walk(source_root):
            dirnames[:] = sorted(
                dirname
                for dirname in dirnames
                if dirname not in (".git", "build", "__pycache__")
            )
            for filename in filenames:
                if filename.endswith(".py"):
                    return True
    return False


def find_unexpected_residuals(repo_root: str) -> tuple[str, list[str]] | None:
    findings: list[str] = []
    for current_root, dirnames, filenames in os.walk(repo_root):
        current_root_name = os.path.basename(current_root)
        if current_root_name == "build":
            dirnames[:] = []
            continue

        kept_dirnames: list[str] = []
        for dirname in sorted(dirnames):
            if dirname == ".git":
                continue
            if dirname == "build":
                continue
            if dirname == "__pycache__":
                findings.append(os.path.join(current_root, dirname))
                continue
            kept_dirnames.append(dirname)
        dirnames[:] = kept_dirnames

        for filename in sorted(filenames):
            if filename.endswith(".pyc") or filename.endswith(".pyo"):
                findings.append(os.path.join(current_root, filename))

    if not findings:
        return None
    return ("Python cache artifacts", findings)
