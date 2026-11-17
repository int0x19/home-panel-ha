# HA Configuration Page

## Scope

The manual-install companion registers **Home Panel** in HA's administrator
sidebar at `/home-panel-config`. It provides read/import/check and a
[room/action draft editor](HA_DRAFT_EDITOR.md) with explicit HA checkpoints and
[flash candidate Send](HA_CANDIDATE_SEND.md). The existing
[read/check backend](HA_READ_CHECK_API.md) remains in use; Send is an explicit
extension, not activation. There are no Apply, firmware-upload or household-action
controls, and unsupported firmware remains read/check-only.

The page's JavaScript/CSS live in `custom_components/home_panel/www` on the HA
host, not ESP32. Registration uses the official async static-path/custom-panel
helpers, with `require_admin`, no iframe, CDN, frontend build step or external
asset URL. HA provides its theme, icons, authenticated `hass.callWS` connection
and sidebar. The module includes English/Russian labels.

Headless HA keeps the backend without registering a page. The shared page is
registered once per HA instance, not per panel. Unloading/removing an entry does
not remove the global page or another entry's access; reloading its panel list
shows unavailable/empty entries. A conflicting sidebar path is logged and left
unchanged, rather than overwriting another integration's panel.

## Workflow

1. Install the [companion](HA_INTEGRATION.md#installation-and-setup) and open
   **Home Panel**. Select a panel explicitly: loading the page only lists
   entries and never starts an export/validation job.
2. Selection first restores any HA checkpoint without contacting the device;
   otherwise it reads fresh metadata. Inspect loaded source/revision, SD status,
   byte ceiling, supported widget families and active/candidate/backup files.
   Collapsed capabilities include the remaining decoder/resource ceilings.
3. Import a valid file explicitly. The backend exports exact bytes and checks
   them with the device's shared validator before showing the original JSON,
   source/revision/byte count, digest and report. **Download original** retains
   whitespace/CRLF; it does not serialize a parsed object or read the textarea.
4. Use **Check JSON** for independent local input, pasted or loaded from a
   UTF-8 file. Input stays separate from the original. **Validate** calls only
   the shared device validator, without changing any SD file or active screen.
   Invalid model results are displayed as results, not network errors.
   Alternatively, **Edit draft** creates an independent structured room/action
   draft from the checked original; it does not change this raw input. Draft
   checking **In HA** uses the [shared Python model](HA_MODEL_VALIDATION.md)
   offline. **On ESP32** remains the separate device check; refresh device status
   explicitly after restoring an HA checkpoint before running it.
5. Edited text makes an earlier report visibly stale. Switching panel with
   local text asks for confirmation; cancelling keeps both text and selection.
   Local text also requests browser unload confirmation where supported.

The current scope is explicitly **action preview**, with unmanaged authority,
unmeasured budgets/incomplete assets and deployment unavailable. A successful
validation does not enable deployment or migrate generated rooms. See
[compatibility](CORE_CONTRACT.md): the firmware installed on
2026-11-05 lacks the prepared identity/capabilities extension and cannot yet
pair with this companion. The page does not bypass that gate.

## Recovery And Security

Only one explicit operation is sent at a time. Busy/restarting metadata blocks
jobs; missing SD blocks imports but need not prevent validate-only. Every
operation still rechecks its guards in the backend, even if a button was enabled
from an earlier snapshot. Firmware mismatch, missing entries/SD, negative
validation, changed source and unknown result have distinct UI states.

A disconnect or uncertain result disables jobs until an explicit fresh idle
status succeeds. Reconnection does not replay POSTs or silently restore a
report's freshness. A status refresh marks previous checks as previous checks;
changed source digests do not erase the downloaded original. A panel switch,
detached component, user change or privilege loss invalidates pending replies.
Privilege loss clears document/input buffers and hides the workspace.

The browser receives no panel origin, key, hardware ID or boot nonce. All four
device read/check WS commands enforce administrator access server-side; hiding a sidebar item is
not the authorization boundary. Names/documents use text nodes, never HTML.
No browser-to-ESP32 requests, arbitrary URLs, service calls, local/session
browser storage or automatic draft persistence are added. Explicit
[HA Save/Load/Delete](HA_DRAFT_STORAGE.md) use three additional administrator-only
commands and local HA storage, never device I/O. The separate admin-only `model_check`
command checks the full shared Python model in an executor, not on ESP32.
One original, one raw-check input
and an optional structured draft are held in the attached component; only an
explicitly saved HA checkpoint survives it. Unsaved edits have no automatic
device side effects.
Exports/local file reads have a 64 KiB ceiling; pasted input has a 65,536-code-unit
editor ceiling and may exceed the device byte budget locally. Its UTF-8 byte
count is shown, and validation is blocked above the negotiated device ceiling
(at most 64 KiB). Local JSON remains in HA/browser memory, not a second ESP32
editor buffer. Temporary export/validator costs on ESP32 still need measurement.

The current management key is still the debug key; scoped credentials and
enforced authority remain prerequisites for general write deployment. Static
assets contain no user data and may be read without auth, like other HA assets.
The authenticated WS backend remains the only path to paired metadata/files.

## Verification

Acceptance uses HA **2026.11.0**, official frontend **20261028.4**, the matching
official pytest plugin and a separate Python 3.14 environment. See
[test setup](HA_INTEGRATION.md#tests). Run:

```sh
.venv/bin/python -m pytest -c tests/ha_integration/pytest.ini tests/ha_integration
```

The tests exercise actual HA frontend registration, static HTTP, admin versus
non-admin sidebar filtering, headless operation and route collision handling.
Chromium drives the production component through a small test-only `hass`
property adapter and real authenticated HA WebSocket commands. Device wire I/O
is synthetic. EN/RU, light/dark, 320/390/1280px, tab keyboard navigation, exact
downloads, UTF-8 limits/files, dirty selection, negative checks, no-SD/busy,
disconnect/unknown-result recovery and late-reply privilege changes are covered.
Screenshots and the exact downloaded fixture are under `build/ha-frontend`.
Container-width tests at 320/460/850px in a 1280px browser also cover the space
reserved by HA's sidebar; responsive rules do not depend only on viewport width.
The combined run on 2026-11-07 passes **74 HA tests**, **37 standalone/native C++
tests** and **six standalone HTTP tests**, for 117 targeted checks, not whole-repo
or branch coverage. The browser case is included in the 74, not counted again
for each screenshot/assertion.

Those initial checks are **component-browser acceptance**: the isolated fixture
uses fallback icon glyphs, while HA supplies `ha-icon` in production. The later
[navigation acceptance](HA_NAVIGATION.md) also loads the installed HA 2026.11
frontend with actual auth, icons, sidebar, router and standard backend APIs,
without the property adapter. It covers dirty Settings/sidebar/Back cancellation,
accepted discard, clean remount and 390/1280px screenshots. Broader browser and
companion-mobile behavior, physical pairing, ESP32 memory/latency and long-duration
acceptance remain open, including the documented Chromium Forward limitation.
No real
HA/panel connections, firmware compilation/OTA, actuator commands or physical
SD writes occur in these tests. Existing upstream deprecations and the separate
[pre-auth WS probe limitation](HA_READ_CHECK_API.md#verification-notes) are not
silently patched or declared resolved.

For a local visual preview after browser acceptance:

```sh
node tests/ha_frontend_preview.cjs 8775 "$(.venv/bin/python -c 'from home_panel_core import asset_path; print(asset_path("runtime-draft.mjs"))')"
```

Open `http://127.0.0.1:8775`. It binds loopback only and serves synthetic captured
metadata/imports from `build/ha-frontend/preview.json`. Its banner distinguishes
the fixture from HA; it has no credentials, validator, device connection or
write endpoints. Its checkpoint simulation is in that page's memory only.
Validation deliberately reports unavailable. It is not an
alternate integration, protocol implementation or device editor.

## Next

Extend the accepted action registry picker/checkpoint/history editor with
capability-aware selection for other families, templates and Linux preview
integration. Keep exact import artifacts separate.
Broader HA registry selection, ownership, candidate/Apply
and rollout to other runtime widget families remain their own roadmap gates.
