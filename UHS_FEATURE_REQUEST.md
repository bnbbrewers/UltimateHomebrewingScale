
# Feature request: Generic HTTP integration and outgoing webhooks

Hi!

It would be useful to support a generic HTTP integration alongside the existing Brewfather connection. This would allow Ultimate Homebrewing Scale to work with other brewing applications, automation platforms and self-hosted services.

There are two complementary use cases:

1. Fetch batches and ingredient targets for guided malt and hop weighing.
2. Send measurements and completed weighing or keg filling results to an external service.

A webhook-only mode would already be useful for free weighing. Guided recipe weighing additionally requires a way to retrieve batches and ingredient targets.

## Suggested configuration

Add a generic HTTP provider alongside the existing Brewfather option.

Suggested settings:

- API base URL.
- Optional webhook URL for event delivery.
- Optional API token or configurable authentication header.
- Enable or disable live measurement delivery.
- Measurement update interval.

Example:

```text
API base URL: https://brewing.example.com/api/scale/v1
Authorization: Bearer <API_TOKEN>
```

Existing Brewfather functionality should remain available.

## Retrieving batches and ingredient targets

The existing `ApiBase` abstraction appears suitable for an additional connector.

A possible endpoint structure is:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/info` | Verify connection and supported capabilities |
| GET | `/batches` | Retrieve selectable batches |
| GET | `/batches/{id}` | Retrieve scaled ingredient targets |

The connector could implement the existing methods:

- `get_batches()`
- `get_malts(batch_id)`
- `get_hops_list(batch_id)`

A weighing plan should contain:

- Batch ID and name.
- Actual batch volume.
- Ingredient IDs and names.
- An individual ID for each ingredient addition.
- Target mass with an explicit unit.
- Hop addition use and timing.
- A plan version to detect changed recipe data.
- Optional ingredient colour.

Separate addition IDs are important when the same hop is used at multiple times. These IDs should survive grouping, sorting, selection and completion of individual weighings.

Unsupported units or unknown ingredient colours should remain explicitly unknown.

## Outgoing events

Support HTTP POST requests with JSON payloads.

Suggested event types:

| Event | Purpose |
| --- | --- |
| `weight` | Current net weight |
| `weighing.completed` | Completed ingredient weighing |
| `filling.completed` | Completed keg filling |
| `filling.cancelled` | Interrupted keg filling |

Common fields could include:

- Payload schema version.
- Event ID.
- Weighing or filling session ID.
- Measurement timestamp with timezone.
- Weight and unit.
- Weight stability.
- Optional batch and ingredient addition context.
- Optional keg ID and explicitly calculated filling volume.

Example completed weighing:

```json
{
  "schema": 1,
  "eventId": "result-uuid",
  "sessionId": "weighing-uuid",
  "type": "weighing.completed",
  "timestamp": "2026-11-02T12:00:00Z",
  "batchId": "batch-001",
  "planVersion": "sha256:RETURNED-64-HEX-DIGEST",
  "additionId": "item-0",
  "weight": 4.005,
  "unit": "kg",
  "stable": true
}
```

For standalone weighing, batch and ingredient fields could be omitted.

For live measurements, an increasing sequence number would help receivers ignore delayed or out-of-order readings.

## Reliable delivery

Completed results should be retained locally until acknowledged by the receiver.

If the connection fails or the response is lost:

- Retry the same event ID and payload.
- Preserve the original measurement timestamp.
- Use bounded exponential backoff.
- Avoid generating a new event ID on each retry.

A receiver could acknowledge newly stored results with HTTP 201 and repeated results with HTTP 200 and `duplicate: true`.

Authentication failures, missing permissions and outdated recipe plans should produce actionable messages.

Live measurements do not need the same persistent queue as completed results. Sending the current reading after reconnecting should normally be sufficient.

## Keep filling control local

HTTP communication must not interfere with weighing or keg filling.

Tare handling, target detection, relay control, valve cutoff and no-flow protection should continue to run locally, even if Wi-Fi or the receiving service becomes unavailable.

The integration would report results rather than require remote approval to close the valve.

If filling volume is included, it should be an explicit estimate or measurement. Receivers should not automatically assume that one kilogram of beer equals one litre.

## Suggested implementation stages

1. Generic outgoing webhooks for standalone weighing.
2. A configurable HTTP provider for batches and ingredient targets.
3. Completed ingredient weighing results.
4. Keg filling completion and cancellation events.
5. Persistent retry handling for completed results.

## Acceptance criteria

- Brewfather remains selectable and functional.
- Another compatible service can provide selectable batches and scaled targets.
- Multiple additions of the same hop retain their separate identities and timings.
- Completed results survive temporary network loss without duplicate processing.
- Revoked credentials and changed weighing plans are reported clearly.
- Live update traffic remains configurable and bounded.
- Keg filling stops correctly when the network or receiving service is unavailable.

Would you consider a generic provider interface and outgoing webhook support, or accept a contribution implementing these capabilities?
