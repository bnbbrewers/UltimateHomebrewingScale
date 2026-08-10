import tarfile
import tempfile
import unittest
from pathlib import Path

from updater import tar_extract
from updater import workflow


def _write_tar(path, relative, content):
    with tarfile.open(path, "w") as archive:
        info = tarfile.TarInfo(relative)
        info.size = len(content)
        archive.addfile(info, __import__("io").BytesIO(content))


class UpdaterMpyCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.archive = self.root / "update.tar"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_extracting_mpy_removes_existing_source_py(self):
        source = self.root / "apps/demo.py"
        source.parent.mkdir(parents=True)
        source.write_text("old", encoding="utf-8")
        _write_tar(self.archive, "apps/demo.mpy", b"compiled")

        tar_extract.extract(str(self.archive), dest_root=str(self.root))

        self.assertFalse(source.exists())
        self.assertEqual((self.root / "apps/demo.mpy").read_bytes(), b"compiled")

    def test_extracting_mpy_succeeds_when_source_py_is_absent(self):
        _write_tar(self.archive, "apps/demo.mpy", b"compiled")

        count = tar_extract.extract(str(self.archive), dest_root=str(self.root))

        self.assertEqual(count, 1)
        self.assertTrue((self.root / "apps/demo.mpy").is_file())

    def test_config_files_are_not_removed_by_mpy_cleanup(self):
        (self.root / "config.py").write_text("private", encoding="utf-8")
        (self.root / "config.py.example").write_text("example", encoding="utf-8")
        _write_tar(self.archive, "config.mpy", b"compiled")

        tar_extract.extract(str(self.archive), dest_root=str(self.root))

        self.assertTrue((self.root / "config.py").is_file())
        self.assertTrue((self.root / "config.py.example").is_file())

    def test_explicit_delete_accepts_both_variants_for_removed_module(self):
        for relative in ("apps/demo.py", "apps/demo.mpy"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("old", encoding="utf-8")

        workflow._apply_deletes(
            ["apps/demo.py", "apps/demo.mpy"],
            str(self.root).replace("\\", "/"),
        )

        self.assertFalse((self.root / "apps/demo.py").exists())
        self.assertFalse((self.root / "apps/demo.mpy").exists())

    def test_explicit_delete_rejects_config_example(self):
        with self.assertRaises(RuntimeError):
            workflow._apply_deletes(
                ["config.py.example"],
                str(self.root).replace("\\", "/"),
            )

    def test_manifest_accepts_mpy_runtime_format(self):
        parsed = workflow._manifest_archive(
            {
                "strategy": "tar-diff",
                "runtime_format": "mpy",
                "archive": {
                    "url": "https://example.com/update.tar",
                    "size": 1,
                    "sha256": "a" * 64,
                },
            }
        )

        self.assertEqual(parsed["runtime_format"], "mpy")

    def test_manifest_rejects_unknown_runtime_format(self):
        with self.assertRaises(RuntimeError):
            workflow._manifest_archive(
                {
                    "strategy": "tar-diff",
                    "runtime_format": "native",
                    "archive": {
                        "url": "https://example.com/update.tar",
                        "size": 1,
                        "sha256": "a" * 64,
                    },
                }
            )


if __name__ == "__main__":
    unittest.main()
