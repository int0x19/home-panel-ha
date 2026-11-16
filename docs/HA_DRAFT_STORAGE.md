# HA Draft Checkpoints

## Scope

This is local configuration storage in the HA companion, not a device candidate,
Apply mechanism or replacement for ESPHome Native API. There is **one current
checkpoint per paired config entry**, including its exact original artifact
and capability snapshot, plus up to three bounded [previous records](HA_DRAFT_HISTORY.md).
There is no automatic merge, autosave or
browser local/session storage. Working generated rooms and physical SD files
are never modified by these commands.

Explicitly saved checkpoints survive page detach, integration unload/options
reload and HA restart. Selecting the same panel reads its checkpoint and restores
the editor, even when the panel itself is offline/unloaded. Unsaved edits,
uncommitted fields and the independent raw-check textarea remain temporary;
internal HA navigation is not a universal dirty-page guard.
When a checkpoint is restored, selection does not start a device metadata read:
use Refresh status explicitly before ESP32 validation/import. The separate
[HA shared-model check](HA_MODEL_VALIDATION.md) also works offline. HA Save/Load do
not have to wait for an offline panel's HTTP timeout.

## Administrator API

All four commands use the normal authenticated `hass.callWS` connection and
server-side `require_admin`. They accept an existing companion `entry_id`, never
a filename, address, credential override or HA service. They perform **zero
panel I/O** and do not require a loaded Native API/HTTP connection.

```js
const current = await hass.callWS({
  type: "home_panel/config/draft_get", entry_id: entryId,
});
const saved = await hass.callWS({
  type: "home_panel/config/draft_save", entry_id: entryId,
  expected_revision: current.revision,
  document: localJSONText,
  original: {
    source: imported.source, revision: imported.revision,
    sha256: imported.sha256, document: imported.document,
  },
  capabilities: imported.capabilities,
});
await hass.callWS({
  type: "home_panel/config/draft_delete", entry_id: entryId,
  expected_revision: saved.revision,
});
```

The fourth command, `draft_history_get`, explicitly reads one archived record
using the current observed checkpoint token. See [history](HA_DRAFT_HISTORY.md)
for its metadata-only list, bounded record lookup and unsaved editor restoration.

`draft_get` does not create a file. Every result contains:

- `version: 1`, integer `generation` and opaque `revision` token.
- `record: null`, or `{document, sha256, original, capabilities}`.
- `saved_at`, `document_high_water`, bounded metadata-only `history` and `history_limits`.
- `model_validated: false`, `deployment_ready: false`.

Treat the revision token as opaque optimistic-concurrency data, not a credential
or device boot nonce. It combines a fresh HA repository-instance nonce with a
persisted generation, independently of the runtime document's numeric revision.
Old tokens stop working after HA restart even if the on-disk generation matches.
Generation is capped at JavaScript's safe integer maximum; exhaustion refuses
writes instead of wrapping.

Save and Delete require the token from the observed checkpoint. A stale token
returns `draft_conflict`; a concurrent in-flight write returns `draft_busy`
without queuing a second write. Delete publishes a null-record tombstone with
an incremented generation, preventing stale create/delete requests from becoming
valid again. Delete clears history as well, while keeping the numeric model
revision high-water mark. Removing the companion entry explicitly removes its own HA file;
unload/reload does not. Other panels' checkpoints and device configuration are
unaffected.

## Validation Boundary

The backend checks character/UTF-8 byte limits, duplicate-free finite JSON,
depth/node limits, the runtime envelope/basic UI shape, original revision/SHA
integrity and the public capability snapshot's bounded shape. Draft input is
capped at 64 KiB and the supplied negotiated document ceiling; original text at
64 KiB; capability metadata at 16 KiB. These are storage/edit guards, **not full
shared-model validation** or measured ESP32 resource acceptance.

The draft is encoded using
`home_panel_core.json_codec`. Host runtime tools
load the same pure implementation through `scripts/panel_runtime_codec.py`,
without importing HA in the ESPHome environment or repository scripts in HA.
It retains existing Python sorted-key UTF-8/finite-number encoding. Arrays
preserve order; this is not RFC 8785 or a numeric-schema migration. Browser
draft export may use a different equivalent numeric spelling.

`original.document` is not reserialized: its whitespace, CRLF and Unicode bytes
round-trip exactly, with a verified digest/revision. This integrity check is
**not device attestation**. Original/capability fields submitted by an admin are
not a persisted native-validator certificate, and saved drafts are always
reported unvalidated. Restoring a checkpoint clears transient validation reports.
Successful HA Save never bypasses a future fresh device validation, authority,
source/session/revision/digest or renderer-readiness gate.

Unknown sections are not silently regenerated. A checkpoint whose model cannot
be edited by the current action pilot falls back to raw checking rather than
rewriting the file. Full shared-model checking is now a separate explicit
[HA operation](HA_MODEL_VALIDATION.md), not a condition or certificate of Save.
An explicit [change summary](HA_DRAFT_CHANGES.md) can now compare the local draft
against the original or fresh observed checkpoint without writing storage.
Bounded history and explicit local restoration are now available separately.
Broader configuration migration and richer editor widget families remain roadmap work.

## Storage And Recovery

Production uses HA's public `Store` APIs with a fixed owned key
`home_panel.draft.<entry_id>`, version 2/minor 1, private permissions, atomic
writes and serialization in the executor. The payload holds the pinned factory
ID, generation, current/archived records, timestamps, model-revision high-water
mark and canonical checksum. API responses omit the factory
ID, panel origin/key and native boot nonce. HA storage/backups remain sensitive
configuration data; this is not encryption at rest or a scoped device credential.

Before HA loads a file, an executor preflight bounds reads to 512 KiB and checks
the exact storage version/envelope. Valid legacy 1.1 files are read without
rewriting; only explicit Save/Delete upgrades them. Corrupt, oversized, wrong-identity or future
records fail closed and remain untouched, without automatic migration,
quarantine-as-empty, reset or overwrite. Loaded records also verify checksum
and canonical content, including every archived record. Observed generation,
storage version and high-water mark cannot move backwards; a missing
previously populated file is not treated as a fresh empty draft in that owner.

Save rechecks the current disk state before publication. HA 2026.11's `Store`
can log and swallow a write failure, so the companion reads back the actual
file and compares the complete payload before reporting success. Old verified
state remains recoverable after a failed update. Read-back verification is not
a claim about filesystem/controller power-loss durability, encryption or
multi-process locking across two HA installations sharing one config directory.

One tracked HA commit owns the per-entry lock. Cancelling/disconnecting its WS
waiter does not cancel the commit; a subsequent Get waits for it and rereads disk.
If the result was lost, never replay Save/Delete automatically. The UI retains
local changes, disables Save and requests an explicit current checkpoint load.
Conflicts likewise preserve local edits until the user confirms replacing them;
there is no blind overwrite or automatic merge option in this stage.

The UI keeps HA-storage errors separate from device metadata availability.
Losing a Save reply does not mark the ESP32 disconnected or trigger an export,
validation, candidate upload or household command. Full logical-model validation
is available as a separate HA operation; actual device acceptance still uses the
[device read/check operation](HA_READ_CHECK_API.md).

## Verification

The 2026-11-07 checkpoint run passes **98 HA 2026.11 tests**, including 24 new
storage cases and the expanded Chromium acceptance. The standard HA pytest
storage mock is replaced only for this owned namespace by the real HA file-I/O
implementation on temporary config directories; the production code uses no
private storage methods. Other HA test stores remain standard fixtures.

Coverage includes private real files, exact original bytes, canonical content,
new-owner restart tokens, two-editor conflicts, tombstones, zero device I/O,
invalid/deep/oversized/nonfinite input, corrupt/future/checksum/identity/oversized
disk data, swallowed write failures, cancelled waiters, parallel rejection,
entry removal and non-admin refusal. Chromium uses actual HA auth/WS/Store to
test page reattach/restore, two tabs, conflict preservation, lost committed
replies with no replay, reload and deletion. It is not full installed-HA-shell
or physical-panel acceptance.

The isolated host regression also passes **41 codec/runtime-config/client tests**
and **42 storage/journal tests**, for **181 targeted tests** in total. The shared
encoder is checked against golden bytes and identical source paths. No ESP32 compile/OTA, physical
SD write or real HA/household connection is performed. The existing upstream
WS raw-surrogate/pre-dispatch close/timer limitation is not patched or ignored:
the companion's UTF-8 guard is tested directly, while authenticated WS cases
use valid frames. See [the earlier probe note](HA_READ_CHECK_API.md#verification-notes).

```sh
.venv/bin/python -m pytest -c tests/ha_integration/pytest.ini tests/ha_integration
# Native/host acceptance: run the corresponding command in the firmware repository.
# Native/host acceptance: run the corresponding command in the firmware repository.
```

The loopback preview at `http://127.0.0.1:8775` only simulates checkpoint controls
in that fixture page's memory. It has no real HA persistence, validation or device
connection and labels that limitation explicitly. Real acceptance above uses HA
Store on temporary disk, not this simulation.

The [history extension](HA_DRAFT_HISTORY.md) adds read-only migration, count/byte/
depth pruning, restart/revision protection and explicit unsaved restoration tests;
the original checkpoint guarantees remain in force.
