"""Read/validate/save config.py for the embedded setup portal."""

import os
import re

import nvs_store
from webportal.config_keys import EDITABLE_KEYS, EDITABLE_ORDER

_ASSIGN_RE = re.compile(r"^\s*([A-Z0-9_]+)\s*=\s*(.+?)\s*$")
_WIFI_KEYS = ("WIFI_SSID", "WIFI_PASSWORD")
# The portal's Battery checkbox is virtual: no BATTERY line is ever written to
# config.py, the box only drives the presence of WATCHDOG_TIMEOUT_MS.  A scale
# running on the M5Dial battery cannot be recovered by cutting the power, so it
# needs the watchdog; a mains-powered one does not, and a stuck watchdog there
# only adds reset loops.  Keeping a single source of truth in config.py leaves
# runtime_watchdog.py unaware of the checkbox.
_BATTERY_KEY = "BATTERY"
_WATCHDOG_KEY = "WATCHDOG_TIMEOUT_MS"
_BATTERY_WATCHDOG_TIMEOUT_MS = 15000
# Mirrors runtime_watchdog._MIN_TIMEOUT_MS: below this the watchdog ignores the
# setting, so the checkbox must read back as unchecked.
_MIN_WATCHDOG_TIMEOUT_MS = 5000
# Wi-Fi credentials and the update flag live in NVS; nvs_store owns the
# namespaces, the key names and the get/set fallbacks.
# Mirrors devices.scale.CALIBRATION_FILE; importing that module here would pull
# the hardware layer into the portal.
_CALIBRATION_FILE = "scale_calibration.json"


def resolve_config_path():
    candidates = ["/flash/config.py", "config.py"]
    for path in candidates:
        try:
            os.stat(path)
            return path
        except Exception:
            pass
    return "config.py"


def resolve_calibration_path():
    for path in ("/flash/" + _CALIBRATION_FILE, _CALIBRATION_FILE):
        try:
            os.stat(path)
            return path
        except Exception:
            pass
    return _CALIBRATION_FILE


def read_calibration_points(calibration_path=None):
    """Return the scale calibration points, or [] when there are none."""
    import json

    path = calibration_path or resolve_calibration_path()
    try:
        with open(path, "r") as f:
            data = json.load(f)
        points = data["scale"]["CalibrationPoints"]
    except Exception:
        return []
    return points if isinstance(points, list) else []


def write_calibration_points(points, calibration_path=None):
    import json

    path = calibration_path or resolve_calibration_path()
    try:
        with open(path, "w") as f:
            json.dump({"scale": {"CalibrationPoints": list(points)}}, f)
    except Exception:
        return False
    return True


def ensure_config_file(config_path=None):
    """Create config.py when it is missing, so a restore has a file to edit.

    A full firmware flash ships config.py.example only (build_runtime keeps the
    real config out of the image), and that is exactly when a restore runs.
    Seeding from the example also brings back the settings the portal does not
    expose, such as KEG_RELAY_IO.
    """
    path = config_path or resolve_config_path()
    try:
        os.stat(path)
        return path
    except Exception:
        pass

    try:
        with open(path + ".example", "r") as f:
            seed = f.read()
    except Exception:
        seed = ""
    with open(path, "w") as f:
        f.write(seed)
    return path


def _parse_literal(raw):
    value = raw.strip()
    if value == "True":
        return True
    if value == "False":
        return False
    if len(value) >= 2 and ((value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")):
        return value[1:-1]
    try:
        return int(value)
    except Exception:
        return value


def _has_control_characters(text):
    """True when a value cannot be written as a single config.py line."""
    for ch in text:
        if ch in ("\n", "\r", "\x00"):
            return True
    return False


def _format_literal(value, kind):
    if kind == "bool":
        return "True" if bool(value) else "False"
    if kind == "int":
        return str(int(value))
    text = str(value)
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    # A raw line break would end the assignment and turn the rest of the value
    # into config.py source. validate_payload already refuses one; escaping it
    # here means no other caller can corrupt the file either.
    text = text.replace("\r", "\\r").replace("\n", "\\n")
    return '"{}"'.format(text)


def _watchdog_timeout_in_text(src_text):
    """Return the active watchdog timeout, or None when the watchdog is off.

    Applies the same rules as runtime_watchdog: a commented-out line, a
    non-integer, or a value below the minimum all mean "disabled".
    """
    for line in src_text.splitlines():
        m = _ASSIGN_RE.match(line)
        if not m or m.group(1) != _WATCHDOG_KEY:
            continue
        value = _parse_literal(m.group(2))
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        if value < _MIN_WATCHDOG_TIMEOUT_MS:
            return None
        return value
    return None


def _apply_battery_to_text(src_text, on_battery):
    """Enable or disable the watchdog line according to the Battery checkbox."""
    if not on_battery:
        return remove_keys_from_text(src_text, (_WATCHDOG_KEY,))
    if _watchdog_timeout_in_text(src_text) is not None:
        # Keep a timeout the user tuned by hand instead of forcing the default:
        # the portal exposes no timeout field, so overwriting it here would give
        # no way to get that value back.
        return src_text
    # Drop any ignored value (too small, malformed) before appending a valid one
    # so the file never ends up with two competing assignments.
    out = remove_keys_from_text(src_text, (_WATCHDOG_KEY,))
    return "{}{} = {}\n".format(out, _WATCHDOG_KEY, _BATTERY_WATCHDOG_TIMEOUT_MS)


def _read_wifi_from_nvs():
    return nvs_store.read_wifi_credentials()


def wifi_credentials_ready():
    ssid, _password = _read_wifi_from_nvs()
    return bool(ssid)


def wifi_credentials_report():
    report = {
        "nvs_ssid": False,
        "config_path": "",
        "config_exists": False,
        "config_ssid": False,
        "error": "",
    }
    try:
        nvs_ssid, _nvs_password = _read_wifi_from_nvs()
        report["nvs_ssid"] = bool(nvs_ssid)
    except Exception as e:
        report["error"] = "nvs: {}".format(e)

    path = resolve_config_path()
    report["config_path"] = path
    try:
        text = read_config_text(config_path=path)
        report["config_exists"] = True
        for line in text.splitlines():
            m = _ASSIGN_RE.match(line)
            if m and m.group(1) == "WIFI_SSID":
                report["config_ssid"] = bool(_parse_literal(m.group(2)))
                break
    except Exception as e:
        if report["error"]:
            report["error"] += "; "
        report["error"] += "config: {}".format(e)
    return report


def _write_wifi_to_nvs(ssid, password):
    return nvs_store.write_wifi_credentials(ssid, password)


def is_update_requested():
    return nvs_store.read_update_flag()


def set_update_requested(requested):
    try:
        nvs_store.write_update_flag(requested)
        return True, ""
    except Exception as e:
        return False, str(e)


def read_config_text(config_path=None):
    path = config_path or resolve_config_path()
    with open(path, "r") as f:
        return f.read()


def _write_config_text(config_path, text):
    tmp = config_path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    try:
        os.remove(config_path)
    except Exception:
        pass
    os.rename(tmp, config_path)


def remove_keys_from_text(src_text, keys):
    if not keys:
        return src_text
    remove = set(keys)
    out = []
    for line in src_text.splitlines():
        m = _ASSIGN_RE.match(line)
        if m and m.group(1) in remove:
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def _migrate_config_wifi_to_nvs(path, values):
    ssid = values.get("WIFI_SSID") or ""
    if not ssid:
        return False
    password = values.get("WIFI_PASSWORD") or ""
    nvs_ok, _nvs_error = _write_wifi_to_nvs(ssid, password)
    if not nvs_ok:
        return False
    src = read_config_text(config_path=path)
    out = remove_keys_from_text(src, _WIFI_KEYS)
    if out != src:
        _write_config_text(path, out)
    return True


def load_current_values(config_path=None):
    path = config_path or resolve_config_path()
    text = read_config_text(config_path=path)
    values = {}

    for line in text.splitlines():
        m = _ASSIGN_RE.match(line)
        if not m:
            continue
        key = m.group(1)
        if key not in EDITABLE_KEYS:
            continue
        values[key] = _parse_literal(m.group(2))

    for key in EDITABLE_ORDER:
        spec = EDITABLE_KEYS[key]
        if key not in values:
            values[key] = spec.get("default")

    # Derived, never stored: the checkbox reflects the watchdog line itself.
    values[_BATTERY_KEY] = _watchdog_timeout_in_text(text) is not None

    # Source of truth for Wi-Fi credentials is NVS.
    nvs_ssid, nvs_password = _read_wifi_from_nvs()
    if nvs_ssid:
        values["WIFI_SSID"] = nvs_ssid
        values["WIFI_PASSWORD"] = nvs_password
        return values

    if values.get("WIFI_SSID") or "":
        _migrate_config_wifi_to_nvs(path, values)

    return values


def validate_payload(payload):
    clean = {}
    errors = {}

    for key, value in payload.items():
        spec = EDITABLE_KEYS.get(key)
        if not spec:
            continue

        kind = spec.get("type")
        if kind == "bool":
            if isinstance(value, bool):
                clean[key] = value
            elif isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in ("1", "true", "on", "yes"):
                    clean[key] = True
                elif lowered in ("0", "false", "off", "no", ""):
                    clean[key] = False
                else:
                    errors[key] = "invalid boolean"
            else:
                errors[key] = "invalid boolean"

        elif kind == "int":
            try:
                parsed = int(value)
            except Exception:
                errors[key] = "invalid integer"
                continue
            if "min" in spec and parsed < spec["min"]:
                errors[key] = "below minimum"
                continue
            if "max" in spec and parsed > spec["max"]:
                errors[key] = "above maximum"
                continue
            clean[key] = parsed

        elif kind == "enum":
            parsed = str(value)
            if parsed not in spec.get("choices", []):
                errors[key] = "invalid value"
                continue
            clean[key] = parsed

        elif kind == "str":
            parsed = str(value)
            max_len = spec.get("max_len")
            if max_len and len(parsed) > max_len:
                errors[key] = "too long"
                continue
            # A line break submitted through the portal, or carried by a
            # restored backup, would land verbatim in config.py and leave a
            # file that no longer imports: the device then boots without its
            # settings and the portal itself becomes unreachable.
            if _has_control_characters(parsed):
                errors[key] = "invalid characters"
                continue
            clean[key] = parsed

        else:
            errors[key] = "unsupported type"

    return len(errors) == 0, clean, errors


def apply_updates_to_text(src_text, updates):
    if not updates:
        return src_text

    lines = src_text.splitlines()
    out = []
    seen = {}

    for line in lines:
        m = _ASSIGN_RE.match(line)
        if m:
            key = m.group(1)
            if key in updates and key in EDITABLE_KEYS:
                spec = EDITABLE_KEYS[key]
                out.append("{} = {}".format(key, _format_literal(updates[key], spec.get("type"))))
                seen[key] = True
                continue
        out.append(line)

    for key in EDITABLE_ORDER:
        if key in updates and key not in seen:
            spec = EDITABLE_KEYS[key]
            out.append("{} = {}".format(key, _format_literal(updates[key], spec.get("type"))))

    return "\n".join(out) + "\n"


def save_updates(updates, config_path=None):
    path = config_path or resolve_config_path()
    ok, clean, errors = validate_payload(updates)
    if not ok:
        return False, errors

    file_updates = {}
    wifi_updates = {}
    # Pull the virtual key out before the file update so it is never written as
    # an assignment; None means the caller did not submit the checkbox at all.
    on_battery = clean.pop(_BATTERY_KEY, None)
    for key, value in clean.items():
        if key in _WIFI_KEYS:
            wifi_updates[key] = value
        else:
            file_updates[key] = value

    if wifi_updates:
        # Keep the current NVS value when only one field is provided.
        current_ssid, current_password = _read_wifi_from_nvs()
        next_ssid = wifi_updates.get("WIFI_SSID", current_ssid)
        next_password = wifi_updates.get("WIFI_PASSWORD", current_password)
        nvs_ok, nvs_error = _write_wifi_to_nvs(next_ssid, next_password)
        if not nvs_ok:
            return False, {
                "WIFI_SSID": "nvs write failed: {}".format(nvs_error),
                "WIFI_PASSWORD": "nvs write failed: {}".format(nvs_error),
            }
    src = read_config_text(config_path=path)
    out = apply_updates_to_text(src, file_updates)
    if wifi_updates:
        out = remove_keys_from_text(out, _WIFI_KEYS)
    # Last, so the watchdog line is decided on the fully updated file.
    if on_battery is not None:
        out = _apply_battery_to_text(out, on_battery)

    _write_config_text(path, out)
    return True, {}
