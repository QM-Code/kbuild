import json
import os
import subprocess
import tempfile

from . import errors


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, env=env)


def _load_json_object(path: str) -> dict[str, object]:
    if not os.path.isfile(path):
        errors.die(f"missing required JSON file: {path}")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        errors.die(f"could not parse {path}: {exc}")
    if not isinstance(payload, dict):
        errors.die(f"expected JSON object in {path}")
    return payload


def load_git_urls(repo_root: str) -> tuple[str, str]:
    config_path = os.path.join(repo_root, "kbuild.json")
    raw = _load_json_object(config_path)

    git_raw = raw.get("git")
    if not isinstance(git_raw, dict):
        errors.die("kbuild.json key 'git' must be an object")

    url_raw = git_raw.get("url")
    if not isinstance(url_raw, str) or not url_raw.strip():
        errors.die("kbuild.json key 'git.url' must be a non-empty string")
    auth_raw = git_raw.get("auth")
    if not isinstance(auth_raw, str) or not auth_raw.strip():
        errors.die("kbuild.json key 'git.auth' must be a non-empty string")
    return url_raw.strip(), auth_raw.strip()


def verify_remote_repo_access(repo_url: str, auth_url: str) -> None:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(
        ["git", "ls-remote", repo_url],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        errors.die(
            f"Could not reach\n  {repo_url}\n\n"
            "This is most likely due to one of the following reasons:\n"
            "  (1) There is a typo in the git repo specified in kbuild.json (git.url).\n"
            "  (2) You have not created the remote repo.\n"
            "  (3) You do not have network access.\n"
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


def initialize_git_repo(repo_root: str, repo_url: str, auth_url: str) -> int:
    verify_remote_repo_access(repo_url, auth_url)

    inside_worktree = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "--is-inside-work-tree"],
        check=False,
        capture_output=True,
        text=True,
    )
    if inside_worktree.returncode == 0 and inside_worktree.stdout.strip().lower() == "true":
        errors.die("current directory is already inside a git worktree.")

    git_dir = os.path.join(repo_root, ".git")
    if os.path.exists(git_dir):
        errors.die("'./.git' already exists.")

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
    worktree_check = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "--is-inside-work-tree"],
        check=False,
        capture_output=True,
        text=True,
    )
    if worktree_check.returncode != 0 or worktree_check.stdout.strip().lower() != "true":
        errors.die("git repository is not initialized. Run `./kbuild.py --git-initialize`.")

    add_result = subprocess.run(["git", "-C", repo_root, "add", "."], check=False)
    if add_result.returncode != 0:
        errors.die("git add failed.")

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
