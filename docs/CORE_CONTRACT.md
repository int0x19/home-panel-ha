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
HA-managed authority, and no Send/Apply method is added to the shared client.
The running panel and published Marketplace 0.1.1 remain unchanged.

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
