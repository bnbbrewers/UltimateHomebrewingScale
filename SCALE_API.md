# Generic Brewing Scale Integration — HTTP API v1

This document defines a provider-neutral HTTP interface for connecting a brewing scale to brewing software or another self-hosted system.

The interface supports two directions:

- Retrieving batches and ingredient weighing targets.
- Reporting live weights, completed ingredient weighings and keg filling results.

The interface does not require a particular brewing application or MQTT broker.

## 1. Connection settings

A compatible scale firmware should provide these settings:

| Setting | Description |
| --- | --- |
| API base URL | Address of the receiving service, without a trailing slash |
| API token | Token issued by the receiving service |
| Integration enabled | Enable or disable communication with the service |

Example base URL:

`https://brewing.example.com/api/scale/v1`

Use HTTPS outside a trusted local network.

Any reverse proxy in front of the receiving service must allow device requests to reach the API.

## 2. Authentication

Every device request uses an HTTP Bearer token:

```http
Authorization: Bearer <API_TOKEN>
```

Treat the token as an opaque value. Firmware must not depend on a particular token prefix or internal format.

Tokens must not appear in URLs, measurement payloads or diagnostic logs. Browser login cookies and an `Origin` header are not required.

Each physical scale should receive a separate token. The receiving service derives device identity from the token.

Supported scopes:

| Scope | Permission |
| --- | --- |
| `batches:read` | Retrieve batch lists and weighing plans |
| `events:write` | Submit measurements and completed results |

The receiving service should support individual token revocation. Device credentials should grant access only to the integration endpoints.

## 3. General conventions

- Requests and responses use JSON.
- Event requests require `Content-Type: application/json`.
- Responses use `Cache-Control: no-store`.
- Request bodies must not exceed 16,384 bytes.
- Submit one event per request; arrays are not supported.
- All timestamps include a timezone.
- Firmware should use HTTP status codes and machine-readable error codes rather than matching message text.

The reference limits are five requests per second per device, with a burst allowance of 30 requests. Normally, live measurements should be sent at most once per second and only when useful.

## 4. Device endpoints

Paths below are relative to the API base URL.

| Method | Path | Required scope | Purpose |
| --- | --- | --- | --- |
| GET | `/info` | Any valid device scope | Verify connection and retrieve device capabilities |
| GET | `/batches` | `batches:read` | Retrieve available batches |
| GET | `/batches/{batchId}` | `batches:read` | Retrieve a batch weighing plan |
| POST | `/events` | `events:write` | Submit a measurement or completed result |

### GET /info

Example response:

```json
{
  "schema": 1,
  "apiVersion": 1,
  "deviceId": "scale-01",
  "name": "Brewing scale",
  "scopes": [
    "batches:read",
    "events:write"
  ],
  "serverTime": "2026-11-02T12:00:00.000Z",
  "weightUnits": [
    "g",
    "kg"
  ],
  "maxBodyBytes": 16384,
  "maxRequestsPerSecond": 5,
  "eventTypes": [
    "weight",
    "weighing.completed",
    "filling.completed",
    "filling.cancelled"
  ]
}
```

The server-assigned `deviceId` identifies the authenticated device. Clients must not supply another device identity in event payloads.

### GET /batches

Returns batches available for selection.

Example response:

```json
{
  "schema": 1,
  "batches": [
    {
      "batchId": "batch-001",
      "number": "BATCH-001",
      "name": "Helles",
      "phase": "planned",
      "date": "2026-11-02",
      "volumeL": 20
    }
  ]
}
```

Supported phase values:

| Value | Meaning |
| --- | --- |
| `planned` | Planned batch |
| `brewing` | Brew day in progress |
| `fermenting` | Fermentation |
| `conditioning` | Conditioning or maturation |
| `packaging` | Packaging |

Completed batches are omitted from this list. An existing completed batch may still be retrieved directly by ID.

Firmware can offer planned and brewing batches for ingredient preparation, and packaging batches for keg filling.

### GET /batches/{batchId}

Returns the batch’s saved recipe, scaled to its actual batch volume.

Example response:

```json
{
  "schema": 1,
  "batchId": "batch-001",
  "number": "BATCH-001",
  "name": "Helles",
  "phase": "planned",
  "date": "2026-11-02",
  "volumeL": 20,
  "boilMinutes": 60,
  "planVersion": "sha256:RETURNED-64-HEX-DIGEST",
  "items": [
    {
      "additionId": "item-0",
      "ingredientId": "ingredient-001",
      "name": "Pilsner malt",
      "category": "Malz",
      "quantity": 4,
      "unit": "kg",
      "targetWeightG": 4000,
      "use": "Mash",
      "timeMinutes": null,
      "step": "Mash",
      "colorEbc": null
    },
    {
      "additionId": "item-1",
      "ingredientId": "ingredient-002",
      "name": "Hallertauer",
      "category": "Hopfen",
      "quantity": 30,
      "unit": "g",
      "targetWeightG": 30,
      "use": "Boil",
      "timeMinutes": 60,
      "step": "Boil — 60 min",
      "colorEbc": null
    }
  ]
}
```

The `planVersion` value above is a placeholder. Clients must retain and return the actual value supplied by the server.

#### Plan version

`planVersion` identifies the batch volume and weighing-relevant recipe data.

It should remain stable across phase changes and changes unrelated to weighing, such as inventory prices.

Changing relevant quantities, units or ingredient rows produces a different version. Results submitted against an outdated plan are rejected with `stale_plan`.

Firmware must not silently assign a new plan version to an old measurement.

#### Ingredient and addition identity

`ingredientId` identifies an ingredient.

`additionId` identifies an individual recipe row within the returned plan. Multiple additions of the same hop can therefore have different addition IDs.

Firmware must retain these IDs while grouping, sorting, displaying and completing weighings. Ingredient names and translated labels must not be used as identifiers.

#### Quantities and units

| Field | Meaning |
| --- | --- |
| `quantity` | Required amount, already scaled to batch volume |
| `unit` | Source unit |
| `targetWeightG` | Target mass in grams, or `null` when mass is unknown |
| `category` | Ingredient category |
| `use` | Intended use, preferably using BeerXML values |
| `timeMinutes` | Addition time in minutes, if known |
| `step` | Human-readable addition description |
| `colorEbc` | Ingredient colour in EBC, if known |

The reference category values are:

- `Malz`: malt or fermentable ingredients.
- `Hopfen`: hops.
- `Hefe`: yeast.
- `Sonstiges`: other ingredients.

Display labels may be translated independently.

Source quantities in `kg` or `g` have a corresponding `targetWeightG`. Packages, pieces and litres must not be treated as known masses without additional information.

Typical `use` values include `Mash`, `Boil`, `First Wort`, `Aroma` and `Dry Hop`.

For a boil addition, `timeMinutes` means minutes before the end of boiling. It is not elapsed time.

Unknown times and colours are represented by `null`. If the source stores colour in Lovibond, the reference conversion to EBC is multiplication by 1.97.

## 5. Event payloads

### Common fields

| Field | Requirement |
| --- | --- |
| `schema` | Integer `1` |
| `eventId` | Unique event identifier; unchanged on retry |
| `sessionId` | Identifier of the weighing or filling operation |
| `type` | Supported event type |
| `timestamp` | ISO timestamp with seconds and timezone |
| `weight` | Finite numeric net mass |
| `unit` | Exactly `g` or `kg` |
| `stable` | Optional boolean; defaults to false |
| `batchId` | Required for completed weighing and filling events |
| `planVersion` | Required whenever `batchId` is present |
| `additionId` | Required for `weighing.completed` |
| `sequence` | Required for live `weight` events |
| `kegId` | Optional identifier for filling events |
| `volumeL` | Optional explicit filling volume in litres |

Identifiers must contain 1–100 ASCII letters, digits, underscores or hyphens. UUIDs are suitable.

Weights exclude container or keg tare.

`weightG`, `targetWeightG`, `deviationG` and device identity are server-derived response fields. They must not be included as request fields.

Unknown fields and unsupported schema versions are rejected.

### Validation limits

- Maximum net mass: 10,000,000 g.
- Live measurements may be negative down to −100,000 g.
- Completed weighings and completed fillings require positive net mass.
- Cancelled fillings may report zero net mass.
- Explicit volume: 0.01–100,000 L.
- New events may be up to 30 days old or five minutes in the future.
- Live sequence values must be nonnegative safe integers.

An offline measurement retains its original timestamp when eventually delivered.

## 6. Live weight

Example request:

```json
{
  "schema": 1,
  "eventId": "live-00042",
  "sessionId": "weighing-session-1",
  "type": "weight",
  "timestamp": "2026-11-02T12:00:00Z",
  "sequence": 42,
  "weight": 3.995,
  "unit": "kg",
  "stable": false
}
```

Live measurements update the latest device reading. They do not create permanent weighing history.

Within a session, `sequence` must increase monotonically. Older timestamps or non-increasing sequences are acknowledged with `ignored: true` and must not replace a newer reading.

Use a new unique session ID for a new weighing operation.

Optional batch context may include `batchId`, `planVersion` and `additionId`.

Do not queue an entire offline live stream. Send the current reading after reconnecting.

## 7. Completed ingredient weighing

Example request:

```json
{
  "schema": 1,
  "eventId": "weighing-result-1",
  "sessionId": "weighing-session-1",
  "type": "weighing.completed",
  "timestamp": "2026-11-02T12:00:05Z",
  "batchId": "batch-001",
  "planVersion": "sha256:RETURNED-64-HEX-DIGEST",
  "additionId": "item-0",
  "weight": 4.005,
  "unit": "kg",
  "stable": true
}
```

Completed ingredient weighings require `stable: true`.

The stored result includes:

- Normalized actual mass: `weightG`.
- Planned mass: `targetWeightG`.
- Signed difference: `deviationG`.
- Ingredient identity and name.
- `status: "recorded"`.

A weighing records ingredient preparation. Actual addition to the brewing vessel is a separate action.

Receiving a weighing result must not automatically consume inventory a second time or mark an ingredient as added. Any reconciliation of planned and actual consumption requires a separately defined operation.

New weighing sessions create separate history entries. They do not automatically replace or sum earlier results.

## 8. Keg filling results

### Completed filling

Example request:

```json
{
  "schema": 1,
  "eventId": "filling-result-1",
  "sessionId": "filling-session-1",
  "type": "filling.completed",
  "timestamp": "2026-11-02T13:00:00Z",
  "batchId": "batch-001",
  "planVersion": "sha256:RETURNED-64-HEX-DIGEST",
  "kegId": "keg-01",
  "weight": 19.8,
  "unit": "kg",
  "stable": true,
  "volumeL": 19.6
}
```

One session represents one physical keg filling operation. Use a new session for another keg.

`volumeL` must be explicitly supplied when available. The receiving service must not assume that 1 kg of beer equals 1 L.

A result without volume can still be recorded, but cannot be imported as a volume-based packaging record without additional information.

Completed fillings initially have `status: "pending"`. An authorized operator may confirm their import into packaging records.

Confirmation must be atomic and idempotent. It must check that the batch is in the packaging phase and that cumulative packaged volume does not exceed batch volume.

Imported results expose `importedAt` and `packagingId`.

### Cancelled filling

Use `type: "filling.cancelled"` for interrupted filling operations.

Cancelled results remain available as history and must not be imported as completed packaging records.

### Local control

Tare, target evaluation, valve cutoff and no-flow detection remain local to the scale.

Network requests must not delay weight sampling or prevent the valve from closing. This interface provides no remote actuator commands.

## 9. Responses and duplicate handling

### New completed result

HTTP 201:

```json
{
  "schema": 1,
  "accepted": true,
  "duplicate": false,
  "event": {
    "id": "server-result-id",
    "eventId": "weighing-result-1",
    "status": "recorded"
  }
}
```

The `event` object also contains the stored measurement and its associated metadata.

### Repeated completed result

HTTP 200 with `duplicate: true`.

The server returns the existing result, including its current import status.

### Live measurement

HTTP 200:

```json
{
  "schema": 1,
  "accepted": true,
  "duplicate": false,
  "ignored": false
}
```

### Identity rules

The combination of authenticated device and `eventId` uniquely identifies a stored completed result.

- Retrying the same ID and payload returns the existing result.
- Reusing the ID with different data returns `event_conflict`.
- Sending another completed event of the same type for the same session, batch and addition under a different event ID returns `operation_conflict`.

Persist completed event IDs, session IDs and payloads on the device before transmission.

A lost response must result in a retry of the original event, not creation of a new event ID.

Previously stored completed events are recognized before applying new-event age and plan checks.

The reference capacity is 50,000 completed or cancelled results per device. Live readings do not consume this capacity.

## 10. Errors and retry policy

Example error:

```json
{
  "error": "The weighing plan has changed.",
  "code": "stale_plan"
}
```

Human-readable messages may be localized. Firmware must use status and code for decisions.

General malformed JSON or body-limit errors may contain only `error`.

| HTTP | Typical code | Meaning |
| --- | --- | --- |
| 400 | `invalid_request` | Invalid fields or values |
| 400 | `unsupported_schema` | Unsupported payload version |
| 400 | `invalid_timestamp` | Measurement time outside permitted limits |
| 400 | `invalid_addition` | Unknown or unsupported weighing target |
| 401 | `invalid_token` | Missing, invalid, revoked or deleted credentials |
| 403 | `insufficient_scope` | Required permission missing |
| 404 | `batch_not_found`, `not_found` | Unknown batch or endpoint |
| 405 | `method_not_allowed` | Unsupported HTTP method |
| 409 | `stale_plan` | Retrieve the weighing plan again |
| 409 | `event_conflict` | Event ID reused with different data |
| 409 | `operation_conflict` | Operation already completed under another event ID |
| 409 | `event_limit` | Result storage limit reached |
| 413 | — | Request body too large |
| 415 | `unsupported_media_type` | JSON content type required |
| 429 | `rate_limited` | Request rate exceeded |

For network errors, HTTP 429 and 5xx responses, use bounded exponential backoff. Honor `Retry-After` when supplied.

On 401, stop delivery and request valid credentials. On 403, request the missing permission.

Validation and conflict errors require investigation rather than blind retries. In particular, an outdated result must not be silently reassigned to a new weighing plan.

## 11. Administrative operations

Device credentials must not authorize administrative operations.

The receiving application may provide separate operator endpoints for:

- Creating, revoking and deleting device credentials.
- Viewing latest device readings.
- Reviewing completed weighing and filling results.
- Confirming a filling result as a packaging record.

A reference administrative interface can use:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/scales` | List devices and latest readings |
| POST | `/api/scales` | Create credentials using `{name, scopes}` |
| POST | `/api/scales/{id}/revoke` | Revoke a device credential |
| DELETE | `/api/scales/{id}` | Delete a device access record |
| GET | `/api/scale-events?batchId=ID&limit=100` | Retrieve recent results |
| POST | `/api/scale-events/{id}/import` | Confirm a completed filling |

Administrative authentication is separate from the device API.

Completed results should remain available after device access is revoked or deleted. Missing batches must not be recreated by incoming device events.

## 12. Suggested UHS integration

A compatible connector can map the existing UHS API abstraction as follows:

| UHS operation | HTTP API mapping |
| --- | --- |
| `get_batches()` | Retrieve `/batches` and map batch IDs and names |
| `get_malts(batch_id)` | Retrieve the plan and select supported malt mass rows |
| `get_hops_list(batch_id)` | Retrieve hop rows while preserving individual addition IDs |
| Free weighing | Submit controlled-rate `weight` events |
| Completed ingredient weighing | Submit `weighing.completed` |
| Completed or interrupted keg filling | Submit the corresponding filling event |

Malt targets may be converted from `targetWeightG` to kilograms for existing internal interfaces. Hop targets are already provided in grams.

Connector data structures must retain `batchId`, `additionId` and `planVersion` while sorting or removing completed rows.

On memory-constrained devices, close HTTP responses promptly and keep payloads compact.

Validation should cover real hardware, temporary server outages, repeated delivery, revoked credentials and multiple additions of the same ingredient.
