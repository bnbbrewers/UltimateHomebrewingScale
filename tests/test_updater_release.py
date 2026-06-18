import json
import hashlib
import os
import shutil
import sys
import tempfile
import types
import unittest

sys.modules.setdefault("m5ui", types.SimpleNamespace())
sys.modules.setdefault("lvgl", types.SimpleNamespace())
sys.modules.setdefault("core.screen_manager", types.SimpleNamespace(ScreenManager=object))
sys.modules.setdefault("core.hardware_manager", types.SimpleNamespace(HardwareManager=object))
sys.modules.setdefault("core.app_manager", types.SimpleNamespace(AppManager=object))
sys.modules.setdefault("core.api_factory", types.SimpleNamespace(ApiFactory=object))

from core import updater


class _Response:
    def __init__(self, status_code=200, data=None, content=b"", headers=None):
        self.status_code = status_code
        self._data = data
        self.content = content
        self.text = json.dumps(data) if data is not None else ""
        self.headers = headers or {}
        self.closed = False

    def json(self):
        return self._data

    def close(self):
        self.closed = True


class _Requests:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected GET {}".format(url))
        return self.responses.pop(0)


class UpdaterReleaseSelectionTests(unittest.TestCase):
    def test_stable_channel_uses_latest_release_endpoint(self):
        release = {
            "tag_name": "v1.2.3",
            "draft": False,
            "prerelease": False,
            "assets": [{"name": updater.MANIFEST_ASSET_NAME, "browser_download_url": "https://example/manifest.json"}],
        }
        requests = _Requests([_Response(data=release)])

        selected = updater.resolve_release("stable", requests_module=requests)

        self.assertEqual(selected["tag"], "v1.2.3")
        self.assertEqual(selected["manifest_url"], "https://example/manifest.json")
        self.assertEqual(requests.calls[0][0], updater.latest_release_url())

    def test_stable_channel_requires_direct_manifest_download_url(self):
        release = {
            "tag_name": "v1.2.3",
            "draft": False,
            "prerelease": False,
            "assets": [{"name": updater.MANIFEST_ASSET_NAME, "url": "https://api.example/assets/1"}],
        }
        requests = _Requests([_Response(data=release)])

        with self.assertRaises(RuntimeError) as ctx:
            updater.resolve_release("stable", requests_module=requests)

        self.assertIn("No matching release", str(ctx.exception))

    def test_prerelease_channel_lists_releases_and_chooses_first_prerelease_with_manifest(self):
        releases = [
            {
                "tag_name": "v1.3.0",
                "draft": False,
                "prerelease": False,
                "assets": [{"name": updater.MANIFEST_ASSET_NAME, "browser_download_url": "https://example/stable.json"}],
            },
            {
                "tag_name": "v1.4.0-rc.1",
                "draft": False,
                "prerelease": True,
                "assets": [{"name": updater.MANIFEST_ASSET_NAME, "browser_download_url": "https://example/rc.json"}],
            },
        ]
        requests = _Requests([_Response(data=releases)])

        selected = updater.resolve_release("prerelease", requests_module=requests)

        self.assertEqual(selected["tag"], "v1.4.0-rc.1")
        self.assertEqual(selected["manifest_url"], "https://example/rc.json")
        self.assertEqual(requests.calls[0][0], updater.releases_url())

    def test_prerelease_channel_skips_drafts_and_releases_without_manifest(self):
        releases = [
            {
                "tag_name": "v1.4.0-rc.1",
                "draft": True,
                "prerelease": True,
                "assets": [{"name": updater.MANIFEST_ASSET_NAME, "browser_download_url": "https://example/draft.json"}],
            },
            {
                "tag_name": "v1.4.0-rc.2",
                "draft": False,
                "prerelease": True,
                "assets": [],
            },
            {
                "tag_name": "v1.4.0-rc.3",
                "draft": False,
                "prerelease": True,
                "assets": [{"name": updater.MANIFEST_ASSET_NAME, "browser_download_url": "https://example/rc3.json"}],
            },
        ]
        requests = _Requests([_Response(data=releases)])

        selected = updater.resolve_release("prerelease", requests_module=requests)

        self.assertEqual(selected["tag"], "v1.4.0-rc.3")
        self.assertEqual(selected["manifest_url"], "https://example/rc3.json")

    def test_prerelease_channel_errors_when_no_prerelease_manifest_exists(self):
        requests = _Requests([_Response(data=[{"tag_name": "v1.0.0", "draft": False, "prerelease": True, "assets": []}])])

        with self.assertRaises(RuntimeError) as ctx:
            updater.resolve_release("prerelease", requests_module=requests)

        self.assertIn("No matching release", str(ctx.exception))


class UpdaterManifestInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_validate_manifest_rejects_unsafe_paths(self):
        cases = [
            {
                "name": "relative parent file path",
                "manifest": {
                    "version": "v1.2.3",
                    "files": [{"path": "../config.py", "url": "https://example/config.py"}],
                },
            },
            {
                "name": "absolute file path",
                "manifest": {
                    "version": "v1.2.3",
                    "files": [{"path": "/flash/config.py", "url": "https://example/config.py"}],
                },
            },
            {
                "name": "relative parent delete path",
                "manifest": {
                    "version": "v1.2.3",
                    "files": [],
                    "delete": ["../old.py"],
                },
            },
            {
                "name": "config file",
                "manifest": {
                    "version": "v1.2.3",
                    "files": [{"path": "config.py", "url": "https://example/config.py"}],
                },
            },
            {
                "name": "storage json file",
                "manifest": {
                    "version": "v1.2.3",
                    "files": [{"path": "storage/settings.json", "url": "https://example/settings.json"}],
                },
            },
            {
                "name": "exact parent path",
                "manifest": {
                    "version": "v1.2.3",
                    "files": [{"path": "..", "url": "https://example/escape.py"}],
                },
            },
            {
                "name": "current directory path",
                "manifest": {
                    "version": "v1.2.3",
                    "files": [{"path": ".", "url": "https://example/dot.py"}],
                },
            },
            {
                "name": "parent segment path",
                "manifest": {
                    "version": "v1.2.3",
                    "files": [{"path": "apps/../escape.py", "url": "https://example/escape.py"}],
                },
            },
            {
                "name": "windows absolute path",
                "manifest": {
                    "version": "v1.2.3",
                    "files": [{"path": "C:\\escape.py", "url": "https://example/escape.py"}],
                },
            },
        ]

        for case in cases:
            with self.subTest(case["name"]):
                with self.assertRaises(RuntimeError) as ctx:
                    updater.validate_manifest(case["manifest"])

                self.assertIn("unsafe path", str(ctx.exception))

    def test_validate_manifest_rejects_invalid_urls(self):
        for url in ("not-url", "ftp://example/apps/demo.py", "https:///apps/demo.py", "https://example/bad path.py"):
            manifest = {
                "version": "v1.2.3",
                "files": [{"path": "apps/demo.py", "url": url}],
            }

            with self.subTest(url=url):
                with self.assertRaises(RuntimeError) as ctx:
                    updater.validate_manifest(manifest)

                self.assertIn("Invalid manifest url", str(ctx.exception))

    def test_validate_manifest_rejects_invalid_sizes(self):
        for size in (-1, "1.5", "abc"):
            manifest = {
                "version": "v1.2.3",
                "files": [{"path": "apps/demo.py", "url": "https://example/apps/demo.py", "size": size}],
            }

            with self.subTest(size=size):
                with self.assertRaises(RuntimeError) as ctx:
                    updater.validate_manifest(manifest)

                self.assertIn("Invalid manifest size", str(ctx.exception))

    def test_validate_manifest_normalizes_valid_size(self):
        digest = hashlib.sha256(b"print(1)\n#").hexdigest().upper()
        manifest = {
            "version": "v1.2.3",
            "files": [
                {"path": "apps/demo.py", "url": "http://example/apps/demo.py", "size": "10", "sha256": digest},
                {"path": "apps/empty.py", "url": "https://example/apps/empty.py"},
            ],
        }

        clean = updater.validate_manifest(manifest)

        self.assertEqual(clean["files"][0]["size"], 10)
        self.assertEqual(clean["files"][0]["sha256"], digest.lower())
        self.assertIsNone(clean["files"][1]["size"])

    def test_validate_manifest_rejects_invalid_sha256(self):
        for digest in ("abc", "z" * 64):
            manifest = {
                "version": "v1.2.3",
                "files": [{"path": "apps/demo.py", "url": "https://example/apps/demo.py", "sha256": digest}],
            }

            with self.subTest(digest=digest):
                with self.assertRaises(RuntimeError) as ctx:
                    updater.validate_manifest(manifest)

                self.assertIn("Invalid manifest sha256", str(ctx.exception))

    def test_install_manifest_writes_temp_then_replaces_destination(self):
        manifest = {
            "version": "v1.2.3",
            "files": [
                {"path": "apps/demo.py", "url": "https://example/apps/demo.py", "size": 10},
            ],
            "delete": ["old.py"],
        }
        requests = _Requests([_Response(content=b"print(1)\n#")])
        old_path = os.path.join(self.tmp, "old.py")
        with open(old_path, "w") as f:
            f.write("old")

        result = updater.install_manifest(manifest, requests_module=requests, dest_root=self.tmp)

        installed = os.path.join(self.tmp, "apps", "demo.py")
        self.assertEqual(result["ok"], 1)
        self.assertEqual(result["failed"], 0)
        with open(installed, "rb") as f:
            self.assertEqual(f.read(), b"print(1)\n#")
        self.assertFalse(os.path.exists(installed + ".tmp"))
        self.assertFalse(os.path.exists(old_path))

    def test_install_manifest_keeps_existing_file_when_download_size_mismatch(self):
        manifest = {
            "version": "v1.2.3",
            "files": [
                {"path": "apps/demo.py", "url": "https://example/apps/demo.py", "size": 99},
            ],
        }
        dest_dir = os.path.join(self.tmp, "apps")
        os.mkdir(dest_dir)
        installed = os.path.join(dest_dir, "demo.py")
        with open(installed, "wb") as f:
            f.write(b"old")
        requests = _Requests([_Response(content=b"new")])

        with self.assertRaises(RuntimeError):
            updater.install_manifest(manifest, requests_module=requests, dest_root=self.tmp)

        with open(installed, "rb") as f:
            self.assertEqual(f.read(), b"old")
        self.assertFalse(os.path.exists(installed + ".tmp"))

    def test_install_manifest_follows_file_redirect_and_verifies_sha256(self):
        content = b"demo = 1"
        manifest = {
            "version": "v1.2.3",
            "files": [
                {
                    "path": "apps/demo.py",
                    "url": "https://example/apps/demo.py",
                    "size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                },
            ],
        }
        requests = _Requests([
            _Response(status_code=302, headers={"Location": "https://objects.example/apps/demo.py"}),
            _Response(content=content),
        ])

        result = updater.install_manifest(manifest, requests_module=requests, dest_root=self.tmp)

        self.assertEqual(result["ok"], 1)
        self.assertEqual(requests.calls[0][0], "https://example/apps/demo.py")
        self.assertEqual(requests.calls[1][0], "https://objects.example/apps/demo.py")
        with open(os.path.join(self.tmp, "apps", "demo.py"), "rb") as f:
            self.assertEqual(f.read(), content)

    def test_install_manifest_keeps_existing_file_when_sha256_mismatch(self):
        manifest = {
            "version": "v1.2.3",
            "files": [
                {
                    "path": "apps/demo.py",
                    "url": "https://example/apps/demo.py",
                    "size": 3,
                    "sha256": hashlib.sha256(b"expected").hexdigest(),
                },
            ],
        }
        dest_dir = os.path.join(self.tmp, "apps")
        os.mkdir(dest_dir)
        installed = os.path.join(dest_dir, "demo.py")
        with open(installed, "wb") as f:
            f.write(b"old")
        requests = _Requests([_Response(content=b"new")])

        with self.assertRaises(RuntimeError) as ctx:
            updater.install_manifest(manifest, requests_module=requests, dest_root=self.tmp)

        self.assertIn("sha256 mismatch", str(ctx.exception))
        with open(installed, "rb") as f:
            self.assertEqual(f.read(), b"old")
        self.assertFalse(os.path.exists(installed + ".tmp"))

    def test_replace_file_restores_existing_file_when_final_rename_fails(self):
        dest = os.path.join(self.tmp, "demo.py")
        tmp = dest + ".tmp"
        with open(dest, "wb") as f:
            f.write(b"old")
        with open(tmp, "wb") as f:
            f.write(b"new")
        real_rename = updater.os.rename

        def failing_rename(src, dst):
            if src == tmp and dst == dest:
                raise OSError("rename failed")
            return real_rename(src, dst)

        updater.os.rename = failing_rename
        try:
            with self.assertRaises(OSError):
                updater._replace_file(tmp, dest)
        finally:
            updater.os.rename = real_rename

        with open(dest, "rb") as f:
            self.assertEqual(f.read(), b"old")


class UpdaterFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_update_resolves_release_downloads_manifest_and_installs_files(self):
        release = {
            "tag_name": "v1.2.3",
            "draft": False,
            "prerelease": False,
            "assets": [{"name": updater.MANIFEST_ASSET_NAME, "browser_download_url": "https://example/manifest.json"}],
        }
        manifest = {
            "version": "v1.2.3",
            "files": [{"path": "apps/demo.py", "url": "https://example/apps/demo.py", "size": 8}],
        }
        requests = _Requests([
            _Response(data=release),
            _Response(data=manifest),
            _Response(content=b"demo = 1"),
        ])
        events = []

        result = updater.update(
            channel="stable",
            requests_module=requests,
            ensure_wifi=False,
            dest_root=self.tmp,
            progress_callback=events.append,
        )

        self.assertEqual(result["version"], "v1.2.3")
        self.assertEqual(result["ok"], 1)
        self.assertEqual(requests.calls[0][0], updater.latest_release_url())
        self.assertEqual(requests.calls[1][0], "https://example/manifest.json")
        self.assertEqual(requests.responses, [])
        with open(os.path.join(self.tmp, "apps", "demo.py"), "rb") as f:
            self.assertEqual(f.read(), b"demo = 1")
        self.assertEqual(events[-1]["stage"], "done")

    def test_update_follows_manifest_asset_redirect(self):
        release = {
            "tag_name": "v1.2.3",
            "draft": False,
            "prerelease": False,
            "assets": [{"name": updater.MANIFEST_ASSET_NAME, "browser_download_url": "https://example/asset"}],
        }
        manifest = {
            "version": "v1.2.3",
            "files": [{"path": "apps/demo.py", "url": "https://example/apps/demo.py", "size": 8}],
        }
        requests = _Requests([
            _Response(data=release),
            _Response(status_code=302, headers={"Location": "https://objects.example/manifest.json"}),
            _Response(data=manifest),
            _Response(content=b"demo = 1"),
        ])

        result = updater.update(
            channel="stable",
            requests_module=requests,
            ensure_wifi=False,
            dest_root=self.tmp,
        )

        self.assertEqual(result["version"], "v1.2.3")
        self.assertEqual(result["ok"], 1)
        self.assertEqual(requests.calls[1][0], "https://example/asset")
        self.assertEqual(requests.calls[2][0], "https://objects.example/manifest.json")
        self.assertEqual(requests.responses, [])

    def test_update_emits_error_progress_with_failed_path_when_install_fails(self):
        release = {
            "tag_name": "v1.2.3",
            "draft": False,
            "prerelease": False,
            "assets": [{"name": updater.MANIFEST_ASSET_NAME, "browser_download_url": "https://example/manifest.json"}],
        }
        manifest = {
            "version": "v1.2.3",
            "files": [{"path": "apps/demo.py", "url": "https://example/apps/demo.py", "size": 99}],
        }
        requests = _Requests([
            _Response(data=release),
            _Response(data=manifest),
            _Response(content=b"short"),
        ])
        events = []

        with self.assertRaises(RuntimeError) as ctx:
            updater.update(
                channel="stable",
                requests_module=requests,
                ensure_wifi=False,
                dest_root=self.tmp,
                progress_callback=events.append,
            )

        error_events = [event for event in events if event["stage"] in ("error", "incomplete")]
        self.assertTrue(error_events)
        self.assertIn("apps/demo.py", error_events[-1]["detail"])
        self.assertIn("apps/demo.py", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
