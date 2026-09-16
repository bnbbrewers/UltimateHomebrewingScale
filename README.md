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
  tolerance, standby delay, battery mode, debug mode and release channel.
- Hidden updater app that downloads application files from GitHub.
- Optional runtime watchdog with relay-safe reboot and persistent reset lock.
- Optional idle standby with deep sleep and touch wake, for battery builds.
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

### Battery (optional)

The M5Dial carries an internal battery socket, so a flat LiPo cell turns the
scale into a portable one. The Dial then runs without the 12 V supply and still
feeds the Unit Weight I2C through Port A, which is convenient for weighing malt
away from the brewing station. Keg filling stays out of reach on battery: the
solenoid valve needs the 12 V line.

The cell must use a **JST 1.25 mm 2-pin** connector; the larger JST-PH 2.0 mm
connector does not fit. Fitting it means opening the Dial back cover, so do it
before mounting the Dial in the enclosure. The
[Hardware Installation Guide](https://bnbbrewers.github.io/UltimateHomebrewingScale/HardwareInstallationGuide/)
shows the socket and the assembly order.

- Battery: https://s.click.aliexpress.com/e/_c3O6l6n3

On battery, set `STANDBY_TIMEOUT_MIN` and enable the watchdog through the
portal's **Battery powered** checkbox. See [Idle Standby](#idle-standby) and
[Runtime Watchdog](#runtime-watchdog).

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

- Waterproof ABS enclosure, select the 100x68x40mm reference: [https://s.click.aliexpress.com/e/_c37dIrCf](https://s.click.aliexpress.com/e/_c37dIrCf)
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

1. Forces the keg relay output low.
2. Checks the optional watchdog reset streak and stops on the recovery screen
   after three consecutive watchdog resets.
3. Starts the lightweight updater when an update was requested; this path does
   not start the watchdog.
4. Initializes M5, LVGL/m5ui, speaker, i18n, hardware and application managers.
5. Starts the watchdog only after normal application initialization.
6. Starts Settings for an incomplete configuration, otherwise the launcher.

Main packages:

```text
api/        Brewfather connector and brewing software API interface
apps/       Application controllers and business logic
core/       App, screen, hardware, API and updater managers
devices/    Hardware abstractions for scale, Wi-Fi, button and rotary encoder
netcore/    Lightweight HTTP transport without LVGL dependencies
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
Runtime Python modules are deployed as precompiled MicroPython bytecode
(`.mpy`) on the Dial. `main.py` remains the source bootstrap, while
`config.py.example` remains available for setup and the private `config.py` is
never included in release artifacts. The compiler staging is shared by the
complete firmware image and the differential update archive.

### Memory and I/O policy

- In the normal configured path, Wi-Fi warms up in the background while the
  launcher is displayed; unconfigured setup and updater flows remain demand-
  driven.
- API connectors and LVGL screens are created on first use and released at
  workflow boundaries.
- The screen manager keeps the launcher screen stable across transitions,
  releases transient screens before memory-sensitive HTTP calls, and flushes
  LVGL after object deletion to reduce allocator churn.
- HTTP responses are streamed to a temporary file, closed, and only then parsed
  as JSON. Small non-streaming fallbacks are bounded; update archives require a
  streaming response. Response and raw-stream handles are closed explicitly;
  optional HTTP sessions are reused when the installed requests implementation
  supports them.
- The portal service caps request headers and bodies at 4096 bytes before
  reading the body. `setup_portal_service.py` is the entry point; rendering and
  routing are kept in the separate `portal_html.py` and `portal_routes.py`
  modules.
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
- `STANDBY_TIMEOUT_MIN`
- `BATTERY` (virtual key, see below)
- `DEBUG`
- `UPDATE_CHANNEL`

`BATTERY` is never written to `config.py` as such. The **Battery powered**
checkbox is translated by `storage/config_registry.py` into the presence or
absence of `WATCHDOG_TIMEOUT_MS`.

Saving settings reboots the device. The portal can also request an update, which
sets a flag and reboots into the hidden updater app.

### Configuration backup and restore

A full firmware flash wipes `config.py`, the Wi-Fi credentials in NVS,
`kegs.json` and `scale_calibration.json`. The portal's **Backup** section saves
all four into a single `uhs-backup.txt` and puts them back afterwards:

- **Back up** (`GET /backup`) serves the file as a download.
- **Restore** (`POST /restore`) takes the file picked in the upload field,
  applies it and reboots.

The upload arrives as `multipart/form-data`, which `webportal/multipart.py`
reads; the boundary comes from the request `Content-Type`, kept by
`setup_portal_service` for that single purpose. A file larger than
`MAX_REQUEST_BODY_BYTES` is dropped by the request parser before the route
runs, so the browser shows a connection error rather than a message — the
upload field is restricted to `.txt` to make that unlikely.

The file is plain text, one `KEY=value` per line, prefixed by a `UHS-BACKUP 1`
version header; a file from another version is refused rather than applied
partially. Kegs are written as `KEG=<empty_weight_g>|<max_volume_l>|<name>` and
calibration points as `CALIB=<calibration_point>|<weight>|<adc_average>|<step>`.
Kegs and calibration are restored only when the file carries them, so a trimmed
file cannot wipe what the device already holds.

Restoring works on a freshly flashed device: `config.py` is seeded from the
shipped `config.py.example` first, which also brings back settings the portal
does not expose such as `KEG_RELAY_IO`.

**The file contains the Wi-Fi password and the Brewfather API key in clear
text.** Store it accordingly.

### Updater

The hidden updater downloads a compact TAR diff from the latest GitHub Release.
`UPDATE_CHANNEL = "stable"` installs the latest stable release. Set
`UPDATE_CHANNEL = "prerelease"` to allow updates from the newest pre-release.
The device never updates directly from branches. It skips docs, firmware,
Markdown files, examples, `.gitignore`, `LICENSE`, and most example files so the
device receives only runtime files. Runtime modules are delivered as `.mpy`;
after installing `foo.mpy`, the updater removes `foo.py` at the same path when
that source exists. A first `.mpy` release migrates legacy installations by
including all compiled modules; later diffs contain only changed artifacts.
`main.py`, `config.py.example`, and the local `config.py` configuration remain
source/configuration exceptions.

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
STANDBY_TIMEOUT_MIN = 0  # minutes before deep sleep; 30 on battery, 0 disables
DEBUG = False
UPDATE_CHANNEL = "stable"
# Optional: uncomment to enable a 15-second runtime watchdog.
# WATCHDOG_TIMEOUT_MS = 15000
```

The Wi-Fi manager first tries UIFlow NVS credentials (`uiflow:ssid0` /
`uiflow:pswd0`), then falls back to `WIFI_SSID` and `WIFI_PASSWORD` in
`config.py`.

### Runtime Watchdog

The normal application watchdog is enabled only when `config.py` defines
`WATCHDOG_TIMEOUT_MS`. A value of `15000` gives a 15-second timeout; values
below 5000 or invalid values disable it. Leave the setting absent or commented
to disable the feature. Keep at least 15 seconds when using Brewfather so its
10-second request timeout has enough margin. The updater never starts or feeds
the watchdog.

The setup portal exposes this as the **Battery powered** checkbox. It exists
because a mains-powered scale can always be recovered by cutting the power,
while a scale running on the M5Dial battery cannot. Checking the box writes
`WATCHDOG_TIMEOUT_MS = 15000`; unchecking it removes the setting. A timeout
already tuned by hand is kept as is while the box stays checked, so the portal
offers no timeout field of its own.

The keg relay output is forced low before the updater, normal application, or
watchdog error screen starts. During normal operation the main loop feeds the
watchdog only after the UI, hardware, and active application ticks complete.
The bounded Wi-Fi connection wait also feeds it, and Brewfather requests use a
10-second HTTP timeout while the watchdog is running.

After three consecutive watchdog resets, the device remains on a recovery
error screen without launching the application or updater. An incomplete reset
streak is cleared after five minutes of healthy operation, but power cycling
does not clear a locked state. Removing `WATCHDOG_TIMEOUT_MS` bypasses watchdog
and lock processing but does not erase `wdt_count`; re-enabling it restores the
previous lock until the counter is cleared.

From the USB MicroPython REPL, clear the lock with:

```python
import esp32
nvs = esp32.NVS("uhs")
nvs.set_i32("wdt_count", 0)
nvs.commit()
import machine
machine.reset()
```

A complete reflash recovers a locked device only if it erases or replaces the
NVS partition.

### Idle Standby

`STANDBY_TIMEOUT_MIN` puts the device into ESP32 deep sleep after that many
minutes without operator activity. `0` disables the feature, and values outside
`1`-`240` are rejected with a log line rather than applied. **30 minutes is the
recommended value in every install, and is what makes a battery build usable.**
The setting is editable from the portal as **Standby after (min, 0 = off)**.

Activity is the button, the rotary encoder, and a weight change larger than
`HOP_WEIGHT_TOLERANCE`. The updater and the calibration wizard inhibit standby
while they run, so a long download or a calibration session is never cut short.

Before sleeping, the manager pins the keg relay line low and holds it through
deep sleep, dims the display, then arms the wake source. If the relay cannot be
pinned or the wake source cannot be armed, it stays awake rather than sleeping
with no way back.

**Waking is done by touching the screen.** The main button cannot wake the
board: GPIO42 is not an RTC GPIO on the ESP32-S3, so the wake source is the
touch interrupt on GPIO14. Waking is a full reboot, so the device returns to the
launcher rather than to the screen it left.

`standby.py` stays dependency-light on purpose: no UI, no application managers,
no network clients, and no retained references to any of them.

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
python -m unittest discover -s tools -p "test_*.py" -v
```

The setup portal screenshot used by the Software Installation Guide is
generated, not captured by hand:

```bash
python tools/render_portal_screenshot.py
```

It renders `webportal.portal_html.render_form_html` itself in headless Chrome or
Edge and overwrites `docs/SoftwareInstallationGuide/img/PortalPage.png`, so the
image cannot drift from the real form. Rerun it after changing `FIELDS` in
[webportal/portal_html.py](webportal/portal_html.py).

Useful local docs:

- [DEBUG_GUIDE.md](DEBUG_GUIDE.md) - memory and debug traces
- [devices/DEVICES_GUIDE.md](devices/DEVICES_GUIDE.md) - hardware abstraction notes
- [i18n/README.md](i18n/README.md) - translation system
- [FONTS_GUIDE.md](FONTS_GUIDE.md) - font notes

## License

This project is licensed under GPL-3.0. See [LICENSE](LICENSE).
