import json
import os
import re
import subprocess

from . import errors


VCPKG_REPO_URL = "https://github.com/microsoft/vcpkg.git"


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _resolve_prefix(path_arg: str, repo_root: str) -> str:
    if os.path.isabs(path_arg):
        return os.path.abspath(path_arg)
    return os.path.abspath(os.path.join(repo_root, path_arg))


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


def _write_json_object(path: str, payload: dict[str, object]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def local_vcpkg_paths(repo_root: str) -> tuple[str, str, str, str, str]:
    local_vcpkg_root = os.path.join(repo_root, "vcpkg", "src")
    local_toolchain = os.path.join(local_vcpkg_root, "scripts", "buildsystems", "vcpkg.cmake")
    local_vcpkg_build_root = os.path.join(repo_root, "vcpkg", "build")
    local_vcpkg_downloads = os.path.join(local_vcpkg_build_root, "downloads")
    local_vcpkg_binary_cache = os.path.join(local_vcpkg_build_root, "binary-cache")
    return (
        os.path.abspath(local_vcpkg_root),
        os.path.abspath(local_toolchain),
        os.path.abspath(local_vcpkg_build_root),
        os.path.abspath(local_vcpkg_downloads),
        os.path.abspath(local_vcpkg_binary_cache),
    )


def is_local_vcpkg_bootstrapped(vcpkg_root: str) -> bool:
    candidates = [
        os.path.join(vcpkg_root, "vcpkg"),
        os.path.join(vcpkg_root, "vcpkg.exe"),
        os.path.join(vcpkg_root, "vcpkg.bat"),
    ]
    return any(os.path.isfile(path) for path in candidates)


def run_vcpkg_bootstrap(vcpkg_root: str) -> None:
    if os.name == "nt":
        bootstrap = os.path.join(vcpkg_root, "bootstrap-vcpkg.bat")
        if not os.path.isfile(bootstrap):
            errors.die(f"missing bootstrap script: {bootstrap}")
        _run(["cmd", "/c", bootstrap, "-disableMetrics"])
        return

    bootstrap = os.path.join(vcpkg_root, "bootstrap-vcpkg.sh")
    if not os.path.isfile(bootstrap):
        errors.die(f"missing bootstrap script: {bootstrap}")
    _run([bootstrap, "-disableMetrics"])


def install_local_vcpkg(repo_root: str) -> tuple[str, str, str, str]:
    (
        local_vcpkg_root,
        local_toolchain,
        local_vcpkg_build_root,
        local_vcpkg_downloads,
        local_vcpkg_binary_cache,
    ) = local_vcpkg_paths(repo_root)

    vcpkg_parent = os.path.dirname(local_vcpkg_root)
    if os.path.isfile(vcpkg_parent):
        errors.die(f"expected directory at {vcpkg_parent}, found file")
    os.makedirs(vcpkg_parent, exist_ok=True)

    if not os.path.isdir(local_vcpkg_root):
        print(f"Installing vcpkg checkout -> {local_vcpkg_root}", flush=True)
        _run(["git", "clone", VCPKG_REPO_URL, local_vcpkg_root])

    if not os.path.isfile(local_toolchain):
        errors.die(
            "vcpkg checkout is invalid; missing toolchain file.\n"
            f"Expected:\n  {local_toolchain}"
        )

    if not is_local_vcpkg_bootstrapped(local_vcpkg_root):
        print("Bootstrapping vcpkg...", flush=True)
        run_vcpkg_bootstrap(local_vcpkg_root)

    if os.path.isfile(local_vcpkg_build_root):
        errors.die(f"expected directory at {local_vcpkg_build_root}, found file")
    os.makedirs(local_vcpkg_downloads, exist_ok=True)
    os.makedirs(local_vcpkg_binary_cache, exist_ok=True)

    print(
        f"vcpkg ready -> src={local_vcpkg_root} | build={local_vcpkg_build_root}",
        flush=True,
    )
    return local_vcpkg_root, local_toolchain, local_vcpkg_downloads, local_vcpkg_binary_cache


def read_cache_value(cache_path: str, key: str) -> str:
    if not os.path.isfile(cache_path):
        return ""

    needle = f"{key}:"
    try:
        with open(cache_path, "r", encoding="utf-8") as cache:
            for line in cache:
                if line.startswith(needle):
                    return line.split("=", 1)[1].strip()
    except OSError:
        return ""

    return ""


def infer_triplet_from_installed_dir(installed_dir: str) -> str:
    try:
        entries = sorted(
            entry
            for entry in os.listdir(installed_dir)
            if os.path.isdir(os.path.join(installed_dir, entry)) and entry != "vcpkg"
        )
    except OSError:
        return ""

    if len(entries) == 1:
        return entries[0]
    return ""


def resolve_build_vcpkg_context(build_dir: str, repo_root: str) -> tuple[str, str]:
    build_dir_abs = _resolve_prefix(build_dir, repo_root)
    installed_dir = os.path.join(build_dir_abs, "installed")
    if os.path.isdir(installed_dir):
        cache_path = os.path.join(build_dir_abs, "CMakeCache.txt")
        triplet = read_cache_value(cache_path, "VCPKG_TARGET_TRIPLET")
        if triplet and os.path.isdir(os.path.join(installed_dir, triplet)):
            return os.path.abspath(installed_dir), triplet

        inferred = infer_triplet_from_installed_dir(installed_dir)
        if inferred:
            return os.path.abspath(installed_dir), inferred

    env_installed = os.environ.get("VCPKG_INSTALLED_DIR", "").strip()
    env_triplet = os.environ.get("VCPKG_TARGET_TRIPLET", "").strip()
    if env_installed and env_triplet:
        env_installed_abs = _resolve_prefix(env_installed, repo_root)
        if os.path.isdir(os.path.join(env_installed_abs, env_triplet)):
            return env_installed_abs, env_triplet

    errors.die(
        "could not resolve vcpkg installed tree/triplet for a vcpkg-enabled build.\n"
        f"Core build directory:\n  {build_dir_abs}\n"
        "Expected a core build layout like:\n"
        "  build/<slot>/installed/<triplet>\n"
        "You can also set VCPKG_INSTALLED_DIR and VCPKG_TARGET_TRIPLET explicitly."
    )


def read_git_head_commit(repo_path: str) -> str:
    result = subprocess.run(
        ["git", "-C", repo_path, "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git rev-parse failed"
        errors.die(
            "could not read vcpkg baseline commit from ./vcpkg/src.\n"
            f"Details:\n  {detail}"
        )

    commit = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        errors.die(
            "unexpected git commit format from ./vcpkg/src HEAD.\n"
            f"Value:\n  {commit}"
        )
    return commit.lower()


def sync_vcpkg_baseline(repo_root: str) -> str:
    local_vcpkg_root, _, _, _, _ = local_vcpkg_paths(repo_root)
    if not os.path.isdir(local_vcpkg_root):
        errors.die(
            "missing vcpkg checkout under ./vcpkg/src.\n"
            "Run:\n"
            "  kbuild --vcpkg-install"
        )

    baseline = read_git_head_commit(local_vcpkg_root)

    manifest_path = os.path.join(repo_root, "vcpkg", "vcpkg.json")

    manifest = _load_json_object(manifest_path)

    configuration = manifest.get("configuration")
    if not isinstance(configuration, dict):
        errors.die("vcpkg.json key 'configuration' must be an object")

    registry = configuration.get("default-registry")
    if not isinstance(registry, dict):
        errors.die("vcpkg.json key 'configuration.default-registry' must be an object")
    old_baseline = registry.get("baseline")
    registry["baseline"] = baseline

    _write_json_object(manifest_path, manifest)

    old_text = old_baseline.strip() if isinstance(old_baseline, str) and old_baseline.strip() else "<unset>"
    print(f"vcpkg baseline synced -> {baseline}", flush=True)
    print(
        "  ./vcpkg/vcpkg.json: "
        f"configuration.default-registry.baseline {old_text} -> {baseline}",
        flush=True,
    )
    return baseline


def ensure_local_vcpkg(repo_root: str) -> tuple[str, str, str, str]:
    (
        local_vcpkg_root,
        local_toolchain,
        local_vcpkg_build_root,
        local_vcpkg_downloads,
        local_vcpkg_binary_cache,
    ) = local_vcpkg_paths(repo_root)

    ready = (
        os.path.isdir(local_vcpkg_root)
        and os.path.isdir(local_vcpkg_build_root)
        and os.path.isfile(local_toolchain)
        and is_local_vcpkg_bootstrapped(local_vcpkg_root)
    )
    if not ready:
        errors.die("vcpkg has not been set up. Run `kbuild --vcpkg-install`")

    os.makedirs(local_vcpkg_downloads, exist_ok=True)
    os.makedirs(local_vcpkg_binary_cache, exist_ok=True)
    return local_vcpkg_root, local_toolchain, local_vcpkg_downloads, local_vcpkg_binary_cache
