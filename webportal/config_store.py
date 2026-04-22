"""Read/validate/save config.py for web portal."""

import os
import re

from .config_keys import EDITABLE_KEYS, EDITABLE_ORDER

_ASSIGN_RE = re.compile(r"^\s*([A-Z0-9_]+)\s*=\s*(.+?)\s*$")


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


def read_config_text(config_path=None):
    path = config_path or resolve_config_path()
    with open(path, "r") as f:
        return f.read()


def load_current_values(config_path=None):
    text = read_config_text(config_path=config_path)
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

    src = read_config_text(config_path=path)
    out = apply_updates_to_text(src, clean)

    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(out)
    try:
        os.remove(path)
    except Exception:
        pass
    os.rename(tmp, path)
    return True, {}
