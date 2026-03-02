# Ultimate Homebrewing Scale - Architecture

## Overview

Modular application architecture for M5Stack Dial with memory-optimized design.

## Architecture Diagram

```
main.py (Entry Point)
  ├─ Initialize M5Stack (once)
  ├─ Load i18n
  └─ Launch Launcher
        │
        ├─ apps/scale.py (Scale App)
        ├─ apps/grain_assistant.py (Grain Weighing)
        ├─ apps/hop_assistant.py (Hop Weighing)
        ├─ apps/keg_filler.py (Keg Filling)
        └─ apps/settings.py (Settings Menu)
```

## Directory Structure

```
UltimateHomebrewingScale/
├── main.py                     # Main entry point
├── launcher.py                 # Circular launcher UI
├── launcher_config.py          # Launcher configuration
├── config.py                   # Application configuration
│
├── apps/                       # Application modules
│   ├── __init__.py            # Package exports
│   ├── base_app.py            # Base application class
│   ├── scale.py               # Scale application
│   ├── grain_assistant.py     # Grain weighing assistant
│   ├── hop_assistant.py       # Hop weighing assistant
│   ├── keg_filler.py          # Keg filling automation
│   └── settings.py            # Settings menu
│
├── i18n/                       # Internationalization
│   ├── __init__.py            # I18n manager
│   ├── README.md              # i18n documentation
│   └── locales/
│       ├── en.py              # English translations
│       └── fr.py              # French translations
│
├── devices/                    # Hardware devices abstraction
│   ├── __init__.py
│   ├── scale.py               # CalibratedScale class
│   └── relay.py               # RelayController class (futur)
│
├── ui/                         # Reusable UI components
│   ├── __init__.py
│   └── weight_display.py      # WeightDisplay component
│
├── api/                        # Brewing software APIs
│   ├── __init__.py
│   ├── brewing_software_api.py  # Abstract base interface
│   └── brewfather_api.py        # Brewfather implementation
│
├── assets/                     # Resources
│   └── icons/                 # Application icons (58x58 PNG)
│       ├── Home.png
│       ├── Scale.png
│       ├── Malt.png
│       ├── Hop.png
│       ├── Keg.png
│       └── Parameters.png
│
└── ScaleCalibration/          # Calibration tools
    └── ScaleCalibrationWizard.py
```

## Application Pattern

All applications inherit from `BaseApp` and follow this pattern:

```python
from apps.base_app import BaseApp

class MyApp(BaseApp):
    def __init__(self, i18n=None):
        super().__init__(i18n)
        # Initialize app-specific state
    
    def create_ui(self):
        # Create LVGL/M5UI interface
        self.page = m5ui.M5Page(bg_c=0x000000)
        # ... create labels, buttons, etc.
        self.page.screen_load()
    
    def check_return_to_launcher(self):
        # Detect exit gesture (e.g., long press)
        return False
    
    def update(self):
        # Update app state every frame
        pass
    
    # run() and cleanup() inherited from BaseApp
```

## Execution Flow

### 1. Startup (`main.py`)

```python
M5.begin()              # Initialize hardware once
m5ui.init()             # Initialize UI library
i18n = I18n(language)   # Load translations
launcher = CircularLauncher(i18n)
launcher.run()          # Start launcher loop
```

### 2. App Launch (from launcher)

```python
launcher.hide()         # Hide launcher UI
app = ScaleApp(i18n)    # Create app with i18n
app.run()               # Run app loop
  ├─ create_ui()        # Create UI
  ├─ loop:
  │   ├─ M5.update()
  │   ├─ check_return_to_launcher()
  │   └─ update()
  └─ cleanup()          # Clean up resources
gc.collect()            # Free memory
launcher.show()         # Re-show launcher
```

### 3. Memory Management

- `gc.collect()` before/after app launches
- Apps clean up UI elements in `cleanup()`
- No persistent objects between apps
- Minimal object creation in loops

## BaseApp Class

Provides:
- ✅ Common initialization pattern
- ✅ i18n integration (`self.t()` method)
- ✅ Standard run loop
- ✅ Cleanup on exit
- ✅ Return to launcher mechanism

## Launcher Features

- Circular icon menu (configurable arc)
- Rotary encoder navigation
- Visual feedback (selection indicator)
- Audio feedback (beep on selection)
- i18n support for menu labels
- Memory-optimized (smooth animations)

## Key Design Principles

1. **Single Initialization**: M5Stack initialized once in `main.py`
2. **Memory Conscious**: Cleanup between apps, gc.collect()
3. **Modular**: Each app is independent
4. **Simple**: No complex frameworks, direct LVGL/M5UI usage
5. **i18n First**: All text translatable
6. **Return Pattern**: Apps can return to launcher

## Configuration Files

- **`config.py`** — API credentials, language
- **`launcher_config.py`** — Launcher appearance, menu items
- **`scale_calibration.json`** — Scale calibration data (runtime)

## Translation Keys

Apps use hierarchical keys:
- `launcher.*` — Launcher menu labels
- `scale.*` — Scale app strings
- `grain.*` — Grain assistant strings
- `hop.*` — Hop assistant strings
- `keg.*` — Keg filler strings
- `settings.*` — Settings menu strings
- `common.*` — Shared strings

## Testing

Each app can be tested standalone:

```python
# Standalone mode
exec(open('apps/scale.py').read())
exec(open('apps/grain_assistant.py').read())
# etc.
```

Production mode:

```python
# Via launcher
exec(open('main.py').read())
```

## Next Steps

- Implement scale integration in grain/hop assistants
- Add API data fetching
- Implement settings persistence
- Add return gesture (long press rotary)
- Memory profiling and optimization
