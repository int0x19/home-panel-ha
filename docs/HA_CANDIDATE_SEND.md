# HA Candidate Send

Development 0.1.2 adds an administrator-only **Send to panel** command to the
existing draft editor. It stores a flash candidate, not a running configuration.
No Apply, restart, Discard/recovery, SD upload or household command is enabled.
It reuses HA authentication, the existing backend-only panel key and HTTP Upload
job; no new ESP32 code, ownership service or HA entity-state connection is needed.

## Workflow

1. Explicitly import active/candidate/backup from a healthy supported flash panel.
   HA retains one immutable imported snapshot and random 32-character `import_id`
   per entry. This marker identifies that snapshot; it is not a credential. It
   is returned only by Import, not by status or HA checkpoints. Another import
   replaces it, so another browser's old import cannot authorize a write.
2. Edit or load a saved HA draft. A restored checkpoint is never write-ready by
   itself. Explicitly importing its identical original source/SHA/revision and
   capabilities can reconnect it to a live baseline; a different source cannot.
   New draft revisions include the device high-water counter, not just files.
3. Choose **On ESP32**. With an import marker, the backend canonicalizes/validates
   the draft in HA's executor, checks the original full snapshot, sends exactly
   those canonical bytes to the ESP32 validator and rechecks the snapshot. It
   retains only the checked SHA, not another JSON buffer. The response returns
   the exact checked canonical document to that browser. Ordinary raw Check and
   HA-only model validation keep their separate behavior.
4. Choose **Send to panel** and confirm. HA requires the same import marker and
   exact checked bytes, then the shared client rechecks its paired identity and
   original baseline, uploads once and exports the candidate for exact readback.
   Success reports revision/SHA/size, `changed` and `applied: false`. The editor
   displays **Candidate saved; not applied**. HA checkpoint Save remains separate.

Fields/edits, status refresh and connection changes invalidate the UI's checked
payload. Send consumes the backend marker before submission, even if the reply
is lost or the task is cancelled. Status refresh alone cannot revive it. After
an unknown result, inspect status and explicitly import/review again; never
automatically replay Send. Importing and checking an already identical candidate
can verify it without another flash write. A different existing candidate is
refused; until HA Discard is implemented, use the separately authenticated native
maintenance workflow to remove it explicitly, not another Send or an overwrite.

## API And Lifetime

- `home_panel/config/import` additionally returns nullable `import_id`.
- `home_panel/config/validate` optionally accepts `import_id` and returns nullable
  `candidate_document` containing the exact canonical bytes as UTF-8 text.
- `home_panel/config/send` requires `entry_id`, `import_id`, `document` and HA
  administrator authorization. No URL, credential, base token or revision override
  is accepted. The response contains metadata/receipt, not the access credential.
- Status adds `candidate_send_available` and nullable `status.high_water_revision`.
  This is not managed ownership, deployment readiness or a permission grant.
- The existing per-entry job gate serializes Import/Check/Send/status. Background
  polls do not enter an explicit transaction. Unload cancels it and forgets its
  import marker. HA restart/reconfigure also requires a new explicit import.

The HA-only backend extends the pinned read-backend operation gate, rather than
duplicating it. Its use of that package-private gate is covered by consumer
lifecycle/concurrency tests; keep the exact core source pin checked on upgrades.
Core remains functional source `7d8189d10c3fa464c18306965fcd9d43b0c5e705` and
unpublished version 0.1.2. Default core HTTP transport and unpaired discovery
stay read/check-only; only a paired HA client opts into Upload. Apply, restore,
Discard, scan and actuator routes remain excluded independently by transport.

## Acceptance And Next Step

Local acceptance on 2026-11-17 passes all 232 HA 2026.11 tests and 66
installed-core tests. Five existing upstream deprecation warnings remain.
The focused Send/bundle subset passes 28 tests again after the final packaging
assertions and CI-browser compatibility adjustment. No physical panel writes,
ESP32 compilation/OTA, installed-HA update, publication or household commands
were performed. Both packages remain unpublished development 0.1.2.

The HA tests use actual HA 2026.11 WebSocket/HTTP and Chromium, replacing only
the device with synthetic flash. They check exact bytes, unchanged active/
backup/loaded state, administrator and field allowlists, stale/two-tab imports,
changed drafts, lost replies, polling/unload cancellation and no automatic retry.
Browser checks cover confirm/cancel, separate HA Save, pending fields, HA-only
versus device checks, unknown outcomes, EN/RU and light/dark at 320/1280px.
These are not physical panel acceptance, publication or a firmware OTA.

Next implement explicit Apply/restart and verification of the actual running
model, then guarded Discard/recovery. Keep management/dispatch flags unchanged
until their own acceptance and authorize any physical tests separately.
