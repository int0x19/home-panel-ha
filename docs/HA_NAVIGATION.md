# Unsaved Navigation Protection

The HA editor protects unsaved model changes, uncommitted form fields and the
independent raw JSON check input. Explicit **Save in HA** clears the model's
unsaved flag, but does not save unfinished fields or raw input. Model checking,
comparison, export and opening history are not checkpoint saves.

## Behavior

- In browsers with the Navigation API, a cancelable same-document departure
  requests confirmation before HA changes its route. Cancel keeps the URL,
  history cursor/state and local fields; confirm lets the original navigation
  proceed. No navigation is replayed and no history entry is injected.
- Sidebar links, integration settings, programmatic push/replace and browser
  Back/Forward use that same live dirty check. Same-path query/hash changes,
  HA dialog history and editor tabs keep the editor mounted and do not prompt.
- Full-document departures and reload use the browser's `beforeunload` warning.
  Browser policy controls its wording/availability; forced process termination
  is not recoverable. There is no autosave or browser draft storage.
  Forced component teardown, including HA's background suspension, is not a
  cancelable navigation; only explicit checkpoints survive that teardown.
- Without the Navigation API, ordinary same-window same-origin links are
  guarded in capture phase, including links through HA shadow roots. Modified
  clicks, downloads and other targets are not blocked. A visible warning states
  that SPA Back/Forward and programmatic history cannot be protected there.
- All listeners belong to the mounted component and are removed on detach.
  A disconnected HA connection does not clear dirty state. Privilege/user loss
  retains the existing security behavior: clear local data and ignore late
  results instead of retaining another user's draft behind a prompt.

Confirmation is synchronous so HA retains ownership of the original operation.
No HA router/history functions are patched and no hashed frontend bundle or
private unsaved-guard registry is imported. HA's built-in editor mixin currently
registers through an internal module, not a documented custom-panel contract.

### Browser Limits

The browser can make a history traversal non-cancelable or suppress dialogs,
especially without user activation; the guard cannot override that policy.
Chromium 153 also ignores a repeated programmatic `history.forward()` to the
same entry after a canceled Forward in the measured sequence. The URL/current
entry and local fields are preserved, and other navigation/reload remains
available. A standalone reproduction with only Navigation/History APIs and no
HA, custom element or confirmation dialog has the same result. This remains a
browser-compatibility gate, not something hidden by monkey-patching history.

## Verification

`tests/ha_frontend_navigation.cjs` exercises real Chromium Navigation/History
APIs against the production component and authenticated HA backend, with only
device wire I/O synthetic. It checks cancellation, accepted navigation,
checkpoint-versus-field/raw dirtiness, reload, offline edits, listener cleanup
and the explicit unsupported-browser fallback.

`tests/ha_frontend_shell.cjs` loads the installed HA frontend, real authentication,
custom panel, icons, sidebar and router rather than the component property
adapter. Mobile/desktop screenshots are written under `build/ha-frontend`.
Standard brands, labs and persistent-notification components and the official
in-memory recorder fixture supply the shell's real backend APIs; unknown
commands or browser exceptions are not suppressed.
These checks do not certify companion-app webviews, all browser releases,
physical ESP32 pairing, device memory or runtime deployment.

The complete HA 2026.11 suite passes **196 tests** on 2026-11-07, including
source/release checks and both browser paths. The same five upstream dependency
deprecations remain; no HA source patches or exception/cleanup suppression were
added. The test harness retains its existing distro-Playwright cleanup adapter.

References:

- [Navigation API specification](https://html.spec.whatwg.org/multipage/nav-history-apis.html#the-navigation-api)
- [HA 20261028.4 navigation implementation](https://github.com/home-assistant/frontend/blob/20261028.4/src/common/navigate.ts)
- [HA 20261028.4 internal editor mixin](https://github.com/home-assistant/frontend/blob/20261028.4/src/mixins/prevent-unsaved-mixin.ts)
