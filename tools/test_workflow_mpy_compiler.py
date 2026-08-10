import unittest
from pathlib import Path


class WorkflowMpyCompilerTests(unittest.TestCase):
    def test_mpy_cross_is_built_before_esp_idf_changes_the_host_path(self):
        workflow = Path(".github/workflows/repack-firmware.yml").read_text(
            encoding="utf-8"
        )
        compiler_start = workflow.index("- name: Build pinned mpy-cross compiler")
        idf_start = workflow.index("- name: Install ESP-IDF Python tools")
        compiler_end = workflow.find("\n      - name:", compiler_start + 1)
        compiler_step = workflow[compiler_start:compiler_end]

        self.assertLess(compiler_start, idf_start)
        self.assertIn(".ci-mpy-cross", compiler_step)
        self.assertNotIn("dist/uiflow-micropython", compiler_step)


if __name__ == "__main__":
    unittest.main()
