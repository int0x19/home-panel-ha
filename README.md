# Home Panel HA

![Home Panel](custom_components/home_panel/brand/icon.png)

Home Assistant companion for the ESP32/LVGL Home Panel. This repository owns the
integration, administrator configuration page, bounded HA draft checkpoints,
HA-specific validation orchestration, translations and HA/browser tests.

The firmware/generator/simulator remain in `esp32panel`. Shared models, JSON
codec, bounded configuration client and immutable JS draft editing live in the independent
`home-panel-core` Python package. There are no sibling-directory imports,
submodules or handwritten copies of those implementations here.

## Installation

Current source development is **0.1.2** with a capability-gated
[numeric-sensor/group editor](docs/HA_SENSOR_DRAFT.md) and explicit
[candidate Send](docs/HA_CANDIDATE_SEND.md) plus separate
[Apply and activation inspection](docs/HA_CANDIDATE_APPLY.md). It is not yet a
published Marketplace release and does not enable managed device deployment.
The build examples below use the matching development core wheel.

Version **0.1.1** fixes pairing/import with internal-flash firmware
(`flash-confirmed`, `flash-nvs`). No SD card or firmware update is required for
this compatibility fix. Upgrade/restart HA, then retry the panel setup.

Requires **Home Assistant 2026.11.0 or newer**. Marketplace installs the ZIP
attached to a [published release](https://github.com/int0x19/home-panel-ha/releases),
not a source branch. Select **0.1.1**, not `main` or a commit hash.
See the [publication and installation checklist](docs/MARKETPLACE.md).

### Marketplace

Open [Home Panel in your Marketplace](https://my.home-assistant.io/redirect/marketplace_repository/?owner=int0x19&repository=home-panel-ha&category=integration),
add the custom repository and install **Home Panel Configuration**. Only
`home-panel-ha` is installed here: core is included, firmware stays on ESP32.
Restart HA when requested, then add **Home Panel Configuration** in Devices &
Services. Setup asks for the panel's local HTTP address and configuration key,
not a Home Assistant access token. Standard ESPHome integration remains in use.

### Manual Installation

Build or obtain a `home_panel_core-0.1.2-py3-none-any.whl`, then create the
offline-installable integration archive:

```sh
python3 tools/build_release.py --wheel /path/to/home_panel_core-0.1.2-py3-none-any.whl
```

Extract `dist/home-panel-ha.zip` into the Home Assistant configuration directory,
so the result is `config/custom_components/home_panel/`. Restart HA, then add
**Home Panel Configuration** through Devices & Services. The archive includes
the exact core wheel code/assets under `_vendor`; no PyPI package, extra HA
container pip command or firmware checkout is needed on the HA host.

Do not copy only this repository's source `custom_components` directory for a
production installation: source development expects an installed core package.
Release vendoring is generated, version-checked and recorded with the input wheel
SHA-256. It is not a fork and is never edited by hand. An incompatible bundled
core fails closed instead of falling back to an installed version.

Marketplace must use release asset **`home_panel.zip`**, not the manually
extractable `home-panel-ha.zip`. It extracts into the component folder itself;
our builder supports both layouts and bundles the same pinned core in each.
An unbuilt default branch is not a supported production installation.

The GitHub repository is public; a custom repository can be installed without
waiting for catalog inclusion. Pairing requires firmware exposing the negotiated identity and
capabilities contract; merely installing the integration does not add firmware
features or enable device writes. See [compatibility](docs/CORE_CONTRACT.md).

## Development And Tests

Use Python >=3.14.2 for HA 2026.11, separately from the firmware ESPHome environment:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
make core-install CORE_WHEEL=/path/to/home_panel_core-0.1.2-py3-none-any.whl
make test CORE_WHEEL=/path/to/home_panel_core-0.1.2-py3-none-any.whl
make release CORE_WHEEL=/path/to/home_panel_core-0.1.2-py3-none-any.whl
make marketplace CORE_WHEEL=/path/to/home_panel_core-0.1.2-py3-none-any.whl
```

The tests use actual HA 2026.11 fixtures, synthetic transport and temporary
storage. Browser acceptance additionally needs Node, distro Playwright and
`/usr/bin/chromium`; it skips if those optional tools are absent. No real HA,
ESP32, household command or physical SD write is involved.

GitHub CI uses the npm-locked Playwright/browser rather than a runner's system
Chromium. The same path is available locally with Node >=20:

```sh
npm ci
npx playwright install --with-deps chromium
HA_BROWSER_MANAGED_PLAYWRIGHT=1 make test CORE_WHEEL=/path/to/home_panel_core-0.1.2-py3-none-any.whl
```

After installing npm dependencies, use this managed-browser mode; the distro
compatibility workaround is only for the pre-existing Debian test environment.

The shared JS asset is served from the installed/bundled core using HA's static
path API. It is not duplicated in `www`. Source and bundled release must both
retain administrator authorization, bounded validation and exact-original guards.

## Roadmap And Docs

Apply acceptance: **254 HA tests and 79 installed-core tests pass**. The
[Apply workflow](docs/HA_CANDIDATE_APPLY.md) is now implemented in source and
local archives, not yet published or installed in the user's HA. Next is guarded
Discard/recovery, followed by separately authorized physical acceptance.

Candidate Send acceptance: **232 tests pass** on HA 2026.11, including actual
WS/HTTP/Chromium and self-contained manual/Marketplace archives; 66 pinned-core
tests pass separately. This is source/host acceptance, not publication or an
installed-HA/physical-panel update. See [Send contract](docs/HA_CANDIDATE_SEND.md).

Current functionality and deployment limits are documented in `docs/HA_*.md`.
The [action entity picker](docs/HA_ENTITY_CATALOG.md) supports registry/state
search with domain/area filters without contacting ESP32.
The same catalog has a separate numeric-sensor scope with allowlisted defaults;
[sensor draft acceptance](docs/HA_SENSOR_DRAFT.md) covers grouping and the shared
Linux renderer. The working firmware's capability/deployment gates remain open.
The [change summary](docs/HA_DRAFT_CHANGES.md) compares a local draft with its
original or observed HA checkpoint independently of Save and validation.
The [bounded history](docs/HA_DRAFT_HISTORY.md) keeps up to three previous
checkpoints and opens them as unsaved drafts without changing the current one.
The [navigation guard](docs/HA_NAVIGATION.md) protects unsaved drafts, unfinished
fields and raw-check JSON, with explicit warnings for unsupported browsers.
The [candidate Send workflow](docs/HA_CANDIDATE_SEND.md) checks exact canonical
bytes on ESP32 and stores them as a flash candidate, without activation/restart.
HA checkpoint Save, device Check, Send and Apply are independent operations.
The [Apply workflow](docs/HA_CANDIDATE_APPLY.md) requires explicit confirmation
and reports a running configuration only after verified trial startup/readback.
Next: guarded Discard/recovery and separately authorized physical acceptance.

The source subtree history comes from `esp32panel` commit `b72b70f` (2026-11-07).
The original firmware history is unchanged. Shared library history continues in
`home-panel-core`. This repository's origin is prepared as
`https://github.com/int0x19/home-panel-ha.git`; the firmware origin is not reused.

Split acceptance: 121 source-integration tests and 129 release-bundle tests
pass on HA 2026.11, including browser checks and offline dependency loading.
These are host tests, not installed-device or full production-HA acceptance.

Action catalog acceptance: 142 tests pass on HA 2026.11, including registry/area
filters, authenticated boundaries, offline selection and responsive browser checks.

Change-summary acceptance: 169 tests pass on HA 2026.11, including structural
comparison, shared-worker limits and independent storage/validation state.

History acceptance: 195 tests pass on HA 2026.11, including format-1 read-only
access, explicit format-2 publication, bounded retention and two-browser unsaved
restoration/conflict checks. Storage upgrade/downgrade limits are documented in
[HA draft history](docs/HA_DRAFT_HISTORY.md).

Navigation acceptance: **196 tests** pass on HA 2026.11, including actual
installed frontend/router/sidebar/icons at mobile/desktop widths, dirty
Back/settings/sidebar cancellation, accepted discard/remount and listener
cleanup. The five existing upstream deprecations remain. Browser policy,
forced background teardown and Chromium's repeated programmatic Forward
limitation are recorded in [navigation protection](docs/HA_NAVIGATION.md).
No ESP32 firmware, physical SD or household action is involved.

Marketplace preparation acceptance (2026-11-16): **200 tests pass** on HA
2026.11.0, including source/browser checks, deterministic manual/Marketplace
archives, bundled-only imports and both license copies. Five upstream
deprecation warnings remain. Remote hassfest/HACS checks run in GitHub Actions;
a release is only installable after its ZIP assets are published. Local tests
are not a claim of successful installation in a user's running HA instance.

## License

Apache-2.0; see [LICENSE](LICENSE). Copyright 2026 Denis and contributors.
The Lucide-derived brand icon retains its ISC notice in `brand/LICENSE.txt`.
