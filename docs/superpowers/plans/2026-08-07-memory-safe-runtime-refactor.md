# Memory-Safe Runtime Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce boot and workflow memory pressure, centralize HTTP lifecycle handling, harden LVGL/resource cleanup, and preserve existing UHS métier behavior.

**Architecture:** Keep the existing managers and application boundaries. Make screen creation, Wi-Fi startup, API connector creation, HTTP response handling, and runtime-state release explicitly lazy and centralized. Use the local ignored `tests/` harness for regression tests because the repository intentionally keeps tests outside Git.

**Tech Stack:** MicroPython/UIFlow2, LVGL, M5Stack Dial, `requests2`, host-side Python `unittest`.

---

## Files and responsibilities

- Modify `core/screen_manager.py`: empty-by-default screen registry and disposable transition screen.
- Modify `core/app_manager.py`: explicit app runtime cleanup and transition lifecycle.
- Modify `core/hardware_manager.py` and `devices/wifi.py`: demand-driven Wi-Fi and one-pass hardware events.
- Create `core/http_client.py`: shared HTTP request, retry, response-spooling, status, close, and GC policy.
- Modify `updater/http_client.py`: compatibility facade over the shared transport and updater-specific diagnostics.
- Modify `api/brewing_software_api.py` and `api/brewfather_api.py`: use the shared transport and remove duplicated HTTP behavior.
- Modify `core/api_factory.py`: lazy connector creation.
- Modify `apps/malt_app.py`: release selection UI/data before the second API request.
- Modify `webportal/setup_portal_service.py` and `webportal/setup_portal.py`: bounded request parsing and shared size limits.
- Modify `memory_debug.py`: truthful collection behavior and optional Python heap fragmentation metrics.
- Modify `main.py` and `README.md`/`DEBUG_GUIDE.md`: startup policy, memory policy, and validation documentation.
- Use ignored local tests under `tests/` for every red-green cycle; do not force-add them to Git.

### Task 1: Establish local regression coverage

**Files:**
- Create locally: `tests/test_refracto_startup.py`
- Create locally: `tests/test_refracto_http.py`
- Create locally: `tests/test_refracto_lifecycle.py`

- [ ] **Step 1: Write failing startup tests**

```python
def test_screen_manager_does_not_create_launcher_without_explicit_initial_screen():
    manager = ScreenManager(i18n=None, initial_screen_id=None)
    assert manager._screens == {}

def test_api_factory_does_not_import_connector_until_requested():
    factory = ApiFactory()
    assert factory._connectors == {}
    assert factory.get("brewing") is None
```

- [ ] **Step 2: Write failing HTTP tests**

Cover response objects exposing only `raw`, only `iter_content`, only bounded `content`, and a response whose `close()` must be called. Add a test that a large non-streaming archive is rejected before unbounded allocation.

- [ ] **Step 3: Write failing lifecycle tests**

Assert that `release_cleanup_screen()` deletes the temporary LVGL root and that a transition calls `on_exit`, cleanup, app construction, `on_enter`, and transition-screen release in that order.

- [ ] **Step 4: Run the focused tests and confirm expected failures**

Run:

```powershell
rtk python -m unittest tests.test_refracto_startup tests.test_refracto_http tests.test_refracto_lifecycle -v
```

Expected: failures for the missing lazy connector, cleanup release method, and shared response-policy behavior.

- [ ] **Step 5: Commit the local test harness outside Git**

Do not add the ignored `tests/` files to the branch. Keep them available for the implementation and verification commands.

### Task 2: Make startup and screen lifecycle lazy

**Files:** `core/screen_manager.py`, `core/app_manager.py`, `main.py`

- [ ] **Step 1: Implement empty-by-default screen creation**

Change the constructor condition to create the launcher only when `initial_screen_id == screen_ids.LAUNCHER`. Preserve explicit lazy creation through `get(screen_ids.LAUNCHER)`.

- [ ] **Step 2: Add transition-screen release**

Implement:

```python
def release_cleanup_screen(self):
    screen = self._cleanup_screen
    self._cleanup_screen = None
    self._cleanup_label = None
    if screen is None:
        return
    try:
        screen.delete()
    except Exception:
        pass
```

Call it after the new app enters and its screen is loaded. Never delete it while it is the active LVGL screen.

- [ ] **Step 3: Add an explicit app runtime cleanup hook**

Add `release_runtime_state()` to `BaseApp`, have existing apps clear large workflow structures there, and call it from `AppManager._switch_to()` immediately after `on_exit()` and before screen cleanup. Retain `release_screen_refs()` as compatibility during migration.

- [ ] **Step 4: Run lifecycle tests**

```powershell
rtk python -m unittest tests.test_refracto_startup tests.test_refracto_lifecycle -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
rtk git add core/screen_manager.py core/app_manager.py main.py
rtk git commit -m "refactor: make startup screens and transitions lazy"
```

### Task 3: Make Wi-Fi and API creation demand-driven

**Files:** `core/hardware_manager.py`, `devices/wifi.py`, `core/api_factory.py`, `api/brewing_software_api.py`

- [ ] **Step 1: Write failing demand-driven tests**

Assert that `HardwareManager.tick()` does not call `_start_connect()` on an unused `WifiDevice`, while `ensure_connected()` still starts it. Assert that `ApiFactory.get("brewing")` creates and caches the connector exactly once.

- [ ] **Step 2: Implement lazy Wi-Fi tick behavior**

Keep `WifiDevice.tick()` for an already-requested connection, but make it return without starting a connection until `request_connection()` or `ensure_connected()` marks the device as requested. `HardwareManager.tick()` may continue servicing an active connection.

- [ ] **Step 3: Implement a lazy API factory**

Replace eager `_build()` with a connector map/factory map. `get("brewing")` imports and instantiates `BrewfatherAPI` on first request, then stores it. `as_dict()` must not instantiate connectors; applications use `get()` through the existing API map adapter.

- [ ] **Step 4: Remove API-to-hardware singleton coupling**

Allow `ApiBase` to receive a `wifi_device` or a transport callback. `BrewfatherAPI` obtains the existing hardware Wi-Fi once from the factory instead of importing `HardwareManager` inside every request.

- [ ] **Step 5: Run demand-driven tests and existing local tests**

```powershell
rtk python -m unittest tests.test_refracto_startup tests.test_refracto_http -v
```

Expected: PASS for no boot Wi-Fi/API allocation and one-time connector creation.

- [ ] **Step 6: Commit**

```powershell
rtk git add core/hardware_manager.py devices/wifi.py core/api_factory.py api/brewing_software_api.py
rtk git commit -m "refactor: defer Wi-Fi and brewing API initialization"
```

### Task 4: Centralize HTTP response handling

**Files:** `core/http_client.py`, `updater/http_client.py`, `api/brewfather_api.py`, `updater/workflow.py`, `updater/github_release.py`

- [ ] **Step 1: Write the shared transport tests first**

Test these contracts:

```python
assert spool_response_to_file(RawResponse(b"abc"), path) == "raw"
assert spool_response_to_file(IterResponse([b"a", b"bc"]), path) == "iter"
assert spool_response_to_file(ContentResponse(b"abc"), path, max_content_bytes=8) == "content"
with assert_raises(BodyTooLargeError):
    spool_response_to_file(ContentResponse(b"x" * 9), path, max_content_bytes=8)
assert response.closed is True
```

- [ ] **Step 2: Implement `core/http_client.py`**

Provide `get()`, `default_requests_module()`, `response_header()`, `response_text()`, `spool_response_to_file()`, `read_response_json()`, `remove_file()`, `close_response()`, and `gc_hard()`. The spooler tries `raw`, then `iter_content`, then bounded `content`, then bounded text. It never silently loads an unbounded archive body.

- [ ] **Step 3: Preserve updater imports through a facade**

Make `updater/http_client.py` re-export the shared transport functions and retain updater-specific `stats_text()`, `snapshot()`, and logging helpers. Update updater callers only where signatures need the body policy.

- [ ] **Step 4: Route Brewfather through the shared transport**

Remove `ApiBase._get()`'s direct `requests2` import and use the shared request helper. Keep JSON spooling in one place and parse only after response close.

- [ ] **Step 5: Route updater metadata and archives through the same lifecycle**

Use the shared JSON spooler for GitHub and manifest requests. Use the file-only archive policy for the TAR download; allow the bounded content fallback only when the declared archive size is below the configured small-body limit.

- [ ] **Step 6: Run HTTP tests**

```powershell
rtk python -m unittest tests.test_refracto_http -v
```

Expected: PASS for all response variants, close behavior, size limits, and temporary-file cleanup.

- [ ] **Step 7: Commit**

```powershell
rtk git add core/http_client.py updater/http_client.py api/brewfather_api.py api/brewing_software_api.py updater/workflow.py updater/github_release.py
rtk git commit -m "refactor: centralize memory-safe HTTP transport"
```

### Task 5: Reduce workflow and portal allocation peaks

**Files:** `apps/malt_app.py`, `apps/hop_app.py`, `webportal/setup_portal_service.py`, `webportal/setup_portal.py`

- [ ] **Step 1: Write failing peak-behavior tests**

Assert that Malt clears selection items before `get_malts()` and that both portal implementations reject a `Content-Length` over the configured maximum without accumulating it.

- [ ] **Step 2: Release Malt selection state before network access**

Clear the selection screen’s item source, drop the screen reference, call the screen manager cleanup, then request malts. Keep the selected batch ID as a scalar.

- [ ] **Step 3: Add shared portal limits**

Define explicit maximum header and body sizes in one module. Reject invalid or oversized `Content-Length` values before receiving the body. Replace repeated `bytes += chunk` accumulation with bounded accumulation and clear request buffers after dispatch.

- [ ] **Step 4: Bound portal response construction**

Keep the existing chunked send behavior. Add a maximum rendered HTML size and reject or simplify forms that exceed it. Delete local HTML/bytes references after scheduling the response.

- [ ] **Step 5: Run focused portal/workflow tests**

```powershell
rtk python -m unittest tests.test_refracto_http tests.test_refracto_lifecycle -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
rtk git add apps/malt_app.py apps/hop_app.py webportal/setup_portal_service.py webportal/setup_portal.py
rtk git commit -m "perf: bound portal and recipe workflow memory"
```

### Task 6: Correct memory instrumentation and event ownership

**Files:** `memory_debug.py`, `core/app_manager.py`, `core/screen_manager.py`, `devices/button.py`, `main.py`, `DEBUG_GUIDE.md`

- [ ] **Step 1: Write instrumentation tests**

Assert that `snapshot(..., collect=True)` invokes collection exactly once and that disabled snapshots do not import or query C heap diagnostics.

- [ ] **Step 2: Make collection semantics truthful**

Pass the caller’s `collect` flag through all `_mem_snapshot()` wrappers. Keep production debug helpers lazy. Add a best-effort `micropython.mem_info(1)` diagnostic only under `DEBUG`, without allocation probes in normal operation.

- [ ] **Step 3: Centralize button sampling**

Sample the raw button once from `HardwareManager.tick()` and expose queued short/long events. Update apps to consume those events without calling the raw button state updater a second time.

- [ ] **Step 4: Document measurement points**

Update `DEBUG_GUIDE.md` with the exact boot, screen, Wi-Fi, HTTP, JSON, portal, and updater markers and explain that `c_largest` is the fragmentation-sensitive metric.

- [ ] **Step 5: Run instrumentation tests**

```powershell
rtk python -m unittest tests.test_refracto_lifecycle -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
rtk git add memory_debug.py core/app_manager.py core/screen_manager.py devices/button.py main.py DEBUG_GUIDE.md
rtk git commit -m "perf: make memory diagnostics and input ownership explicit"
```

### Task 7: Synchronize documentation and compatibility contracts

**Files:** `README.md`, `INSTALLATION.MD`, `api/README.md`, `webportal/setup_portal.py`, `webportal/setup_portal_service.py`

- [ ] **Step 1: Update runtime documentation**

Document that Wi-Fi starts only for API, portal, or updater workflows; document the shared HTTP transport and the branch’s memory validation procedure.

- [ ] **Step 2: Verify compatibility facade behavior**

Keep `webportal.setup_portal` importable and ensure it delegates to the current service without duplicate state or contradictory limits.

- [ ] **Step 3: Run documentation consistency checks**

```powershell
rtk rg -n "setup_portal|setup_portal_service|WIFI_SSID|UPDATE_ON_BOOT|UPDATE_CHANNEL|requests2" README.md INSTALLATION.MD api webportal updater main.py
```

Expected: no obsolete module name or startup behavior remains undocumented.

- [ ] **Step 4: Commit**

```powershell
rtk git add README.md INSTALLATION.MD api/README.md webportal/setup_portal.py webportal/setup_portal_service.py
rtk git commit -m "docs: document demand-driven runtime and HTTP policy"
```

### Task 8: Full verification and hardware handoff

**Files:** no production changes unless verification exposes a regression.

- [ ] **Step 1: Run AST validation**

```powershell
rtk python -c "import ast, pathlib; files=[p for p in pathlib.Path('.').rglob('*.py') if not any(x in {'.git','.worktrees','__pycache__','.pytest_cache'} for x in p.parts)]; [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print('ast_ok files={}'.format(len(files)))"
```

Expected: `ast_ok` with no traceback.

- [ ] **Step 2: Run the complete local regression suite**

```powershell
rtk python -m unittest discover tests -q
```

Expected: zero failures and zero errors for the local harness. Any tests unavailable because they are external must be reported explicitly.

- [ ] **Step 3: Verify branch and commit history**

```powershell
rtk git status --short
rtk git log --oneline --decorate -12
```

Expected: clean worktree, all refactor commits on `test-refracto`, and `main` unchanged.

- [ ] **Step 4: Prepare Dial validation checklist**

Measure boot, launcher, scale, Malt, Hop, Settings, portal first request, API JSON parse, updater manifest, updater archive, and 20 repeated app transitions. Record `py_free`, `c_free`, and `c_largest` before and after each boundary and check for monotonic memory loss.

