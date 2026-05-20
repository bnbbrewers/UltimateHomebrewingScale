"""
Persistent keg registry helpers.

The keg filler app owns the user flow. This module owns the small persistent
data contract for known kegs and stays free of UI and hardware imports.
"""

import json


KEG_FILE = "kegs.json"
ADD_KEG_ITEM = "Ajouter"


def _positive_float(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _valid_keg(entry):
    if not isinstance(entry, dict):
        return None

    name = entry.get("name")
    empty_weight_g = _positive_float(entry.get("empty_weight_g"))
    max_volume_l = _positive_float(entry.get("max_volume_l"))
    if not isinstance(name, str) or not name or empty_weight_g is None or max_volume_l is None:
        return None

    return {
        "name": name,
        "empty_weight_g": empty_weight_g,
        "max_volume_l": max_volume_l,
    }


def load_kegs(path=KEG_FILE):
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []

    if not isinstance(data, dict):
        return []

    entries = data.get("kegs")
    if not isinstance(entries, list):
        return []

    kegs = []
    for entry in entries:
        keg = _valid_keg(entry)
        if keg is not None:
            kegs.append(keg)
    return kegs


def save_kegs(path, kegs):
    try:
        with open(path, "w") as f:
            json.dump({"kegs": kegs}, f)
    except Exception:
        return False
    return True


def build_select_items(kegs, add_label=ADD_KEG_ITEM):
    return [keg["name"] for keg in kegs] + [add_label]


def default_keg_name(kegs):
    return "keg{}".format(len(kegs))


def append_keg(kegs, name, empty_weight_g, max_volume_l):
    new_kegs = list(kegs)
    new_kegs.append(
        {
            "name": name,
            "empty_weight_g": float(empty_weight_g),
            "max_volume_l": float(max_volume_l),
        }
    )
    return new_kegs
