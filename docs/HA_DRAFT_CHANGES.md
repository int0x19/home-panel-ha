# Draft Change Summary

## Scope And Workflow

The action editor can compare committed draft fields with either the exact
imported original or the last explicitly read/saved HA checkpoint. Choose the
base and press **Compare**. Uncommitted room/action fields must first be updated
or cancelled. A checkpoint baseline requires a fresh HA storage revision; after
a conflict/lost reply/reconnect, explicitly load the checkpoint before using it.
The original baseline remains usable without fresh ESP32 metadata.

The result is an HA-only structural summary, independent of **In HA** validation,
**On ESP32** validation and **Save in HA**. It never changes either input,
checkpoints, SD, the active screen or any household device. It is not a patch,
merge, revision history, permission to deploy or a rollback operation.

Each comparison identifies both exact input SHA-256 digests/UTF-8 byte counts
and numeric document revisions. Whitespace and object key ordering do not create
changes; revision-only changes show no structural changes with the revision
pair still visible. Canonical JSON types remain distinct (`true` is not `1`);
this is not semantic normalization or RFC 8785 numeric equivalence.

## Reported Changes

- Rooms: addition, removal, changed name/type/groups/other fields and changed
  relative order. Insertions/removals do not falsely reorder retained rooms.
- Room widgets: addition, removal, changed name/entity/settings/type/other
  fields, unambiguous cross-room moves and relative order of retained widgets.
- Widget identity is **room-local** in the existing runtime contract. A move
  is inferred only when that ID occurs once in each document. Repeated IDs in
  different rooms stay separate; ambiguous movement is shown as removal/addition
  rather than silently inventing global identity. Duplicate room IDs or duplicate
  IDs within one room refuse comparison instead of overwriting an index entry.
- Panel settings, appearance, required features, reusable views and attention
  are reported as changed sections. Their private/unrecognized values are not
  expanded or returned. This does not make opaque sections editable.

Displayed names are bounded to 256 characters. The response includes at most
64 entries and 32 KiB of canonical UTF-8 JSON. Aggregate counts cover all changes;
`truncated` indicates omitted details. The list is deterministic. It is a summary
of configuration, not live entity state, sensor values or HA registry events.

## Backend Boundary

Administrator-only authenticated WS command:

```js
const changes = await hass.callWS({
  type: "home_panel/config/model_changes",
  entry_id: panelEntry,
  base: originalJSONText,
  document: draftJSONText,
});
```

The entry must be a paired companion, but may be offline/unloaded. There are no
path, address, capability, credential or service-call overrides. Both texts use
the checkpoint's existing 64 KiB UTF-8/framing/finite/duplicate-key guard; this
reuses shared encoding and does not introduce an HA runtime-schema validator.
`model_validated`, `device_checked` and `deployment_ready` are always false.
Input digests identify submitted text; they do not attest that it came from ESP32.

HA executor work shares one slot per entry with full model checks. A disconnected
waiter cannot release a still-running worker and start an unbounded second job.
Entry removal and frontend connection/user/entry epochs discard late results.
The editor additionally checks local draft version and chosen base. Editing or
changing the base marks the old comparison previous; reset/restore clears it.
Request failures do not invalidate device validation or HA checkpoint tokens.
No automatic polling, comparison, retry, Save, upload or Apply is performed.

## Acceptance

Tests cover exact digests, revision/formatting, stable/local IDs, ambiguous moves,
relative ordering, unknown section preservation, JSON type changes, malformed/
oversized/nonfinite input, count/UTF-8 response limits, administrator enforcement,
offline operation, shared-worker cancellation and fixed credential-free errors.
Chromium uses actual HA 2026.11 auth/WS/Store to cover original/saved comparisons,
checkpoint conflicts, stale reports, responsive EN/RU light/dark layouts at
320/390/1280px and unchanged model/storage/device state.

The separate loopback fixture preview has no HA comparison worker. Like its
validation controls, Compare explicitly reports unavailable there instead of
replaying a static report for an unrelated document. Browser acceptance and
saved screenshots exercise the actual backend, not that visual fixture.
