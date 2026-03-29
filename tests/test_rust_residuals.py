import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest


THIS_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))
LIBS_DIR = os.path.join(REPO_ROOT, "libs")
if LIBS_DIR not in sys.path:
    sys.path.insert(0, LIBS_DIR)

from kbuild import config_ops  # noqa: E402
from kbuild import residual_ops  # noqa: E402
from kbuild.entrypoint import run as run_kbuild  # noqa: E402


def _write_text(path: str, contents: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(contents)


def _write_json(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _make_rust_repo(repo_root: str) -> None:
    _write_json(
        os.path.join(repo_root, ".kbuild.json"),
        {
            "project": {
                "title": "Test Rust Repo",
                "id": "test_rust_repo",
            },
            "git": {
                "url": "https://example.invalid/test-rust-repo",
                "auth": "git@example.invalid:test-rust-repo.git",
            },
            "cargo": {
                "manifest": "Cargo.toml",
                "package": "test_rust_repo",
            },
        },
    )
    _write_text(
        os.path.join(repo_root, "Cargo.toml"),
        "[package]\nname = \"test_rust_repo\"\nversion = \"0.1.0\"\nedition = \"2021\"\n",
    )
    _write_text(
        os.path.join(repo_root, "src", "lib.rs"),
        "pub fn sample() -> &'static str { \"ok\" }\n",
    )


def _run_kbuild(repo_root: str, argv: list[str]) -> tuple[int, str]:
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        try:
            exit_code = run_kbuild(
                repo_root=repo_root,
                argv=argv,
                kbuild_root=REPO_ROOT,
                program_name="kbuild",
            )
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            return code, stderr.getvalue()
    return exit_code, stderr.getvalue()


class RustResidualTests(unittest.TestCase):
    def test_build_rejects_target_directory_outside_build(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbuild-rust-residual-build-") as repo_root:
            _make_rust_repo(repo_root)
            _write_text(os.path.join(repo_root, "target", "debug", "stamp"), "generated")

            code, stderr = _run_kbuild(repo_root, ["--build-latest"])

            self.assertEqual(code, 2)
            self.assertIn("refusing to build: found Cargo build artifacts outside build/.", stderr)
            self.assertIn("./target", stderr)

    def test_git_sync_rejects_cargo_home_outside_build(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbuild-rust-residual-git-") as repo_root:
            _make_rust_repo(repo_root)
            _write_text(
                os.path.join(repo_root, ".cargo-home", "registry", "cache", "stamp"),
                "generated",
            )
            subprocess.run(
                ["git", "init", repo_root],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            code, stderr = _run_kbuild(repo_root, ["--git-sync", "Test sync"])

            self.assertEqual(code, 2)
            self.assertIn(
                "refusing to sync git changes: found Cargo build artifacts outside build/.",
                stderr,
            )
            self.assertIn("./.cargo-home", stderr)

    def test_residual_check_ignores_staged_cargo_output_under_build(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbuild-rust-residual-clean-") as repo_root:
            _make_rust_repo(repo_root)
            _write_text(
                os.path.join(repo_root, "build", "latest", "debug", "deps", "artifact"),
                "generated-build-output",
            )
            _write_text(
                os.path.join(
                    repo_root,
                    "build",
                    "latest",
                    "cargo-home",
                    "registry",
                    "cache",
                    "stamp",
                ),
                "generated-cache-output",
            )
            _write_text(
                os.path.join(
                    repo_root,
                    "demo",
                    "exe",
                    "core",
                    "build",
                    "latest",
                    "debug",
                    "core",
                ),
                "generated-demo-output",
            )

            config = config_ops.load_kbuild_config(repo_root)
            residual_ops.ensure_repo_hygiene(
                repo_root=repo_root,
                config=config,
                operation="build",
            )

    def test_residual_check_rejects_generated_dot_cargo_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbuild-rust-residual-dot-cargo-") as repo_root:
            _make_rust_repo(repo_root)
            _write_text(
                os.path.join(repo_root, ".cargo", "registry", "cache", "stamp"),
                "generated-cache-output",
            )

            code, stderr = _run_kbuild(repo_root, ["--build-latest"])

            self.assertEqual(code, 2)
            self.assertIn("refusing to build: found Cargo build artifacts outside build/.", stderr)
            self.assertIn("./.cargo/registry", stderr)


if __name__ == "__main__":
    unittest.main()
