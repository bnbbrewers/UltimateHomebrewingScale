"""
Application updater for UltimateHomebrewingScale.

Downloads the GitHub repository files for a branch while preserving the device
directory structure. Progress is reported through a small callback dictionary so
the UI layer can stay separate from network/file operations.
"""

import gc
import os
import time

try:
    import requests as _requests
except Exception:
    _requests = None


REPO_OWNER = "bnbbrewers"
REPO_NAME = "UltimateHomebrewingScale"

GITHUB_API_BASE = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"

OBSOLETE_PATHS = ("install.py",)


def _t(i18n, key, fallback):
    if i18n:
        return i18n.t(key)
    return fallback


def _tf(i18n, key, fallback, *args):
    if i18n:
        return i18n.t(key, *args)
    return fallback.format(*args)


def _emit(callback, stage, message="", detail="", current=0, total=0, percent=0):
    if callback:
        callback(
            {
                "stage": stage,
                "message": message,
                "detail": detail,
                "current": current,
                "total": total,
                "percent": percent,
            }
        )


def _gc_hard(cycles=2, pause_ms=20):
    for _ in range(cycles):
        gc.collect()
        try:
            time.sleep_ms(pause_ms)
        except Exception:
            time.sleep(pause_ms / 1000.0)


def _ticks_ms():
    if hasattr(time, "ticks_ms"):
        return time.ticks_ms()
    return int(time.time() * 1000)


def _ticks_diff(a, b):
    if hasattr(time, "ticks_diff"):
        return time.ticks_diff(a, b)
    return a - b


def _path_join(a, b):
    if not a:
        return b
    if a.endswith("/") or a.endswith("\\"):
        a = a[:-1]
    if b.startswith("/") or b.startswith("\\"):
        b = b[1:]
    return a + "/" + b


def _ensure_dir(path):
    parts = []
    p = path
    while p not in ("", "/", ".", "\\"):
        parts.append(p)
        p = p.rsplit("/", 1)[0] if "/" in p else ""
    for d in reversed(parts):
        try:
            os.stat(d)
        except OSError:
            try:
                os.mkdir(d)
            except OSError:
                pass


def _basename(path):
    if not path:
        return ""
    return path.rsplit("/", 1)[-1]


def _is_example_path(repo_path):
    lp = repo_path.lower()
    name = _basename(lp)
    if "/examples/" in lp or lp.startswith("examples/") or lp.endswith("/examples"):
        return True
    if name.endswith(".example") and lp != "config.py.example":
        return True
    if "example" in name and lp != "config.py.example":
        return True
    return False


def should_download(repo_path):
    lp = repo_path.lower()
    if lp == "config.py.example":
        return True
    if lp == "license":
        return False
    if lp == ".gitignore":
        return False
    if "/firmware/" in lp or lp.startswith("firmware/") or lp.endswith("/firmware"):
        return False
    if "/docs/" in lp or lp.startswith("docs/") or lp.endswith("/docs"):
        return False
    if lp.endswith(".md"):
        return False
    if _is_example_path(repo_path):
        return False
    if "/icons/origin/" in lp or lp.startswith("assets/icons/origin/"):
        return False
    return True


def github_contents_url(branch, path):
    return "%s/repos/%s/%s/contents/%s?ref=%s" % (
        GITHUB_API_BASE,
        REPO_OWNER,
        REPO_NAME,
        path,
        branch,
    )


def raw_file_url(branch, repo_path):
    return "%s/%s/%s/%s/%s" % (RAW_BASE, REPO_OWNER, REPO_NAME, branch, repo_path)


def _github_api_get_json(url, requests_module, retries=4):
    headers = {
        "User-Agent": "UHS-M5Dial-Updater",
        "Accept": "application/vnd.github+json",
        "Connection": "close",
    }
    last_err = None
    for attempt in range(retries):
        for use_headers in (True, False):
            r = None
            try:
                _gc_hard(cycles=2, pause_ms=20)
                if use_headers:
                    r = requests_module.get(url, headers=headers)
                else:
                    r = requests_module.get(url)
                status = getattr(r, "status_code", None)
                if status is None:
                    status = getattr(r, "status", None)
                if status != 200:
                    raise RuntimeError("HTTP %s: %s" % (status, url))
                return r.json()
            except TypeError as e:
                last_err = e
                if use_headers:
                    continue
                break
            except OSError as e:
                last_err = e
                _gc_hard(cycles=3, pause_ms=80)
            finally:
                try:
                    if r is not None:
                        r.close()
                except Exception:
                    pass
        try:
            time.sleep_ms(200 + (attempt * 250))
        except Exception:
            time.sleep(0.2 + (attempt * 0.25))
    raise RuntimeError("GitHub API request failed: %s err=%r" % (url, last_err))


def list_repo_tree(branch, requests_module=None, progress_callback=None, i18n=None):
    requests_module = requests_module or _requests
    if requests_module is None:
        raise RuntimeError("Missing requests module")

    files = []
    stack = [""]
    while stack:
        path = stack.pop()
        data = _github_api_get_json(github_contents_url(branch, path), requests_module)
        if isinstance(data, dict):
            repo_path = data.get("path", path)
            if should_download(repo_path):
                files.append(repo_path)
            del data
            continue
        for item in data:
            item_type = item.get("type")
            item_path = item.get("path", "")
            if not item_path:
                continue
            if item_type == "dir":
                dir_path = item_path + "/"
                if _is_example_path(dir_path):
                    continue
                if not should_download(dir_path):
                    continue
                stack.append(item_path)
            elif item_type == "file" and should_download(item_path):
                files.append(item_path)
        _emit(progress_callback, "scan", _t(i18n, "updater.scan_repo", "Scanning repository"), path or "/", 0, 0, 0)
        del data
        _gc_hard(cycles=1, pause_ms=10)
    files.sort()
    return files


def _download_to_file(url, dest_path, requests_module):
    try:
        r = requests_module.get(url, stream=True)
    except TypeError:
        r = requests_module.get(url)
    try:
        status = getattr(r, "status_code", None)
        if status is None:
            status = getattr(r, "status", None)
        if status != 200:
            raise RuntimeError("HTTP %s: %s" % (status, url))

        parent = dest_path.rsplit("/", 1)[0] if "/" in dest_path else ""
        if parent:
            _ensure_dir(parent)

        with open(dest_path, "wb") as f:
            raw = getattr(r, "raw", None)
            if raw is not None and hasattr(raw, "read"):
                while True:
                    chunk = raw.read(1024)
                    if not chunk:
                        break
                    f.write(chunk)
            elif hasattr(r, "iter_content"):
                for chunk in r.iter_content(1024):
                    if chunk:
                        f.write(chunk)
            else:
                f.write(getattr(r, "content", b""))
    finally:
        try:
            r.close()
        except Exception:
            pass


def _ensure_wifi(wifi_device, timeout_s, progress_callback, i18n=None):
    if wifi_device is None:
        return
    _emit(progress_callback, "wifi", _t(i18n, "updater.wifi_connecting", "Connecting Wi-Fi"), "", 0, 0, 0)
    if hasattr(wifi_device, "ensure_connected"):
        if wifi_device.ensure_connected(timeout_s=timeout_s):
            return
        raise RuntimeError("WiFi connect timeout")
    start = _ticks_ms()
    while True:
        wifi_device.tick()
        wlan = getattr(wifi_device, "_wlan", None)
        if wlan is not None and hasattr(wlan, "isconnected") and wlan.isconnected():
            return
        if getattr(wifi_device, "_failed", False):
            raise RuntimeError("WiFi connect failed")
        if _ticks_diff(_ticks_ms(), start) > int(timeout_s * 1000):
            raise RuntimeError("WiFi connect timeout")
        try:
            time.sleep_ms(20)
        except Exception:
            time.sleep(0.02)


def _remove_obsolete(dest_root):
    for repo_path in OBSOLETE_PATHS:
        path = _path_join(dest_root, repo_path) if dest_root else repo_path
        try:
            os.remove(path)
        except OSError:
            pass


def update(
    branch="main",
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

    branch = str(branch or "main").strip() or "main"
    dest_root = str(dest_root or "").strip()
    if dest_root in (".", "/"):
        dest_root = ""

    if ensure_wifi:
        _ensure_wifi(wifi_device, wifi_timeout_s, progress_callback, i18n=i18n)

    _emit(progress_callback, "scan", _t(i18n, "updater.search_files", "Searching files"), branch, 0, 0, 0)
    files = list_repo_tree(
        branch,
        requests_module=requests_module,
        progress_callback=progress_callback,
        i18n=i18n,
    )
    total = len(files)

    ok = 0
    failed = 0
    for index, repo_path in enumerate(files, 1):
        percent = int((index * 100) / total) if total else 100
        _emit(
            progress_callback,
            "download",
            _t(i18n, "updater.downloading", "Downloading"),
            repo_path,
            index,
            total,
            percent,
        )
        raw_url = raw_file_url(branch, repo_path)
        dest_path = _path_join(dest_root, repo_path) if dest_root else repo_path
        try:
            _download_to_file(raw_url, dest_path, requests_module)
            ok += 1
        except Exception:
            failed += 1
        gc.collect()

    _remove_obsolete(dest_root)
    result = {"ok": ok, "failed": failed, "total": total}
    if failed:
        _emit(
            progress_callback,
            "error",
            _t(i18n, "updater.incomplete", "Update incomplete"),
            _tf(i18n, "updater.errors_count", "{0} error(s)", failed),
            ok,
            total,
            100,
        )
        raise RuntimeError("Update finished with %d failures" % failed)
    _emit(
        progress_callback,
        "done",
        _t(i18n, "updater.install_done", "Installation complete"),
        _tf(i18n, "updater.files_count", "{0} file(s)", ok),
        ok,
        total,
        100,
    )
    return result
