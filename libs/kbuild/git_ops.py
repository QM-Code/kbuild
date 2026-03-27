import os
import subprocess
import tempfile

from . import config_ops
from . import errors


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, env=env)


def _canonical_path(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _git_worktree_root(repo_root: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    top_level = result.stdout.strip()
    if not top_level:
        return None
    return top_level


def _require_current_root_git_worktree(repo_root: str, *, operation: str) -> str:
    git_dir = os.path.join(repo_root, ".git")
    if not os.path.exists(git_dir):
        errors.die(
            f"refusing to {operation} without local git metadata.\n"
            "required:\n"
            "  ./.git\n\n"
            "Run `kbuild --git-initialize` first."
        )

    top_level = _git_worktree_root(repo_root)
    if top_level is None:
        errors.die("git repository is not initialized. Run `kbuild --git-initialize`.")

    if _canonical_path(top_level) != _canonical_path(repo_root):
        errors.die(
            f"refusing to {operation} outside the current root.\n"
            f"current root:\n  {repo_root}\n"
            f"git worktree root:\n  {top_level}\n\n"
            "Run this command from the actual git repo root, or initialize a repo rooted here first."
        )
    return top_level


def load_git_urls(repo_root: str) -> tuple[str, str]:
    raw = config_ops.load_effective_kbuild_payload(repo_root, require_local=True)

    git_raw = raw.get("git")
    if not isinstance(git_raw, dict):
        errors.die("kbuild config key 'git' must be an object")

    url_raw = git_raw.get("url")
    if not isinstance(url_raw, str) or not url_raw.strip():
        errors.die("kbuild config key 'git.url' must be a non-empty string")
    auth_raw = git_raw.get("auth")
    if not isinstance(auth_raw, str) or not auth_raw.strip():
        errors.die("kbuild config key 'git.auth' must be a non-empty string")
    return url_raw.strip(), auth_raw.strip()


def verify_remote_repo_access(auth_url: str) -> None:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    if auth_url.startswith("git@") or auth_url.startswith("ssh://"):
        env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
    result = subprocess.run(
        ["git", "ls-remote", auth_url],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git ls-remote failed"
        errors.die(
            f"Could not access configured git remote\n  {auth_url}\n\n"
            "This is most likely due to one of the following reasons:\n"
            "  (1) There is a typo in the git repo specified in the kbuild config (git.auth).\n"
            "  (2) The remote repo does not exist.\n"
            "  (3) Your git credentials for this remote are missing, expired, or invalid.\n"
            "  (4) You do not have network access.\n\n"
            f"Detail:\n  {detail}"
        )

    with tempfile.TemporaryDirectory(prefix="kbuild-auth-probe-") as probe_root:
        init_result = subprocess.run(
            ["git", "init", probe_root],
            check=False,
            capture_output=True,
            text=True,
        )
        if init_result.returncode != 0:
            detail = init_result.stderr.strip() or init_result.stdout.strip() or "git init failed"
            errors.die(
                "failed to run git authentication preflight.\n"
                f"Detail:\n  {detail}"
            )

        config_name_result = subprocess.run(
            ["git", "-C", probe_root, "config", "user.name", "kbuild-auth-probe"],
            check=False,
            capture_output=True,
            text=True,
        )
        if config_name_result.returncode != 0:
            detail = (
                config_name_result.stderr.strip()
                or config_name_result.stdout.strip()
                or "git config user.name failed"
            )
            errors.die(
                "failed to run git authentication preflight.\n"
                f"Detail:\n  {detail}"
            )

        config_email_result = subprocess.run(
            ["git", "-C", probe_root, "config", "user.email", "kbuild-auth-probe@example.invalid"],
            check=False,
            capture_output=True,
            text=True,
        )
        if config_email_result.returncode != 0:
            detail = (
                config_email_result.stderr.strip()
                or config_email_result.stdout.strip()
                or "git config user.email failed"
            )
            errors.die(
                "failed to run git authentication preflight.\n"
                f"Detail:\n  {detail}"
            )

        probe_file = os.path.join(probe_root, ".kbuild-auth-probe")
        try:
            with open(probe_file, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("probe\n")
        except OSError as exc:
            errors.die(
                "failed to run git authentication preflight.\n"
                f"Detail:\n  {exc}"
            )

        add_result = subprocess.run(
            ["git", "-C", probe_root, "add", ".kbuild-auth-probe"],
            check=False,
            capture_output=True,
            text=True,
        )
        if add_result.returncode != 0:
            detail = add_result.stderr.strip() or add_result.stdout.strip() or "git add failed"
            errors.die(
                "failed to run git authentication preflight.\n"
                f"Detail:\n  {detail}"
            )

        commit_result = subprocess.run(
            ["git", "-C", probe_root, "commit", "-m", "kbuild auth probe"],
            check=False,
            capture_output=True,
            text=True,
        )
        if commit_result.returncode != 0:
            detail = commit_result.stderr.strip() or commit_result.stdout.strip() or "git commit failed"
            errors.die(
                "failed to run git authentication preflight.\n"
                f"Detail:\n  {detail}"
            )

        push_result = subprocess.run(
            [
                "git",
                "-C",
                probe_root,
                "push",
                "--dry-run",
                auth_url,
                "HEAD:refs/heads/kbuild-auth-probe",
            ],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        if push_result.returncode != 0:
            errors.die(
                f"Authentication failed for\n  {auth_url}\n\n"
                "This is most likely due to one of the following reasons:\n"
                "  (1) Your git credentials for this host are missing, expired, or invalid.\n"
                "  (2) You do not have push permission for this repository.\n"
                "  (3) Your credential helper is not configured for non-interactive use.\n"
            )


def initialize_git_repo(repo_root: str, auth_url: str) -> int:
    git_dir = os.path.join(repo_root, ".git")
    if os.path.exists(git_dir):
        errors.die("'./.git' already exists.")

    top_level = _git_worktree_root(repo_root)
    if top_level is not None and _canonical_path(top_level) == _canonical_path(repo_root):
        errors.die("current directory already has a git worktree rooted here.")

    verify_remote_repo_access(auth_url)

    _run(["git", "init", repo_root])
    _run(["git", "-C", repo_root, "branch", "-M", "main"])

    remote_check = subprocess.run(
        ["git", "-C", repo_root, "remote", "get-url", "origin"],
        check=False,
        capture_output=True,
        text=True,
    )
    if remote_check.returncode == 0:
        _run(["git", "-C", repo_root, "remote", "set-url", "origin", auth_url])
        remote_action = "updated"
    else:
        _run(["git", "-C", repo_root, "remote", "add", "origin", auth_url])
        remote_action = "added"

    _run(["git", "-C", repo_root, "add", "-A"])

    commit_result = subprocess.run(
        ["git", "-C", repo_root, "commit", "-m", "Initial scaffold"],
        check=False,
        capture_output=True,
        text=True,
    )
    if commit_result.returncode != 0:
        detail = commit_result.stderr.strip() or commit_result.stdout.strip() or "git commit failed"
        errors.die(
            "failed to create initial commit.\n"
            "Configure git identity (user.name/user.email) and retry.\n"
            f"Detail:\n  {detail}"
        )

    push_env = os.environ.copy()
    push_env["GIT_TERMINAL_PROMPT"] = "0"
    push_result = subprocess.run(
        ["git", "-C", repo_root, "push", "-u", "origin", "main"],
        check=False,
        capture_output=True,
        text=True,
        env=push_env,
    )
    if push_result.returncode != 0:
        detail = push_result.stderr.strip() or push_result.stdout.strip() or "git push failed"
        errors.die(
            "failed to push initial commit to remote.\n"
            "Ensure the remote exists and git authentication is configured.\n"
            f"Detail:\n  {detail}"
        )

    print("Initialized git repository:", flush=True)
    print("  branch: main", flush=True)
    print(f"  remote origin ({remote_action}): {auth_url}", flush=True)
    print("  initial commit: created", flush=True)
    print("  push: origin/main", flush=True)
    return 0


def git_sync(repo_root: str, commit_message: str) -> int:
    _require_current_root_git_worktree(repo_root, operation="sync git changes")

    add_result = subprocess.run(["git", "-C", repo_root, "add", "-A"], check=False)
    if add_result.returncode != 0:
        errors.die("git add failed.")

    staged_result = subprocess.run(
        ["git", "-C", repo_root, "diff", "--cached", "--quiet"],
        check=False,
    )
    if staged_result.returncode == 0:
        print("No changes to commit.", flush=True)
        return 0
    if staged_result.returncode != 1:
        errors.die("git diff --cached --quiet failed.")

    commit_result = subprocess.run(
        ["git", "-C", repo_root, "commit", "-m", commit_message],
        check=False,
    )
    if commit_result.returncode != 0:
        errors.die("git commit failed.")

    push_result = subprocess.run(["git", "-C", repo_root, "push"], check=False)
    if push_result.returncode != 0:
        errors.die("git push failed.")

    print("Git sync complete.", flush=True)
    return 0
