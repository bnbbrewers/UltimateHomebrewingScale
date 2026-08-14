# Application Memory Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evict every non-launcher application and transient UI module after exit while keeping the launcher instance and LVGL tree cached.

**Architecture:** `AppManager` owns application-instance and `apps.*` module eviction. `ScreenManager` owns deletion of non-launcher screens and eviction of the UI modules that created those screens. Both managers retain shared runtime modules and the launcher. Cleanup happens after the outgoing app lifecycle and before the next app is created or entered.

**Tech Stack:** MicroPython, LVGL/m5ui, Python `unittest`, `sys.modules`, existing `gc` and `memory_debug` helpers.

## Global Constraints

- Preserve the cached launcher application, launcher screen, launcher module, and launcher UI module.
- Preserve core, hardware, networking, i18n, `lvgl`, `m5ui`, and shared UI modules.
- Keep the persistent LVGL transition screen; do not delete it during the normal transition.
- Continue cleanup when app exit hooks raise.
- Do not run a new GC immediately after the target app enters its UI.
- Use `apply_patch` for source and test edits and run commands through `rtk`.

---

### Task 1: Add failing application-eviction tests

**Files:**
- Modify: `tests/test_app_manager_lazy.py`
- Test: `tests/test_app_manager_lazy.py`

**Interfaces:**
- Consumes: `AppManager._switch_to()` and the existing fake screen manager.
- Produces: regression coverage proving that a non-launcher app instance and its owned module are evicted while the launcher remains cached.

- [ ] **Step 1: Add a test for non-launcher instance and module eviction**

Create a fake module under `apps.test_memory_app`, expose it through the `apps` package, create a fake app class whose `__module__` is that module, switch to launcher, and assert that the app is removed from `_apps`, `sys.modules`, and the package attribute.

- [ ] **Step 2: Add a test that launcher remains cached**

Assert that switching away from a non-launcher app does not remove the existing launcher object from `_apps`.

- [ ] **Step 3: Update cache-oriented expectations**

Replace the existing tests that require `keg_filler_app` to remain cached with expectations that the outgoing non-launcher app is released before memory cleanup.

- [ ] **Step 4: Run the focused tests and verify they fail**

Run:

```powershell
rtk python -m unittest tests.test_app_manager_lazy -q
```

Expected: the new eviction assertions fail because the current manager intentionally keeps the outgoing app and module cached.

### Task 2: Add failing transient-UI-module tests

**Files:**
- Modify: `tests/test_screen_manager_release.py`
- Test: `tests/test_screen_manager_release.py`

**Interfaces:**
- Consumes: `ScreenManager.release_all()` and the existing fake LVGL screen loader.
- Produces: regression coverage proving that deleted transient screen modules are evicted and the launcher module remains loaded.

- [ ] **Step 1: Register fake transient and retained modules**

Install fake `ui.weight_screen`, `ui.simple_message_screen`, and `ui.launcher_screen` modules in `sys.modules`, including package attributes, before constructing the manager.

- [ ] **Step 2: Add the eviction assertion**

Create launcher and weight screens, call `release_all(keep_ids=(screen_ids.LAUNCHER,))`, and assert that the weight module and `ui.weight_screen` package attribute are gone while the launcher module and attribute remain.

- [ ] **Step 3: Run the focused test and verify it fails**

Run:

```powershell
rtk python -m unittest tests.test_screen_manager_release -q
```

Expected: the transient module remains loaded because `ScreenManager` currently deletes only screen objects.

### Task 3: Implement application and screen module eviction

**Files:**
- Modify: `core/app_manager.py`
- Modify: `core/screen_manager.py`

**Interfaces:**
- Consumes: the failing tests from Tasks 1 and 2.
- Produces: private `_evict_app()` and screen-module eviction behavior invoked by the existing transition cleanup.

- [ ] **Step 1: Implement safe app-module eviction**

Import `sys` in `core/app_manager.py`. Add `_evict_app(app_id)` that pops the app instance, removes its `apps.*` module from `sys.modules`, removes the matching attribute from the `apps` package, deletes the local reference, and collects twice. Keep the operation best-effort and limited to modules whose names start with `apps.`.

- [ ] **Step 2: Evict the outgoing non-launcher app before screen cleanup**

In `_switch_to()`, after `on_exit()`, `release_runtime_state()`, and `_release_app_screen_refs()`, evict the old app whenever `old != "launcher"`. Set `current_app = None`, collect twice, and emit `switch.after_evict` under debug logging before `_memory_cleanup_before_enter()`.

- [ ] **Step 3: Add explicit screen-module ownership mapping**

In `ScreenManager`, map each transient screen ID to its `ui.*_screen` module and exclude `screen_ids.LAUNCHER`. Keep the mapping local to `ScreenManager` so shared modules are not removed by prefix matching.

- [ ] **Step 4: Evict modules for screens actually deleted**

During `release_all()`, record each removed screen ID, delete its LVGL tree and native resources as today, then remove only the mapped transient modules and their package attributes. Do not remove a module for a screen retained by `keep_ids`.

- [ ] **Step 5: Preserve LVGL transition behavior**

Leave `_cleanup_screen` and `release_cleanup_screen()` persistent. Do not restore the old cleanup-screen deletion or add a GC after the target app enters.

- [ ] **Step 6: Run the focused tests and verify they pass**

Run:

```powershell
rtk python -m unittest tests.test_app_manager_lazy tests.test_screen_manager_release -q
```

Expected: all focused tests pass, including the new eviction assertions.

### Task 4: Verify lifecycle regression and repository state

**Files:**
- Modify: none
- Test: `tests/test_memory_lifecycle_hardening.py`, `tests/test_keg_filler_app.py`, `tests/test_launcher_app_lifecycle.py`

**Interfaces:**
- Consumes: the completed eviction lifecycle.
- Produces: evidence that existing cleanup, launcher reuse, and Keg exit behavior remain intact.

- [ ] **Step 1: Run all memory and launcher lifecycle tests**

Run:

```powershell
rtk python -m unittest tests.test_app_manager_lazy tests.test_screen_manager_release tests.test_memory_lifecycle_hardening tests.test_launcher_app_lifecycle tests.test_keg_filler_app -q
```

Expected: all tests pass.

- [ ] **Step 2: Run the full available test suite**

Run:

```powershell
rtk python -m unittest discover tests -q
```

Record any pre-existing unrelated failures separately; do not claim the complete suite is green if it is not.

- [ ] **Step 3: Check the diff and working tree**

Run:

```powershell
rtk git diff --check
rtk git status --short
```

Expected: no whitespace errors and only the intended source/test/plan changes are present.

- [ ] **Step 4: Perform hardware acceptance validation**

Flash the build with debug logging enabled and repeat `balance → launcher → keg filler → launcher` at least five times. Confirm `switch.after_evict` appears before launcher entry, memory recovers after eviction, and no `MemoryError` occurs.
