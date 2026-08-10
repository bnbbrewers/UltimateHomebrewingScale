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

The custom firmware image is expected to include the application files. Runtime
modules are compiled to `.mpy` bytecode during the GitHub Actions repack. The
entrypoint `main.py` and `config.py.example` remain source files; the local
`config.py` is never packaged. The old standalone `install.py` bootstrap script
is no longer part of the project.

## 4) Update the project from GitHub

Use the hidden updater app (`updater/update_app.py`) when the device needs to pull
the latest files from GitHub. The updater:

- connects to Wi‑Fi using the same mechanism as `devices/wifi.py`:
  1. UIFlow NVS (`uiflow:ssid0/pswd0`)
  2. fallback `config.py` (`WIFI_SSID` / `WIFI_PASSWORD`)
- downloads a compact TAR diff from the latest GitHub Release
- downloads compiled `.mpy` runtime modules rather than application `.py`
  sources
- extracts changed application files locally after closing the HTTPS response
- removes a same-path `.py` after installing its `.mpy`, only when that `.py`
  exists
- applies file deletions listed by the update manifest
- preserves `main.py`, `config.py.example`, and the private `config.py`
- requires the device app version to match the manifest `base_version`; otherwise
  install the full firmware image
- uses `UPDATE_CHANNEL = "stable"` for the latest stable release; set
  `UPDATE_CHANNEL = "prerelease"` to allow updates from the newest pre-release
- never updates directly from branches
- shows progress on screen and waits for OK before rebooting

The first release using `.mpy` includes all compiled runtime modules so devices
that still contain legacy `.py` sources can migrate. Later releases include only
changed `.mpy` files. An absent old `.py` is normal and is not an update error.

The runtime keeps the setup path light: on a normal configured boot, Wi-Fi
warms up in the background while the launcher is displayed; setup and updater
flows start it on demand. The Brewfather connector is warmed before normal
operation, and HTTP bodies are streamed/spooled and closed before JSON parsing.
The embedded portal rejects request bodies larger than 4096 bytes.

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

