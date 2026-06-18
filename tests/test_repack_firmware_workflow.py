import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "repack-firmware.yml"
BASE_ZIP = ROOT / "firmware" / "UHS-m5dial-repack-base.zip"


class RepackFirmwareWorkflowTest(unittest.TestCase):
    def test_workflow_runs_for_version_tags_and_publishes_release(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("tags:", workflow)
        self.assertIn("- 'v*'", workflow)
        self.assertIn("contents: write", workflow)
        self.assertIn("pages: write", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("environment:", workflow)
        self.assertIn("name: github-pages", workflow)
        self.assertIn("url: ${{ steps.deployment.outputs.page_url }}", workflow)
        self.assertIn("HEAD_SHA=$(git rev-parse HEAD)", workflow)
        self.assertIn("git merge-base --is-ancestor \"$HEAD_SHA\" origin/main", workflow)
        self.assertIn("firmware/UHS-m5dial-repack-base.zip", workflow)
        self.assertIn("UHS-app-files-{os.environ['TAG_NAME']}.zip", workflow)
        self.assertIn("dist/out/UHS-app-files-${{ env.TAG_NAME }}.zip", workflow)
        self.assertIn("UHS-firmwareM5Dial.bin", workflow)
        self.assertIn("UHS-firmwareM5Dial.sha256", workflow)
        self.assertIn("actions/upload-artifact@", workflow)
        self.assertIn("softprops/action-gh-release@", workflow)
        self.assertIn("make_latest: true", workflow)
        self.assertIn("dist/out/UHS-firmwareM5Dial.bin", workflow)
        self.assertIn("dist/out/UHS-firmwareM5Dial.sha256", workflow)
        self.assertIn("dist/out/UHS-build-manifest.json", workflow)
        self.assertIn("dist/out/UHS-web-install-manifest.json", workflow)
        self.assertIn("dist/out/UHS-app-files-${{ env.TAG_NAME }}.zip", workflow)
        self.assertIn("dist/out/uhs-update-manifest.json", workflow)
        self.assertIn("https://bnbbrewers.github.io/UltimateHomebrewingScale/SoftwareInstallationGuide/latest", workflow)
        self.assertIn("actions/upload-pages-artifact@", workflow)
        self.assertIn("actions/deploy-pages@", workflow)

    def test_workflow_generates_on_device_update_manifest(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("uhs-update-manifest.json", workflow)
        self.assertIn("raw.githubusercontent.com", workflow)
        self.assertIn('"version": os.environ["TAG_NAME"]', workflow)
        self.assertIn('"path": rel_path', workflow)
        self.assertIn('"url": raw_url', workflow)
        self.assertIn('"size": path.stat().st_size', workflow)
        self.assertIn('"sha256": file_sha256', workflow)
        self.assertIn('"delete": ["install.py"]', workflow)

    def test_workflow_excludes_non_runtime_paths(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn('grep -Ev "(^docs/|^firmware/|^\\\\.git|[.][Mm][Dd]$|^config.py$)"', workflow)
        self.assertIn("[ ! -f dist/fs-user/config.py ]", workflow)
        self.assertIn("[ ! -d dist/fs-user/docs ]", workflow)
        self.assertIn("[ ! -d dist/fs-user/firmware ]", workflow)
        self.assertIn("[ ! -d dist/fs-user/.github ]", workflow)
        self.assertIn("[ ! -f dist/fs-user/.gitignore ]", workflow)

    def test_repack_base_contains_makeimg_dependencies(self):
        with zipfile.ZipFile(BASE_ZIP) as archive:
            names = set(archive.namelist())

        self.assertIn("repack-base/artifacts/sdkconfig", names)
        self.assertIn("repack-base/artifacts/bootloader/bootloader.bin", names)
        self.assertIn("repack-base/artifacts/partition_table/partition-table.bin", names)
        self.assertIn("repack-base/artifacts/nvs.bin", names)
        self.assertIn("repack-base/artifacts/micropython.bin", names)
        self.assertIn("repack-base/artifacts/fs-system.bin", names)
        self.assertIn("repack-base/tools/fs_packed.py", names)
        self.assertIn("repack-base/tools/littlefs2", names)
        self.assertIn("repack-base/tools/makeimg.py", names)
        self.assertIn("repack-base/version.txt", names)
        self.assertIn("repack-base/micropython/tools/uf2conv.py", names)
        self.assertIn("repack-base/micropython/tools/uf2families.json", names)


if __name__ == "__main__":
    unittest.main()
