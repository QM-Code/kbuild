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


def _make_swift_repo(repo_root: str) -> None:
    _write_json(
        os.path.join(repo_root, ".kbuild.json"),
        {
            "project": {
                "title": "Test Swift Repo",
                "id": "test_swift_repo",
            },
            "git": {
                "url": "https://example.invalid/test-swift-repo",
                "auth": "git@example.invalid:test-swift-repo.git",
            },
            "swift": {
                "package_path": "src",
                "demo_package_path": "demo",
                "demo_products": {
                    "bootstrap": {
                        "product": "test-swift-demo",
                        "kind": "executable",
                    },
                },
            },
            "build": {
                "demos": ["bootstrap"],
                "defaults": {
                    "demos": ["bootstrap"],
                },
            },
        },
    )
    _write_text(
        os.path.join(repo_root, "src", "Package.swift"),
        "// swift-tools-version: 5.9\n"
        "import PackageDescription\n"
        "let package = Package(name: \"TestSwiftRepo\")\n",
    )
    _write_text(
        os.path.join(repo_root, "demo", "Package.swift"),
        "// swift-tools-version: 5.9\n"
        "import PackageDescription\n"
        "let package = Package(name: \"TestSwiftDemo\")\n",
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


class SwiftResidualTests(unittest.TestCase):
    def test_build_rejects_swiftpm_build_dirs_outside_build(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbuild-swift-residual-build-") as repo_root:
            _make_swift_repo(repo_root)
            os.makedirs(os.path.join(repo_root, "src", ".build"), exist_ok=True)

            code, stderr = _run_kbuild(repo_root, ["--build-latest"])

            self.assertEqual(code, 2)
            self.assertIn("refusing to build: found SwiftPM build directories outside build/.", stderr)
            self.assertIn("./src/.build", stderr)

    def test_git_sync_rejects_swiftpm_build_dirs_outside_build(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbuild-swift-residual-git-") as repo_root:
            _make_swift_repo(repo_root)
            os.makedirs(os.path.join(repo_root, "demo", ".build"), exist_ok=True)
            subprocess.run(
                ["git", "init", repo_root],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            code, stderr = _run_kbuild(repo_root, ["--git-sync", "Test sync"])

            self.assertEqual(code, 2)
            self.assertIn("refusing to sync git changes: found SwiftPM build directories outside build/.", stderr)
            self.assertIn("./demo/.build", stderr)

    def test_residual_check_ignores_staged_swiftpm_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbuild-swift-residual-clean-") as repo_root:
            _make_swift_repo(repo_root)
            os.makedirs(os.path.join(repo_root, "build", "latest", "swiftpm", "debug"), exist_ok=True)
            os.makedirs(os.path.join(repo_root, "build", "latest", "swiftpm-demo", "release"), exist_ok=True)
            os.makedirs(os.path.join(repo_root, "build", "latest", "_swift", "cache"), exist_ok=True)
            os.makedirs(
                os.path.join(repo_root, "demo", "bootstrap", "build", "latest"),
                exist_ok=True,
            )

            config = config_ops.load_kbuild_config(repo_root)
            residual_ops.ensure_repo_hygiene(
                repo_root=repo_root,
                config=config,
                operation="build",
            )


if __name__ == "__main__":
    unittest.main()
