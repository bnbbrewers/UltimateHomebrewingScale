import gc
import os

from . import http_client


VERSION_FILE = "uhs-version.txt"
ARCHIVE_TMP = "uhs-update.tar.tmp"
ARCHIVE_PATH = "uhs-update.tar"


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


def _ensure_wifi(wifi_device, timeout_s, progress_callback, i18n=None):
    if wifi_device is None:
        return
    _emit(progress_callback, "wifi", _t(i18n, "updater.wifi_connecting", "Connecting Wi-Fi"), "", 0, 0, 0)
    if hasattr(wifi_device, "ensure_connected"):
        if wifi_device.ensure_connected(timeout_s=timeout_s):
            return
        raise RuntimeError("WiFi connect timeout")
    start = http_client.ticks_ms()
    while True:
        wifi_device.tick()
        wlan = getattr(wifi_device, "_wlan", None)
        if wlan is not None and hasattr(wlan, "isconnected") and wlan.isconnected():
            return
        if getattr(wifi_device, "_failed", False):
            raise RuntimeError("WiFi connect failed")
        if http_client.ticks_diff(http_client.ticks_ms(), start) > int(timeout_s * 1000):
            raise RuntimeError("WiFi connect timeout")
        try:
            import time

            time.sleep_ms(20)
        except Exception:
            import time

            time.sleep(0.02)


def _safe_path(path):
    text = str(path or "").replace("\\", "/").strip()
    if not text or text in (".", ".."):
        raise RuntimeError("unsafe path")
    if len(text) >= 2 and text[1] == ":":
        raise RuntimeError("unsafe path: %s" % text)
    if text.startswith("/") or text.startswith("../") or "/../" in text or text.endswith("/.."):
        raise RuntimeError("unsafe path: %s" % text)
    for segment in text.split("/"):
        if segment in (".", ".."):
            raise RuntimeError("unsafe path: %s" % text)
    if text == "config.py" or text.startswith("storage/") and text.endswith(".json"):
        raise RuntimeError("unsafe path: %s" % text)
    return text


def _join(root, path):
    if not root:
        return path
    if root.endswith("/") or root.endswith("\\"):
        root = root[:-1]
    if path.startswith("/") or path.startswith("\\"):
        path = path[1:]
    return root + "/" + path


def _version_path(dest_root):
    return _join(dest_root, VERSION_FILE) if dest_root else VERSION_FILE


def _read_local_version(dest_root):
    try:
        with open(_version_path(dest_root), "r") as f:
            return f.read().strip()
    except Exception:
        return ""


def _write_local_version(dest_root, version):
    with open(_version_path(dest_root), "w") as f:
        f.write(str(version or ""))
        f.write("\n")


def _validate_url(url):
    text = str(url or "").strip()
    if " " in text:
        raise RuntimeError("Invalid archive url")
    if text.startswith("http://") and len(text) > len("http://"):
        rest = text[len("http://") :]
        if rest and not rest.startswith("/"):
            return text
    if text.startswith("https://") and len(text) > len("https://"):
        rest = text[len("https://") :]
        if rest and not rest.startswith("/"):
            return text
    raise RuntimeError("Invalid archive url")


def _validate_size(size):
    if isinstance(size, bool):
        raise RuntimeError("Invalid archive size")
    if isinstance(size, int) and size >= 0:
        return size
    if isinstance(size, str) and size.strip().isdigit():
        return int(size.strip())
    raise RuntimeError("Invalid archive size")


def _validate_sha(digest):
    text = str(digest or "").strip().lower()
    if len(text) != 64:
        raise RuntimeError("Invalid archive sha256")
    for ch in text:
        if ch not in "0123456789abcdef":
            raise RuntimeError("Invalid archive sha256")
    return text


def _manifest_archive(manifest):
    if not isinstance(manifest, dict):
        raise RuntimeError("Invalid manifest")
    if manifest.get("strategy") != "tar-diff":
        raise RuntimeError("Unsupported update manifest strategy")
    archive = manifest.get("archive")
    if not isinstance(archive, dict):
        raise RuntimeError("Invalid update archive")
    return {
        "version": str(manifest.get("version", "") or ""),
        "base_version": str(manifest.get("base_version", "") or ""),
        "url": _validate_url(archive.get("url", "")),
        "size": _validate_size(archive.get("size", None)),
        "sha256": _validate_sha(archive.get("sha256", "")),
        "delete": manifest.get("delete", []),
    }


def _remove_file(path):
    try:
        os.remove(path)
    except Exception:
        pass


def _download_archive(url, req, size, sha):
    current = url
    _remove_file(ARCHIVE_TMP)
    _remove_file(ARCHIVE_PATH)
    for _ in range(5):
        r = http_client.get(req, current, stream=True)
        try:
            status = getattr(r, "status_code", None)
            if status is None:
                status = getattr(r, "status", None)
            if status in (301, 302, 303, 307, 308):
                location = http_client.response_header(r, "Location")
                if not location:
                    raise RuntimeError("Archive redirect missing Location")
                current = location
                continue
            if status != 200:
                raise RuntimeError("HTTP %s: %s" % (status, current))
            http_client.spool_response_to_file(
                r, ARCHIVE_TMP, require_stream=True
            )
            if os.stat(ARCHIVE_TMP)[6] != int(size):
                raise RuntimeError("archive size mismatch")
            http_client.close_response(r)
            r = None
            http_client.gc_hard(cycles=1, pause_ms=10)
            if _file_sha256(ARCHIVE_TMP) != sha:
                raise RuntimeError("archive sha256 mismatch")
            os.rename(ARCHIVE_TMP, ARCHIVE_PATH)
            return ARCHIVE_PATH
        finally:
            try:
                r.close()
            except Exception:
                pass
    raise RuntimeError("Archive redirect limit exceeded")


def _file_sha256(path):
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024)
            if not chunk:
                break
            digest.update(chunk)
            del chunk
    return digest.hexdigest().lower()


def _apply_deletes(paths, dest_root):
    if not isinstance(paths, list):
        raise RuntimeError("Invalid manifest delete")
    for path in paths:
        path = _safe_path(path)
        target = _join(dest_root, path) if dest_root else path
        try:
            os.remove(target)
        except OSError:
            pass


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
    requests_module = requests_module or http_client.default_requests_module()
    if requests_module is None:
        raise RuntimeError("Missing requests2 module")

    channel = str(channel or "stable").strip().lower()
    if channel != "prerelease":
        channel = "stable"
    dest_root = str(dest_root or "").strip()
    if dest_root in (".", "/"):
        dest_root = ""

    if ensure_wifi:
        _ensure_wifi(wifi_device, wifi_timeout_s, progress_callback, i18n=i18n)

    from . import github_release

    _emit(progress_callback, "release", _t(i18n, "updater.search_release", "Searching release"), channel, 0, 0, 0)
    selected = github_release.resolve_release(channel, requests_module=requests_module, i18n=i18n)
    http_client.snapshot("updater.workflow.after_resolve_release")
    http_client.gc_hard(cycles=1, pause_ms=10)
    http_client.snapshot("updater.workflow.after_resolve_release_gc")
    _emit(
        progress_callback,
        "manifest",
        _t(i18n, "updater.downloading_manifest", "Downloading manifest"),
        selected.get("tag", ""),
        0,
        0,
        0,
    )
    http_client.snapshot("updater.workflow.before_download_manifest")
    manifest = github_release.download_manifest(selected["manifest_url"], requests_module=requests_module, i18n=i18n)
    http_client.snapshot("updater.workflow.after_download_manifest")
    del selected
    http_client.gc_hard(cycles=1, pause_ms=10)
    http_client.snapshot("updater.workflow.after_manifest_gc")

    archive = _manifest_archive(manifest)
    del manifest
    http_client.gc_hard(cycles=1, pause_ms=10)
    base = archive["base_version"]
    local = _read_local_version(dest_root)
    if base and local != base:
        raise RuntimeError("Firmware update required: local={} base={}".format(local or "unknown", base))

    _emit(progress_callback, "archive", _t(i18n, "updater.downloading_archive", "Downloading update archive"), archive["version"], 0, 0, 0)
    tar_path = _download_archive(archive["url"], requests_module, archive["size"], archive["sha256"])
    http_client.snapshot("updater.workflow.after_archive_download")
    http_client.gc_hard(cycles=2, pause_ms=20)
    http_client.snapshot("updater.workflow.after_archive_download_gc")

    from . import tar_extract

    _emit(progress_callback, "extract", _t(i18n, "updater.installing", "Installing"), archive["version"], 0, 0, 0)
    ok = tar_extract.extract(tar_path, dest_root=dest_root, progress_callback=progress_callback, i18n=i18n)
    _apply_deletes(archive["delete"], dest_root)
    _write_local_version(dest_root, archive["version"])
    _remove_file(tar_path)
    result = {"ok": ok, "failed": 0, "total": ok, "version": archive["version"]}
    del archive
    gc.collect()
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
