"""Serialize the whole device configuration to a single restorable text file.

The format is line based rather than JSON so the file stays readable and
hand-editable, and so restoring needs no json import on the parse path.  It is
also compact once percent-encoded into a form field, which matters because the
setup portal caps a request body at MAX_REQUEST_BODY_BYTES.
"""

BACKUP_VERSION = 1
BACKUP_HEADER = "UHS-BACKUP {}".format(BACKUP_VERSION)
BACKUP_FILENAME = "uhs-backup.txt"
# The keg name comes last so a "|" typed into it cannot be read as a separator.
_KEG_PREFIX = "KEG="
_CALIB_PREFIX = "CALIB="
_CALIB_FIELDS = ("calibration_point", "weight", "adc_average", "step")


def _format_value(value):
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def build_backup_text(values, kegs=None, calibration=None):
    lines = [BACKUP_HEADER]
    for key in sorted(values or {}):
        lines.append("{}={}".format(key, _format_value(values[key])))
    for keg in kegs or []:
        lines.append("{}{}|{}|{}".format(
            _KEG_PREFIX,
            float(keg.get("empty_weight_g", 0)),
            float(keg.get("max_volume_l", 0)),
            keg.get("name", ""),
        ))
    for point in calibration or []:
        lines.append(_CALIB_PREFIX + "|".join(
            str(point.get(field, 0)) for field in _CALIB_FIELDS))
    return "\n".join(lines) + "\n"


def parse_backup_text(text):
    """Return (ok, {"values", "kegs", "calibration"}, error).

    Values are kept verbatim after the first "=": a Wi-Fi password may legally
    end with a space. Lines that do not parse are dropped rather than failing
    the whole restore, so one bad keg cannot cost the user their settings.
    """
    lines = [line for line in str(text or "").replace("\r\n", "\n").split("\n")
             if line.strip()]
    if not lines or lines[0].strip() != BACKUP_HEADER:
        return False, None, "bad header"

    values = {}
    kegs = []
    calibration = []
    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith(_KEG_PREFIX):
            keg = _parse_keg(stripped[len(_KEG_PREFIX):])
            if keg is not None:
                kegs.append(keg)
            continue
        if stripped.startswith(_CALIB_PREFIX):
            point = _parse_calibration_point(stripped[len(_CALIB_PREFIX):])
            if point is not None:
                calibration.append(point)
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value
    return True, {"values": values, "kegs": kegs, "calibration": calibration}, ""


def _parse_number(raw):
    try:
        return int(raw)
    except Exception:
        return float(raw)


def _parse_calibration_point(raw):
    parts = raw.split("|")
    if len(parts) != len(_CALIB_FIELDS):
        return None
    try:
        numbers = [_parse_number(part) for part in parts]
    except Exception:
        return None
    return dict(zip(_CALIB_FIELDS, numbers))


def _parse_keg(raw):
    parts = raw.split("|", 2)
    if len(parts) != 3:
        return None
    try:
        empty_weight_g = float(parts[0])
        max_volume_l = float(parts[1])
    except Exception:
        return None
    name = parts[2].strip()
    if not name or empty_weight_g <= 0 or max_volume_l <= 0:
        return None
    return {
        "name": name,
        "empty_weight_g": empty_weight_g,
        "max_volume_l": max_volume_l,
    }


def collect_backup_text(config_path=None, kegs_path=None, calibration_path=None):
    """Read everything a restore needs back: settings, Wi-Fi, kegs, calibration."""
    from storage import config_registry, keg_registry

    return build_backup_text(
        config_registry.load_current_values(config_path=config_path),
        kegs=keg_registry.load_kegs(kegs_path or keg_registry.KEG_FILE),
        calibration=config_registry.read_calibration_points(
            calibration_path=calibration_path),
    )


def apply_backup_text(text, config_path=None, kegs_path=None, calibration_path=None):
    """Write a parsed backup back to the device.

    Kegs and calibration are only written when the backup carries them, so a
    hand-trimmed file cannot silently wipe what the device already holds.
    """
    from storage import config_registry, keg_registry

    ok, payload, error = parse_backup_text(text)
    if not ok:
        return False, error

    path = config_registry.ensure_config_file(config_path=config_path)
    saved, errors = config_registry.save_updates(payload["values"], config_path=path)
    if not saved:
        return False, errors

    if payload["kegs"]:
        if not keg_registry.save_kegs(kegs_path or keg_registry.KEG_FILE,
                                      payload["kegs"]):
            return False, "keg save error"

    if payload["calibration"]:
        if not config_registry.write_calibration_points(
                payload["calibration"], calibration_path=calibration_path):
            return False, "calibration save error"

    return True, ""


