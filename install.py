"""
MicroPython installer for UltimateHomebrewingScale on M5Dial.

Downloads repository files from GitHub (given a branch) while preserving
the directory structure on the device. Skips:
 - Markdown files (*.md)
 - Firmware binaries folder (firmware/)
 - "examples" (directories named examples/, and files with "example" in name,
   and files ending with .example)

Usage (on device):
  import install
  install.run(branch="main")
"""

import gc
import os
import sys
import time

try:
    # On M5Dial UIFlow2, a `requests` module is provided.
    import requests
except Exception:
    requests = None

try:
    # If the project is already installed, reuse its WifiDevice.
    from devices.wifi import WifiDevice
except Exception:
    WifiDevice = None


REPO_OWNER = "bnbbrewers"
REPO_NAME = "UltimateHomebrewingScale"

GITHUB_API_BASE = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"


def _is_enomem(err):
    try:
        eno = getattr(err, "errno", None)
        if eno == 12:
            return True
        args = getattr(err, "args", ()) or ()
        if args and args[0] == 12:
            return True
        return "ENOMEM" in str(err)
    except Exception:
        return False


def _gc_hard(cycles=3, pause_ms=30):
    for _ in range(cycles):
        gc.collect()
        try:
            time.sleep_ms(pause_ms)
        except Exception:
            time.sleep(pause_ms / 1000.0)


def _path_join(a, b):
    if not a:
        return b
    if a.endswith("/"):
        a = a[:-1]
    if b.startswith("/"):
        b = b[1:]
    return a + "/" + b


def _ensure_dir(path):
    # MicroPython often lacks os.makedirs(exist_ok=True)
    parts = []
    p = path
    while p not in ("", "/", "."):
        parts.append(p)
        p = p.rsplit("/", 1)[0] if "/" in p else ""
    for d in reversed(parts):
        try:
            os.stat(d)
        except OSError:
            try:
                os.mkdir(d)
            except OSError:
                # Might be created concurrently or by previous step
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
    if name.endswith(".example"):
        return True
    if "example" in name:
        return True
    return False


def _should_download(repo_path):
    lp = repo_path.lower()
    if lp == ".gitignore":
        return False
    if "/firmware/" in lp or lp.startswith("firmware/") or lp.endswith("/firmware"):
        return False
    if lp.endswith(".md"):
        return False
    if _is_example_path(repo_path):
        return False
    if "/icons/origin/" in lp or lp.startswith("assets/icons/origin/"):
        return False
    return True


def _github_api_get_json(url, headers, retries=4):
    """
    Robust GitHub API GET for constrained MicroPython devices.
    Retries transient network/socket errors (e.g. OSError 16) and falls back to
    a no-header request when the requests port is limited.
    """
    last_err = None

    for attempt in range(retries):
        # Try with headers first, then without headers for compatibility.
        for use_headers in (True, False):
            r = None
            try:
                _gc_hard(cycles=2, pause_ms=20)
                if use_headers:
                    r = requests.get(url, headers=headers)
                else:
                    r = requests.get(url)

                status = getattr(r, "status_code", None)
                if status is None:
                    status = getattr(r, "status", None)
                if status != 200:
                    raise RuntimeError("HTTP %s: %s" % (status, url))
                data = r.json()
                _gc_hard(cycles=1, pause_ms=10)
                return data
            except TypeError as e:
                # Some embedded requests impls don't support headers=.
                last_err = e
                if use_headers:
                    continue
                break
            except OSError as e:
                last_err = e
                # ENOMEM needs a longer pause to let network/TLS buffers clear.
                if _is_enomem(e):
                    _gc_hard(cycles=3, pause_ms=80)
            finally:
                try:
                    if r is not None:
                        r.close()
                except Exception:
                    pass

        # Small backoff + GC helps release sockets/heap on microcontrollers.
        gc.collect()
        try:
            time.sleep_ms(200 + (attempt * 250))
        except Exception:
            time.sleep(0.2 + (attempt * 0.25))

    raise RuntimeError(
        "GitHub API request failed after %d attempts: %s err=%r"
        % (retries, url, last_err)
    )


def _list_repo_tree(branch, start_path=""):
    """
    Returns list of file paths (repo-relative) to download.
    Uses GitHub "contents" API, recursing directories.
    """
    if requests is None:
        raise RuntimeError("Missing urequests module on this firmware.")

    headers = {
        "User-Agent": "UHS-M5Dial-Installer",
        "Accept": "application/vnd.github+json",
        "Connection": "close",
    }

    files = []
    stack = [start_path]

    while stack:
        path = stack.pop()
        url = "%s/repos/%s/%s/contents/%s?ref=%s" % (
            GITHUB_API_BASE,
            REPO_OWNER,
            REPO_NAME,
            path,
            branch,
        )

        data = _github_api_get_json(url, headers)

        # When path points to a file, GitHub returns a dict; for dirs it returns a list
        if isinstance(data, dict):
            repo_path = data.get("path", path)
            if _should_download(repo_path):
                files.append(repo_path)
            del data
            continue

        for item in data:
            item_type = item.get("type")
            item_path = item.get("path", "")
            if not item_path:
                continue

            # Skip examples directories early to avoid scanning their content
            if item_type == "dir":
                dir_path = item_path + "/"
                if _is_example_path(dir_path):
                    continue
                if not _should_download(dir_path):
                    continue
                stack.append(item_path)
            elif item_type == "file":
                if _should_download(item_path):
                    files.append(item_path)
        del data
        _gc_hard(cycles=1, pause_ms=10)

    files.sort()
    return files


def _download_to_file(url, dest_path):
    # Stream to file to reduce RAM usage when supported by the requests port.
    try:
        r = requests.get(url, stream=True)
    except Exception:
        r = requests.get(url)
    try:
        status = getattr(r, "status_code", None)
        if status is None:
            status = getattr(r, "status", None)
        if status != 200:
            raise RuntimeError("HTTP %s: %s" % (r.status_code, url))

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
                # Last resort: buffer whole content in RAM
                f.write(getattr(r, "content", b""))
    finally:
        try:
            r.close()
        except Exception:
            pass


def _ensure_wifi(verbose=True, timeout_s=25):
    """
    Ensure Wi-Fi is connected using the project's WifiDevice logic.
    Uses UIFlow NVS credentials (ssid0/pswd0).
    """
    # Keep installer standalone: if WifiDevice isn't importable yet, use an
    # embedded version of the same logic as devices/wifi.py.
    if WifiDevice is None:
        wifi = _StandaloneWifiDevice(debug=verbose)
    else:
        wifi = WifiDevice(debug=verbose)
    start = time.ticks_ms()
    last_yield = 0
    if verbose:
        print("[install] WiFi: connecting (timeout=%ss)..." % timeout_s)
    while True:
        wifi.tick()
        # Yield to system
        now = time.ticks_ms()
        if time.ticks_diff(now, start) > int(timeout_s * 1000):
            raise RuntimeError("WiFi connect timeout (%ss)" % timeout_s)
        if time.ticks_diff(now, last_yield) > 50:
            last_yield = now
            time.sleep_ms(20)
        # Determine success/fail state without relying on private attrs (best effort)
        wlan = getattr(wifi, "_wlan", None)
        if wlan is not None and hasattr(wlan, "isconnected") and wlan.isconnected():
            if verbose:
                try:
                    print("[install] WiFi: connected ip=%s" % (wlan.ifconfig()[0],))
                except Exception:
                    print("[install] WiFi: connected")
            return
        if getattr(wifi, "_failed", False):
            raise RuntimeError("WiFi connect failed")


class _StandaloneWifiDevice:
    """
    Standalone copy of devices/wifi.py behavior, so install.py can run even
    before the repo is installed on the device.
    """

    def __init__(self, debug=False):
        self._debug = debug
        self._started = False
        self._done = False
        self._failed = False
        self._wlan = None
        self._last_log_ms = 0

    def tick(self):
        if self._done or self._failed:
            return
        if not self._started:
            self._start_connect()
            return
        if self._wlan is None:
            self._failed = True
            return
        if self._wlan.isconnected():
            self._done = True
            if self._debug:
                try:
                    print("[WiFi] Connected:", self._wlan.ifconfig()[0])
                except Exception:
                    print("[WiFi] Connected")
            return
        if self._debug:
            now = time.ticks_ms()
            if time.ticks_diff(now, self._last_log_ms) > 3000:
                self._last_log_ms = now
                print("[WiFi] Connecting...")

    def _start_connect(self):
        self._started = True
        try:
            import network

            self._wlan = network.WLAN(network.STA_IF)
            if self._wlan.isconnected():
                self._done = True
                if self._debug:
                    try:
                        print("[WiFi] Already connected:", self._wlan.ifconfig()[0])
                    except Exception:
                        print("[WiFi] Already connected")
                return
            if not self._wlan.active():
                self._wlan.active(True)
            ssid, pswd, source = _load_wifi_credentials()
            if not ssid:
                raise RuntimeError("missing WiFi SSID")
            self._wlan.connect(ssid, pswd)
            if self._debug:
                print("[WiFi] Background connect start ({}): {}".format(source, ssid))
        except Exception as e:
            self._failed = True
            if self._debug:
                print("[WiFi] Background connect failed:", e)


def _load_wifi_credentials():
    """
    Return (ssid, password, source) with priority:
    1) UIFlow NVS namespace "uiflow" keys "ssid0"/"pswd0"
    2) config.py keys WIFI_SSID / WIFI_PASSWORD (or WIFI_PSWD alias)
    """
    # 1) NVS credentials
    try:
        import esp32
        nvs = esp32.NVS("uiflow")
        ssid = nvs.get_str("ssid0")
        pswd = nvs.get_str("pswd0")
        if ssid:
            return ssid, pswd or "", "nvs"
    except Exception:
        pass

    # 2) config.py fallback (works if config.py already exists on device)
    try:
        import config
        ssid = getattr(config, "WIFI_SSID", "") or ""
        pswd = (
            getattr(config, "WIFI_PASSWORD", "")
            or getattr(config, "WIFI_PSWD", "")
            or ""
        )
        if ssid:
            return ssid, pswd, "config"
    except Exception:
        pass

    return "", "", "none"


def run(branch="main", verbose=True, wifi_timeout_s=25, dest_root=""):
    """
    Install/update the project on the device.

    Args:
      branch: git branch name (e.g. "main", "dev")
      verbose: print progress
      wifi_timeout_s: timeout for wifi connection
      dest_root: optional directory on device where files are installed (default: root)
    """
    if requests is None:
        raise RuntimeError("Missing requests module on this firmware.")

    _ensure_wifi(verbose=verbose, timeout_s=wifi_timeout_s)
    # Give network stack a short settle time before first TLS call.
    try:
        time.sleep_ms(300)
    except Exception:
        time.sleep(0.3)

    # Normalize dest root for MicroPython FS
    dest_root = dest_root.strip()
    if dest_root in ("", ".", "/"):
        dest_root = ""

    if dest_root:
        try:
            os.stat(dest_root)
        except OSError:
            _ensure_dir(dest_root)
            if verbose:
                print("[install] created dir:", dest_root)

    files = _list_repo_tree(branch=branch, start_path="")
    if verbose:
        print("[install] branch=%s files=%d dest_root=%s" % (branch, len(files), dest_root or "/"))

    ok = 0
    failed = 0
    for repo_path in files:
        raw_url = "%s/%s/%s/%s/%s" % (RAW_BASE, REPO_OWNER, REPO_NAME, branch, repo_path)
        dest_path = _path_join(dest_root, repo_path) if dest_root else repo_path
        if verbose:
            print("[install] (%d/%d) %s" % (ok + failed + 1, len(files), repo_path))
        try:
            _download_to_file(raw_url, dest_path)
            ok += 1
        except Exception as e:
            failed += 1
            if verbose:
                print("[install] FAILED:", repo_path, "err=", e)
        gc.collect()

    if verbose:
        print("[install] done ok=%d failed=%d" % (ok, failed))
    if failed:
        raise RuntimeError("Install finished with %d failures" % failed)


def _main_from_argv():
    # Best-effort CLI. On some MicroPython builds, sys.argv may exist.
    branch = "main"
    dest_root = ""
    verbose = True

    argv = getattr(sys, "argv", None) or []
    for a in argv[1:]:
        if a.startswith("--branch="):
            branch = a.split("=", 1)[1]
        elif a.startswith("--dest="):
            dest_root = a.split("=", 1)[1]
        elif a == "--quiet":
            verbose = False

    run(branch=branch, dest_root=dest_root, verbose=verbose)


if __name__ == "__main__":
    _main_from_argv()

