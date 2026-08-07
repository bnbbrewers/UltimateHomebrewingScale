# Memory-Safe Runtime Refactor Design

## Goal

Improve the architecture and memory behavior of the M5Dial runtime while preserving the existing brewing workflows and keeping the refactor incremental and measurable.

## Constraints

- MicroPython/UIFlow2 on ESP32-S3 with constrained Python and C heaps.
- LVGL and M5Stack APIs must remain compatible with the custom firmware.
- Existing métier behavior is already functional and must not be redesigned.
- `main` remains untouched; implementation happens on the local `test-refracto` branch.
- Tests remain external/local according to the repository convention.

## Architecture

Keep the current `AppManager`, `ScreenManager`, `HardwareManager`, and `ApiFactory` boundaries. Strengthen them incrementally:

- `ScreenManager` starts empty unless an initial screen is explicitly requested.
- Application startup owns the initial route; screen creation remains lazy.
- Wi-Fi is demand-driven and is not started by the generic hardware tick.
- API connectors are created on first use and cached thereafter.
- Screen destruction and application runtime-state release become explicit lifecycle operations.
- The transition/loading LVGL screen is deleted after the target screen is loaded.

## Memory policy

- Preserve streamed HTTP responses and close responses before JSON parsing.
- Clear UI lists and large workflow data before network calls.
- Bound portal request headers and bodies.
- Avoid retaining response/request buffers after a client is closed.
- Centralize memory snapshots and make their `collect` parameter truthful.
- Record Python free memory, C free memory, and C largest contiguous block around boot, screens, Wi-Fi, API, portal, and updater boundaries.

## Compatibility and error handling

- Keep existing public app and device interfaces where practical.
- Do not introduce a full active-app rewrite in this branch.
- Keep optional hardware behavior tolerant, but avoid silently swallowing errors in core lifecycle paths.
- Keep the existing `webportal.setup_portal` compatibility facade.

## Validation

- Add local regression tests for startup routing, lazy Wi-Fi/API creation, LVGL cleanup lifecycle, bounded portal requests, and updater response fallbacks.
- Run host-side syntax checks and the available local test suite.
- Verify the branch remains clean and document any tests unavailable from the repository because tests are kept outside Git.
- On hardware, repeat app transitions and measure `py_free`, `c_free`, and `c_largest` to detect memory ratcheting.

