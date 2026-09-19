"""Named NVS namespaces, keys and accessors shared across the runtime.

Leaf module: `esp32` is imported inside the calls, nothing else is imported at
all, so the boot updater can use it while keeping its lazy-import discipline.

The key names used to be repeated as literals in devices/wifi.py,
storage/config_registry.py, updater/boot.py and runtime_watchdog.py, where a
typo in any copy silently read the wrong slot.

runtime_watchdog keeps its own reset-count reader on purpose: it treats an
undecodable blob as zero rather than as a byte value, so a corrupt counter can
never lock the application out. Do not route it through get_int().
"""

# UIFlow owns this namespace: the Wi-Fi credentials written by the M5 firmware
# and by the setup portal both live here.
UIFLOW_NAMESPACE = "uiflow"
WIFI_SSID_KEY = "ssid0"
WIFI_PASSWORD_KEY = "pswd0"

# Our own namespace.
APP_NAMESPACE = "uhs"
UPDATE_KEY = "update"
WATCHDOG_COUNT_KEY = "wdt_count"


def open_nvs(namespace):
    """Open a namespace. Raises when esp32/NVS is unavailable."""
    import esp32

    return esp32.NVS(namespace)


def get_text(nvs, key, max_len=128):
    if hasattr(nvs, "get_str"):
        try:
            return nvs.get_str(key) or ""
        except Exception:
            pass

    if hasattr(nvs, "get_blob"):
        try:
            buf = bytearray(max_len)
            size = nvs.get_blob(key, buf)
            if isinstance(size, int) and size >= 0:
                raw = bytes(buf[:size])
            else:
                raw = bytes(buf).split(b"\x00", 1)[0]
            try:
                return raw.decode("utf-8")
            except Exception:
                return raw.decode("latin-1")
        except Exception:
            pass

    return ""


def set_text(nvs, key, value):
    text = str(value or "")
    if hasattr(nvs, "set_str"):
        nvs.set_str(key, text)
        return
    if hasattr(nvs, "set_blob"):
        nvs.set_blob(key, text)
        return
    raise OSError("NVS string write API unavailable")


def get_int(nvs, key):
    if hasattr(nvs, "get_i32"):
        try:
            return int(nvs.get_i32(key))
        except Exception:
            pass

    if hasattr(nvs, "get_blob"):
        try:
            buf = bytearray(8)
            size = nvs.get_blob(key, buf)
            if isinstance(size, int) and size > 0:
                raw = bytes(buf[:size])
            else:
                raw = bytes(buf).split(b"\x00", 1)[0]
            if not raw:
                return 0
            try:
                return int(raw.decode("utf-8"))
            except Exception:
                return int(raw[0])
        except Exception:
            pass

    return 0


def set_int(nvs, key, value):
    ivalue = int(value)
    if hasattr(nvs, "set_i32"):
        nvs.set_i32(key, ivalue)
        return
    if hasattr(nvs, "set_blob"):
        nvs.set_blob(key, str(ivalue))
        return
    raise OSError("NVS integer write API unavailable")


def read_wifi_credentials():
    """Return (ssid, password) from NVS, or ("", "") when unreadable."""
    try:
        nvs = open_nvs(UIFLOW_NAMESPACE)
        ssid = get_text(nvs, WIFI_SSID_KEY, max_len=96)
        password = get_text(nvs, WIFI_PASSWORD_KEY, max_len=128)
        return ssid, password
    except Exception:
        return "", ""


def write_wifi_credentials(ssid, password):
    """Return (ok, error_text)."""
    try:
        nvs = open_nvs(UIFLOW_NAMESPACE)
        set_text(nvs, WIFI_SSID_KEY, ssid)
        set_text(nvs, WIFI_PASSWORD_KEY, password)
        nvs.commit()
        return True, ""
    except Exception as e:
        return False, str(e)


def read_update_flag(nvs=None):
    try:
        nvs = nvs or open_nvs(APP_NAMESPACE)
        return get_int(nvs, UPDATE_KEY) == 1
    except Exception:
        return False


def write_update_flag(requested, nvs=None):
    nvs = nvs or open_nvs(APP_NAMESPACE)
    set_int(nvs, UPDATE_KEY, 1 if requested else 0)
    nvs.commit()
