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


def _make_javascript_repo(repo_root: str) -> None:
    _write_json(
        os.path.join(repo_root, ".kbuild.json"),
        {
            "project": {
                "title": "Test JavaScript Repo",
                "id": "test_javascript_repo",
            },
            "git": {
                "url": "https://example.invalid/test-javascript-repo",
                "auth": "git@example.invalid:test-javascript-repo.git",
            },
            "javascript": {
                "package": "testpkg",
                "sdk_dir": "src",
            },
        },
    )
    _write_text(
        os.path.join(repo_root, "src", "testpkg", "index.js"),
        '"use strict";\nmodule.exports = {};\n',
    )


def _write_generated_launcher(path: str) -> None:
    _write_text(
        path,
        (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'export KTOOLS_JS_SDK_ROOT_TESTPKG="/tmp/fake-sdk"\n'
            'exec node "/tmp/test.js" "$@"\n'
        ),
    )
    os.chmod(path, 0o755)


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


class JavaScriptResidualTests(unittest.TestCase):
    def test_build_rejects_generated_sdk_metadata_outside_build(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbuild-javascript-residual-build-") as repo_root:
            _make_javascript_repo(repo_root)
            _write_json(
                os.path.join(repo_root, "share", "kbuild-javascript-sdk.json"),
                {
                    "package": "testpkg",
                    "sdk_dir": "src",
                },
            )

            code, stderr = _run_kbuild(repo_root, ["--build-latest"])

            self.assertEqual(code, 2)
            self.assertIn("refusing to build: found JavaScript kbuild artifacts outside build/.", stderr)
            self.assertIn("./share/kbuild-javascript-sdk.json", stderr)

    def test_git_sync_rejects_generated_launchers_outside_build(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbuild-javascript-residual-git-") as repo_root:
            _make_javascript_repo(repo_root)
            _write_generated_launcher(os.path.join(repo_root, "generated", "run-tests"))
            subprocess.run(
                ["git", "init", repo_root],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            code, stderr = _run_kbuild(repo_root, ["--git-sync", "Test sync"])

            self.assertEqual(code, 2)
            self.assertIn(
                "refusing to sync git changes: found JavaScript kbuild artifacts outside build/.",
                stderr,
            )
            self.assertIn("./generated/run-tests", stderr)

    def test_residual_check_ignores_generated_artifacts_inside_build(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbuild-javascript-residual-clean-") as repo_root:
            _make_javascript_repo(repo_root)
            _write_json(
                os.path.join(repo_root, "build", "latest", "sdk", "share", "kbuild-javascript-sdk.json"),
                {
                    "package": "testpkg",
                    "sdk_dir": "src",
                },
            )
            _write_generated_launcher(
                os.path.join(repo_root, "demo", "exe", "core", "build", "latest", "test")
            )

            config = config_ops.load_kbuild_config(repo_root)
            residual_ops.ensure_repo_hygiene(
                repo_root=repo_root,
                config=config,
                operation="build",
            )


if __name__ == "__main__":
    unittest.main()
