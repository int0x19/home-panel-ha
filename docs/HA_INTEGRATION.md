# Home Panel Configuration Integration

## Scope And Compatibility

Experimental manual-install companion in `custom_components/home_panel`, tested
against **Home Assistant 2026.11.0** and the matching official
`pytest-homeassistant==2026.11.0`. No Home Assistant downgrade, ESPHome upgrade
or replacement of the standard ESPHome integration is required. Other HA
versions are not accepted by these tests automatically.

The companion reads runtime metadata and exposes an administrator-only
[JSON import/check backend](HA_READ_CHECK_API.md) and [HA sidebar page](HA_FRONTEND.md).
It includes a [room/action editor](HA_DRAFT_EDITOR.md) and explicit
[HA draft checkpoints](HA_DRAFT_STORAGE.md), not yet
the full production editor,
and it does not migrate working `panel.yaml` rooms to runtime JSON.
The runtime document still controls the separate action preview, with dispatch
disabled. Household states/actions continue through ESPHome Native API.

The panel must provide the prepared `capabilities.v1` extension and a stable
factory ID. The firmware installed on 2026-11-05 does not provide them: adding
that firmware returns an explicit unsupported-firmware error, without pairing
by IP or changing the panel. A separately authorized firmware build/OTA and
physical identity/memory acceptance are still required before real pairing.
See [the contract](CORE_CONTRACT.md#prepared-capabilities-extension).

## Installation And Setup

1. Build the offline release ZIP with `tools/build_release.py --wheel ...`, as
   described in the repository README. Extract it under the HA configuration
   directory, beside `configuration.yaml`. The ZIP includes the pinned core;
   copying only the source component folder is not a production installation.
2. Restart HA and add **Home Panel Configuration** through Settings -> Devices
   & services -> Add integration. Keep the existing ESPHome integration.
3. Supply the panel origin, for example `http://192.168.1.45`, and its current
   debug/configuration API key. Paths, query strings and credential URLs are
   rejected. Do not supply an HA token or the OTA password.
4. Setup reads status and capabilities, verifies their boot session and byte
   ceiling, and stores the factory ID as the config entry's unique identity.
   The same ID cannot be registered twice, even through another address.
5. Administrators see **Home Panel** in the HA sidebar (`/home-panel-config`).
   Select a panel explicitly, then import a file or check separate local JSON.
   No YAML `panel_custom` entry or external JavaScript URL is required.

English and Russian forms/entity names are included. The entry/device name can
be renamed through HA normally. Diagnostic entities show:

- Runtime configuration source (`builtin`, `file`, `backup`) and revision.
- Current runtime JSON input ceiling in bytes.
- Whether configuration SD storage is ready and the configuration API is busy.

The source sensor's attributes explicitly report action-preview-only scope,
unmanaged authority, unsupported managed deployment and incomplete/unmeasured
asset/budget acceptance. A loaded revision is not a claim that a configuration
has passed the pending first-frame/trial-confirmation gate. Missing SD or a
busy job does not prevent read-only pairing.

## Connection And Lifecycle

Polling defaults to 60 seconds; integration options allow 30-600 seconds. Each
idle poll makes exactly two bounded GET requests under one client lock: status and
capabilities. It does not scan SD, allocate exports, create jobs or send POSTs.
Explicit import/check operations pause background I/O and use the same client.
The matching snapshots are immutable, and a mixed boot/session/identity/limit
response is rejected rather than published as fresh data.

Use **Reconfigure** to change IP/hostname or key. The key must be entered again,
and the new endpoint must report the existing factory ID. Another panel at the
old IP is never adopted automatically. Authentication failure triggers HA's
reauthentication flow; updating a key retains the paired ID and address.
Unavailable/incompatible responses mark metadata entities unavailable. A reboot
with a new session nonce is allowed when the stable ID remains unchanged.

The coordinator lives in the config entry's `runtime_data`. Options reload and
unload remove listeners/timers and cancel explicit read/check requests through
HA's lifecycle. The HTTP session is
provided by HA and is never closed by this integration. Removing the companion
does not remove the separate ESPHome integration or change panel files.

## Security And Remaining Work

The setup key is masked, never prefilled into returned forms, and omitted from
entity states/attributes and downloadable diagnostics. Diagnostics use an
allowlist, not a dump of config-entry data or client objects: origin, hardware
ID and boot nonce are also excluded. HA stores credentials in its backend
configuration; protect HA storage and backups. This does not imply encrypted
at-rest storage or a new configuration-only credential.

The current API shares the powerful debug key. Plain HTTP is appropriate only
on a trusted LAN/VPN, must not be internet-exposed, and does not gain transport
encryption from ESPHome Native API encryption. The MAC-based ID guards pairing
mistakes but is not cryptographic device attestation. TLS verification is not
disabled and HTTP redirects are not followed.

Four administrator-only HA WebSocket commands now provide panel listing,
explicit status refresh, exact active/candidate/backup JSON import with device
validation, and validate-only. See [the API and recovery contract](HA_READ_CHECK_API.md).
The administrator-only frontend displays imports, validate-only results and
room/action drafts. Three additional administrator-only commands save/load/delete
one HA checkpoint per panel, independently of device connectivity; they are not
device writes. A separate [model-check command](HA_MODEL_VALIDATION.md) uses the
same pure Python models as the host generators, including profiles, references
and no-scroll geometry, without device I/O or template files. HA and ESP32
reports remain independent. There is no device uploader, service or actuator control.
Never expose keys/native boot nonces to browser storage or perform
browser-to-panel HTTP. Managed writes remain separate roadmap gates.

## Tests

Use a **separate** Python >=3.14.2 environment; do not install HA into the
ESPHome virtualenv:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
make core-install CORE_WHEEL=/path/to/home_panel_core-0.1.0-py3-none-any.whl
make test CORE_WHEEL=/path/to/home_panel_core-0.1.0-py3-none-any.whl
```

The official HA plugin supplies the real config-entry manager, registries,
entities, options/reauth/reconfigure flows and cleanup checks. Most tests
replace only wire I/O; the HTTP test uses an actual loopback aiohttp server
and the HA-owned session. All fixture credentials/identities are synthetic.
The socket guard remains enabled except for loopback HTTP/WebSocket tests. `pytest.ini`
disables early automatic `respx` loading so HA 2026.11 can initialize its
official `httpx2` alias first; no installed HA sources or cleanup guards are
modified. Checkpoint tests selectively bypass the official storage fixture's
I/O mock only for our owned namespace, exercising actual HA Store on temporary disk.
The matching official frontend package is pinned separately in the test
requirements. Browser acceptance additionally needs Node, distro `playwright`
and `/usr/bin/chromium`; it is explicitly skipped without Node/Chromium.

Client-only checks now belong to `home-panel-core/tests`; native C++/LVGL
acceptance stays in the firmware repository. Both consumers install the pinned
wheel. HA release bundles include it automatically, without `PYTHONPATH`
modifications or neighboring source repositories.

Initial setup-slice acceptance on 2026-11-07: **29 HA tests pass** on real HA 2026.11.0/Python
3.14.10, including English/Russian entity names, packaged catalogs, setup,
replacement rejection, reauth/reconfigure, missing SD/busy metadata, stale
sessions, 429/503 handling, options reload/unload and actual loopback HTTP.
The eight HA adapter modules have 100% statement coverage in this run; this is
not whole-project/branch coverage or physical acceptance. Separately, **31
client/native C++ tests and six client HTTP tests pass** after relocating the
library, for 66 passing targeted checks in this slice. The five reported
deprecations originate in HA's HTTP application and its `backoff` dependency.

The later backend slice adds actual authenticated WS/HTTP transactions, two
admin sessions, refusal of overlapping jobs, explicit recovery after lost
receipts, source/boot/digest guards and unload cancellation. Native C++ tests
also check unchanged file contents/mtime, expired downloads and validation
without SD. Its detailed boundary/remaining gates are recorded in the
[backend verification notes](HA_READ_CHECK_API.md#verification-notes).
Its combined acceptance is 70 HA tests plus 37 standalone/native and six HTTP
tests, for 113 targeted passes. This supersedes the initial setup-only count,
without claiming that physical pairing or the frontend editor is complete.

The frontend slice adds real HA panel registration/static HTTP/admin-sidebar
tests and Chromium component acceptance through actual authenticated HA
WebSocket commands. It covers 24 captures across EN/RU, light/dark and
320/390/1280px, exact downloads, input limits, disconnect/recovery and privilege
changes. See [frontend verification](HA_FRONTEND.md#verification) for the boundary
between component acceptance and the still-pending full installed-HA shell.
The combined frontend/backend/client run now passes 74 HA, 37 standalone/native
C++ and six standalone HTTP tests (117 targeted checks total).

These slices perform no firmware compilation, OTA, real HA/panel connection,
household command or physical SD write. HA dependency deprecation warnings are
reported separately from integration failures. Physical pairing, memory,
long-duration behavior and full installed-HA-shell acceptance remain open.

References: official [config flows](https://contributors.home-assistant.io/core/integrations/config-flow/),
[reauthentication/reconfiguration](https://contributors.home-assistant.io/core/integrations/reauth-reconfigure/),
[runtime data](https://contributors.home-assistant.io/core/quality-scale/runtime-data/)
and [test environment](https://contributors.home-assistant.io/core/development/testing/).
