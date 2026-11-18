# Marketplace Publication And Installation

## Repository Roles

The prepared destinations are `int0x19/home-panel-ha` (this integration) and
`int0x19/home-panel-core` (build dependency). Their local origins already point
to those GitHub URLs. Firmware's original `esp32panel` remote is unchanged.
Only the integration belongs in Marketplace. There is no separate core install
and no PyPI requirement on the user's HA instance.

Home Assistant 2026.11 Marketplace still uses the root `hacs.json`, the
`hacs/action` validator and the `hacs/default` catalog. This is not an ESPHome
add-on, Lovelace card or replacement of the standard ESPHome integration.

## Prepared Locally

- One component: `custom_components/home_panel`, version `0.1.0`.
- Root `hacs.json`: HA >=2026.11.0, release ZIP, no default-branch installation
  offered by legacy HACS. Always choose a published release in Marketplace too.
- Maintainer `@int0x19`, target documentation/issues URLs and EN/RU translations.
- Local `brand/icon.png`, rendered from the existing Lucide house icon under
  its ISC license (`brand/LICENSE.txt`), not Home Assistant's logo.
- A pinned core repository and full commit in `core-source.json`; no floating
  `main`, source-tree import or manual copy of shared model code.
- GitHub Actions for hassfest, HACS validation, HA tests, two archive layouts
  and draft release creation. Only the draft-release job has write permission.

These files do not mean a public repository exists, that remote CI has passed
or that the catalog has accepted the integration. Repository-level checks need
GitHub metadata and published releases and cannot all be completed offline.

Local acceptance, 2026-11-16: 200 tests passed on HA 2026.11.0, including
browser checks and offline imports of both archive layouts, with five upstream
deprecation warnings. The licensed core wheel is about 63 KiB; Marketplace ZIP
119 KiB; manual ZIP 122 KiB. No ESP32 build/OTA, live HA service, device settings
change or SD write was performed for publication preparation.

## Before First Publication

1. Repository names `int0x19/home-panel-ha` and `int0x19/home-panel-core` and
   Apache-2.0 were confirmed by the owner on 2026-11-16. Both repositories have
   a `LICENSE`; core's wheel and both integration archives carry their licenses.
   The icon retains its separate ISC notice. Review other third-party notices
   before adding new dependencies or redistributing media.
2. Create both GitHub repositories (public for the planned public distribution),
   with no generated README/history. Enable Issues and Actions, add descriptions
   and relevant topics (`home-assistant`, `esphome`, `lvgl`, `home-panel`).
3. Give the connected GitHub application access to the new repositories.
   This does not configure shell `git push` credentials. Use SSH or a credential
   helper on this host, or push yourself; never put a token in Git remote URLs,
   source files or chat. Review history for private data before a public push.
4. Push core first, including the commit recorded in `core-source.json`. Then
   push this repository. The workflow builds the wheel from that exact commit;
   a private core needs a separately scoped CI credential and is not the
   prepared public workflow's default. No dependency token is needed publicly.
5. Check Actions. The HACS repository-metadata/release checks may need the first
   public release before they can all pass; do not suppress checks for catalog
   submission. Review remaining compatibility/physical acceptance limits in
   `ROADMAP.md` and release notes before offering the integration to others.

Do not push the firmware's real `panel.yaml`, `device.yaml`, `secrets.yaml`,
debug keys, private images or device logs to a public repository by accident.
This preparation does not create GitHub repositories or publish any files.

## Build And Release

Local packaging, using the pinned core wheel:

```sh
make release marketplace CORE_WHEEL=/path/to/home_panel_core-0.1.2-py3-none-any.whl
```

| Artifact | Destination when unpacking |
| --- | --- |
| `dist/home_panel.zip` | Marketplace's `custom_components/home_panel/` target |
| `dist/home-panel-ha.zip` | HA configuration directory, manual installation |

The Marketplace ZIP has `manifest.json`, `__init__.py`, `www/`, `translations/`,
`brand/` and `_vendor/` at its root. It must **not** contain another
`custom_components/home_panel` nesting. Both layouts include the wheel SHA-256
receipt `core-release.json`. Tests verify deterministic bytes and importing the
bundled core with standalone-core imports explicitly blocked.

After pushing and reviewing CI, create/push a tag matching the manifest version
exactly, for example `0.1.2` (no `v` prefix). The workflow attaches both ZIPs and
`SHA256SUMS` to a **draft** GitHub release. Review notes, files and licensing,
then publish it. A tag or Actions artifact alone is not an installable release.
For a pre-release, mark it accordingly; users must enable pre-release versions.
Do not overwrite an already published version: bump manifest/tag for changes
and retain older compatible releases. Core's package version is independent.

## Install In Home Assistant

After a release exists, open:

https://my.home-assistant.io/redirect/marketplace_repository/?owner=int0x19&repository=home-panel-ha&category=integration

Accept adding the custom repository as an **integration**, install the published
version and restart when requested. Add **Home Panel Configuration** via
Settings > Devices & Services. Supply the panel's local address and its
configuration/debug HTTP key through the config flow, not an HA token. The key
remains in HA backend configuration; never include it in screenshots or exports.

Before setup, the panel must expose the identity/capability API documented in
`CORE_CONTRACT.md`. HA checkpoint Save is not ESP32 Send or Apply. Version
0.1.2 offers explicit candidate operations only on a compatible paired panel;
it does not enable automatic deployment or household service calls.
Installing this integration neither flashes ESP32 nor migrates an existing
YAML-built panel automatically. Runtime support is capability-gated, not implied
by the library being able to parse a widget's JSON.

## Catalog Listing Later

A custom repository can be installed without catalog acceptance. For discovery
by everyone, pass hassfest and all HACS checks without ignored validators,
publish a reviewed full release, then submit `int0x19/home-panel-ha` to the
alphabetically sorted `integration` list in `hacs/default`. Do this separately
from the first private testing/install round.

Primary requirements:
- https://contributors.home-assistant.io/marketplace/guides/integrations/
- https://contributors.home-assistant.io/marketplace/guides/releases/
- https://contributors.home-assistant.io/marketplace/reference/hacs-json/
- https://contributors.home-assistant.io/marketplace/guides/catalog/
