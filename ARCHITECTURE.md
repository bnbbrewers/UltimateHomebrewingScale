# UHS Architecture and Development Notes

How Ultimate Homebrewing Scale works inside, for contributors and for anyone
recovering a device by hand. Building and using UHS is covered by the
[documentation site](https://bnbbrewers.github.io/UltimateHomebrewingScale/).

## Boot Sequence

The runtime entrypoint is [main.py](main.py). On boot it:

1. Forces the keg relay output low.
2. Checks the optional watchdog reset streak and stops on the recovery screen
   after three consecutive watchdog resets.
3. Starts the lightweight updater when an update was requested; this path does
   not start the watchdog.
4. Initializes M5, LVGL/m5ui, speaker, i18n, hardware and application managers.
5. Starts the watchdog only after normal application initialization.
6. Starts Settings for an incomplete configuration, the calibration wizard
   when `scale_calibration.json` is missing, otherwise the launcher.

## Packages

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
docs/       Published hardware, software and user guides
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

## Memory and I/O Policy

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
  `c_largest` at the markers documented in [DEBUG_GUIDE.md](DEBUG_GUIDE.md).

## Hardware Choices

The reference build targets a garage brewery: splashes, wet hands, no exposed
wiring. The
[Hardware Installation Guide](https://bnbbrewers.github.io/UltimateHomebrewingScale/HardwareInstallationGuide/)
lists the parts to buy; this section records why each was chosen and what a
substitute has to respect.

- **Controller: M5Stack Dial.** Screen, rotary encoder with push button,
  Wi-Fi and ESP32-S3 in one unit: little wiring, a small enclosure, and a
  control that works with wet hands where a touch screen would not (the touch
  screen is not used). The firmware, its ports and the power latch used by
  standby are specific to it; no other controller is supported.
- **Weight reader: M5Stack Unit Weight I2C.** Turns the load-cell signal into
  I2C readings on Port A, address `0x26`. Another reader needs its own driver
  in `devices/scale.py`.
- **Platform: VEVOR postal scale.** Cheap, robust, 25 kg, and its RJ9
  connector lets the platform be unplugged or replaced without mechanical
  rework. A substitute needs a 4-wire load-cell bridge (E+, E-, A+, A-) and a
  capacity of at least 25 kg, the top calibration point; the calibration
  absorbs differences in sensitivity.
- **Spunding valve: mechanical, with a gauge.** Pressure regulation stays
  mechanical so the pressure in the keg never depends on software; UHS only
  decides when the fill stops.
- **Solenoid valve: 12 V, normally closed, on the gas path.** Normally closed
  so that a power loss, a crash or a reboot closes it; the boot sequence and
  standby also force the relay line low. A normally-open valve defeats both.
  On the gas outlet of the spunding valve, closing it stops the
  counter-pressure fill, and the valve never touches the beer. 12 V to share
  the build's supply.
- **Relay: M5Stack Unit Relay on Port B.** Keeps the valve's 12 V circuit
  apart from the control signal. Port A stays reserved for the weight reader;
  the relay pins are `KEG_RELAY_IO`.
- **Power: 12 V 3 A supply, jack connectors.** One voltage for the Dial and the
  valve; the jacks let the scale be unplugged for cleaning or transport.
- **Battery: optional 3.7 V LiPo, JST 1.25 mm 2-pin.** The only connector the
  Dial's internal socket takes. On battery the 12 V line is absent, so keg
  filling is unavailable, and nothing can cut the power on a frozen device:
  hence the 30-minute [standby](#idle-standby) and the
  [watchdog](#runtime-watchdog) the portal's **Battery powered** box enables.
- **Enclosure: waterproof ABS box, 100x68x40 mm, PG7 cable glands.** Sized for
  the Dial and the units; the glands give strain relief and keep splashes out.

## Hardware Defaults

- Unit Weight I2C on Port A: address `0x26`, SCL pin `15`, SDA pin `13`.
- Unit Relay on Port B: `KEG_RELAY_IO` in `config.py`, not exposed by the
  portal.
- Calibration file: `scale_calibration.json`, written by the wizard for the
  points `0 g`, `100 g`, `500 g`, `5000 g` and `25000 g` and read by
  `devices/scale.py` for piecewise linear interpolation.
- Kegs: `kegs.json`.

## Configuration

`config.py` is created from `config.py.example` on first boot, then edited by
the setup portal. It can also be written by hand:

```python
BREWING_SOFTWARE = "brewfather"
BREWFATHER_USER_ID = "your_user_id_here"
BREWFATHER_API_KEY = "your_api_key_here"
LANGUAGE = "en"  # "en" or "fr"
GRAIN_WEIGHT_TOLERANCE = 10
HOP_WEIGHT_TOLERANCE = 1
KEG_SPUNDING_VALVE_INERTIA_ML = 200
KEG_FILL_STALL_TIMEOUT_S = 10  # seconds without weight change before the valve closes (3-600)
STANDBY_TIMEOUT_MIN = 0  # minutes before power off; 30 on battery, 0 disables
DEBUG = False
UPDATE_CHANNEL = "stable"
# Optional: uncomment to enable a 15-second runtime watchdog.
# WATCHDOG_TIMEOUT_MS = 15000
```

The Wi-Fi manager first tries UIFlow NVS credentials (`uiflow:ssid0` /
`uiflow:pswd0`), then falls back to `WIFI_SSID` and `WIFI_PASSWORD` in
`config.py`.

## Setup Portal

The Settings app serves the portal on port `8080`: on the LAN address when
station Wi-Fi is up, otherwise on the open fallback access point `UHS-Setup`
(`http://192.168.4.1:8080/`). Editable settings are defined in
[webportal/config_keys.py](webportal/config_keys.py), and their layout in tabs
in `FIELDS` and `TABS` of [webportal/portal_html.py](webportal/portal_html.py).

`BATTERY` is a virtual key, never written to `config.py` as such. The
**Battery powered** checkbox is translated by `storage/config_registry.py` into
the presence or absence of `WATCHDOG_TIMEOUT_MS`.

Saving settings reboots the device. Requesting an update sets a flag and
reboots into the hidden updater app.

### Backup File Format

A full firmware flash wipes `config.py`, the Wi-Fi credentials in NVS,
`kegs.json` and `scale_calibration.json`. The portal saves all four into a
single `uhs-backup.txt` (`GET /backup`) and restores them (`POST /restore`,
`multipart/form-data` read by `webportal/multipart.py`), then reboots.

The file is plain text, one `KEY=value` per line, prefixed by a `UHS-BACKUP 1`
version header; a file from another version is refused rather than applied
partially. Kegs are written as `KEG=<empty_weight_g>|<max_volume_l>|<name>` and
calibration points as `CALIB=<calibration_point>|<weight>|<adc_average>|<step>`.
Kegs and calibration are restored only when the file carries them, so a trimmed
file cannot wipe what the device already holds.

Restoring works on a freshly flashed device: `config.py` is seeded from the
shipped `config.py.example` first, which also brings back settings the portal
does not expose such as `KEG_RELAY_IO`.

## Updater

The hidden updater downloads a compact TAR diff from the latest GitHub Release.
It starts from the portal, or from the **UPDATE** icon the launcher adds once
per boot, when connected to Wi-Fi, if the release channel has a newer release.

`UPDATE_CHANNEL = "stable"` installs the latest stable release;
`UPDATE_CHANNEL = "prerelease"` installs the newest published release, stable
or pre-release. The device never updates directly from branches.

The archive carries runtime files only: docs, firmware, Markdown files,
examples, `.gitignore` and `LICENSE` are left out. Runtime modules are
delivered as `.mpy`; after installing `foo.mpy`, the updater removes `foo.py`
at the same path when that source exists. `main.py`, `config.py.example`, and
the local `config.py` remain source/configuration exceptions.

## Runtime Watchdog

The normal application watchdog is enabled only when `config.py` defines
`WATCHDOG_TIMEOUT_MS`. A value of `15000` gives a 15-second timeout; values
below 5000 or invalid values disable it. Keep at least 15 seconds when using
Brewfather so its 10-second request timeout has enough margin. The updater
never starts or feeds the watchdog.

The portal exposes it as the **Battery powered** checkbox because a
mains-powered scale can always be recovered by cutting the power, while a scale
running on the M5Dial battery cannot. Checking the box writes
`WATCHDOG_TIMEOUT_MS = 15000`; unchecking it removes the setting. A timeout
already tuned by hand is kept as is while the box stays checked.

The keg relay output is forced low before the updater, normal application, or
watchdog error screen starts. During normal operation the main loop feeds the
watchdog only after the UI, hardware, and active application ticks complete.
The bounded Wi-Fi connection wait also feeds it, and Brewfather requests use a
10-second HTTP timeout while the watchdog is running.

### Recovering a Locked Device

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

## Idle Standby

`STANDBY_TIMEOUT_MIN` powers the device off after that many minutes without
operator activity. `0` disables the feature, and values outside `1`-`240` are
rejected with a log line rather than applied.

Activity is the button, the rotary encoder, and a weight change larger than
`HOP_WEIGHT_TOLERANCE`. An app inhibits standby through `inhibits_standby()`:
the updater and the calibration wizard while they run, the keg filler from the
moment the valve opens until the end-of-fill or no-flow screen is left.

Before powering off, the manager pins the keg relay line low, blacks out the
display, then releases the supply latch (GPIO46). If the relay cannot be pinned
or the knob cannot be read, it stays awake rather than sleeping with no way
back.

On the battery connector, releasing the latch cuts the power, and the knob,
wired to the power-on circuit, turns it back on. On USB or the 5 V connector
the latch changes nothing: the board stays up with a black screen until the
knob is pressed, then restarts. Both cases end in a full boot. Deep sleep is
not used: the knob, GPIO42, is not an RTC GPIO on the ESP32-S3 and could not
wake it.

`standby.py` stays dependency-light on purpose: no UI, no application managers,
no network clients, and no retained references to any of them.

## Brewfather Integration

The connector uses Basic Auth with `BREWFATHER_USER_ID` and
`BREWFATHER_API_KEY`, then calls the Brewfather v2 API to retrieve:

- batches with `status=Brewing`
- fermentables for malt weighing
- hops grouped into compact addition steps for hop weighing

## Development

Most files are MicroPython/UIFlow2 code intended to run on the M5Dial, but a few
host-side tests are available:

```bash
python -m unittest discover -s tools -p "test_*.py" -v
```

The setup portal screenshots used by the User Guide, one per tab, are
generated, not captured by hand:

```bash
python tools/render_portal_screenshot.py
```

It renders `webportal.portal_html.render_form_html` itself in headless Chrome or
Edge and overwrites `docs/SoftwareInstallationGuide/img/PortalPage-<tab>.png`, so
the images cannot drift from the real form. Rerun it after changing `FIELDS`,
`TABS` or the inline `_CSS` in
[webportal/portal_html.py](webportal/portal_html.py).

Further notes:

- [firmware/CustomFirmware.MD](firmware/CustomFirmware.MD) - building the custom firmware
- [DEBUG_GUIDE.md](DEBUG_GUIDE.md) - memory and debug traces
- [devices/DEVICES_GUIDE.md](devices/DEVICES_GUIDE.md) - hardware abstraction notes
- [FONTS_GUIDE.md](FONTS_GUIDE.md) - font notes
