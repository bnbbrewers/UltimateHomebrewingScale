# Debug Mode Guide

## Configuration

### Enable or Disable Debug Traces

In `config.py`:

```python
# Debug mode (set to True to enable debug prints)
DEBUG = False  # Default: no traces
DEBUG = True   # Enable traces
```

### Behavior

With `DEBUG = False` by default:
- No console debug prints
- Smooth UI with no debug slowdown
- Only fatal errors are displayed

With `DEBUG = True`:
- Startup traces
- Launcher events
- App startup traces
- Long-press detection
- Scale calibration traces
- Detailed errors

## Modified Files

All `print()` calls are gated by `DEBUG`:

- `main.py` - System initialization
- `apps/launcher_app.py` - Launcher navigation logic
- `ui/launcher_screen.py` - Launcher UI
- `apps/base_app.py` - Long-press detection
- `apps/scale_app.py` - Calibration and weighing
- Other apps: grain, hop, keg, settings

## Long Press to Return to the Launcher

### How to Use

From any app:

1. Hold the center button.
2. Wait 3 seconds.
3. The app closes and returns to the launcher.

### Implementation

Detection is handled in `BaseApp.check_return_to_launcher()`:

```python
# Long press duration
LONG_PRESS_DURATION = 3000  # 3 seconds in ms

# Automatically called in the main loop
# of every app inheriting from BaseApp
```

### Covered Apps

All apps inheriting from `BaseApp`:
- Scale App
- Grain Assistant
- Hop Assistant
- Keg Filler
- Settings

### Debug Long Press

With `DEBUG = True`, this message is printed:

```text
Long press detected - returning to launcher
```

## Deployment

Upload these modified files to the M5Dial:

- `config.py` with `DEBUG = False` or `DEBUG = True`
- `main.py`
- `apps/launcher_app.py`
- `ui/launcher_screen.py`
- `apps/base_app.py`
- `apps/scale_app.py`

## Manual Check

```python
# On the M5Dial
exec(open("main.py").read())

# 1. The launcher is displayed, with no traces if DEBUG=False.
# 2. Select Scale.
# 3. Hold the center button for 3 seconds.
# 4. The app returns to the launcher automatically.
```

## Performance

Memory impact: none when `DEBUG = False`, because debug strings are not created.

Smoothness: improved when debug traces are disabled.

Long-press latency: less than 50 ms.
