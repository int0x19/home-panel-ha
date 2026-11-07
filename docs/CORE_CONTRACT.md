# Shared Core Contract

The canonical configuration-management contract now belongs to
`home-panel-core/docs/CONFIGURATION_CONTRACT.md`. That repository owns the
versioned logical model, canonical encoding, protocol/client and shared JS edits.
This integration consumes its pinned wheel; it does not define another schema.

## Prepared Capabilities Extension

The prepared `capabilities.v1` metadata and stable factory identity remain
required for pairing. They are still subject to physical firmware acceptance;
the repository split did not install them. See the core contract for the exact
compatibility matrix and the firmware roadmap for device acceptance.

HA checks, saved checkpoints and generated release bundles do not grant
ownership or deployment readiness. Those gates remain unchanged. Hosted links
can be added after separate origins have been configured for the new repos.
