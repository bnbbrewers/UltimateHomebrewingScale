# Release-Based Updater Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace branch-based device updates with a GitHub Releases updater using a persistent `UPDATE_CHANNEL` setting for stable or pre-release updates.

**Architecture:** Keep the hidden updater app and boot-time NVS update flag. Rework `core/updater.py` into release selection, manifest validation, and file installation helpers that can be unit tested without network calls. Update portal config/i18n/docs so the user chooses a persistent release channel instead of a branch.

**Tech Stack:** MicroPython-compatible Python, `unittest`, existing setup portal, existing i18n locale dictionaries, GitHub REST Releases API, streaming HTTP requests through the existing `requests` compatibility layer.

---

## File Structure

- Modify `core/updater.py`: replace branch tree scanning with release selection, manifest download, manifest validation, streaming temp-file install, delete list handling, and installed-state write.
- Modify `apps/updater_app.py`: read `UPDATE_CHANNEL` instead of `UPDATE_BRANCH` and pass it to `core.updater.update()`.
- Modify `webportal/config_keys.py`: replace editable `UPDATE_BRANCH` with enum `UPDATE_CHANNEL`.
- Modify `webportal/setup_portal_service.py`: replace the lightweight fallback field with a release channel select.
- Modify `storage/config_registry.py`: rely on existing enum validation and defaults; no schema-specific logic should be needed beyond `config_keys`.
- Modify `config.py.example`: replace `UPDATE_BRANCH` with `UPDATE_CHANNEL`.
- Modify `i18n/locales/en.py` and `i18n/locales/fr.py`: add updater release/channel strings and portal field/choice labels.
- Modify `README.md` and `INSTALLATION.MD`: describe release-based updates.
- Create `tests/test_updater_release.py`: release selection, manifest validation, install behavior, update result.
- Modify `tests/test_webportal_kegs.py`: portal schema/rendering tests for `UPDATE_CHANNEL`.
- Modify `tests/test_setup_portal_service.py`: lightweight portal field tests for `UPDATE_CHANNEL`.

## Task 1: Portal Config Schema

**Files:**
- Modify: `webportal/config_keys.py`
- Modify: `config.py.example`
- Modify: `i18n/locales/en.py`
- Modify: `i18n/locales/fr.py`
- Test: `tests/test_webportal_kegs.py`

- [ ] **Step 1: Write failing tests for the new persistent channel**

Append these tests to `WebPortalKegTests` in `tests/test_webportal_kegs.py`:

```python
    def test_update_channel_replaces_update_branch_in_schema(self):
        self.assertIn("UPDATE_CHANNEL", EDITABLE_KEYS)
        self.assertNotIn("UPDATE_BRANCH", EDITABLE_KEYS)
        self.assertEqual(EDITABLE_KEYS["UPDATE_CHANNEL"]["type"], "enum")
        self.assertEqual(EDITABLE_KEYS["UPDATE_CHANNEL"]["choices"], ["stable", "prerelease"])
        self.assertEqual(EDITABLE_KEYS["UPDATE_CHANNEL"]["default"], "stable")
        self.assertIn("UPDATE_CHANNEL", EDITABLE_ORDER)
        self.assertNotIn("UPDATE_BRANCH", EDITABLE_ORDER)

    def test_render_form_includes_release_channel_selector(self):
        html = render_form_html({"LANGUAGE": "en", "UPDATE_CHANNEL": "prerelease"}, i18n=I18n("en"))

        self.assertIn("Release channel", html)
        self.assertIn("name='UPDATE_CHANNEL'", html)
        self.assertIn("value='stable'", html)
        self.assertIn("value='prerelease' selected", html)
        self.assertNotIn("Update branch", html)
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
python -m unittest tests.test_webportal_kegs.WebPortalKegTests.test_update_channel_replaces_update_branch_in_schema tests.test_webportal_kegs.WebPortalKegTests.test_render_form_includes_release_channel_selector
```

Expected: both tests fail because `UPDATE_BRANCH` still exists and `UPDATE_CHANNEL` is missing.

- [ ] **Step 3: Update the editable config schema**

In `webportal/config_keys.py`, replace the `UPDATE_BRANCH` entry with:

```python
    "UPDATE_CHANNEL": {
        "type": "enum",
        "choices": ["stable", "prerelease"],
        "default": "stable",
        "label": "Release channel",
    },
```

Replace `"UPDATE_BRANCH",` in `EDITABLE_ORDER` with:

```python
    "UPDATE_CHANNEL",
```

- [ ] **Step 4: Update example config**

In `config.py.example`, replace:

```python
# Git branch used by the hidden updater app
UPDATE_BRANCH = "main"
```

with:

```python
# Release channel used by the hidden updater app: "stable" or "prerelease"
UPDATE_CHANNEL = "stable"
```

- [ ] **Step 5: Update i18n portal field and choices**

In `i18n/locales/en.py`, under `portal.fields`, replace `UPDATE_BRANCH` with:

```python
            'UPDATE_CHANNEL': 'Release channel',
```

Under `portal.choices`, add:

```python
            'update_channel_stable': 'Stable',
            'update_channel_prerelease': 'Pre-release',
```

In `i18n/locales/fr.py`, under `portal.fields`, replace `UPDATE_BRANCH` with:

```python
            'UPDATE_CHANNEL': 'Canal de mise a jour',
```

Under `portal.choices`, add:

```python
            'update_channel_stable': 'Stable',
            'update_channel_prerelease': 'Pre-release',
```

- [ ] **Step 6: Run focused tests and verify they pass**

Run:

```bash
python -m unittest tests.test_webportal_kegs.WebPortalKegTests.test_update_channel_replaces_update_branch_in_schema tests.test_webportal_kegs.WebPortalKegTests.test_render_form_includes_release_channel_selector
```

Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add webportal/config_keys.py config.py.example i18n/locales/en.py i18n/locales/fr.py tests/test_webportal_kegs.py
git commit -m "feat: add release update channel setting"
```

## Task 2: Lightweight Portal Fallback

**Files:**
- Modify: `webportal/setup_portal_service.py`
- Test: `tests/test_setup_portal_service.py`

- [ ] **Step 1: Write failing tests for the lightweight form**

Append these tests to `SetupPortalServiceTests` in `tests/test_setup_portal_service.py`:

```python
    def test_minimal_form_uses_update_channel_not_branch(self):
        html = portal.render_minimal_form_html({"UPDATE_CHANNEL": "prerelease"})

        self.assertIn("Release channel", html)
        self.assertIn("name='UPDATE_CHANNEL'", html)
        self.assertIn("<option value='prerelease' selected>prerelease</option>", html)
        self.assertNotIn("UPDATE_BRANCH", html)
        self.assertNotIn("Update branch", html)

    def test_minimal_current_values_defaults_update_channel_to_stable(self):
        old_config = sys.modules.get("config")
        sys.modules["config"] = types.SimpleNamespace()
        try:
            values = portal._current_values()
        finally:
            if old_config is None:
                sys.modules.pop("config", None)
            else:
                sys.modules["config"] = old_config

        self.assertEqual(values["UPDATE_CHANNEL"], "stable")
        self.assertNotIn("UPDATE_BRANCH", values)
```

If `sys` or `types` are not already imported in `tests/test_setup_portal_service.py`, add:

```python
import sys
import types
```

- [ ] **Step 2: Run focused tests and verify they fail**

Run:

```bash
python -m unittest tests.test_setup_portal_service.SetupPortalServiceTests.test_minimal_form_uses_update_channel_not_branch tests.test_setup_portal_service.SetupPortalServiceTests.test_minimal_current_values_defaults_update_channel_to_stable
```

Expected: failures because `_EDITABLE_FIELDS` still contains `UPDATE_BRANCH`.

- [ ] **Step 3: Update lightweight field list**

In `webportal/setup_portal_service.py`, replace:

```python
    ("UPDATE_BRANCH", "Update branch", "text", ()),
```

with:

```python
    ("UPDATE_CHANNEL", "Release channel", "select", ("stable", "prerelease")),
```

- [ ] **Step 4: Give `_current_values()` the right fallback default**

In `_current_values()`, inside the loop over `_EDITABLE_FIELDS`, keep the existing select default logic:

```python
        elif typ == "select" and choices:
            default = choices[0]
```

No additional code is needed because `("stable", "prerelease")` makes `"stable"` the default.

- [ ] **Step 5: Run focused tests and verify they pass**

Run:

```bash
python -m unittest tests.test_setup_portal_service.SetupPortalServiceTests.test_minimal_form_uses_update_channel_not_branch tests.test_setup_portal_service.SetupPortalServiceTests.test_minimal_current_values_defaults_update_channel_to_stable
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add webportal/setup_portal_service.py tests/test_setup_portal_service.py
git commit -m "feat: update minimal portal release channel"
```

## Task 3: Release Selection Helpers

**Files:**
- Modify: `core/updater.py`
- Test: `tests/test_updater_release.py`

- [ ] **Step 1: Create failing release selection tests**

Create `tests/test_updater_release.py` with this initial content:

```python
import json
import os
import shutil
import tempfile
import unittest

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

    def test_prerelease_channel_errors_when_no_prerelease_manifest_exists(self):
        requests = _Requests([_Response(data=[{"tag_name": "v1.0.0", "draft": False, "prerelease": True, "assets": []}])])

        with self.assertRaises(RuntimeError) as ctx:
            updater.resolve_release("prerelease", requests_module=requests)

        self.assertIn("No matching release", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
python -m unittest tests.test_updater_release.UpdaterReleaseSelectionTests
```

Expected: failures for missing `MANIFEST_ASSET_NAME`, `resolve_release()`, `latest_release_url()`, or `releases_url()`.

- [ ] **Step 3: Add release constants and URL helpers**

In `core/updater.py`, keep `REPO_OWNER`, `REPO_NAME`, and `GITHUB_API_BASE`. Add:

```python
MANIFEST_ASSET_NAME = "uhs-update-manifest.json"


def latest_release_url():
    return "%s/repos/%s/%s/releases/latest" % (GITHUB_API_BASE, REPO_OWNER, REPO_NAME)


def releases_url():
    return "%s/repos/%s/%s/releases" % (GITHUB_API_BASE, REPO_OWNER, REPO_NAME)
```

- [ ] **Step 4: Add asset and release selection helpers**

In `core/updater.py`, add:

```python
def _asset_download_url(release, asset_name=MANIFEST_ASSET_NAME):
    assets = release.get("assets", []) if isinstance(release, dict) else []
    for asset in assets:
        if asset.get("name") == asset_name:
            return asset.get("browser_download_url") or asset.get("url") or ""
    return ""


def _release_info(release, manifest_url):
    return {
        "tag": release.get("tag_name", ""),
        "name": release.get("name", "") or release.get("tag_name", ""),
        "manifest_url": manifest_url,
        "prerelease": bool(release.get("prerelease", False)),
    }


def resolve_release(channel="stable", requests_module=None, i18n=None):
    requests_module = requests_module or _requests
    if requests_module is None:
        raise RuntimeError("Missing requests module")

    normalized = str(channel or "stable").strip().lower()
    if normalized != "prerelease":
        release = _github_api_get_json(latest_release_url(), requests_module, i18n=i18n)
        manifest_url = _asset_download_url(release)
        if manifest_url:
            return _release_info(release, manifest_url)
        raise RuntimeError("No matching release manifest")

    releases = _github_api_get_json(releases_url(), requests_module, i18n=i18n)
    for release in releases:
        if release.get("draft"):
            continue
        if not release.get("prerelease"):
            continue
        manifest_url = _asset_download_url(release)
        if manifest_url:
            return _release_info(release, manifest_url)
    raise RuntimeError("No matching release manifest")
```

- [ ] **Step 5: Run release selection tests**

Run:

```bash
python -m unittest tests.test_updater_release.UpdaterReleaseSelectionTests
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add core/updater.py tests/test_updater_release.py
git commit -m "feat: resolve updater releases"
```

## Task 4: Manifest Validation and Safe File Installation

**Files:**
- Modify: `core/updater.py`
- Test: `tests/test_updater_release.py`

- [ ] **Step 1: Add failing manifest tests**

Append this test class to `tests/test_updater_release.py` before the `if __name__ == "__main__"` block:

```python
class UpdaterManifestInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_validate_manifest_rejects_unsafe_paths(self):
        manifest = {
            "version": "v1.2.3",
            "files": [
                {"path": "../config.py", "url": "https://example/config.py"},
                {"path": "/flash/config.py", "url": "https://example/config.py"},
            ],
            "delete": ["../old.py"],
        }

        with self.assertRaises(RuntimeError) as ctx:
            updater.validate_manifest(manifest)

        self.assertIn("unsafe path", str(ctx.exception))

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
```

- [ ] **Step 2: Run manifest tests and verify they fail**

Run:

```bash
python -m unittest tests.test_updater_release.UpdaterManifestInstallTests
```

Expected: failures for missing `validate_manifest()` and `install_manifest()`.

- [ ] **Step 3: Add path validation helpers**

In `core/updater.py`, add:

```python
def _safe_repo_path(path):
    text = str(path or "").replace("\\", "/").strip()
    if not text:
        raise RuntimeError("unsafe path")
    if text.startswith("/") or text.startswith("../") or "/../" in text or text.endswith("/.."):
        raise RuntimeError("unsafe path: %s" % text)
    if text == "config.py" or text.startswith("storage/") and text.endswith(".json"):
        raise RuntimeError("unsafe path: %s" % text)
    return text


def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise RuntimeError("Invalid manifest")
    files = manifest.get("files", [])
    deletes = manifest.get("delete", [])
    if not isinstance(files, list):
        raise RuntimeError("Invalid manifest files")
    if not isinstance(deletes, list):
        raise RuntimeError("Invalid manifest delete")
    validated_files = []
    for item in files:
        if not isinstance(item, dict):
            raise RuntimeError("Invalid manifest file")
        path = _safe_repo_path(item.get("path", ""))
        url = str(item.get("url", "")).strip()
        if not url:
            raise RuntimeError("Invalid manifest url")
        validated_files.append(
            {
                "path": path,
                "url": url,
                "size": item.get("size", None),
                "sha256": str(item.get("sha256", "") or ""),
            }
        )
    validated_delete = [_safe_repo_path(path) for path in deletes]
    return {
        "version": str(manifest.get("version", "") or ""),
        "channel": str(manifest.get("channel", "") or ""),
        "files": validated_files,
        "delete": validated_delete,
    }
```

- [ ] **Step 4: Add temp-file install helper**

In `core/updater.py`, add:

```python
def _replace_file(tmp_path, dest_path):
    try:
        os.remove(dest_path)
    except OSError:
        pass
    os.rename(tmp_path, dest_path)


def _download_to_temp(url, dest_path, requests_module, expected_size=None):
    tmp_path = dest_path + ".tmp"
    try:
        os.remove(tmp_path)
    except OSError:
        pass
    _download_to_file(url, tmp_path, requests_module)
    if expected_size is not None:
        try:
            if os.stat(tmp_path)[6] != int(expected_size):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                raise RuntimeError("size mismatch")
        except TypeError:
            pass
    _replace_file(tmp_path, dest_path)
```

- [ ] **Step 5: Add manifest installer**

In `core/updater.py`, add:

```python
def install_manifest(manifest, requests_module=None, progress_callback=None, dest_root="", i18n=None):
    requests_module = requests_module or _requests
    if requests_module is None:
        raise RuntimeError("Missing requests module")
    clean = validate_manifest(manifest)
    files = clean["files"]
    total = len(files)
    ok = 0
    failed = 0
    for index, item in enumerate(files, 1):
        percent = int((index * 100) / total) if total else 100
        _emit(progress_callback, "download", _t(i18n, "updater.downloading", "Downloading"), item["path"], index, total, percent)
        dest_path = _path_join(dest_root, item["path"]) if dest_root else item["path"]
        parent = dest_path.rsplit("/", 1)[0] if "/" in dest_path else ""
        if parent:
            _ensure_dir(parent)
        try:
            _download_to_temp(item["url"], dest_path, requests_module, expected_size=item.get("size"))
            ok += 1
        except Exception:
            failed += 1
            try:
                os.remove(dest_path + ".tmp")
            except OSError:
                pass
        gc.collect()
    if failed:
        raise RuntimeError("Update finished with %d failures" % failed)
    for repo_path in clean["delete"]:
        path = _path_join(dest_root, repo_path) if dest_root else repo_path
        try:
            os.remove(path)
        except OSError:
            pass
    return {"ok": ok, "failed": failed, "total": total, "version": clean.get("version", "")}
```

- [ ] **Step 6: Run manifest tests and verify they pass**

Run:

```bash
python -m unittest tests.test_updater_release.UpdaterManifestInstallTests
```

Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add core/updater.py tests/test_updater_release.py
git commit -m "feat: install updater manifests safely"
```

## Task 5: Wire Main Updater Flow to Releases

**Files:**
- Modify: `core/updater.py`
- Modify: `apps/updater_app.py`
- Modify: `i18n/locales/en.py`
- Modify: `i18n/locales/fr.py`
- Test: `tests/test_updater_release.py`

- [ ] **Step 1: Add failing end-to-end updater test**

Append this test class to `tests/test_updater_release.py`:

```python
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
        with open(os.path.join(self.tmp, "apps", "demo.py"), "rb") as f:
            self.assertEqual(f.read(), b"demo = 1")
        self.assertEqual(events[-1]["stage"], "done")
```

- [ ] **Step 2: Run flow test and verify it fails**

Run:

```bash
python -m unittest tests.test_updater_release.UpdaterFlowTests
```

Expected: failure because `update()` still expects `branch` and scans repository files.

- [ ] **Step 3: Add manifest download helper**

In `core/updater.py`, add:

```python
def download_manifest(url, requests_module=None, i18n=None):
    requests_module = requests_module or _requests
    if requests_module is None:
        raise RuntimeError("Missing requests module")
    return _github_api_get_json(url, requests_module, i18n=i18n)
```

- [ ] **Step 4: Replace `update()` with release-based signature**

Change `core.updater.update()` to this signature and body:

```python
def update(
    channel="stable",
    progress_callback=None,
    requests_module=None,
    wifi_device=None,
    wifi_timeout_s=25,
    dest_root="",
    ensure_wifi=True,
    i18n=None,
):
    requests_module = requests_module or _requests
    if requests_module is None:
        raise RuntimeError("Missing requests module")

    channel = str(channel or "stable").strip().lower()
    if channel != "prerelease":
        channel = "stable"
    dest_root = str(dest_root or "").strip()
    if dest_root in (".", "/"):
        dest_root = ""

    if ensure_wifi:
        _ensure_wifi(wifi_device, wifi_timeout_s, progress_callback, i18n=i18n)

    _emit(progress_callback, "release", _t(i18n, "updater.search_release", "Searching release"), channel, 0, 0, 0)
    release = resolve_release(channel, requests_module=requests_module, i18n=i18n)
    _emit(progress_callback, "manifest", _t(i18n, "updater.downloading_manifest", "Downloading manifest"), release.get("tag", ""), 0, 0, 0)
    manifest = download_manifest(release["manifest_url"], requests_module=requests_module, i18n=i18n)
    result = install_manifest(
        manifest,
        requests_module=requests_module,
        progress_callback=progress_callback,
        dest_root=dest_root,
        i18n=i18n,
    )
    _emit(
        progress_callback,
        "done",
        _t(i18n, "updater.install_done", "Installation complete"),
        _tf(i18n, "updater.files_count", "{0} file(s)", result.get("ok", 0)),
        result.get("ok", 0),
        result.get("total", 0),
        100,
    )
    return result
```

- [ ] **Step 5: Update `UpdaterApp` to pass channel**

In `apps/updater_app.py`, replace:

```python
                branch=self._update_branch(),
```

with:

```python
                channel=self._update_channel(),
```

Replace `_update_branch()` with:

```python
    def _update_channel(self):
        try:
            import config

            value = getattr(config, "UPDATE_CHANNEL", "stable")
        except Exception:
            value = "stable"
        value = str(value or "stable").strip().lower()
        if value != "prerelease":
            return "stable"
        return "prerelease"
```

- [ ] **Step 6: Add updater i18n strings**

In `i18n/locales/en.py`, under `updater`, add:

```python
        'search_release': 'Searching release',
        'downloading_manifest': 'Downloading manifest',
```

In `i18n/locales/fr.py`, under `updater`, add:

```python
        'search_release': 'Recherche de release',
        'downloading_manifest': 'Telechargement manifest',
```

- [ ] **Step 7: Run updater tests**

Run:

```bash
python -m unittest tests.test_updater_release
```

Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
git add core/updater.py apps/updater_app.py i18n/locales/en.py i18n/locales/fr.py tests/test_updater_release.py
git commit -m "feat: update from github releases"
```

## Task 6: Documentation and Full Regression

**Files:**
- Modify: `README.md`
- Modify: `INSTALLATION.MD`
- Test: existing full test suite

- [ ] **Step 1: Update documentation references**

In `README.md` and `INSTALLATION.MD`, replace descriptions saying the updater downloads from `UPDATE_BRANCH` or a Git branch with:

```markdown
The hidden updater downloads application files from the latest GitHub Release.
`UPDATE_CHANNEL = "stable"` installs the latest stable release. Set
`UPDATE_CHANNEL = "prerelease"` to allow updates from the newest pre-release.
The device never updates directly from branches.
```

- [ ] **Step 2: Search for stale branch updater references**

Run:

```bash
rg -n "UPDATE_BRANCH|Update branch|branch used by the hidden updater|downloads application files from GitHub branch" README.md INSTALLATION.MD config.py.example webportal i18n apps core tests
```

Expected: no hits except tests that explicitly assert old branch config is ignored, if such a test remains.

- [ ] **Step 3: Run targeted tests**

Run:

```bash
python -m unittest tests.test_updater_release tests.test_webportal_kegs tests.test_setup_portal_service tests.test_main_startup_routing
```

Expected: `OK`.

- [ ] **Step 4: Run full test suite**

Run:

```bash
python -m unittest discover -s tests
```

Expected: `OK`.

- [ ] **Step 5: Compile all Python files**

Run:

```bash
python -m compileall -q .
```

Expected: no output and exit code `0`.

- [ ] **Step 6: Commit docs and any final fixes**

```bash
git add README.md INSTALLATION.MD
git commit -m "docs: describe release-based updater"
```

## Self-Review

- Spec coverage: Tasks cover persistent `UPDATE_CHANNEL`, release-only selection, pre-release mode, manifest asset contract, temp-file install, portal/i18n/docs migration, and tests.
- Scope: This plan does not build CI release asset generation. It implements the device updater contract and documents the expected manifest. Add a later plan for automated release asset generation if desired.
- Placeholder scan: No `TBD`, `TODO`, or vague "handle later" steps remain.
- Type consistency: The plan consistently uses `UPDATE_CHANNEL`, `MANIFEST_ASSET_NAME`, `resolve_release()`, `download_manifest()`, `validate_manifest()`, `install_manifest()`, and `update(channel=...)`.

