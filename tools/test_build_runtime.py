import tempfile
import unittest
from pathlib import Path

from tools.build_runtime import (
    artifact_path,
    build_staging,
    include_runtime_path,
    plan_diff,
    should_compile,
)


class BuildRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "source"
        self.staging = self.root / "staging"
        for relative, content in {
            "main.py": "print('main')\n",
            "config.py": "SECRET = True\n",
            "config.py.example": "SECRET = False\n",
            "apps/scale_app.py": "VALUE = 1\n",
            "apps/__init__.py": "",
            "assets/icons/Scale.png": "PNG",
            "docs/README.md": "docs",
            "tools/build_runtime.py": "build tool",
        }.items():
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_runtime_selection_and_artifact_mapping(self):
        self.assertTrue(should_compile("apps/scale_app.py"))
        self.assertFalse(should_compile("main.py"))
        self.assertFalse(should_compile("config.py.example"))
        self.assertFalse(should_compile("config.py"))
        self.assertEqual(artifact_path("apps/scale_app.py"), "apps/scale_app.mpy")
        self.assertEqual(artifact_path("main.py"), "main.py")
        self.assertEqual(
            artifact_path("assets/icons/Scale.png"),
            "assets/icons/Scale.png",
        )
        self.assertFalse(include_runtime_path("docs/README.md"))
        self.assertFalse(include_runtime_path("tools/build_runtime.py"))

    def test_build_staging_compiles_runtime_and_keeps_exceptions(self):
        def fake_compile(source_path, output_path):
            output_path.write_bytes(b"MPY:" + source_path.read_bytes())

        build_staging(
            self.source,
            self.staging,
            "v-test",
            compile_file=fake_compile,
            tracked_paths=[
                "main.py",
                "config.py",
                "config.py.example",
                "apps/scale_app.py",
                "apps/__init__.py",
                "assets/icons/Scale.png",
                "docs/README.md",
                "tools/build_runtime.py",
            ],
        )

        self.assertTrue((self.staging / "main.py").is_file())
        self.assertTrue((self.staging / "config.py.example").is_file())
        self.assertFalse((self.staging / "config.py").exists())
        self.assertTrue(
            (self.staging / "apps/scale_app.mpy")
            .read_bytes()
            .startswith(b"MPY:")
        )
        self.assertTrue((self.staging / "apps/__init__.mpy").is_file())
        self.assertTrue((self.staging / "assets/icons/Scale.png").is_file())
        self.assertFalse((self.staging / "docs/README.md").exists())
        self.assertFalse((self.staging / "tools/build_runtime.py").exists())
        self.assertEqual(
            (self.staging / "uhs-version.txt").read_text(encoding="utf-8"),
            "v-test\n",
        )

    def test_post_migration_diff_maps_python_sources_to_mpy(self):
        current_staging = self.root / "current"
        for relative in (
            "apps/scale_app.mpy",
            "apps/new_app.mpy",
            "main.py",
            "assets/icons/Scale.png",
            "uhs-version.txt",
        ):
            path = current_staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"artifact")

        plan = plan_diff(
            changed_paths=[
                ("M", "apps/scale_app.py"),
                ("A", "apps/new_app.py"),
                ("D", "apps/old_app.py"),
                ("M", "main.py"),
                ("M", "assets/icons/Scale.png"),
            ],
            base_paths=["tools/build_runtime.py", "apps/old_app.py"],
            staging_root=current_staging,
        )

        self.assertEqual(
            plan.archive_paths,
            (
                "apps/new_app.mpy",
                "apps/scale_app.mpy",
                "assets/icons/Scale.png",
                "main.py",
                "uhs-version.txt",
            ),
        )
        self.assertEqual(
            plan.delete_paths,
            ("apps/old_app.mpy", "apps/old_app.py"),
        )
        self.assertFalse(plan.first_mpy_migration)

    def test_first_mpy_migration_archives_all_mpy_and_removes_legacy_sources(self):
        current_staging = self.root / "current"
        for relative in (
            "apps/scale_app.mpy",
            "apps/new_app.mpy",
            "main.py",
            "config.py.example",
            "uhs-version.txt",
        ):
            path = current_staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"artifact")

        plan = plan_diff(
            changed_paths=[("M", "main.py")],
            base_paths=[
                "apps/scale_app.py",
                "apps/old_app.py",
                "main.py",
                "config.py.example",
            ],
            staging_root=current_staging,
        )

        self.assertEqual(
            plan.archive_paths,
            (
                "apps/new_app.mpy",
                "apps/scale_app.mpy",
                "main.py",
                "uhs-version.txt",
            ),
        )
        self.assertEqual(
            plan.delete_paths,
            ("apps/old_app.py", "apps/scale_app.py"),
        )
        self.assertTrue(plan.first_mpy_migration)


if __name__ == "__main__":
    unittest.main()
