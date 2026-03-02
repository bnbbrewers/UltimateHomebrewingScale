"""
Ultimate Homebrewing Scale - Main Entry Point
M5Stack Dial - UIFlow2 / LVGL

Architecture mémoire
--------------------
Le launcher est chargé, affiché, puis COMPLÈTEMENT déchargé (instance + module
sys.modules) avant de lancer une app. Cela libère ~10-15 KB de bytecode Python
qui seraient sinon occupés pendant toute la durée de l'app (et pendant l'appel
HTTPS qui nécessite de la mémoire contiguë pour mbedTLS).

Flux :
  while True:
      charger   ui.launcher → CircularLauncher → run() → module_name
      détruire  launcher.cleanup() + del + sys.modules + gc.collect()
      lancer    app(module_name).run()
      détruire  app.cleanup() + del + gc.collect()
"""

import gc
import sys
import M5
from M5 import *
import m5ui

try:
    import config
    DEBUG = getattr(config, 'DEBUG', False)
except Exception:
    DEBUG = False

gc.collect()

if DEBUG:
    print("=" * 50)
    print("Ultimate Homebrewing Scale")
    print("=" * 50)

# Initialize M5Stack hardware (once for all)
M5.begin()
m5ui.init()

# i18n
i18n_instance = None
try:
    from i18n import I18n
    language = getattr(config, 'LANGUAGE', 'en')
    i18n_instance = I18n(language)
    if DEBUG:
        print(f"Language: {language}")
except Exception as e:
    if DEBUG:
        print(f"Warning: i18n failed ({e})")

gc.collect()


# ---------------------------------------------------------------------------
# App runner
# ---------------------------------------------------------------------------

def _run_app(module_name):
    """Import, run, then destroy the requested app."""
    if DEBUG:
        print(f"[APP] importing {module_name}...")
    app = None
    try:
        if module_name == 'scale':
            from apps.scale import ScaleApp
            app = ScaleApp(i18n=i18n_instance)
        elif module_name == 'grain_assistant':
            from apps.grain_assistant import GrainAssistantApp
            app = GrainAssistantApp(i18n=i18n_instance)
        elif module_name == 'hop_assistant':
            from apps.hop_assistant import HopAssistantApp
            app = HopAssistantApp(i18n=i18n_instance)
        elif module_name == 'keg_filler':
            from apps.keg_filler import KegFillerApp
            app = KegFillerApp(i18n=i18n_instance)
        elif module_name == 'settings':
            from apps.settings import SettingsApp
            app = SettingsApp(i18n=i18n_instance)
        else:
            if DEBUG:
                print(f"Unknown module: {module_name}")
            return

        if app:
            if DEBUG:
                print(f"[APP] running {module_name}...")
            app.run()

    except KeyboardInterrupt:
        # In MicroPython, KeyboardInterrupt IS a subclass of Exception so it
        # would be silently swallowed by the block below – re-raise explicitly.
        raise
    except Exception as e:
        if DEBUG:
            print(f"App error ({module_name}): {e}")
            sys.print_exception(e)
    finally:
        if app:
            try:
                app.cleanup()
            except Exception:
                pass
        del app
        gc.collect()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
# The outer try/except is the single authoritative KeyboardInterrupt handler.
# Inner code (launcher, apps) may also have try/except blocks; in MicroPython
# KeyboardInterrupt IS a subclass of Exception and can be silently swallowed.
# The outer handler is the guaranteed backstop regardless of what the inner
# code does with the interrupt.
# ---------------------------------------------------------------------------

try:
    while True:
        # -- Load and run launcher -------------------------------------------
        launcher  = None
        selected_module = None
        try:
            from ui.launcher import CircularLauncher
            launcher = CircularLauncher(i18n_instance=i18n_instance)
            selected_module = launcher.run()
        except Exception as e:
            if DEBUG:
                print(f"Launcher error: {e}")
                sys.print_exception(e)

        # -- Destroy launcher and unload its module from sys.modules ---------
        try:
            if launcher:
                launcher.cleanup()
        except Exception:
            pass
        del launcher

        _remove = [k for k in sys.modules if k in ('ui.launcher', 'ui.launcher_config')]
        for k in _remove:
            del sys.modules[k]
        del _remove

        gc.collect()

        if DEBUG:
            print(f"[MEM] launcher unloaded – free={gc.mem_free()}  module={selected_module}")

        # If the launcher returned without a selection (Ctrl+C or error),
        # exit – no point restarting the launcher endlessly.
        if not selected_module:
            break

        # -- Run the selected app --------------------------------------------
        _run_app(selected_module)

        gc.collect()

except KeyboardInterrupt:
    pass   # clean exit – UIFlow2 / REPL takes control

if DEBUG:
    print("Scale stopped.")
