# Shared Core Contract

The canonical configuration-management contract now belongs to
`home-panel-core/docs/CONFIGURATION_CONTRACT.md`. That repository owns the
versioned logical model, canonical encoding, protocol/client and shared JS edits.
This integration consumes its pinned wheel; it does not define another schema.

Development 0.1.2 pins core 0.1.2 at its tested source commit and adds shared
sensor/group draft transactions. It preserves the v1 model/protocol and all
read/check guards. Editing is conditional on negotiated features and widget
inventory, not a claim of device-family or managed-deployment acceptance.

The same unpublished 0.1.2 now pins the subsequent core source that recognizes
`esp32-readings-preview` alongside the legacy action-only target. The firmware
flash profile exposes sensors/status/groups and a configured combined source/
subscription ceiling. HA reports the negotiated readings-preview scope; its
source pin is recorded in `core-source.json`. Local maintenance storage is not
HA-managed authority. That readings-profile checkpoint added no Send/Apply method.
The running panel and published Marketplace 0.1.1 remain unchanged.

The next core source lock adds typed `write-base.v1` status and snapshot
freshness checks. Flash maintenance writes require the device-issued base,
rechecked under the NVS transaction lease. At that checkpoint the shared client
and HA had no write methods. Read/check imports reject changed bases at the same numeric
generation and require an explicit fresh status, without replay. This metadata
stays on the backend; no frontend-supplied guard can claim an owner or permission.
Persistent ownership/scoped credentials and explicit handover remain pending.

The subsequent firmware-only source step prepares private NVS owner persistence
and a leased native write-authorization gate, including Claim/Rotate/Release.
It does not add public HTTP handover, change the core read/check API, expose
credentials in the frontend or enable managed capability flags. Raw owner keys
are not stored in runtime JSON or its exports. Exact core source/version pins
stay unchanged; authenticated transport, explicit local recovery and guarded
HA Send/Apply remain next. See firmware `docs/RUNTIME_AUTHORITY.md` for the
private record/failure contract, including the non-transparent downgrade fence.

Scope correction, 2026-11-17: public owner handover/scoped keys are deferred, not
prerequisites of the first single-HA configuration workflow. Reuse existing HA
administrator checks and the backend-only panel credential, with exact imported
base/session/generation/digest conflicts. The private journal stays inactive;
next implement minimal explicit Send-candidate, then Apply/restart. This is not
exclusive ownership and does not enable any currently false deployment flag.
No package version, functional core pin, frontend auth or device firmware changes.

## Candidate Send Library Boundary

The Send checkpoint advanced to core functional commit
`7d8189d10c3fa464c18306965fcd9d43b0c5e705`, still unpublished development 0.1.2.
Its explicit `send_candidate` validates canonical JSON against negotiated limits,
checks the original imported snapshot, submits existing flash Upload once, then
verifies exact exported bytes and unchanged active/backup/loaded state. Stale
imports and different candidates conflict; uncertain writes are never replayed.
An identical candidate is checked without a flash write. That checkpoint did not implement Apply.

The core HTTP transport requires `allow_candidate_upload=True` for Upload.
Pairing remains read/check-only. The subsequent
[HA Send extension](HA_CANDIDATE_SEND.md) opts its paired client into Upload
only, with an administrator command, retained imported snapshot and one-use
checked digest. HA-local checkpoint Save stays distinct from device Upload.

Consumer acceptance on HA 2026.11.0: 215 component/browser tests pass, including
the then-default read-only transport regression and deterministic self-contained
manual/Marketplace ZIP checks. All 22 wheel source/assets match the functional
commit above; 66 installed-core tests pass. Firmware acceptance adds 84 scoped
flash HTTP/NVS/client and 25 compatibility checks, with two optional sanitizer
skips. This is not publication, ESP32 OTA or physical acceptance. Package versions
stay at unpublished 0.1.2; published Marketplace 0.1.1 remains unchanged.

## Core Apply Boundary

The current functional lock advances to core
`ac24832776852116018ad47cdf120685c9d37567`, still unpublished 0.1.2. It adds
`apply_candidate(expected=...)` and `inspect_activation(expected=...)` using
existing flash Apply/export and boot metadata. Separate transport opt-ins keep
Send independent from Apply. Request acknowledgement is only a scheduled trial;
inspection must verify the expected boot/generation/files, local first-frame/
health confirmation and active export SHA before reporting `confirmed`.
Rollback, still-confirming and unverified states remain distinct; no Apply retry.

HA deliberately keeps `allow_candidate_apply=False`, exposes no Apply WebSocket
command/control and does not retain an activation intent yet. Pairing is
read/check-only; its paired client still opts only into Upload. The no-Apply
transport/command and bundled-only import tests cover the new package. Next
implement an explicit administrator Apply/inspection backend and UI, using the
same per-panel gate and no automatic replay. See core `docs/CANDIDATE_APPLY.md`.

Consumer acceptance on 2026-11-17: all 79 installed-core tests and 232 HA
component/browser/bundle tests pass with this functional pin. The firmware's
scoped native flash/NVS/read-check/decoder suite runs 116 cases: 114 pass and
two optional sanitizer runs skip. All 23 wheel package files match the pinned
source. No MCU production source, physical Apply, build/OTA, installed-HA update
or release publication is implied. The source-test-only timeout expectation fix
does not move this functional pin or change its wheel.

## Prepared Capabilities Extension

Compatibility update, 2026-11-16: the deployed panel now exposes valid factory
identity and `capabilities.v1` with `flash-nvs` / `flash-confirmed`. Integration
0.1.0 still assumed legacy SD sources and rejected this valid status. Version
0.1.1 bundles core 0.1.1 to support storage readiness and the required flash
generation header. A live read/check import of active flash JSON passes without
a card, firmware rebuild, OTA or persistent configuration change. This does not
complete measured-resource, asset-inventory, authority or managed-write gates.

The prepared `capabilities.v1` metadata and stable factory identity remain
required for pairing. They are still subject to physical firmware acceptance;
the repository split did not install them. See the core contract for the exact
compatibility matrix and the firmware roadmap for device acceptance.

HA checks, saved checkpoints and generated release bundles do not grant
ownership or deployment readiness. Those gates remain unchanged. Hosted links
can be added after separate origins have been configured for the new repos.
