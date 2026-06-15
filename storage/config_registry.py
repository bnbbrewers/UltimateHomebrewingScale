"""Read/validate/save config.py for the embedded setup portal."""

import os
import re

from webportal.config_keys import EDITABLE_KEYS, EDITABLE_ORDER

_ASSIGN_RE = re.compile(r"^\s*([A-Z0-9_]+)\s*=\s*(.+?)\s*$")
_WIFI_KEYS = ("WIFI_SSID", "WIFI_PASSWORD")
_NVS_NAMESPACE = "uiflow"
_NVS_WIFI_SSID_KEY = "ssid0"
_NVS_WIFI_PASSWORD_KEY = "pswd0"
_APP_NVS_NAMESPACE = "uhs"
_NVS_UPDATE_KEY = "update"


def _nvs_get_text(nvs, key, max_len=128):
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


def _nvs_set_text(nvs, key, value):
    text = str(value or "")
    if hasattr(nvs, "set_str"):
        nvs.set_str(key, text)
        return
    if hasattr(nvs, "set_blob"):
        nvs.set_blob(key, text)
        return
    raise OSError("NVS string write API unavailable")


def _nvs_get_int(nvs, key):
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


def _nvs_set_int(nvs, key, value):
    ivalue = int(value)
    if hasattr(nvs, "set_i32"):
        nvs.set_i32(key, ivalue)
        return
    if hasattr(nvs, "set_blob"):
        nvs.set_blob(key, str(ivalue))
        return
    raise OSError("NVS integer write API unavailable")


def resolve_config_path():
    candidates = ["/flash/config.py", "config.py"]
    for path in candidates:
        try:
            os.stat(path)
            return path
        except Exception:
            pass
    return "config.py"


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


def _format_literal(value, kind):
    if kind == "bool":
        return "True" if bool(value) else "False"
    if kind == "int":
        return str(int(value))
    text = str(value)
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    return '"{}"'.format(text)


def _read_wifi_from_nvs():
    try:
        import esp32

        nvs = esp32.NVS(_NVS_NAMESPACE)
        ssid = _nvs_get_text(nvs, _NVS_WIFI_SSID_KEY, max_len=96)
        password = _nvs_get_text(nvs, _NVS_WIFI_PASSWORD_KEY, max_len=128)
        return ssid, password
    except Exception:
        return "", ""


def wifi_credentials_ready():
    ssid, _password = _read_wifi_from_nvs()
    return bool(ssid)


def _write_wifi_to_nvs(ssid, password):
    try:
        import esp32

        nvs = esp32.NVS(_NVS_NAMESPACE)
        _nvs_set_text(nvs, _NVS_WIFI_SSID_KEY, ssid)
        _nvs_set_text(nvs, _NVS_WIFI_PASSWORD_KEY, password)
        nvs.commit()
        return True, ""
    except Exception as e:
        return False, str(e)


def is_update_requested():
    try:
        import esp32

        nvs = esp32.NVS(_APP_NVS_NAMESPACE)
        return _nvs_get_int(nvs, _NVS_UPDATE_KEY) == 1
    except Exception:
        return False


def set_update_requested(requested):
    try:
        import esp32

        nvs = esp32.NVS(_APP_NVS_NAMESPACE)
        _nvs_set_int(nvs, _NVS_UPDATE_KEY, 1 if requested else 0)
        nvs.commit()
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

    _write_config_text(path, out)
    return True, {}
