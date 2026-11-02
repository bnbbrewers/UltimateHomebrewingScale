# Generic HTTP integration

This implementation follows `UHS_FEATURE_REQUEST.md` and `SCALE_API.md`.
Brewfather remains the default provider. No receiving application is required
by name; the receiver implements the documented HTTP API v1 contract.

## Setup

In the setup portal, open **Brewing → Generic HTTP**, save, then reboot.
For guided ingredient weighing and batch-associated keg results:

```python
BREWING_SOFTWARE = "generic_http"
HTTP_INTEGRATION_ENABLED = True
HTTP_API_BASE_URL = "https://brewing.example.com/api/scale/v1"
HTTP_API_TOKEN = "<opaque device token>"
HTTP_WEBHOOK_URL = ""  # empty selects API base URL + /events
HTTP_LIVE_ENABLED = True
HTTP_MEASUREMENT_INTERVAL_MS = 1000
```

Issue the device token with `batches:read` and `events:write` scopes. The client
uses `Authorization: Bearer ...` and JSON POST bodies. The optional webhook URL
overrides only the event destination. It uses the same Bearer token. Keep the
endpoint and token in device configuration, not in source control. HTTPS is
recommended outside a trusted local network. Credentials are masked in the
portal, but are stored in configuration and included in configuration backups;
protect the device and backups as you do the existing Brewfather credentials.

The integration switch disables the HTTP provider and event delivery. The
Brewfather provider remains usable independently.

For webhook-only free weighing, keep the current provider, enable the HTTP
integration, set `HTTP_WEBHOOK_URL`, and enable live delivery. The base URL may
be empty. This mode sends `weight` events without batch fields. Recipe and keg
results require batch/plan context from the generic provider and cannot be
reported against Brewfather IDs using this API. Local Brewfather weighing and
local keg control remain available in webhook-only mode.

## Clock and capabilities

`GET /info` checks schema/API version and supplies `serverTime`. Valid UTC ISO
values ending in `Z` or `+00:00` initialize the event clock without changing old
measurements. The worker retries failed initial clock discovery once a minute.
The guided batch picker also checks `/info`. A webhook-only device without a
base URL needs an already-correct UTC RTC. An uninitialized clock prevents new
events; it never replaces their timestamps with delivery time. No external NTP
service is required by this implementation.

## Guided weighing

Planned and brewing batches are selectable. Plans already contain scaled
masses, so the firmware applies no second volume scaling. Malt mass is mapped
to kilograms for compatibility while preserving the exact gram target. Hop
mass remains in grams, including sub-gram targets.

Each malt row or hop addition retains its original `batchId`, `additionId`,
`ingredientId` and `planVersion`. Hop additions are separate list entries even
when their names or timings match. Display labels and vessel grouping do not
identify results. Hop use/timing is retained; the server's step label is used
without interpreting boil time as elapsed time.

Only positive, finite targets with source units `g` or `kg` are selectable.
Other source units and unknown masses are skipped rather than converted into
fictional masses. Unknown EBC remains `None`; the connector does not invent a
colour. The complete source plan remains available through `get_plan()`.

A confirmed ingredient result must be currently within tolerance and stable
according to the local scale's existing five-sample stability check. The row
is removed only after the completed event is saved locally. A failed save
keeps the row available and displays the error. Brewfather's existing workflow
is unchanged when it has no generic plan context.

## Filling

With the generic provider, select a packaging batch before selecting a keg.
The returned plan version remains attached to that physical filling session.
Resuming after no-flow detection retains the same session. A new keg starts a
new session. Batch selection and HTTP plan retrieval happen before filling.

Before opening the relay, event networking is suspended and any already-active
request is allowed to finish. No HTTP requests run while the valve is open or
while a stalled fill is waiting to resume. Tare, target detection, relay cutoff
and no-flow protection stay in the local state machine.

At the target, the relay closes **before** persistence or HTTP delivery.
Exiting an unfinished or stalled fill closes it and records `filling.cancelled`.
Reported mass subtracts the calibrated empty keg mass. A stopped fill may have
zero mass; completed fills require positive mass. Filling stability is reported
from the scale, rather than unconditionally claimed. A valid clock and an
available outbox slot are checked before beginning a batch-associated fill.

No `volumeL` is reported: the existing firmware's local volume/weight conversion
is not treated as an independent beer-density measurement. The server can
record a mass-only result for later review. Keg names are not invented API keg
IDs. This implementation does not add a separate keg-ID/density setting or
remote actuator commands.

A live reading can be retained in memory during filling, but transmission
resumes only after closing the valve. Long-press exit is a cancellation; loss
of device power closes the relay through the existing boot/hardware behavior,
but cannot create a final measurement after power has disappeared.

## Delivery and recovery

Completed/cancelled results are atomically staged in `storage/scale_events/`.
Each file contains the original JSON request, including its IDs, session,
measurement timestamp and weighing plan. IDs are random 128-bit ASCII hex.
Pending events are recovered after reboot; complete staged files are promoted
to pending files. Invalid staged files are retained for inspection.

- HTTP 200/201 with schema 1 and `accepted: true` acknowledges delivery. A
  duplicate acknowledgement removes the same pending result normally.
- Lost responses, transport errors, HTTP 429 and 5xx retry the original body.
  Exponential backoff is bounded at 300 seconds. `Retry-After` seconds and HTTP
  dates are respected even when longer. Successful traffic is capped at one
  event request per second.
- HTTP 401/403 pauses transmission until the operator updates credentials or
  permissions and reboots. Pending records stay on disk.
- Other validation/conflict errors retain the original file as `.blocked`.
  The launcher displays an actionable error, including `stale_plan` where
  relevant. Old results are never assigned a new plan version automatically.
- Live readings have a monotonic sequence within each random session. They
  occupy one replaceable in-memory slot, are sampled at most once per configured
  interval (minimum one second), and are not written to flash. After an outage,
  the current reading replaces prior readings; completed events have priority.

The device outbox holds **128** completed or blocked results, independent of
the server's larger storage limit. Full storage stops new tracked operations
rather than deleting older results. File-system errors are shown to the
operator. Pending and blocked events are excluded from firmware packages and
protected against update archive replacement. Factory reset/formatting or a
failed flash filesystem can still destroy local records. Outbox files are not
part of the existing configuration backup.

For rejected results, inspect the retained JSON and error on the device before
manually retrying or archiving it. After fixing the receiver, an operator can
rename `.blocked` to `.json` to retry the **same** request. Do not change IDs,
weights, timestamps or plan versions to bypass conflicts. If the recipe truly
changed, investigate the historical result separately and obtain a fresh plan
for a new physical weighing. The firmware does not expose a bulk deletion or
automatic rewriting operation.

## Verification

Run the portable regression suite:

```sh
python tools/verify_scale_http.py
```

It covers repeated hop additions, unknown units/colour, batch phases, preserved
sub-gram targets, response cleanup, JSON/Bearer requests, persistence across
restart, lost acknowledgements, actual worker retry/drain behavior, revoked
credentials, stale-plan quarantine, rate bounds, clock checks, outbox capacity,
firmware update protection, valve-before-persistence ordering, network
suspension and unchanged local no-flow cutoff.

All runtime Python modules also pass `mpy-cross` syntax compilation. These
checks do not validate the actual UIFlow2 `requests2` thread behavior, TLS heap
usage, LVGL layout or physical relay/load-cell timing. Before relying on this
firmware, validate on an M5Dial with the intended firmware and receiver:

1. Test Brewfather and disabled-integration startup.
2. Select a generic batch, weigh repeated hop additions, and verify distinct
   addition IDs and original plan versions in the receiver.
3. Disconnect Wi-Fi/stop the receiver, confirm results, reboot, reconnect, and
   verify a single stored result after lost acknowledgements.
4. Revoke a token, restrict scopes and change a recipe; verify retained data
   and the credential/permission/stale-plan messages.
5. During a fill, disconnect networking and stop the receiver. Check physical
   cutoff and no-flow protection; check resumed vs cancelled sessions and net
   mass. No HTTP request may be active while the relay is open.
6. Check heap headroom with TLS and the UI open. If `_thread` is unavailable,
   delivery remains disabled with a visible error and saved results stay local.
