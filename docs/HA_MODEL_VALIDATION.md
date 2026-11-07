# Shared Model Validation In HA

## Scope

The room/action editor has two explicit checks: **In HA** and **On ESP32**.
The first checks the complete existing Python logical model offline; the second
uses the negotiated device's C++ validator. Neither saves a file, uploads a
candidate, applies configuration, invokes a household command or enables runtime
dispatch. Saving a checkpoint in HA remains a separate operation.

HA validation works with an unloaded/offline panel entry and a restored draft,
without a metadata request. It does not negotiate current firmware features,
loaded font/icon assets, ownership or measured ESP32 memory/subscription budgets.
A supported host family may pass while the device action pilot cannot render
it. Device validation and all deployment gates remain mandatory before any
future Send/Apply operation.

## One Implementation

`home_panel_core.runtime_model` contains the existing
logical models, profiles, references, feature checks, no-scroll row planners
and resolved-style geometry validator moved from the host scripts. It has no
Home Assistant, YAML, repository-template, hardware or secrets dependency.
Standard-library timezone validation uses the installed timezone database.
HA executes the shared validator in its executor, not its event loop.

The old `scripts/panel_*` modules retain compatible imports through a host-only
bridge to those same physical source files. `panel_model.py` keeps YAML/hardware/
template I/O; `panel_runtime.py` keeps YAML conversion and explicit file loading.
Runtime validation consumes the document's fully resolved numeric theme/layout,
without loading `templates/base.yaml` or silently filling missing fields.
The style field inventory is part of the versioned model, checked in tests
against the editable base template. Adding a schema token requires updating
the shared inventory and relevant native decoder, not just a new template key.

This is not an HA-only schema, duplicate field validator or browser renderer.
The existing pure canonical encoder is also shared. JSON schema/protocol
versions and canonical numeric spelling are unchanged by the extraction.

## Administrator API

```js
const checked = await hass.callWS({
  type: "home_panel/config/model_check",
  entry_id: entryId,
  document: jsonText,
});
```

Only an existing Home Panel entry and JSON text are accepted. No path, URL,
credential, caller-supplied limit or capability override is accepted. Server-side
administrator authorization runs before scheduling work. Input has a 64 KiB
UTF-8 ceiling, then the shared depth/node/string/count/geometry/binding budgets.
Duplicate keys, nonfinite numbers, unsupported schema/required features, invalid
profiles, references, widget identities and overflowing ordinary rooms fail.
Dedicated Actions pages use the existing shared pagination planner.

Responses contain `version: 1`, `validator: "shared_python"`,
`scope: "host_model"`, exact `input_bytes`/`input_sha256`, host `limits`, `valid`
and the shared `report` or null. A successful report includes canonical
`bytes`/`sha256`, revision, counts and room/page heights. The exact input digest
may differ from the canonical report digest; input is not re-exported or
silently substituted for the imported original.

Invalid models return a normal result with `valid: false`,
`error: "invalid_model"` and no report. Untrusted exception messages/JSON fields
are not relayed or logged. Empty/oversized/non-UTF-8 transport input instead uses
the fixed WS error `invalid_document`. Missing entries use `panel_unavailable`.
`device_checked`, `limits_measured_on_device` and `deployment_ready` are always
false. A successful HA result is not a device acceptance certificate.

One tracked executor check per entry is allowed; another returns
`model_check_busy`, without a queued second document. Disconnecting/cancelling
the waiter does not release the slot before its executor work actually ends.
Removed entries discard late results. There is no automatic check/retry or
persisted validation history. Browser replies are tied to the selected entry,
component epoch and draft version, and edits mark an earlier report previous.
HA model errors do not invalidate device metadata or HA checkpoint tokens.
Restoring a checkpoint clears both transient validation reports.

## Verification

The 2026-11-07 run passes **121 HA 2026.11 tests**, including 23 new model-check
cases and expanded Chromium scenarios. A broader host run executes 180 tests:
**143 pass, 37 are skipped** by their native/integration prerequisites. A separate
native-enabled run passes **28 C++/LVGL draft/decoder/presentation tests**;
these overlap the host run and must not be added as unique coverage.

Tests cover standalone copied-bundle operation without HA/YAML/templates, source
identity with host validation, template field parity, valid current config,
semantic rejection, actual authenticated/admin HA WS, cancellation and worker
bounds. Chromium checks separate reports, stale results after edits, checking
before device status refresh after restore, error isolation and EN/RU
light/dark layouts at 320/390/1280px. Existing Linux C++/LVGL parity tests
exercise the moved models.

```sh
# Native/host acceptance: run the corresponding command in the firmware repository.
.venv/bin/python -m pytest -c tests/ha_integration/pytest.ini tests/ha_integration
# Native/host acceptance: run the corresponding command in the firmware repository.
```

Full installed-HA-shell, physical companion pairing and measured device
acceptance remain open. No ESP32 build/OTA or household/physical SD operation is
part of this stage. The local visual fixture intentionally has no validator;
its check buttons report unavailable rather than simulating acceptance.
