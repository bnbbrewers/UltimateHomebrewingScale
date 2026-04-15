# Installation (M5Dial / UIFlow2)

This project is designed to run on an **M5Stack Dial (M5Dial)** with the custom UIFlow2 firmware included in this repository.

## 1) Flash the custom firmware

- Firmware path in this repo: `firmware/firmwareM5DialCustom.bin`
- Flash it to the M5Dial (example with esptool):

```bash
esptool.py --chip esp32s3 --port COM4 --baud 1500000 write_flash 0x0 firmware/firmwareM5DialCustom.bin
```

- Reboot the device.

## 2) Configure `config.py` (including Wi‑Fi fallback)

- Copy `config.py.example` to `config.py`.
- Fill at least:
  - `BREWFATHER_USER_ID`
  - `BREWFATHER_API_KEY`
  - `WIFI_SSID`
  - `WIFI_PASSWORD`
- `LANGUAGE` is optional (`en` or `fr`).

## 3) Open UIFlow2 and upload the installer

- Open **UIFlow2**.
- Create/open a project for your M5Dial.
- Copy the repository’s `install.py` content into the device (UIFlow2 file editor).
- Save it on the device as `install.py` (at the filesystem root).

## 4) Install the project from GitHub

Open the UIFlow2 **console / REPL** and run:

```python
import install
install.run(branch="main")
```

Notes:
- The installer connects to Wi‑Fi using the same mechanism as `devices/wifi.py`:
  1. UIFlow NVS (`uiflow:ssid0/pswd0`)
  2. fallback `config.py` (`WIFI_SSID` / `WIFI_PASSWORD`)
- Existing files are **overwritten**.
- The installer skips `*.md`, `.gitignore`, `firmware/`, `examples/` directories, and files `*.example` / names containing `example`.

To install another branch:

```python
import install
install.run(branch="your-branch-name")
```

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

