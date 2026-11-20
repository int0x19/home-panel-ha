# Home Panel HA Roadmap

The complete editor/integration backlog moved here from esp32panel at the
repository split. Device firmware/native renderer acceptance stays in that repo;
shared model/protocol work belongs to home-panel-core.

## Current Checkpoint (2026-11-20)

Installed HA 0.1.2 and the physical panel passed Send, Discard and backup
staging. Exact exports confirmed Active 56 and Backup 55 stayed unchanged.
Candidate 73 was discarded, Backup 55 was staged as Candidate 74 with
only the revision replaced, then the slot was emptied with high-water 74.
Next verify separate Apply on installed HA; successful Apply rotates Backup.

## Candidate Maintenance (2026-11-18)

Import **Candidate** and choose **Remove candidate** to clear the staged slot.
Import **Backup** and choose **Stage backup as candidate** to stage the exact
copy at a higher revision when the slot is empty. Both require the latest
matching import and explicit confirmation. Recovery prepares a separate Apply.
All 262 HA tests passed with the pinned wheel, including Chromium and
offline bundles. Shared core passed 80 tests and the Linux production flash
client passed 12 checks.

HA Apply/inspection is now host-accepted at functional commit `1730ee0`.
All 254 HA tests and 79 installed-core tests pass. It uses the unchanged core
pin below, one-use saved-candidate approval and explicit status inspection;
an acknowledgement is never shown as running. Next implement guarded
Discard/recovery, then separately authorized installed-HA/device acceptance.
No firmware build/OTA, dependency upgrade, installed-HA update or publication.
See [HA Apply](docs/HA_CANDIDATE_APPLY.md). Earlier checkpoints below describe
the preceding source stages, not the latest UI capability.

Core Apply/inspection is now pinned at functional source
`ac24832776852116018ad47cdf120685c9d37567`, still development 0.1.2. All 79
installed-core tests, 232 HA tests and 114 scoped native checks pass (two
optional sanitizer skips). HA remains Send-only; Apply's separate transport
flag and WebSocket/UI path are not enabled. Next implement that explicit
administrator Apply/inspection flow, then Discard/recovery. No firmware build,
OTA, installed-HA update or publication. See [core boundary](docs/CORE_CONTRACT.md#core-apply-boundary).

The next core slice pins `ac24832776852116018ad47cdf120685c9d37567`: guarded
Apply request and bounded activation inspection, reusing existing boot/flash
metadata. Confirmed means the exact primary trial passed local first-frame/
binding health and active export SHA, not merely a reconnect or HTTP receipt.
No MCU code, new endpoint, controller journal or HA Apply control is added.
Next expose explicit Apply/inspection through the existing HA administrator
backend/UI; keep the transport opt-in false until that path is accepted.

Candidate Send acceptance: all 232 HA tests and 66 installed-core tests pass.
The final Send/bundle subset passes 28 tests again; five upstream HA
deprecations remain. No ESP32 build/OTA or publication. The next concrete step
is explicit Apply/restart with observed running-model verification, then
Discard/recovery. See [HA candidate Send](docs/HA_CANDIDATE_SEND.md).

Scope correction: use existing HA administrator permissions, the existing panel
access credential and ESPHome Native API for states/actions. The shared client
and HA editor now support guarded Send-candidate. The next delivery is explicit
Apply/restart with observed activation, then Discard/recovery. Persistent multi-controller
ownership, scoped-key rotation and special receipt credentials are deferred,
not prerequisites. Keep exact imported-base/session/generation/digest guards,
independent validation, no automatic replay and known-good recovery. The
experimental owner HTTP prototype was not accepted, committed or deployed;
working firmware source remains at the private inactive backend. This correction
supersedes ownership-first sequencing in the historical checkpoints below.

The candidate Send library checkpoint pins functional core
`7d8189d10c3fa464c18306965fcd9d43b0c5e705`. It reuses the current Upload endpoint,
original imported snapshot, one operation lock and exact readback; it never
applies or automatically retries. At that checkpoint HA remained read/check-only,
with a regression test that refuses mutation routes before network I/O. No
Send button/command, managed flags, publication or physical acceptance is implied.
The pinned wheel passes 66 core tests and all 215 HA/component-browser tests,
including deterministic bundled archives and the read-only transport boundary.
Firmware/native acceptance passes 84 flash HTTP/NVS/client and 25 compatibility
checks, with two optional sanitizer skips. No dependency upgrade or OTA.

The subsequent [HA candidate Send](docs/HA_CANDIDATE_SEND.md) extension adds the
administrator command/editor button, sharing the existing per-entry operation
gate. One backend import marker and checked SHA bind the exact canonical bytes;
another import, a stale snapshot or changed payload conflicts. Send consumes its
marker and never automatically replays, including lost replies/unload. Pairing
stays read-only; a paired client opts into Upload only. No Apply, physical flash
write, dependency upgrade, managed-readiness change or publication is implied.

Development 0.1.2 adds the [numeric-sensor/group draft slice](docs/HA_SENSOR_DRAFT.md)
using core 0.1.2. Local acceptance passes 212 HA/browser tests, including actual
registry metadata, independent Python checks, HA checkpoint restore and EN/RU
light/dark forms at 320/390/1280px. The browser's exact edited JSON also renders
through Linux C++/LVGL with mock readings and no overflow. Sensor/group controls
require explicit capability features and widget inventory; the deployed
action-only configuration profile remains gated. No managed write, firmware
upload, physical-device command or 0.1.2 publication is implied.

The subsequent host-tested firmware slice aligns flash capabilities/storage
with its existing general decoder. Development core/HA 0.1.2 now recognize
`esp32-readings-preview`, expose the negotiated readings scope and retain
legacy action-only compatibility. Shared-client Check/Export work through the
production C++ handler on Linux; managed ownership/Send/Apply and physical
readings acceptance remain next, not inferred from metadata.
Current acceptance passes 213 HA/component-browser tests with the pinned
wheel, 50 installed-core tests and 70 scoped native HTTP/NVS/LVGL checks (one
optional skip). Published 0.1.1 does not recognize the new target, so companion
verification must precede a future readings-profile OTA. Next implement
ownership and exact base revision/digest/generation checks before Send/Apply.

The subsequent `write-base.v1` slice implements the device's base-snapshot
comparison under the fresh NVS writer lease. The pinned core/HA read backend
rejects changed bases without replay, including unchanged numeric generation.
No HA writer or managed authority is enabled; next add persistent owner/scoped
authentication and explicit local handover/recovery, then Send/Apply.
This slice passes 214 HA/component-browser and 52 installed-core tests, with
80 focused firmware flash HTTP/NVS/client checks (two optional skips), 28
compatibility/decode/codegen checks and separate flash ASan/UBSan/two loopback
browser flows. No full firmware sweep, ESP32 build/OTA or release is implied.

The following firmware-only private authority backend adds the persistent
two-copy owner journal and leased owner/epoch write check. Native Claim/Rotate/
Release, restart/failure paths, revoked keys and the preceding-writer downgrade
fence are host-tested. No HTTP handover, HA writer, managed readiness or physical
activation is enabled. This checkpoint reruns 52 installed-core tests and the
40-test HA release/setup/lifecycle subset, not the full HA/browser suite.
Core 0.1.2 and its tested functional source pin remain unchanged. Public handover
is deferred by the scope correction; next implement minimal guarded Send/Apply.

Release 0.1.1 is published for Marketplace with bundled core 0.1.1. CI passes,
including 204 HA/browser tests on HA 2026.11.0. The flash-NVS compatibility fix
was checked against the running ESP32: factory identity/capabilities, exact
active JSON export and validate-only work without SD. No Apply, managed write
or household command was performed. Installed-HA setup after updating still
needs user confirmation.

References to undeployed metadata in the dated 2026-11-07 progress notes below
are historical; the read/check metadata path is now deployed. Broader asset,
capacity, authority and managed-deployment acceptance gates remain open.
Next, complete one HA-edited room with real temperature/humidity bindings,
accepted runtime readings capabilities and guarded flash Save/Apply without a
firmware rebuild. The editing/shared-Linux part now passes; retain device
capability, ownership and storage/recovery checks. This plan does not
enable runtime action dispatch or waive deployment/recovery prerequisites.

### 3.8. HA integration and primary configuration editor

Accepted direction, 2026-11-05: HA builds configuration from user-selected
entities, rooms and presentation settings, then initiates explicit deployment.
ESP32 validates and stores JSON, builds the shared LVGL UI and handles live
states/actions through ESPHome Native API. The integration does not replace the
standard ESPHome integration, and ESP32 needs neither an HA access token nor a
parallel HA state WebSocket client. Only configuration management moves to HA.

The contract/read-check client and stable-identity/decoder-metadata extension
are host-tested on 2026-11-07; the latter is not deployed. A read-only companion
now passes setup/lifecycle, administrator-backed read/check and component-browser
tests on HA 2026.11.0. The administrator-only metadata/import/check page is
implemented in 3.8.2/3.8.3, with an action/room editor and bounded HA checkpoints.
Full shared-model validation, action registry selection, structural change
summaries and bounded draft history are now available in HA. Retain the device
identity/limits/asset acceptance gates in 3.8.1. Develop 3.8.3 against the Linux
action pilot while 3.6/3.7 progress; gate
device writes in 3.8.4 on the contract/security checks and add widget families in
3.8.5 only as their runtime support passes. Do not wait for all device families
before starting the editor, or claim that the editor alone completes migration.
The current ESP32 JSON path is a separate action preview with dispatch disabled;
its 16 KiB input ceiling is not the host schema's larger provisional budget.

#### 3.8.1. Shared contract, authority and capability handshake

- [x] Document the HA/device responsibilities and versioned configuration-management contract, reusing the schema, canonical encoding, stable IDs, validator and storage API from 3.5. Distinguish HA draft revision, device active/candidate revisions and content digests; renaming/reordering must not change widget identity. The 2026-11-07 [contract and compatibility matrix](docs/CORE_CONTRACT.md) distinguish installed HTTP v1, prepared identity/decoder metadata and pending ownership/activation checks; physical device acceptance remains open below.
- [x] Prepare the additive `capabilities.v1` boundary and explicit client identity pinning on Linux (2026-11-07): factory eFuse MAC-48 ID independent of IP/name/boot/SD, ID/session guards in status/jobs/metadata, one main-loop cached GET document, actual boot ceilings and inventories shared with the C++ decoder. Test restart/replacement/invalid identity, repeated read-only cache access, configured input limits and legacy fallback. Report action-preview-only/model-only support, zero subscriptions, unmeasured limits, incomplete loaded asset inventory and unmanaged/not-enforced authority. No target build/OTA, managed write enablement or physical identity/memory claim; see [prepared metadata](docs/CORE_CONTRACT.md#prepared-capabilities-extension).
- [ ] Finish and accept device metadata on the physical board: verify factory identity across restart/network changes, complete loaded font/icon inventory and measured per-board input/room/widget/subscription budgets. Distinguish accepted decoder syntax from renderable assets and compiled-only room families. Keep schema/protocol negotiation and reject incompatible documents rather than downgrading controls silently; the prepared configured ceilings do not complete this gate.
- [ ] Deferred until a concrete multi-controller or credential-isolation requirement: define/enforce optional HA-managed authority, handover and authenticated emergency recovery. This is not a prerequisite for the first single-HA/single-credential Send/Apply. Exact base/revision/digest conflicts remain mandatory; managed mode stays unadvertised and the native owner journal inactive.
- [x] Prepare the private firmware authority backend (2026-11-17): persist a bounded two-copy NVS owner journal, recheck owner/epoch in the native config transaction, and implement explicit Claim/Rotate/Release with exact configuration-base/trial guards. Native fault/restart/downgrade checks pass. This is not the public HTTP/HA handover or managed activation gate above; keep that gate open and all deployment permissions false.
- [ ] Specify portable import/export and migration/precedence for existing YAML defaults, socket aliases, Plant overrides, light presets and backlight preferences. Keep hardware, Wi-Fi/API/OTA credentials, executable code and live entity readings out of runtime JSON. Preserve compatible recovery documents on schema/firmware downgrade.

Exit gate: a documented compatibility/authority matrix and shared test fixtures;
the installed firmware's limitations are explicit, with no device write needed.

#### 3.8.2. Read-only HA integration and device client

- [x] Prepare the HA-independent async read/check client and optional injected-session aiohttp transport (2026-11-07): status, exact active/candidate/backup export and validate-only, bounded response/stream/job polling, session/revision/path/header/SHA guards and no persistent write/actuator methods. Add synthetic shared fixtures and Linux tests, including the actual C++ file/HTTP component on temporary storage. This client slice alone is not an integration or verified physical pairing; the installed HTTP profile still lacks the prepared identity/decoder-metadata extension and any managed owner. See [configuration-management contract](docs/CORE_CONTRACT.md).
- [x] Add an isolated read-only [custom integration](docs/HA_INTEGRATION.md) with manual address/key setup, stable unique panel identity, duplicate prevention, connection checks, options, identity-preserving reconfigure/reauth and clean unload/reload. Test against actual HA 2026.11.0 and matching official pytest fixtures, including HA-owned HTTP session and loopback requests; no private ESPHome integration APIs or forced ESPHome upgrade. Five diagnostic entities and redacted diagnostics expose metadata only; all poll requests are GET. Physical pairing requires the undeployed metadata firmware, while discovery, browser JSON import/check and editor/write gates remain below.
- [x] Integrate the read/check client with HA-owned session/lifecycle and the negotiated identity/capability extension in the [read/check backend](docs/HA_READ_CHECK_API.md) (2026-11-07). Bound one explicit transaction per paired entry and share its client with background polling. Verify exact import bytes/source/SHA/receipt guards and the device shared-validator report, then reject changed boot/capabilities/source metadata. Cancel old requests on unload/reconfigure, retain no document history and require an explicit fresh idle status after uncertain outcomes; no automatic POST replay. Actual HA WS/HTTP and native C++ temporary-VFS checks pass; physical pairing remains blocked on the undeployed metadata firmware, not inferred from IP or host limits.
- [x] Route read/check requests through four authenticated HA WebSocket backend commands with server-side administrator authorization: list, status, import and validate. Keep key/origin/nonce in backend configuration, return allowlisted metadata and exact credential-free-schema JSON, sanitize error bodies/exception text and refuse address/key/path overrides. Test non-admin refusal before I/O, anonymous admin wrapper, two-session concurrency, UTF-8/device byte limits and task/timer cleanup. No iframe, browser-to-panel HTTP, write endpoint, actuator method or frontend exposure of the panel key is added; see the API's pre-auth probe limitation separately.
- [x] Add the administrator-only [frontend/import display](docs/HA_FRONTEND.md) for active/candidate/backup metadata and validated JSON, using the accepted backend without changing the device (2026-11-07). Show unmanaged versus future HA-managed status, incompatible metadata, unavailable SD and stale/uncertain results. Preserve exact original downloads separately from local check input; serialize explicit requests and require fresh status after uncertain outcomes/reconnect. Real HA 2026.11 registry/admin/static HTTP checks and component-browser acceptance cover EN/RU, light/dark, 320/390/1280px, UTF-8, file limits, no automatic job replay and discarded late replies. No structured editor, writes or device acceptance is implied; full installed-HA-shell, scoped credentials, physical pairing and resource gates remain open.

Exit gate: integration/client tests and read-only import/check against fixtures
and the existing device API; no Save, Apply, firmware upload or household command.

#### 3.8.3. HA-hosted room/widget editor and JSON generation

- [x] Register an administrator-only [custom frontend panel](https://contributors.home-assistant.io/frontend/custom-ui/panel/) backed by authenticated HA [WebSocket commands](https://contributors.home-assistant.io/frontend/extending/websocket-api/) (2026-11-07). Use official async static-path/panel registration, HA themes/icons/sidebar events, one shared panel across entries and no iframe/CDN/frontend build step. Headless HA retains the backend; path collisions do not replace another integration's panel. This first surface reads/imports/checks only; it has no persistent drafts or independent renderer/validator.
- [x] Add the [action/room session-draft pilot](docs/HA_DRAFT_EDITOR.md) (2026-11-07): explicit creation from a checked original, room rename/create/reorder/delete, stable-ID action edit/move/delete, entity suggestions from existing HA states, allowlisted icons/interactions/optional script Stop, bounded export and explicit validate-only. Extract the host editor's action transaction/identity/order/required-feature/revision logic into one JS module used by HA and Linux; retain the existing Python/C++ validators and LVGL renderer. Test Unicode, atomic rejection, capabilities/budgets/no-scroll action planning, opaque-section preservation, actual C++ decode/LVGL render and both browser surfaces. No persistent HA draft, browser pixel preview, write endpoint or real household/device operation is implied.
- [x] Add bounded [HA draft checkpoints](docs/HA_DRAFT_STORAGE.md) and two-editor optimistic conflicts (2026-11-07): explicit Save/Load/Delete, one current record plus exact original/capability snapshot per paired entry, private atomic HA Store writes with read-back verification, checksummed/versioned bounded reads, tombstone generations and fresh HA-owner revision tokens after restart. Cancelled WS waiters do not cancel an in-flight tracked commit; unknown replies require a read, never automatic replay. Checkpoints survive unload/reload and are removed only with explicit HA draft deletion or removal of that companion entry, not from ESP32. Keep both original bytes and unvalidated status distinct; source-digest integrity is not device attestation. Real temporary-file/HA WS and two-browser tests pass, with no device I/O from the new commands.
- [x] Move canonical Python encoding to one pure bundled codec used by HA checkpoints and the host tools through a host-only bridge, without importing HA in the ESPHome environment or repository scripts in HA. Test identical source/golden bytes and finite UTF-8 errors. This preserves the existing Python numeric format, not RFC 8785 or new schema semantics.
- [x] Add [full shared-model validation in HA](docs/HA_MODEL_VALIDATION.md) without an HA-only schema fork (2026-11-07): move existing Python models/profiles/references/geometry into one bundled pure package, retain host YAML/template/file adapters and validate fully resolved JSON without repository I/O. Add an admin-only bounded executor check and separate HA/ESP32 reports, with one worker per entry across disconnects, no device calls or storage and explicit false deployment readiness. Cover standalone bundle/source parity, semantic rejections, actual HA WS, offline restore, stale reports and Linux C++/LVGL regression.
- [x] Add explicit [HA structural change summaries](docs/HA_DRAFT_CHANGES.md) against the imported original or fresh observed checkpoint (2026-11-07). Cover room/widget addition/removal/settings/relative order, infer moves only for unambiguous room-local IDs, summarize opaque sections without returning their values and distinguish revision-only changes. Bound inputs/output and share one executor slot with full model checks across disconnected waiters; preserve checkpoint/device freshness, reject stale frontend results and keep all validation/deployment flags false. Actual HA 2026.11 and EN/RU mobile/desktop browser checks involve no device or storage writes from Compare.
- [x] Add [bounded HA checkpoint history](docs/HA_DRAFT_HISTORY.md) (2026-11-07): up to three distinct previous records/256 KiB, one atomic 512 KiB/depth/node-bounded Store envelope, metadata-only lists and admin/CAS-protected archive reads. Preserve read-only legacy access and upgrade only on explicit Save/Delete. Open history as an unsaved draft with shared revision/budget helpers, preserved IDs/original/capabilities, cleared reports and explicit Save; keep conflicts/late replies/write failures safe. Delete clears current/history, with tombstone/high-water metadata retained. Actual HA 2026.11 Store/WS and responsive two-browser acceptance involve no device I/O.
- [x] Add [unsaved-navigation protection](docs/HA_NAVIGATION.md) and installed-HA-shell acceptance (2026-11-07). Protect dirty models, unfinished fields and raw-check JSON through cancelable browser Navigation API departures, with same-origin link/unload fallback and an explicit old-browser warning. Keep the guard scoped to the mounted route, remove listeners on detach and avoid private HA imports/history patches or automatic checkpoint/device writes. Actual HA 2026.11 frontend/router/sidebar/icons and Chromium desktop/mobile checks cover cancellation, accepted discard/remount, Back, saved-versus-dirty state and cleanup. Document forced-teardown/non-cancelable traversal limits and the independently reproduced Chromium 153 repeated-programmatic-Forward issue; broader browser/companion acceptance remains in 3.8.6. Checkpoint Save/model checks still do not certify device deployment.
- [x] Add the [action entity registry/state picker](docs/HA_ENTITY_CATALOG.md) (2026-11-07): admin-only offline-capable HA catalog, bounded pages, name/ID search, domain/effective-area filters, optional disabled/hidden entries, availability labels and manual-entry fallback. Selection preserves custom labels and only changes open fields; no room rearrangement, service call or device I/O. Actual HA 2026.11 WS/registry and EN/RU light/dark mobile/desktop browser acceptance cover cancellation, late replies and errors without invalidating checkpoints/device checks.
- [ ] Extend registry/state selection with capability-aware defaults for other accepted families (light color modes, climate/humidifier modes/ranges, socket readings and Plant bindings). Let users choose what to import and override labels/grouping; HA areas may seed rooms but never silently rearrange them. Missing/null attributes or temporary unavailability must not erase existing settings.
- [x] Add capability-gated numeric-sensor/group editing (2026-11-17) using the shared core transaction/fit module: entity/name/unit/class, standalone or named/unnamed group, stable IDs, reorder/move/delete, mixed action rows and atomic no-scroll rejection. A scoped HA sensor catalog offers bounded unit/class defaults without raw states or arbitrary attributes. HA model/checkpoint and browser-to-Linux JSON acceptance pass; device-family advertisement, binary-status editing and managed deployment remain pending.
- [ ] Support room create/rename/reorder, Cyrillic names, stable widget identities, entity/attribute bindings, sensor groups and bundled icons. Start with pilot action tiles; expose additional deployable families only from the device capability handshake. Preserve unmodified unsupported sections on import and block deployment until required capabilities are present.
- [ ] Reuse resolved template/theme/layout tokens and the existing row planners for the fixed no-scroll grid. Show capacity errors, explicit page placement and optional dedicated Actions pagination rather than shrinking device cards. Resolve templates into numeric JSON values on HA; new fonts/icons/renderer code still require firmware. Validate accurate previews through the shared Linux LVGL path, not a separate browser-only layout promise.
- [x] Keep HA checkpoint history/change summaries and independent HA/device checks separate from SD-candidate Send/Apply. Retain canonical bounded JSON, required-feature declarations and exact originals; history restoration is a local unsaved edit, never an automatic rebind, save or deployment. Broader ownership/deployment acceptance remains in 3.8.4.

Exit gate: a user-selected configuration round-trips through HA and the shared
Linux validator/preview, including Unicode, reordered/repeated entities, full
rooms and two-editor conflicts. Firmware changes and real actions are not needed.

#### 3.8.4. Guarded deployment, activation and recovery

- [x] Prepare guarded candidate Send in shared core and pin its tested source; keep HA's default transport read/check-only until the administrator backend/editor path is accepted. No Apply or MCU changes in this library step.
- [x] Add explicit HA candidate Send using the existing administrator permission, backend-only key and bounded Upload job. Bind an imported snapshot/one-use marker to exact canonical bytes checked on ESP32; share the per-entry gate with reads/polls/unload, refuse stale tabs and retain no JSON buffer on HA. Report saved candidate, not activation; see [Send workflow](docs/HA_CANDIDATE_SEND.md).
- [x] Add explicit HA Apply/restart with one-use server-held approval and separate activation inspection. Reuse the administrator/per-panel gate and core's original base, identity/session/generation/digest checks; distinguish acknowledgement, confirming, confirmed, rollback and unknown. Inspect only on explicit status refresh, preserve intent but not permission after lost replies and forget both on unload/reload. All 254 HA tests and 79 installed-core tests pass; no physical acceptance or owner/managed flags are implied. See [Apply workflow](docs/HA_CANDIDATE_APPLY.md).
- [x] Expose flash Discard and backup staging through the existing main-loop API and per-panel gate. Bind each administrator action to a one-use import of its source, verify the resulting flash state and preserve the running configuration and backup. Require an explicit Apply to activate the recovered candidate.
- [ ] Report draft, checked, saved candidate, applying, running, fallback and unknown-result states separately. After restart, reread identity/session, loaded source/revision/digest and renderer readiness before reporting success; HTTP 202, an upload receipt or a TCP reconnect is not proof of successful activation. Keep the pending first-frame/trial-confirmation work in 3.5 explicit.
- [ ] Reconcile reconnect, HA restart, lost replies, expired receipts and concurrent local recovery by reading device state first. Never silently replay Apply, restore an older document or overwrite a newer one. Require explicit user conflict review; optional local/HA ownership transfer is deferred and must not block the single-credential workflow.
- [ ] Keep a validated local document, previous-valid backup and compiled recovery path, plus the minimal local maintenance page. HA downtime must not prevent loading the cached UI; live readings/actions still depend on HA. Do not format SD, touch factory media or claim ordinary FatFs rename is power-loss atomic; carry the physical failure gates from 3.5 into release acceptance.
- [ ] Verify the complete transfer path without enabling runtime dispatch or commanding household devices. Keep executable templates, arbitrary file paths and generic HA service-call definitions out of the configuration channel; a configuration deployment must not execute an action tile as a side effect.

Exit gate: host fault tests and a separately authorized device test demonstrate
candidate Save versus Apply, restart verification, recovery and conflict handling
with preserved local preferences and no household commands.

#### 3.8.5. Existing widget rollout and working-panel cutover

- [ ] Connect the editor to each runtime family from 3.7 as it is accepted: room navigation/grouped and standalone sensors first, then lights, sockets, climate, humidifiers, Plant and attention. Reuse the same constructors for room tiles, reusable pages and detail/pop-up hosts; do not add an HA-specific LVGL renderer.
- [ ] Replace per-entity compiled imports/bindings with bounded Native API runtime adapters, applying structural changes by controlled restart first. Keep states, availability and alarm decisions authoritative in HA. Runtime action dispatch remains gated by the sender/readiness/permission/callback contract in 3.6, independently of editor completion.
- [ ] Import the current `panel.yaml` into an HA draft, compare stable identities/settings and generated-versus-runtime Linux captures, then migrate one accepted family/configuration at a time. Preserve local overrides by the rules in 3.8.1, action targets, offline startup and an explicit way back to the working generated configuration until parity and recovery are proven.
- [ ] Demonstrate room/name/entity/binding/placement changes with only JSON Save/Apply and no firmware build for already supported families. Explain which changes still require firmware (hardware, new widget code/assets or expanded limits); never advertise complete runtime configuration while any selected family remains compiled-only.

Exit gate: the working configuration has matching layout/state/targets, bounded
repeated Apply/restart behavior and accepted runtime support for every selected
family; activation is not inferred from the editor's ability to export JSON.

#### 3.8.6. Acceptance, compatibility and distribution

- [ ] Test integration setup/authentication/admin enforcement/unload, entity rename/removal, two HA instances, multiple browser tabs, stale sessions, network/HA restarts, interrupted transfer, malformed/oversized/unsupported JSON and unavailable/full/read-only/corrupt SD. Preserve the no-actuator default; real device commands require separate explicit authorization.
- [ ] Measure internal free/minimum/largest block, PSRAM, main/HTTP stack minima, latency and retained-buffer cleanup with maximum supported JSON, simultaneous HA/native-web clients, repeated export/check/Save/Apply and long navigation/capture runs. Compare against the current deployed baseline; moving the editor does not remove ESP32 parser/LVGL costs or close existing reset/warning gates.
- [ ] Check responsive HA editor layouts on mobile/desktop, light/dark themes, keyboard/touch access and actionable validation errors. Extend the installed-shell Chromium acceptance to supported browser/companion versions, non-cancelable history/forced background teardown and the recorded Forward compatibility issue. Compare representative previews to actual shared-renderer captures; do not make the HA integration depend on an always-running Linux simulator merely to edit or deploy JSON.
- [ ] Maintain a tested HA/ESPHome/schema/transport compatibility matrix with capability negotiation, explicit migrations and preserved recovery on downgrade. Reassess released official extension APIs before adding adapters; avoid silent SDK patches and promises about unspecified future versions.
- [ ] Document installation, secure pairing, authority handover, draft versus candidate versus Apply, backup/recovery and removal of the integration without erasing the panel's cached configuration. Package the custom integration for manual installation first, then optional HACS distribution and multi-panel backup/deploy after single-panel acceptance; never auto-deploy to a fleet on reconnect.

Release gate: host/browser acceptance plus separately authorized OTA/device,
physical SD/power-loss and long memory/reconnect checks. Planning these stages
does not authorize a firmware build, upload or real household action.
