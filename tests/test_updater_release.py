import json
import sys
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
    def __init__(self, status_code=200, data=None, content=b""):
        self.status_code = status_code
        self._data = data
        self.content = content
        self.text = json.dumps(data) if data is not None else ""
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


if __name__ == "__main__":
    unittest.main()
