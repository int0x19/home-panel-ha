# Room/Action Draft Editor

Development 0.1.2 adds capability-gated numeric sensors and groups; see
[sensor editing](HA_SENSOR_DRAFT.md). The action pilot history below does not
imply that the deployed action-only API now accepts sensors.

## Scope

The HA companion now includes a structured **Draft** tab for the action pilot.
It edits a local copy of a checked export, not the running panel. Three
[HA-only checkpoint commands](HA_DRAFT_STORAGE.md) save/load/delete a draft.
The subsequent [candidate Send extension](HA_CANDIDATE_SEND.md) explicitly stores
checked bytes in flash. [Apply](HA_CANDIDATE_APPLY.md) is a separate saved-candidate
action, never an implicit deployment of unfinished fields. There is no SD upload
or household-action method.
Generated production `panel.yaml` rooms are unchanged.

**Save in HA** explicitly retains one committed draft plus its exact original
and capability snapshot per panel. Selecting that panel again restores the
checkpoint, even if the panel integration is currently offline/unloaded.
Up to three [previous checkpoints](HA_DRAFT_HISTORY.md) can be explicitly opened
as unsaved drafts. There is no autosave, browser storage or automatic cross-tab
merge. [Unsaved-navigation protection](HA_NAVIGATION.md) now requests a discard
decision for cancelable same-document departures, including HA sidebar/settings
and browser Back/Forward in supported browsers. Cancel retains URL/history and
all local fields; confirm leaves without saving. Reload/full-document departures
retain the browser warning. Unsaved data still disappears on confirmed departure,
forced teardown or reload; older browsers explicitly warn about limited history
protection. Only explicit checkpoints survive a fresh component/session.

## Workflow

1. Select a paired panel and explicitly import active/candidate/backup through
   the existing [read/check workflow](HA_FRONTEND.md#workflow).
2. Select **Edit draft**. The original byte-for-byte download and independent
   raw-check input are retained unchanged. The draft has its own suggested next
   revision, above the observed loaded/file/flash-high-water revisions; this is not a reserved
   device revision or authorization to deploy.
3. Create, rename, reorder or delete rooms. Unicode names use the negotiated
   UTF-8 string budget. Change a compatible page between ordinary Room and
   Actions; Actions pages paginate, while ordinary rooms cannot overflow.
4. Add/edit/delete/reorder actions or move them between compatible pages.
   Rename, reordering, entity edits and moves preserve existing IDs. New IDs use
   `crypto.getRandomValues`, including trusted-LAN HA pages where
   `randomUUID` is unavailable outside a secure context.
5. Select entity, label, bundled icon, activation (`tap`/`hold`/`confirm`) and
   enabled state. Script Stop is offered only with the negotiated feature;
   scenes/buttons never receive Stop settings. The magnifier opens an
   authenticated HA registry/state picker for `script`, `scene`, `button` and
   `input_button`, with name/ID search, domain/area filters and explicit paging.
   Entity IDs may also be typed; up to 50 existing `hass.states` suggestions
   remain available without a catalog request. No extra state connection,
   device query or service call is opened.
6. Commit or cancel uncommitted fields before export/validation. **Export draft**
   downloads an independent compact JSON document. **In HA** invokes the full
   shared Python model validator without contacting ESP32, even offline.
   **On ESP32** invokes the negotiated device shared-validator path, without
   writing SD or changing the active screen. The two reports are independent;
   neither authorizes deployment. See [model validation](HA_MODEL_VALIDATION.md).
7. **Save in HA** creates a local HA checkpoint, without calling ESP32 or
   claiming validation. **Load HA draft** replaces local edits only after a
   discard decision. **Delete HA draft** explicitly clears the stored checkpoint,
   its bounded history and local model, not the device or its SD files.
8. A second editor's save causes a version conflict instead of overwriting it.
   Local edits remain exportable; Save stays disabled until the current HA
   checkpoint is loaded. A lost reply or HA reconnect similarly requires a
   read, with no automatic save retry. Restored documents are **Not checked**,
   regardless of an earlier browser's transient validation result.
9. **Compare** shows a bounded [change summary](HA_DRAFT_CHANGES.md) against the
   imported original or fresh observed HA checkpoint. It does not validate or
   save anything. Reports become previous after edits/base changes; HA checkpoint
   conflicts require an explicit load before comparing against that checkpoint.
10. **HA history / Open as draft** reads one previous version under the current
    checkpoint token. After confirmation it restores identities/settings with a
    revision above known high-water marks, clears transient reports and marks the
    model unsaved. It does not overwrite the current checkpoint until Save in HA;
    stale tokens or a failed local preflight preserve existing local edits.

Unsupported widgets/unknown action settings remain read-only and are preserved
on unrelated room edits/reordering. Mixed rooms are not assigned an invented
action-only capacity. Room deletion/conversion and action placement are guarded
when unsupported content is present. Light, binary-status, socket, climate,
humidifier, Plant and attention profiles remain read-only. Numeric sensors are
editable only with the explicit reading features and widget inventory.

The draft records its original source/digest. A changed source or capability
set is shown rather than silently rebased. Capability changes block mutations
and device validation until a new draft is explicitly created; HA model checking and local export of an
already committed draft remains possible. Source changes do not imply that
the local model is invalid, but they prevent any future deployment from treating
the old base as current. Disconnect/unknown-result recovery follows the same
explicit fresh-status rules as raw checks. Prior validation is marked previous
after edits; device checks also become previous after a status refresh.
Selection changes require a discard decision;
privilege loss/detach clears the model and discards late replies.

## Shared Code

`home_panel_core/assets/runtime-draft.mjs` owns immutable room/action
edits, stable identity, ordering, the action upsert/move transaction, controlled
required-feature normalization, next-revision checks and edit budgets. The
Linux host editor serves **the same file**, not a copied/generated variant. It
reuses its action transaction, identity/order, revision and feature primitives;
its existing storage, room-form lifecycle and renderer remain unchanged.

Local edit guards are not a second complete runtime-schema validator. They
check allowlisted action fields, duplicates, capabilities, names, total widget/
room/page/byte budgets and known action-only no-scroll geometry. The small
action-capacity calculation is parity-tested against the existing Python
planner and actual C++ decoder. Unknown sections are not normalized into a
new schema. The existing shared Python/C++ validation and LVGL constructors
remain authoritative; the HA page does not draw a substitute pixel preview.

Local draft export is standard compact browser JSON; HA checkpoints now use the
same pure Python canonical encoder as the host tools. This is not RFC 8785 or a
claim that JavaScript preserves the numeric spelling of an imported original.
That original remains a separate exact artifact. The full Python model validator
now lives in the independent `home-panel-core` package and is used by the host
tools too, without requiring HA or reading templates during validation.
Capability-aware selection for other widget families, ownership and candidate/Apply are pending.
The deployed panel now supports metadata and flash read/check pairing (0.1.1
compatibility fix). Runtime readings capabilities and managed deployment remain
separate gates; the draft form does not advertise them for the device.

## Verification

The initial session-editor run passed **74 HA 2026.11 tests**, including the expanded
Chromium case for create/rename/reorder/move, field preservation, entity-domain
filtering, exact-original separation, bounded export and validate-only. It
captures 12 draft views plus the earlier 24 read/check views across EN/RU,
light/dark and 320/390/1280px. Browser acceptance uses the production components,
real authenticated HA WS and synthetic device replies, not an installed HA shell.

That targeted Linux run added **nine model/native draft tests**, **13 host-editor
tests** and **24 client tests**. It checks atomic failure, Unicode/surrogates,
opaque sections, feature flags, budgets, existing Python row planning, actual
C++ decoding and a nonblank 320x480 LVGL capture. The existing Linux editor's
separate Chromium acceptance also passes authenticated mock Save/Apply,
conflict/dirty guards, Stop, CSP and actual LVGL previews. All writes are to
temporary/ignored host fixtures, never the physical panel or its SD card.

The checkpoint slice passes **98 HA tests** including actual HA Store/private
temporary files, corrupt/future-state preservation, read-back write-failure
detection, cancellation, restart identity/tokens, tombstones, entry removal,
non-admin refusal and two-browser restore/conflict/lost-reply scenarios. See
[storage verification](HA_DRAFT_STORAGE.md#verification) for current limits.
The later [shared-model check](HA_MODEL_VALIDATION.md#verification) passes
121 HA tests and the separate native C++/LVGL regression, including offline
restoration and independent, versioned HA/device reports.

```sh
# Native/host acceptance: run the corresponding command in the firmware repository.
# Native/host acceptance: run the corresponding command in the firmware repository.
.venv/bin/python -m pytest -c tests/ha_integration/pytest.ini tests/ha_integration
```

Native checks require the existing Linux runtime binary and local IPC/socket
permission; no ESP32 compilation is needed. See [HA test setup](HA_INTEGRATION.md#tests)
for the isolated Python/official HA frontend dependencies.

The loopback [visual fixture](HA_FRONTEND.md#verification) at
`http://127.0.0.1:8775` also exposes the Draft tab after import. It has no real
HA entity registry or validator; checks deliberately report unavailable. Its
checkpoint controls operate only in that fixture page's memory, not HA storage.
Full HA shell/mobile behavior, real pairing and ESP32 resource/
long-duration acceptance are still open, not inferred from these host tests.
