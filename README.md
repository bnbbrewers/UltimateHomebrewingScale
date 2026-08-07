# Ultimate Homebrewing Scale (UHS)

Ultimate Homebrewing Scale is a DIY connected brewing scale for the M5Stack Dial.
It runs on UIFlow2 / MicroPython and combines a calibrated load platform, a
rotary-driven UI, Brewfather recipe integration, a smartphone setup portal, and
an on-device updater.

The project is designed for real brewery use: simple operation on the device,
minimal wiring, and a memory-conscious runtime that can survive LVGL, Wi-Fi and
HTTPS on an ESP32-S3.

## Current Status

Implemented:

- Launcher with rotary selection and single-button validation.
- Scale mode with live weight display and tare.
- Malt assistant using Brewfather batches and fermentables.
- Hop assistant using Brewfather batches and grouped hop additions.
- Scale calibration wizard with multi-point calibration saved to
  `scale_calibration.json`.
- Smartphone settings portal for Wi-Fi, Brewfather credentials, language,
  tolerance, debug mode and update branch.
- Hidden updater app that downloads application files from GitHub.
- English and French UI strings.

Work in progress:

- Keg filler app. The menu entry and weight screen exist, but automated filling
  logic and relay/valve control are not complete yet.

## Quick Start

1. Assemble the hardware:
   [Hardware Installation Guide](https://bnbbrewers.github.io/UltimateHomebrewingScale/HardwareInstallationGuide/).
2. Flash the custom M5Dial firmware:
   [Software Installation Guide](https://bnbbrewers.github.io/UltimateHomebrewingScale/SoftwareInstallationGuide/).
3. Configure Wi-Fi and Brewfather credentials from the Settings portal or from
   `config.py`.
4. Run the calibration wizard and save `scale_calibration.json`.
5. Reboot the M5Dial and start from `main.py`.

See [INSTALLATION.MD](INSTALLATION.MD) for the repository-level installation
notes and [firmware/CustomFirmware.MD](firmware/CustomFirmware.MD) for details
about the custom firmware build.

## Hardware

### General Considerations

The reference build is designed for a garage brewery environment, with splash
resistance, clean integration, and no exposed wiring.

### Controller

The M5Stack Dial offers a good balance between cost, integration, and usability.
Its rotary encoder with push button is well suited to menu navigation during
brewing sessions, while the built-in screen, Wi-Fi, and ESP32-S3 reduce wiring,
enclosure complexity, and overall project cost.

- M5Dial: https://s.click.aliexpress.com/e/_c3fnF9C9
- Weight Reader I2C: https://s.click.aliexpress.com/e/_c42It9IZ
- Weight Reader I2C alternative link: https://s.click.aliexpress.com/e/_c3VIvQvL
- Relay: https://s.click.aliexpress.com/e/_c3OikdVR

### Scale Platform

Using a VEVOR postal scale platform provides a cost-effective and robust base.
It is designed to handle heavy loads and offers easy integration through its
standard RJ9 connector, which keeps the platform reusable without mechanical
redesign.

- VEVOR scale: https://s.click.aliexpress.com/e/_c3xr1w7n
- RJ9 cable: https://s.click.aliexpress.com/e/_c2u5O1C5

### Spunding Valve

The keg filler hardware is based on a mechanical spunding valve with a physical
pressure gauge, chosen for reliability and simplicity.

The spunding valve is only required for the keg filler function. A 12 V
normally-closed solenoid valve is added so the controller can automate the gas
outlet while keeping a failsafe default: if the system loses power or stops
unexpectedly, the valve closes.

This combines the robustness of mechanical pressure regulation with electronic
control. The software keg filler flow is still WIP, but the hardware target is
documented here for the reference build.

- Spunding valve: https://s.click.aliexpress.com/e/_c3Ccjltr
- Solenoid valve: https://s.click.aliexpress.com/e/_c2Q1v85j
- 1/4 adapter: https://s.click.aliexpress.com/e/_c3iy7LDR

### Integration Box

- Waterproof ABS enclosure, ref. F200-120-75: https://s.click.aliexpress.com/e/_c2w8dSkf
- Cable gland, ref. PG7 white: https://s.click.aliexpress.com/e/_c4UINtHd
- Jack connectors: https://s.click.aliexpress.com/e/_c3Z0z0F5
- Power supply, EU plug 12 V 3 A: https://s.click.aliexpress.com/e/_c353g2MJ

Scale defaults in code:

- I2C address: `0x26`
- SCL pin: `15`
- SDA pin: `13`
- Calibration file: `scale_calibration.json`
- Calibration points used by the wizard: `0 g`, `100 g`, `500 g`, `5000 g`, `25000 g`

## Software Architecture

The runtime entrypoint is [main.py](main.py). On boot it:

1. Creates `config.py` from `config.py.example` if needed.
2. Initializes M5, LVGL/m5ui, speaker and i18n.
3. Builds shared hardware and API managers.
4. Starts the calibration wizard if no calibration file exists.
5. Starts Settings if this is the first generated configuration.
6. Starts the hidden updater if the setup portal requested an update.
7. Otherwise starts the launcher.

Main packages:

```text
api/        Brewfather connector and brewing software API interface
apps/       Application controllers and business logic
core/       App, screen, hardware, API and updater managers
devices/    Hardware abstractions for scale, Wi-Fi, button and rotary encoder
i18n/       English/French translations
ui/         LVGL screens and reusable UI helpers
webportal/  Embedded HTTP settings portal
firmware/   Custom UIFlow2 firmware image and notes
docs/       Published hardware/software installation guides
tests/      Host-side regression tests where possible
```

The app manager creates only the active app at boot and lazy-loads the others.
This is intentional: the M5Dial has limited Python and C heap, and the project
tries to avoid loading every UI and API flow at once.

### Memory and I/O policy

- Wi-Fi connection attempts start only when an API, portal, or updater workflow
  requests them.
- API connectors and LVGL screens are created on first use and released at
  workflow boundaries.
- HTTP responses are streamed to a temporary file, closed, and only then parsed
  as JSON. Small non-streaming fallbacks are bounded; update archives require a
  streaming response.
- The two portal modules cap request headers and bodies at 4096 bytes before
  reading the body. `setup_portal_service.py` is the normal lightweight entry
  point; `setup_portal.py` remains the full compatibility implementation.
- With `DEBUG = True`, compare `py_free`, `c_free`, and especially
  `c_largest` at the markers documented in `DEBUG_GUIDE.md`.

## Features

### Scale Mode

Scale mode shows the current calibrated weight in grams and supports tare from
the device button. Readings use a moving average, cached hardware reads and a
small reporting threshold to reduce UI jitter.

### Malt Assistant

The malt assistant connects to Brewfather, lists batches with status `Brewing`,
loads fermentables for the selected batch, and guides weighing one malt at a
time. Each target is shown as a countdown in grams. Validation is allowed once
the remaining weight is within `GRAIN_WEIGHT_TOLERANCE`.

### Hop Assistant

The hop assistant loads Brewfather hop additions, groups them by hop name, then
lets the brewer select each addition step. It prompts for recipient preparation,
tares before each weighing step, and removes completed steps from the in-memory
work list to keep RAM use low.

### Calibration Wizard

If `scale_calibration.json` is missing, the app starts directly in the
calibration wizard. The wizard samples raw ADC values for the configured weight
points and writes the calibration file used by `devices/scale.py` for piecewise
linear interpolation.

### Settings Portal

The Settings app starts a lightweight HTTP server on port `8080` and displays
the portal URL on the M5Dial. If station Wi-Fi is available, it serves the portal
on the LAN address. Otherwise it starts the fallback access point `UHS-Setup`.

Editable settings are defined in [webportal/config_keys.py](webportal/config_keys.py):

- `LANGUAGE`
- `WIFI_SSID`
- `WIFI_PASSWORD`
- `BREWING_SOFTWARE`
- `BREWFATHER_USER_ID`
- `BREWFATHER_API_KEY`
- `GRAIN_WEIGHT_TOLERANCE`
- `HOP_WEIGHT_TOLERANCE`
- `KEG_SPUNDING_VALVE_INERTIA_ML`
- `DEBUG`
- `UPDATE_CHANNEL`

Saving settings reboots the device. The portal can also request an update, which
sets a flag and reboots into the hidden updater app.

### Updater

The hidden updater downloads a compact TAR diff from the latest GitHub Release.
`UPDATE_CHANNEL = "stable"` installs the latest stable release. Set
`UPDATE_CHANNEL = "prerelease"` to allow updates from the newest pre-release.
The device never updates directly from branches. It skips docs, firmware,
Markdown files, examples, `.gitignore`, `LICENSE`, and most example files so the
device receives only runtime files.

## Configuration

Create `config.py` from `config.py.example` or let `main.py` create it on first
boot.

Important values:

```python
BREWING_SOFTWARE = "brewfather"
BREWFATHER_USER_ID = "your_user_id_here"
BREWFATHER_API_KEY = "your_api_key_here"
LANGUAGE = "en"  # "en" or "fr"
GRAIN_WEIGHT_TOLERANCE = 10
HOP_WEIGHT_TOLERANCE = 1
KEG_SPUNDING_VALVE_INERTIA_ML = 200
DEBUG = False
UPDATE_CHANNEL = "stable"
```

The Wi-Fi manager first tries UIFlow NVS credentials (`uiflow:ssid0` /
`uiflow:pswd0`), then falls back to `WIFI_SSID` and `WIFI_PASSWORD` in
`config.py`.

## Brewfather Integration

The current brewing software connector is Brewfather. It uses Basic Auth with
`BREWFATHER_USER_ID` and `BREWFATHER_API_KEY`, then calls the Brewfather v2 API
to retrieve:

- batches with `status=Brewing`
- fermentables for malt weighing
- hops grouped into compact addition steps for hop weighing

See [api/README.md](api/README.md) for the API interface and extension points
for future brewing software connectors.

## Development

Most files are MicroPython/UIFlow2 code intended to run on the M5Dial, but a few
host-side tests are available:

```bash
python -m unittest discover tests
```

Useful local docs:

- [DEBUG_GUIDE.md](DEBUG_GUIDE.md) - memory and debug traces
- [devices/DEVICES_GUIDE.md](devices/DEVICES_GUIDE.md) - hardware abstraction notes
- [i18n/README.md](i18n/README.md) - translation system
- [FONTS_GUIDE.md](FONTS_GUIDE.md) - font notes

## License

This project is licensed under GPL-3.0. See [LICENSE](LICENSE).
