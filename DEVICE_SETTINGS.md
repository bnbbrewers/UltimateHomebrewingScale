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

## If the setup AP responds to ping but the portal does not open

The setup listener now starts without loading the full HTML renderer. The QR
screen is released before loading the full settings page on the first request.
If that page cannot be imported or rendered due to memory pressure, a minimal
recovery form is returned instead. `/recovery` always offers that small form
without importing the full renderer; it edits only Wi-Fi, hostname and the
simulation switch and preserves unrelated settings.

The AP startup stops unsuccessful STA retries, reinitializes an inherited AP
once, requests the `192.168.4.1/24` subnet, and checks the actual interface IP.
An AP failure no longer returns a fictitious success/address. Unsupported
hostname operations cannot prevent portal startup. A startup failure is shown
on the Dial with a short-press retry action and logged over USB.

With a rebuilt firmware, connect to `UHS-Setup` and try:

- `http://192.168.4.1:8080/health` — a small JSON liveness check.
- `http://192.168.4.1:8080/recovery` — minimal setup without the full page.
- `http://192.168.4.1:8080/` — full settings, with automatic low-memory fallback.

Use HTTP, not HTTPS. The server is active while the Dial is in Settings. A ping
response alone does not prove that the HTTP listener has started. If the issue
persists, collect the USB output while entering Settings; `[settings] portal
init error` includes the exception that stopped startup. These changes address
observable startup failure paths; successful DHCP and portal operation on the
reported device still require a hardware check.

Additional regressions: `python tools/verify_portal_recovery.py`.

### HTTP headers arrive, but the HTML body stalls

If `/health` returns its complete JSON while `/recovery` returns only headers,
the setup connection and listener work; changing IP configuration will not
address the HTML response path. The response sender now keeps headers separate
from HTML fragments and sends one bounded slice per main-loop tick. It retains
partially accepted bytes for retry, yields to the UIFlow/Wi-Fi event loop after
each write, and uses a stall timeout reset on actual progress instead of a
fixed deadline for the entire page. TCP_NODELAY is requested when supported.

`python tools/verify_portal_transport.py` checks complete recovery/full-settings
bodies, exact UTF-8 Content-Length, short writes, EAGAIN, long transfers that
still make progress, consecutive responses and permanent socket backpressure.
These host-side checks cannot reproduce every native UIFlow socket behavior.

After attempting a failing page in a newly built firmware, the small endpoint
`/health?transfer=1` returns the previous response's `state`, expected
`bodyBytes`/`headerBytes`, `sentBytes` and any write error type. It follows the
portal's token policy. `sentBytes` means accepted by the socket API, not a
remote browser acknowledgement. `/health` without the parameter stays unchanged.
