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

## Shared HTTP transport

All network consumers use one shared HTTP transport. The transport owns Wi-Fi readiness, retries, request option compatibility, response status checks, streaming preference, response closing, temporary-file cleanup, and GC boundaries.

The body policy is explicit per use case rather than duplicated per caller:

- JSON/API responses are streamed to a temporary file and parsed only after the response is closed.
- Update archives are streamed directly to a file and require streaming for large payloads.
- `response.content` or `response.text` is accepted only for bounded small responses or when the declared size is below a safe limit.
- An unsupported large non-streaming response fails clearly instead of allocating an unbounded body.

This keeps Brewfather, GitHub metadata, manifests, and archive downloads on the same lifecycle while preserving their different memory limits.

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
