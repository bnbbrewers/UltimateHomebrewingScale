# Application Memory Lifecycle Design

> **Status:** Approved direction, pending implementation review

## Goal

After leaving any application, return the runtime as close as safely possible to its initial launcher state while keeping the launcher screen and launcher application cached.

## Constraints

- The project runs on an ESP32-S3/UIFlow2 runtime with separate Python heap, ESP-IDF C heap, and largest contiguous C block.
- The launcher remains cached, including its `LauncherApp` instance and `LauncherScreen` LVGL tree.
- Core services remain alive: `AppManager`, `ScreenManager`, hardware objects, Wi-Fi, i18n, `lvgl`, `m5ui`, and shared core/device modules.
- The transition LVGL screen remains persistent because deleting it during a transition can destabilize the M5UI/LVGL task handler.
- App modules and transient UI modules may be re-imported on the next entry; the extra import cost is accepted in exchange for lower steady-state memory pressure.

## Lifecycle

When switching from a non-launcher application:

1. Capture the target app and shared runtime dependencies before releasing the current app.
2. Call the current app's `on_exit()` and `release_runtime_state()`, even if `on_exit()` raises.
3. Clear cached screen references from all app instances.
4. Keep only `screen_ids.LAUNCHER` in `ScreenManager`; delete every other screen tree and release screen-owned native resources.
5. Remove the outgoing app instance from `AppManager._apps`.
6. Remove the outgoing `apps.<module>` entry from `sys.modules` and from its `apps` package attribute.
7. Remove transient UI modules that are no longer represented by a retained screen. The launcher UI module and shared UI helpers remain loaded.
8. Drop local references to the outgoing app and run multiple garbage-collection cycles.
9. Enter the next app. If it is not cached, it is lazily re-created and imported.

The launcher is never evicted by this lifecycle. Returning to it reuses the existing LVGL tree and icon objects.

## Module policy

The eviction code uses explicit ownership rather than deleting every module with an `apps` or `ui` prefix. This prevents accidental removal of shared runtime modules still needed by the hardware, manager, or launcher.

Evictable modules include the outgoing application module and UI modules whose screen objects were deleted, including weight, select-item, simple-message, keg-volume, settings, updater, and calibration screens when they are no longer retained.

Retained modules include the launcher application and screen, `core`, `devices`, `ui.screen_ids`, shared UI helpers, `config`, `i18n`, `lvgl`, `m5ui`, and hardware/network modules.

## Error handling

- Cleanup continues when an app's `on_exit()` or release hook raises; errors are debug-logged only.
- A failed module deletion must not remove a live reference from `_apps` or the retained launcher.
- Screen deletion remains best-effort and follows the existing LVGL-safe transition order.
- No GC is run re-entrantly immediately after the new screen enters; cleanup and GC happen before the new application allocates its UI.

## Tests and acceptance

Host tests must verify:

- the launcher instance remains cached across switches;
- a non-launcher app instance is removed after exit;
- its application module and package attribute are removed;
- transient UI modules are removed while shared and launcher modules remain;
- cleanup still runs when `on_exit()` raises;
- the launcher is not deleted or reloaded by the eviction path.

On hardware, repeat this sequence at least five times with debug memory logging enabled:

`balance → launcher → keg filler → launcher`

The sequence must complete without `MemoryError`, and the log must show memory recovery after app eviction before the launcher is entered.
