"""One description per app: what to import, how to name it, how it behaves.

Adding an app used to mean editing seven places: the import branch and the
known-id list in core/app_manager.py, its loading label and colour in the same
file, LAUNCHER_ITEMS in apps/launcher_app.py, the label map in
ui/launcher_screen.py, and the standby inhibition list in standby.py. They are
all derived from this table now, so an entry cannot half-exist.

Leaf module: it imports nothing, so core, apps, ui and standby can all read it
without inverting the layering or dragging anything onto the heap. Classes are
named, never imported here: creating an app must stay lazy.

Keys:
    module, cls        where the app class lives; imported on demand
    label              English fallback shown when i18n is unavailable
    i18n               translation key for that name
    color              accent colour, shared by the launcher and the loading
                       screen so the transition keeps the app's identity
    loading_i18n       optional override for the whole loading line
    loading_label      English fallback for that override
    icon, order        launcher entry; an app without them is not listed
    inhibits_standby   never deep-sleep while this app is active
"""

LAUNCHER = "launcher"
SCALE = "scale_app"
MALT = "malt_app"
HOP = "hop_app"
KEG = "keg_filler_app"
SETTINGS = "settings_app"
CALIBRATION_WIZARD = "scale_calibration_wizard_app"
UPDATER = "updater_app"

DEFAULT_COLOR = 0x333333

APPS = {
    LAUNCHER: {
        "module": "apps.launcher_app",
        "cls": "LauncherApp",
        "label": "Launcher",
        "color": DEFAULT_COLOR,
    },
    SCALE: {
        "module": "apps.scale_app",
        "cls": "ScaleApp",
        "label": "Scale",
        "i18n": "launcher.scale",
        "color": 0x00A8E8,
        "icon": "/flash/assets/icons/Scale.png",
        "order": 0,
    },
    MALT: {
        "module": "apps.malt_app",
        "cls": "GrainAssistantApp",
        "label": "Malt",
        "i18n": "launcher.malt",
        "color": 0xD4840A,
        "icon": "/flash/assets/icons/Malt.png",
        "order": 1,
    },
    HOP: {
        "module": "apps.hop_app",
        "cls": "HopAssistantApp",
        "label": "Hop",
        "i18n": "launcher.hop",
        "color": 0x388E3C,
        "icon": "/flash/assets/icons/Hop.png",
        "order": 2,
        # The hop flow downloads recipes before it can show anything, so the
        # transition says what the wait is for instead of naming the app.
        "loading_i18n": "recipe.loading_recipes",
        "loading_label": "Loading recipes...",
    },
    KEG: {
        "module": "apps.keg_filler_app",
        "cls": "KegFillerApp",
        "label": "Keg",
        "i18n": "launcher.keg",
        "color": 0x607D8B,
        "icon": "/flash/assets/icons/Keg.png",
        "order": 3,
    },
    SETTINGS: {
        "module": "apps.settings_app",
        "cls": "SettingsApp",
        "label": "Settings",
        "i18n": "launcher.settings",
        "color": 0x7E57C2,
        "icon": "/flash/assets/icons/Parameters.png",
        "order": 4,
    },
    CALIBRATION_WIZARD: {
        "module": "apps.scale_calibration_wizard_app",
        "cls": "ScaleCalibrationWizardApp",
        "label": "Calibration",
        "i18n": "scale_calibration.title",
        "color": 0x00897B,
        # Sleeping mid-calibration would lose the samples and leave the scale
        # with a half-written calibration file.
        "inhibits_standby": True,
    },
    UPDATER: {
        "module": "updater.update_app",
        "cls": "UpdaterApp",
        "label": "Updater",
        "i18n": "updater.title",
        "color": 0x1565C0,
        # A reboot during an install leaves an incomplete runtime on flash.
        "inhibits_standby": True,
    },
}


def is_known(app_id):
    return app_id in APPS


def spec(app_id):
    return APPS.get(app_id)


def module_name(app_id):
    entry = APPS.get(app_id)
    return entry["module"] if entry else None


def color(app_id):
    entry = APPS.get(app_id)
    return entry.get("color", DEFAULT_COLOR) if entry else DEFAULT_COLOR


def inhibits_standby(app_id):
    entry = APPS.get(app_id)
    return bool(entry.get("inhibits_standby")) if entry else False


def load_class(app_id):
    """Import the app module on demand and return its class.

    The module name is a string so that nothing here is imported at boot, and
    so that core.app_manager can evict the module again by that same name.
    """
    entry = APPS.get(app_id)
    if entry is None:
        return None
    module = __import__(entry["module"], None, None, ("*",))
    return getattr(module, entry["cls"])


def launcher_items():
    """The launcher entries, in wheel order.

    Each item carries its own translation key, so the launcher screen reads it
    from the item instead of keeping a second label-to-key table.
    """
    listed = [
        (entry["order"], app_id, entry)
        for app_id, entry in APPS.items()
        if "order" in entry
    ]
    listed.sort()
    return [
        {
            "label": entry["label"],
            "i18n": entry.get("i18n"),
            "icon": entry.get("icon", ""),
            "module": app_id,
            "color": entry.get("color", DEFAULT_COLOR),
            "order": order,
        }
        for order, app_id, entry in listed
    ]
