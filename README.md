# Home Panel HA

Home Assistant companion for the ESP32/LVGL Home Panel. This repository owns the
integration, administrator configuration page, bounded HA draft checkpoints,
HA-specific validation orchestration, translations and HA/browser tests.

The firmware/generator/simulator remain in `esp32panel`. Shared models, JSON
codec, read/check client and immutable JS draft editing live in the independent
`home-panel-core` Python package. There are no sibling-directory imports,
submodules or handwritten copies of those implementations here.

## Installation

Build or obtain a `home_panel_core-0.1.0-py3-none-any.whl`, then create the
offline-installable integration archive:

```sh
python3 tools/build_release.py --wheel /path/to/home_panel_core-0.1.0-py3-none-any.whl
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

No HACS publication, hosted remote or real HA/device installation is performed
by the repository split. The installed ESP32 still needs the prepared metadata
firmware before companion pairing. This repo does not bypass that acceptance gate.

## Development And Tests

Use Python >=3.14.2 for HA 2026.11, separately from the firmware ESPHome environment:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
make core-install CORE_WHEEL=/path/to/home_panel_core-0.1.0-py3-none-any.whl
make test CORE_WHEEL=/path/to/home_panel_core-0.1.0-py3-none-any.whl
make release CORE_WHEEL=/path/to/home_panel_core-0.1.0-py3-none-any.whl
```

The tests use actual HA 2026.11 fixtures, synthetic transport and temporary
storage. Browser acceptance additionally needs Node, distro Playwright and
`/usr/bin/chromium`; it skips if those optional tools are absent. No real HA,
ESP32, household command or physical SD write is involved.

The shared JS asset is served from the installed/bundled core using HA's static
path API. It is not duplicated in `www`. Source and bundled release must both
retain administrator authorization, bounded validation and exact-original guards.

## Roadmap And Docs

Current functionality and deployment limits are documented in `docs/HA_*.md`.
Next: HA entity/area selection, richer editor families, history and guarded
device deployment. Host model checks, HA checkpoint Save, device validation,
SD-candidate Save and Apply remain independent operations.

The source subtree history comes from `esp32panel` commit `b72b70f` (2026-11-07).
The original firmware history is unchanged. Shared library history continues in
`home-panel-core`. Configure the new repository's own origin before publishing;
the firmware origin is intentionally not reused.
