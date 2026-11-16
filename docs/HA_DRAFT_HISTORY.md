# Bounded HA Draft History

## Scope

Explicit HA checkpoint saves retain up to **three previous distinct records**
per paired panel. Each includes its complete draft, exact imported original and
capability snapshot. This is HA configuration storage, not ESP32/SD backup or
device rollback. Nothing in this feature calls a household service, uploads JSON,
applies configuration or flashes firmware.

History is newest first by HA checkpoint generation. Identical consecutive
records do not fill history, although an explicit Save still increments the
concurrency generation and updates its timestamp. Model revision `rN`, HA
generation `vN`, storage format version and device loaded revision are separate.
Timestamps are UTC milliseconds displayed in browser-local time; ordering relies
on generations, not wall-clock monotonicity. Legacy save times remain unknown.

## Limits And Persistence

- At most three previous records, with at most 256 KiB of canonical history JSON.
- The complete private HA Store file remains at most 512 KiB, including the
  current record, originals, capability snapshots, checksum and storage envelope.
- Preparation uses HA's public Store JSON serializer and the same bounded
  byte/depth/node reader used after publication. Oldest records are removed
  before writing until all budgets fit. Large/deep records can retain fewer than
  three versions; an oversized current record alone refuses Save.
- Current checkpoint and trimmed history are published in one atomic Store
  update and verified by rereading the actual file before success. A failed
  write is not acknowledged. An uncertain response requires an explicit read,
  never automatic replay. Filesystem power-loss durability and shared-directory
  multi-process locking are not claimed.
- History survives entry unload/reload and HA restart. **Delete HA draft** clears
  both current record and history, retaining only the concurrency tombstone and
  numeric model-revision high-water mark. Removing the companion entry removes
  its owned HA file. Neither operation changes ESP32, SD or other panels.

## Migration And Downgrade

The Store envelope is now major **2**, minor **1**, under the same fixed
`home_panel.draft.<entry_id>` key. Existing valid 1.1 checkpoints and deletion
tombstones can be read without changing even one byte on disk. Matching-version
public Store readers avoid HA's automatic migrate-and-save path on Get.

Only explicit Save/Delete publishes format 2. A legacy current record can become
the first history entry, with unknown timestamp. Its known original/model
revisions initialize the high-water mark; revisions already erased by an old
format deletion cannot be reconstructed. Future/corrupt/oversized/checksum-invalid
files and invalid nested history fail closed, remain untouched and are not
treated as an empty history. Observed generation, storage version and high-water
mark cannot decrease within a repository owner.

The old integration cannot read format 2. Back up HA configuration before a
downgrade; retain/export needed JSON while using the newer integration. There is
no silent down-conversion, regeneration or automatic deletion of newer data.
The runtime JSON schema and `home-panel-core` version do not change.

## Administrator API

`draft_get`, Save and Delete still return API `version: 1`, with additive fields:
`saved_at`, `document_high_water`, `history_limits` and `history`. The history list
contains **metadata only**: generation, saved time, model revision, exact draft
SHA-256 and UTF-8 byte count. It does not return every archived document.

Read one archived record explicitly with the current observed checkpoint token:

```js
const selected = await hass.callWS({
  type: "home_panel/config/draft_history_get",
  entry_id: panelEntry,
  expected_revision: current.revision,
  history_generation: current.history[0].generation,
});
```

The result contains the selected `record`, `history_generation`, `saved_at`,
current generation/token and persisted `document_high_water`. The current
checkpoint does not change. `model_validated` and `deployment_ready` remain false.
Like the existing checkpoint commands, this uses authenticated HA WS with a
server-side administrator guard and no path/address/credential overrides. It
works with an offline/unloaded panel. Stale/previous-owner tokens return
`draft_conflict`; unknown/pruned/current generations return `draft_history_missing`.
Malformed generations are rejected. No new unauthenticated HTTP route exists.

## Editor Restoration

Open **HA history** and select **Open as draft**, then confirm replacement of
local edits. The editor retains room/widget identities, archived settings,
original artifact and capability snapshot. It uses the existing shared
`nextRevision` and budget helpers to choose a revision above the persisted
high-water mark, selected/local model and observed device revisions. Exhaustion
or a failed budget check leaves the previous local draft intact.

The restored document is **unsaved and not checked**. Save in HA is a separate
action using the still-current checkpoint token; it archives the previous
current checkpoint, not a blindly replayed historical save. Compare against the
saved HA draft can show the intended change before Save. The selected archive's
old validation state never becomes a certificate. Changed live capabilities may
block editing through the existing guards; restoration does not migrate models
or invent new asset support.

A second editor's commit rejects a stale history read/Save instead of overwriting
it. Local edits survive conflicts. History controls require a fresh observed HA
checkpoint, not fresh ESP32 metadata; explicit Load after a conflict/reconnect
reconciles storage. Entry/user/connection epochs, local draft version and expected
token discard late responses. No automatic restoration, retry, merge or device
deployment is performed.

## Acceptance

The complete history-stage run passes **195 tests** on HA 2026.11, including
Chromium and release dependency checks, with no ESP32 compile or OTA.

Real HA 2026.11 tests use temporary private Store files, not a storage mock for
this namespace. Cases cover legacy read-only access/explicit migration, exact
original preservation, restart tokens, history pruning by count/bytes/depth,
single-record rejection, tombstones/high-water marks, malformed/future/corrupt
history, write failures, administrator checks and zero device I/O.

Chromium covers EN/RU light/dark layouts at 320/390/1280px, cancellation,
unsaved revision-bumped restoration, independent Compare/Save, failed local
preflight, two-editor conflict preservation, old-connection replies and deletion.
This is component acceptance with actual HA auth/WS/Store, not full installed-HA
shell or physical device acceptance. The loopback fixture only simulates bounded
history in page memory; it has no real HA persistence or device connection.
