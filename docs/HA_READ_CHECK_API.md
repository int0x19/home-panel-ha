# HA Read/Check Backend API

## Scope

The companion registers four **administrator-only** commands in the normal
authenticated HA WebSocket API. It does not register a parallel HTTP server,
generic proxy, HA service caller, device uploader or frontend editor. Use the
existing HA frontend connection (`hass.callWS`); a browser never contacts ESP32
directly and does not receive its access key, origin or boot nonce.

This is the read/check slice of roadmap 3.8.2, tested on HA 2026.11.0. It uses
the [same paired entry/client](HA_INTEGRATION.md), prepared `capabilities.v1`
profile and fixed source names. Current hardware still needs the separately
authorized metadata firmware before physical pairing. All results explicitly
describe the **separate action preview**, unmanaged authority and unsupported
deployment; the working generated rooms are not yet runtime-configurable.

The later [HA draft checkpoint API](HA_DRAFT_STORAGE.md) adds three separate
administrator-only commands. Those write only HA storage, not ESP32; the four
device-facing read/check operations below retain their original behavior.
The separate [shared-model check](HA_MODEL_VALIDATION.md), `model_check`, runs
only in HA and does not replace the device validator described here.

## Commands

HA supplies the numeric request ID when using `hass.callWS`.

```js
const listing = await hass.callWS({type: "home_panel/config/panels"});
const entryId = listing.panels[0].entry_id;

const status = await hass.callWS({
  type: "home_panel/config/status",
  entry_id: entryId,
});

const imported = await hass.callWS({
  type: "home_panel/config/import",
  entry_id: entryId,
  source: "active", // active | candidate | backup; no paths or URLs
});

const checked = await hass.callWS({
  type: "home_panel/config/validate",
  entry_id: entryId,
  document: imported.document, // original UTF-8 JSON text, not a parsed object
});
```

This is an API example, not a claim of deployment in the user's HA. The
frontend handles an empty panel list, unavailable entries and failed
promises; never select a panel or deploy a document without user choice.

### Panels

Returns `{version: 1, panels: [{entry_id, name, state}]}` from HA entries only,
without device I/O. It includes unloaded/retrying entries so an editor can
explain why a panel is unavailable. Names are HA entry titles, not authority or
device identity. Extra connection fields are rejected, not used as overrides.

### Status

Reads fresh status/capabilities via the pinned client and returns:

- `version: 1`, `entry_id`, `scope: "action_preview_only"`.
- `requires_status_refresh`, a backend recovery flag, not a device state.
- `status`: SD/busy/restarting flags, loaded source/revision, current JSON byte
  limit, HTTP feature names and file metadata for active/candidate/backup/temp.
- `capabilities`: schema/features, supported widget/room kinds, display size,
  actual configured limits and shared decoder inventory. Accepted syntax is
  not proof of complete loaded assets or measured board budgets.
- `authority: {mode: "unmanaged", enforced: false}`, `management_ready: false`
  and `deployment_ready: false` for this negotiated profile.

File metadata contains presence, validity/status codes, size, document revision
and SHA-256. It does not substitute a builtin document when a source is absent.
An idle status refresh clears a prior read/check recovery flag; a busy/restarting
response leaves it set. Scheduled background polls do not clear it.

### Import

Reads one selected source without publishing or applying a file:

1. Read and negotiate the pinned panel's status/capabilities.
2. Export the source through the bounded job/download API, checking source,
   receipt ID/session/revision, byte count, headers and computed SHA-256.
3. Submit those exact bytes to the panel's existing validate-only endpoint.
   Require a successful shared-model report and matching revision/room count.
4. Reread metadata. Reject a changed boot/capability profile or source metadata,
   rather than combining one document with another boot/file's metadata.

On success the status result additionally contains `source`, `revision`,
`sha256`, `bytes`, `document` (exact decoded UTF-8 text), `validation` and
`validator: "panel_shared"`. UTF-8 reencoding of `document` reproduces the
downloaded bytes, including whitespace, key order and newlines. Do not parse
and regenerate it when retaining an original export.

The report is from the device's shared C++ model validator, not a new Python
widget validator. Backend framing/receipt checks do not prove renderer first
frame/trial confirmation or permit unsupported widget families. Import does
not save an HA draft, claim ownership, alter active/candidate/backup files or
activate the imported document.

### Validate

Accepts nonempty text, not an arbitrary URL/path/object. Character count is
bounded before UTF-8 allocation, encoded input is capped at 65536 bytes and the
**fresh device byte ceiling** is enforced again before POST. The prepared board
default remains 16384 bytes, not the larger host schema budget.

Syntactically or semantically invalid JSON may be sent to the common device
validator. A completed negative report is a successful WS response with
`validation.valid: false`, not an SD error. A positive report must match the
input envelope/revision/room count. Responses include current guarded metadata,
`validation` and `validator`, but do not echo/retain the document or save it.
No SD card is required for validate-only when the validator is available.

## Limits, Recovery And Lifecycle

One backend transaction is allowed per paired entry across all browser sessions;
another request gets `panel_busy` immediately, without queuing document buffers.
The underlying shared client continues to serialize device jobs. Scheduled
metadata polling does no I/O during an explicit transaction and never restores
previously failed availability solely because a transaction is busy.

The total transaction budget is 45 seconds; individual client operations retain
their 15-second budgets and bounded job polling. Only export/validate POSTs are
possible; no POST is retried automatically. A failure after attempting a job
sets `requires_status_refresh`, including lost replies, expired receipts,
changed boot/source data, cancellation or malformed reports. Conservative
unknown outcomes may include a request that never reached the panel.

Refresh status explicitly before another job; if the device is still busy,
wait and refresh again. After idle metadata is verified, a **new explicit user
request** may start another import/check. This is not automatic replay or proof
that a lost old report was recovered. No persistent write is involved.

Unload/reconfigure closes the old backend, cancels its active request and
releases its slot. A late result from an old entry/coordinator cannot be
published as a current result. The device may finish an already submitted
ephemeral job; it will not be resumed or replayed by the integration. Browser
disconnection alone does not resubmit a job: an already running transaction is
bounded by its deadline and is not stored as a background document history.

## Errors And Authorization

All commands check `require_admin` server-side before any device I/O or async
handler scheduling. A non-admin receives HA's `unauthorized` error even if they
know a config entry ID. Missing, other-domain, unloaded and reloading entries
are not proxy targets. There is no request field to override address/key.

Stable codes include `panel_unavailable`, `panel_busy`, `invalid_auth`,
`identity_mismatch`, `invalid_document`, `invalid_import`, `not_found`,
`read_conflict`, `expired`, `incompatible_response`, `cannot_connect`,
`outcome_unknown`, `status_refresh_required`, `panel_error` and `internal_error`.
Unknown fields/types/source names use HA's `invalid_format`. No Save/Apply,
restore, discard or actuator commands are registered.

Device error bodies, keys, URLs, nonces and arbitrary exception text are not
included in custom results/errors. Unexpected handler errors produce a fixed
message/log without the document or raw exception. Original exported user text
is intentionally preserved, not modified by a heuristic secret scrubber; valid
runtime schema has no hardware/Wi-Fi/API/OTA credential fields. HA drafts and
portable export design must continue to keep credentials separate.

The configuration API still shares the powerful debug key. Review scoped
credentials and enforce managed authority before write deployment. Plain HTTP
to ESP32 remains limited to a trusted LAN/VPN; Native API encryption does not
encrypt this separate management connection.

## Verification Notes

Backend-only acceptance on 2026-11-07: **70 HA integration/WS/HTTP tests**, **37 standalone
client/backend/native C++ tests** and **six standalone HTTP tests** pass, for
113 targeted checks. The HA run includes the earlier setup/lifecycle tests;
these are not 113 new cases or whole-repository coverage. Its package statement
coverage is 90%, not branch coverage or proof of physical acceptance.

Tests use real HA 2026.11 WebSocket authentication/authorization on loopback,
the HA-owned session and an HTTP fixture representing the device wire protocol.
The same backend is separately tested against the actual C++ HTTP component,
shared decoder and temporary VFS: all three original sources remain unchanged
in content and modification time. These checks are not physical SD/power-loss
or ESP32 heap/stack acceptance. The subsequent [frontend slice](HA_FRONTEND.md)
adds component-browser acceptance through the same actual HA WS backend, not
full installed-HA-shell or physical-panel acceptance.
That combined run passes 74 HA plus the same 43 standalone/native/HTTP checks,
for 117 targeted tests; the earlier backend-only coverage figure is not a
JavaScript/branch coverage claim.

A raw malformed **pre-authentication** WS-close probe, before any companion
handler, left an aiohttp heartbeat timer in this test environment. It is an
unresolved HA/aiohttp test-boundary issue, not fixed by monkey-patching HA or
relaxing cleanup checks here. Anonymous rejection is tested at the official
admin wrapper with no user; authenticated non-admin denial is tested over the
real WS connection. Integration requests/unload pass task/timer cleanup checks.

See [HA's WebSocket extension API](https://contributors.home-assistant.io/frontend/extending/websocket-api/)
for the supported registration/authorization hooks and
[integration testing](HA_INTEGRATION.md#tests) for the pinned environment.
