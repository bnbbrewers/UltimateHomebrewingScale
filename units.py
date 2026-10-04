"""
Unit systems shared by the Dial apps, the screens and the setup portal.

Everything is stored and compared in metric: grams on the scale, in config.py,
in the calibration file and in kegs.json, litres for keg volumes, millilitres
for the spunding inertia. This module only converts for display, and parses
what the portal user typed back into those metric values. Switching systems
therefore never touches stored data.

The system comes from UNITS in config.py ("metric", "us" or "imperial"), read
once and cached, like LANGUAGE: it changes with a reboot. Every function also
takes an explicit ``system`` so it can be used and tested without a config.

Leaf module on purpose: apps must not import ui.weight_screen, which pulls in
lvgl/m5ui at module level and is evicted from sys.modules between apps, and the
portal must not pull in the core managers. This one is never evicted.
"""

METRIC = "metric"
US = "us"
IMPERIAL = "imperial"
SYSTEMS = (METRIC, US, IMPERIAL)

# Beer at pitching temperature. One value, used both to compute the fill
# target in grams and to render that weight back as a volume.
LIQUID_DENSITY = 1.005

GRAMS_PER_OZ = 28.349523125
GRAMS_PER_LB = 453.59237
# us and imperial share the pound and the ounce; the gallon and the fluid
# ounce are what tell them apart.
_LITRES_PER_GAL = {US: 3.785411784, IMPERIAL: 4.54609}
_ML_PER_FL_OZ = {US: 29.5735295625, IMPERIAL: 28.4130625}

# Readings within this band display as zero: load cell noise, not a weight.
ZERO_WEIGHT_DISPLAY_THRESHOLD_G = 1

# Keg volume picker, in the display unit:
# (default, minimum, maximum, step, decimals).
_KEG_VOLUME = {
    METRIC: (18.0, 0.5, 60.0, 0.5, 1),
    US: (5.0, 0.25, 15.0, 0.25, 2),
    IMPERIAL: (4.0, 0.25, 13.0, 0.25, 2),
}

_METRIC_CALIBRATION_POINTS_G = [0, 100, 500, 5000, 25000]
# 0, 4 oz, 1 lb, 10 lb, 50 lb: weights an imperial user actually owns.
_IMPERIAL_CALIBRATION_POINTS_G = [
    0,
    GRAMS_PER_OZ * 4,
    GRAMS_PER_LB,
    GRAMS_PER_LB * 10,
    GRAMS_PER_LB * 50,
]

_current = None


def _setting(name, default=None):
    import runtime_debug

    return runtime_debug.setting(name, default)


def current_system():
    """The configured system, read once; anything unknown is metric."""
    global _current
    if _current is None:
        try:
            value = _setting("UNITS", METRIC)
        except Exception:
            value = METRIC
        _current = value if value in SYSTEMS else METRIC
    return _current


def _resolve(system):
    if system is None:
        return current_system()
    return system if system in SYSTEMS else METRIC


def is_metric(system=None):
    return _resolve(system) == METRIC


def volume_l_to_weight_g(volume_l):
    return float(volume_l) * 1000.0 * LIQUID_DENSITY


# ── weights ────────────────────────────────────────────────────────

def _format_metric_weight(weight):
    abs_w = abs(weight)
    if abs_w <= ZERO_WEIGHT_DISPLAY_THRESHOLD_G:
        return "0 g"
    if abs_w >= 1000:
        if weight < 0:
            return "-{:.2f} kg".format(abs_w / 1000.0)
        return "{:.2f} kg".format(abs_w / 1000.0)
    g = int(round(abs_w))
    if weight < 0:
        return "-{} g".format(g)
    return "{} g".format(g)


def _imperial_weight_unit(abs_g, kind):
    """Brewfather's habit: hops in ounces, grain in pounds, anything else in
    ounces below a pound and pounds above."""
    if kind == "hop":
        return "oz", GRAMS_PER_OZ
    if kind == "grain" or abs_g >= GRAMS_PER_LB:
        return "lb", GRAMS_PER_LB
    return "oz", GRAMS_PER_OZ


def format_weight(weight_g, kind="auto", system=None):
    """A scale reading for the 40 pt value label.

    ``kind`` is "hop", "grain" or "auto"; metric ignores it.
    """
    if weight_g is None:
        return "---"
    if _resolve(system) == METRIC:
        return _format_metric_weight(weight_g)
    abs_w = abs(weight_g)
    unit, grams_per_unit = _imperial_weight_unit(abs_w, kind)
    if abs_w <= ZERO_WEIGHT_DISPLAY_THRESHOLD_G:
        return "0.00 " + unit
    text = "{:.2f}".format(abs_w / grams_per_unit)
    if weight_g < 0 and text != "0.00":
        text = "-" + text
    return "{} {}".format(text, unit)


def _compact_number(value, decimals):
    text = ("{:.%df}" % decimals).format(value)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def format_hop_amount(amount_g, system=None):
    """The quantity in a hop addition list line, without a space: "5g"."""
    a = float(amount_g)
    if _resolve(system) == METRIC:
        if abs(a - round(a)) < 0.05:
            return "{}g".format(int(round(a)))
        return _compact_number(a, 1) + "g"
    return _compact_number(a / GRAMS_PER_OZ, 2) + "oz"


# ── volumes ────────────────────────────────────────────────────────

def volume_unit(system=None):
    return "L" if _resolve(system) == METRIC else "gal"


def volume_l_to_display(volume_l, system=None):
    system = _resolve(system)
    if system == METRIC:
        return float(volume_l)
    return float(volume_l) / _LITRES_PER_GAL[system]


def volume_display_to_l(value, system=None):
    system = _resolve(system)
    if system == METRIC:
        return float(value)
    return float(value) * _LITRES_PER_GAL[system]


def format_volume(volume_l, decimals=2, system=None):
    system = _resolve(system)
    value = volume_l_to_display(volume_l, system)
    return ("{:.%df} {}" % decimals).format(value, volume_unit(system))


def keg_volume_settings(system=None):
    """(default, minimum, maximum, step, decimals) for the keg volume picker,
    all in the display unit."""
    return _KEG_VOLUME[_resolve(system)]


# ── scale calibration ──────────────────────────────────────────────

def calibration_points_g(system=None):
    if _resolve(system) == METRIC:
        return list(_METRIC_CALIBRATION_POINTS_G)
    return list(_IMPERIAL_CALIBRATION_POINTS_G)


def calibration_step_g(weight_g, system=None):
    """One dial notch while adjusting a reference weight."""
    if _resolve(system) == METRIC:
        return 1
    if weight_g < GRAMS_PER_LB - 0.01:
        return GRAMS_PER_OZ * 0.1
    return GRAMS_PER_LB * 0.01


def adjust_calibration_weight(weight_g, notches, system=None):
    """``weight_g`` moved by ``notches`` dial steps, kept on the display grid.

    Metric moves by whole grams, as it always has. Imperial snaps to the tenth
    of an ounce below a pound and to the hundredth of a pound above, so
    crossing the pound in either direction lands on a value the screen shows
    exactly.
    """
    system = _resolve(system)
    if system == METRIC:
        return weight_g + notches
    weight_g = weight_g + notches * calibration_step_g(weight_g, system)
    grid = calibration_step_g(weight_g, system)
    return round(weight_g / grid) * grid


def format_calibration_weight(weight_g, compact=False, system=None):
    sep = "" if compact else " "
    if _resolve(system) == METRIC:
        return "{}{}g".format(int(round(weight_g)), sep)
    # A pound reached by summing 0.1 oz notches lands a hair below 453.59 g.
    if weight_g < GRAMS_PER_LB - 0.01:
        return "{:.1f}{}oz".format(weight_g / GRAMS_PER_OZ, sep)
    return "{:.2f}{}lb".format(weight_g / GRAMS_PER_LB, sep)


# ── setup portal fields ────────────────────────────────────────────
#
# A setting kind maps to (metric unit, imperial unit, imperial decimals,
# grams-or-millilitres-or-litres per imperial unit). Metric fields keep the
# integer handling config_registry already does; only us/imperial convert.

def _imperial_spec(kind, system):
    if kind == "tolerance":
        return "oz", 1, GRAMS_PER_OZ, True
    if kind == "inertia":
        return "fl oz", 0, _ML_PER_FL_OZ[system], True
    if kind == "keg_weight":
        return "lb", 2, GRAMS_PER_LB, False
    if kind == "keg_volume":
        return "gal", 2, _LITRES_PER_GAL[system], False
    raise ValueError(kind)


_METRIC_UNITS = {"tolerance": "g", "inertia": "ml", "keg_weight": "g", "keg_volume": "L"}
_METRIC_STEPS = {"tolerance": "1", "inertia": "1", "keg_weight": "0.1", "keg_volume": "0.1"}


def setting_unit(kind, system=None):
    system = _resolve(system)
    if system == METRIC:
        return _METRIC_UNITS[kind]
    return _imperial_spec(kind, system)[0]


def setting_step(kind, system=None):
    system = _resolve(system)
    if system == METRIC:
        return _METRIC_STEPS[kind]
    decimals = _imperial_spec(kind, system)[1]
    if decimals == 0:
        return "1"
    return "0." + "0" * (decimals - 1) + "1"


def setting_to_text(kind, value, system=None):
    """The stored metric value as the portal shows it."""
    system = _resolve(system)
    if system == METRIC:
        return str(value)
    _unit, decimals, per_unit, _integer = _imperial_spec(kind, system)
    return ("{:.%df}" % decimals).format(float(value) / per_unit)


def setting_from_text(kind, text, system=None):
    """What the portal user typed, back to the stored metric value.

    Raises ValueError on anything that is not a number. Tolerances and the
    inertia are stored as whole grams/millilitres, keg values as floats.
    """
    system = _resolve(system)
    if system == METRIC:
        return int(text) if kind in ("tolerance", "inertia") else float(text)
    _unit, _decimals, per_unit, integer = _imperial_spec(kind, system)
    value = float(str(text).strip()) * per_unit
    if integer:
        return int(round(value))
    return value
