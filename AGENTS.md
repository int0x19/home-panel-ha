# Project Working Agreement

- End each task or stage with the result, verification status, remaining blockers
  and the next concrete step from the current roadmap. Keep the summary concise.
- Make focused intermediate commits when a coherent change is ready or many
  changes accumulate; do not wait for an entire roadmap stage. Run relevant checks
  first, keep commits reviewable and never include unrelated user changes.
- At stage boundaries check all three project repositories: esp32panel,
  home-panel-core and home-panel-ha. Commit related changes in each repository;
  do not create empty commits or assume a commit also means push/publication.
- Keep shared contracts, package versions, consumer pins, bundled assets,
  documentation and roadmaps consistent. Check affected consumers when shared
  code changes. Documentation-only commits do not require package version bumps
  or moving an exact source pin away from its tested release commit.
- Dependency upgrades require compatibility checks; do not automatically update
  ESPHome, HA or a consumer pin merely to match the newest available version.
- Distinguish source changes, tested artifacts, published releases and firmware
  actually running on the panel. Do not claim unperformed device acceptance.
- Prioritize the main HA configuration/panel workflow. Debug tools are
  maintenance-only unless a reproducible failure or explicit request needs more.
- Before adding functionality, verify the concrete panel use case and check
  existing public HA/ESPHome facilities in the supported versions. Reuse them
  instead of building a parallel auth, state, automation or management system.
- Keep custom device code limited to gaps required by the panel. Weigh retained
  RAM/stack, flash writes, latency and recovery/maintenance complexity against
  user benefit. Defer speculative multi-controller and infrastructure features;
  do not make them prerequisites for the single-HA workflow. Preserve necessary
  authentication, validation, conflict checks and safe recovery.
