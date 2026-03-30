import json
import os
import sys
import tempfile
import unittest


THIS_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))
LIBS_DIR = os.path.join(REPO_ROOT, "libs")
if LIBS_DIR not in sys.path:
    sys.path.insert(0, LIBS_DIR)

from kbuild import config_ops  # noqa: E402


def _write_json(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


class BatchConfigTests(unittest.TestCase):
    def test_load_batch_targets_prefers_targets_key(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbuild-batch-targets-") as project_root:
            _write_json(
                os.path.join(project_root, ".kbuild.json"),
                {
                    "project": {"title": "Test Project", "id": "test_project"},
                    "git": {
                        "url": "https://example.invalid/test-project",
                        "auth": "git@example.invalid:test-project.git",
                    },
                    "cmake": {"sdk": {"package_name": "TestProjectSDK"}},
                    "batch": {"targets": ["kcli", "ktrace"]},
                },
            )

            self.assertEqual(config_ops.load_batch_targets(project_root), ["kcli", "ktrace"])

    def test_load_batch_targets_rejects_repos_key(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kbuild-batch-reject-repos-") as project_root:
            _write_json(
                os.path.join(project_root, ".kbuild.json"),
                {
                    "project": {"title": "Test Project", "id": "test_project"},
                    "git": {
                        "url": "https://example.invalid/test-project",
                        "auth": "git@example.invalid:test-project.git",
                    },
                    "cmake": {"sdk": {"package_name": "TestProjectSDK"}},
                    "batch": {"repos": ["kcli", "ktrace"]},
                },
            )

            with self.assertRaises(SystemExit) as exc:
                config_ops.load_batch_targets(project_root)

            self.assertEqual(exc.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
