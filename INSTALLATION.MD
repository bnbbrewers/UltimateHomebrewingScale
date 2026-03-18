# Installation (M5Dial / UIFlow2)

This project is designed to run on an **M5Stack Dial (M5Dial)** with **UIFlow2 firmware**.

## 1) Flash the latest UIFlow2 firmware

- Install/launch **M5Burner**.
- Flash the **latest UIFlow2 firmware** for M5Dial.
- Boot the device and **configure Wi‑Fi** (so SSID/password are stored in UIFlow NVS).

## 2) Open UIFlow2 and upload the installer

- Open **UIFlow2**.
- Create/open a project for your M5Dial.
- Copy the repository’s `install.py` content into the device (UIFlow2 file editor).
- Save it on the device as `install.py` (at the filesystem root).

## 3) Install the project from GitHub

Open the UIFlow2 **console / REPL** and run:

```python
import install
install.run(branch="main")
```

Notes:
- The installer connects to Wi‑Fi using the same mechanism as `devices/wifi.py` (UIFlow NVS `ssid0/pswd0`).
- Existing files are **overwritten**.
- The installer skips `*.md`, `*.example`, anything containing `example` in the filename, `examples/` directories, and `.gitignore`.

To install another branch:

```python
import install
install.run(branch="your-branch-name")
```

## 4) Create your `config.py`

- Copy `config.py.example` to `config.py` on the device.
- Edit `config.py` and set at least:
  - `BREWFATHER_USER_ID`
  - `BREWFATHER_API_KEY`
  - `LANGUAGE` (optional)

## 5) Calibrate the scale

- Run the calibration wizard from the device (UIFlow2 console):

```python
from ScaleCalibration import ScaleCalibrationWizard as wiz
wiz.setup()
while True:
    wiz.loop()
```

- Follow the on-screen instructions and ensure the calibration file is saved.

## 6) Restart and run

- Reboot the M5Dial.
- The application entrypoint is `main.py`.

