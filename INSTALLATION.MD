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

## 3) Build/upload the application files

The custom firmware image is expected to include the application files. The old
standalone `install.py` bootstrap script is no longer part of the project.

## 4) Update the project from GitHub

Use the hidden updater app (`apps/updater_app.py`) when the device needs to pull
the latest files from GitHub. The updater:

- connects to Wi‑Fi using the same mechanism as `devices/wifi.py`:
  1. UIFlow NVS (`uiflow:ssid0/pswd0`)
  2. fallback `config.py` (`WIFI_SSID` / `WIFI_PASSWORD`)
- overwrites existing application files
- skips `*.md`, `.gitignore`, `firmware/`, `examples/` directories, and files
  `*.example` / names containing `example`
- downloads application files from the latest GitHub Release
- uses `UPDATE_CHANNEL = "stable"` for the latest stable release; set
  `UPDATE_CHANNEL = "prerelease"` to allow updates from the newest pre-release
- never updates directly from branches
- shows progress on screen and waits for OK before rebooting

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

