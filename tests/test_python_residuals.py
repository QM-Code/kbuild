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


def _make_python_repo(repo_root: str) -> None:
    _write_json(
        os.path.join(repo_root, ".kbuild.json"),
        {
            "project": {
                "title": "Test Python Repo",
                "id": "test_python_repo",
            },
            "git": {
                "url": "https://example.invalid/test-python-repo",
                "auth": "git@example.invalid:test-python-repo.git",
            },
            "cmake": {
                "minimum_version": "3.20",
                "configure_by_default": True,
                "tests": False,
                "sdk": {
                    "package_name": "TestPythonSDK",
                },
            },
        },
    )
    _write_text(
        os.path.join(repo_root, "src", "sample", "__init__.py"),
        "VALUE = 'sample'\n",
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


class PythonResidualTests(unittest.TestCase):
    def test_build_rejects_pycache_outside_build(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbuild-python-residual-build-") as repo_root:
            _make_python_repo(repo_root)
            _write_text(
                os.path.join(repo_root, "src", "sample", "__pycache__", "__init__.cpython-312.pyc"),
                "compiled",
            )

            code, stderr = _run_kbuild(repo_root, ["--build-latest"])

            self.assertEqual(code, 2)
            self.assertIn("refusing to build: found Python cache artifacts outside build/.", stderr)
            self.assertIn("./src/sample/__pycache__", stderr)

    def test_git_sync_rejects_pyc_files_outside_build(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbuild-python-residual-git-") as repo_root:
            _make_python_repo(repo_root)
            _write_text(os.path.join(repo_root, "tests", "test_sample.pyc"), "compiled")
            subprocess.run(
                ["git", "init", repo_root],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            code, stderr = _run_kbuild(repo_root, ["--git-sync", "Test sync"])

            self.assertEqual(code, 2)
            self.assertIn("refusing to sync git changes: found Python cache artifacts outside build/.", stderr)
            self.assertIn("./tests/test_sample.pyc", stderr)

    def test_residual_check_ignores_build_directories(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbuild-python-residual-clean-") as repo_root:
            _make_python_repo(repo_root)
            _write_text(
                os.path.join(
                    repo_root,
                    "build",
                    "latest",
                    "sdk",
                    "python",
                    "sample",
                    "__pycache__",
                    "__init__.cpython-312.pyc",
                ),
                "compiled",
            )
            _write_text(
                os.path.join(
                    repo_root,
                    "demo",
                    "exe",
                    "core",
                    "build",
                    "latest",
                    "sdk",
                    "python",
                    "sample.pyc",
                ),
                "compiled",
            )

            config = config_ops.load_kbuild_config(repo_root)
            residual_ops.ensure_repo_hygiene(
                repo_root=repo_root,
                config=config,
                operation="build",
            )


if __name__ == "__main__":
    unittest.main()
