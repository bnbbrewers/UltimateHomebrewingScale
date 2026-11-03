# Device settings: hostname, Wi-Fi diagnostics and simulated scale

All new controls are on the setup portal's **General** tab. Save settings to
persist them and reboot. Existing configuration backups include the new keys.

## Hostname

`HOSTNAME` defaults to `uhs-scale`. Enter 1–32 ASCII letters, digits or hyphens,
without a leading/trailing hyphen. Names are stored in lowercase. The firmware
applies the hostname before network initialization and station connection,
using `network.hostname()` with older WLAN configuration fallbacks.

The hostname is the network identity supplied to DHCP. Whether a router
resolves it, or whether `<hostname>.local` is available, depends on the network
and mDNS support in the installed MicroPython build. The IP/QR URL remains the
reliable way to reach the setup portal on port 8080. Restart after changing the
hostname; an already-associated station may need a fresh DHCP lease before the
router shows the new name.

## Wi-Fi

- **Find Wi-Fi networks** fills suggestions in the SSID input. Results show
  signal strength in dBm, channel and open/secured status in the scan API.
  The browser displays signal and security alongside each suggestion.
- Duplicate SSIDs are collapsed to their strongest signal, sorted strongest
  first and limited to 20 suggestions. Hidden networks can be entered manually.
- **Test connection without saving** validates the supplied credentials,
  starts a non-blocking STA connection test and reports success/IP, wrong
  password, missing network, driver failure or timeout (20 seconds).
- The test does not write NVS or `config.py`. It first activates the existing
  `UHS-Setup` recovery AP. If the AP cannot be activated, the current connection
  is not disconnected. Changing STA networks can still interrupt the browser
  session because AP and STA share the ESP32 radio/channel.
- If disconnected, join `UHS-Setup` and open `http://192.168.4.1:8080`. The test
  continues without a browser connection. Candidate credentials remain only
  in memory and prefill the reopened settings page after a successful test.
  Press **Save** to persist them. Failed tests restore the saved network;
  leaving Settings without saving also restores it.
- The normal Wi-Fi manager re-checks the actual link rather than trusting a
  cached connected flag. During a portal test, its automatic connection logic
  is paused so it cannot replace the candidate with the old saved network.

Validation accepts SSIDs up to 32 UTF-8 bytes. Wi-Fi passwords may be empty for
an open network, 8–63 UTF-8 bytes, or a 64-digit hexadecimal PSK. Invalid fields
are displayed individually and no connection test is started. Tests check
association/DHCP, not Internet reachability, DNS or receiver/API authentication.
The M5Dial uses 2.4 GHz Wi-Fi; a 5 GHz-only SSID will not appear.

The scan, diagnostic and simulation endpoints share the portal's existing
optional token check. No submitted passwords are returned in JSON diagnostics
or driver error messages. Like the existing setup portal, these controls are
available while the device is in Settings, not during a physical filling.

## Simulated scale

Enable **Simulate scale**, save and restart. No connected weighing unit or
calibration file is needed. The real calibration file is not changed. When
simulation is disabled again, the real calibration workflow applies normally.

| Setting | Default | Meaning |
| --- | --- | --- |
| `SIMULATION_ENABLED` | `False` | Select simulated sensor and virtual relay at boot |
| `SIMULATION_MODE` | `ramp` | `ramp`: gradual approach; `fixed`: fixed test load |
| `SIMULATION_WEIGHT_G` | `1000` | Default target in grams for free weighing |
| `SIMULATION_RATE_G_S` | `100` | Ramp speed in grams per second |
| `SIMULATION_SEND_EVENTS` | `False` | Explicitly allow synthetic API events |

In ramp mode the net mass approaches the target without overshooting. Recipe
assistants set their own ingredient targets automatically, including sub-gram
hop targets. Tare resets to zero and starts the approach again. In fixed mode,
tare shows zero, then places the configured test load after 500 ms. Stability
uses five sampled readings, rather than always claiming stable weight.

The General tab provides a live preview, **Set test weight**, **Ramp to target**
and **Tare simulated scale**. These buttons change only the running simulator;
persistent defaults are edited in the main settings form. After leaving
Settings the web server stops, and the simulator continues locally. In fixed
mode a new target applies immediately; switch to ramp mode and save/restart
for gradual changes.

Simulated filling starts from the selected keg's calibrated empty mass and
approaches the filling target only while the **virtual** relay is on. Pausing
for no flow and resuming preserve the current simulated mass. The physical
relay constructor is never used in simulation, and boot still applies the
existing force-off safety step. Weight screens carry `[SIM]` in the title.

API event delivery is off by default in simulation, including pending outbox
delivery during that boot. Selecting **Send simulated data to API** explicitly
allows normal API measurements/results, which can create real history in the
receiver. The receiver's strict schema does not accept an extra simulation
flag. Use a test receiver/device token when exercising that option. Recipe
retrieval still uses the configured provider; this mode does not invent batches.

## Validation

```sh
python tools/verify_device_settings.py
python tools/verify_scale_http.py
```

Tests cover hostname and credential validation, hostname fallback, scan
selection, connection success/failure/timeout/recovery, exclusion of normal
reconnect during a test, route authentication, refusing a test without recovery
AP, preventing writes to a real scale, simulator ramp/fixed/tare behavior,
sub-gram targets, virtual relay pause/resume, default exclusion of simulated
API events and avoiding physical hardware constructors in simulation.

Validate on an actual M5Dial before use: DHCP hostname behavior, AP+STA channel
switching, WLAN error-code support, memory headroom with the expanded setup
page and screen readability depend on the installed UIFlow2 build. The portable
suite and MicroPython syntax compilation do not replace those checks.
