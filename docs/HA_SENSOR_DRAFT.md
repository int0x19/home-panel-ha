# Numeric Sensor And Group Drafts

## Scope

Development 0.1.2 extends the room/action form with numeric `sensor.*`
placements. It uses core 0.1.2's shared `runtime-draft.mjs` transactions,
stable IDs, feature normalization and mixed-room fit guards. There is no new
schema, browser layout engine, device writer or HA state connection.

Edit entity, display name, unit, sensor class and destination room. Select
Standalone, an existing group, or New group; an optional title is shared by
the group. Clearing the title retains compact unnamed grouping. Edits/moves
preserve widget IDs; deleting the last member removes only the orphan group
definition. Sources may repeat across rooms. Opaque profiles/settings remain
read-only and preserved. Ordinary rooms reject overflow instead of scrolling.

The existing entity picker has a separate sensor scope with bounded name/unit/
class defaults. Selection fills only empty fields; custom settings survive.
Unavailability is not a reason to erase bindings. Raw values and arbitrary
attributes are not returned. Choosing/editing affects only the local draft.

Existing exact originals, independent Python/device validation, export,
HA checkpoints/history/conflicts and navigation guards retain their meaning.
Save in HA is not Send/Save candidate/Apply on ESP32.

## Capability Gate

Add sensor requires both `widget.sensor` and `sensor` in the negotiated widget
inventory. Groups additionally require `sensor-groups.v1`. Sensors cannot be
placed on Actions pages. A capability change still blocks mutations until a
fresh draft is explicitly opened; HA entities never widen device capabilities.

The current physical configuration API is action-only, so Add sensor stays
disabled there. Tests use a synthetic future reading profile with real HA
registry/checkpoint/model WebSocket handling. Binary-status editing, runtime
publication/authority and device cutover remain later work.

## Verification

The HA 2026.11.0 suite passes 212 tests, including packaging with the exact
core 0.1.2 wheel. Chromium covers action-only refusal, sensor selection,
unavailable-state metadata, grouped temperature/humidity, an adjacent action,
stable IDs, an optional group title, HA save/load and independent Python
checking. Twelve form captures cover EN/RU, light/dark and 320/390/1280px in
`build/ha-frontend/`. Five upstream deprecation warnings remain unchanged.

The actual browser checkpoint is exported as `build/ha-frontend/sensor-draft.json`
(5995 bytes, revision 41 in this fixture). The existing Linux C++/LVGL path
renders it at 320x480 with mock 25.1 C / 48% readings, no overflow or command.
The firmware repository's ignored `build/runtime/sensor-draft-acceptance/`
contains captures. Its native checks also require the strict action-only
decoder to keep rejecting this family. These are host/component checks, not
installed-user-HA or physical-device acceptance.

Next accept the runtime readings capability/storage boundary and implement
guarded ownership-aware Send/Apply with flash-generation/base checks and
known-good recovery. No ESP32 compile/OTA, SD access or household action was
performed; development 0.1.2 has not been published to Marketplace.
