# HA Apply And Activation Status

Development 0.1.2 adds explicit **Apply and restart** to the existing HA page,
separate from Check, Send and HA checkpoint Save. It reuses HA administrator
authorization, the backend-only panel key, shared core and the existing device
Apply/export API. No ESP32 source, endpoint, journal, UI buffer or timer is added.

## Workflow

1. Send a checked draft, or explicitly import the saved candidate. If firmware
   advertises healthy writable flash and enabled stable boot trials, the backend
   retains a verified snapshot and returns a random one-use `apply_id` to that
   browser. Merely reading status, restoring an HA checkpoint, loading a local
   file or checking an unsent draft does not authorize Apply.
2. The metadata area shows the saved candidate revision/SHA, with **Apply and
   restart**. Confirmation names that candidate and explains that unsaved local
   draft fields are not being deployed. Cancel performs no device request.
3. `home_panel/config/apply` accepts only `entry_id` and the 32-character
   `apply_id`, under HA administrator authorization. The backend consumes that
   marker before awaiting core Apply, but retains its pre-Apply snapshot. Core
   performs candidate readback/model validation and exact original-base checks
   before one Apply. An acknowledgement means **Restart scheduled**, not success.
4. Use **Refresh status** to inspect the current outcome. With a retained Apply
   intent, this makes one bounded core activation inspection; it may export the
   active JSON to verify confirmation. Otherwise normal status remains GET-only.
   Background HA polling stays GET-only and does not inspect/replay Apply.

The page distinguishes ready, restart scheduled, waiting for screen confirmation,
confirmed, rolled back, unchanged, unverified and unknown. Only core's verified
trial confirmation plus exact active SHA produces a green confirmed state. Local
firmware health/first-frame confirmation does not certify physical touch, online
HA, complete assets or household commands. Managed/deployment/dispatch flags
remain unchanged. See core `docs/CANDIDATE_APPLY.md` for phase limitations.

## Conflicts And Lifetime

- One per-entry operation gate serializes Import/Check/Send/Apply/inspection and
  unload. A second browser or poll cannot queue another write during a job.
- A newer candidate import replaces the approval marker. Importing another source
  revokes an unused approval. Stale tabs or changed snapshots conflict before
  writing; no frontend-supplied session/generation/base/SHA can override them.
- A lost reply, failed check or cancellation consumes approval, never revives it.
  The original intent survives for explicit inspection; refreshing cannot submit
  another Apply. Explicitly reimport/review a healthy still-saved candidate to
  prepare a new user-approved attempt, never automatic retries.
- Only one current intent and last observed snapshot are retained, not JSON/history.
  Cached status is displayed only with the exact snapshot that verified it; new
  state/network failure loses green confirmation until it is verified again.
- Unload/reconfigure/HA restart forget approval and intent. An old browser marker
  is invalid and startup does not Apply. After a lost HA session no previous
  success is inferred merely from matching device file/revision metadata.
- The browser forgets its marker on HA disconnect. Status inspection can still
  report the backend-retained outcome after reconnect, but cannot restore write
  permission. An error/offline state never remains green.

`apply_id` is a transaction marker, not an access credential. It is returned only
by Send/candidate Import; ordinary status contains an allowlisted `activation`
summary with state/revision/SHA/bytes, never marker, key, address or boot nonce.
Apply responds with `apply_accepted: true`, metadata and activation state. It does
not return a premature `applied: true`.

Unpaired discovery remains read/check-only. Paired clients explicitly opt into
Upload and Apply independently; restore/Discard/scan, authority and actuator
routes are still excluded. The shared core pin remains
`ac24832776852116018ad47cdf120685c9d37567`; no dependency upgrade is involved.

## Acceptance And Next Step

All 254 tests pass on HA 2026.11, with no skips, including actual WebSocket,
loopback HTTP, Chromium and deterministic manual/Marketplace bundle checks.
All 79 installed-core tests pass separately. Five existing upstream deprecation
warnings remain. Screenshots are under ignored `build/ha-apply`. This stage does
not rerun the firmware/native suite: no MCU or shared package code changed.
Core stays at its tested functional pin; source/archives remain unpublished
development 0.1.2, not an installed-HA or physical panel update.

Tests use actual HA 2026.11 WS/HTTP and Chromium with a synthetic flash peer,
not a live panel. They cover admin/field allowlists, stale tabs/base changes,
disabled trials, confirmed/rollback/unknown states, lost replies, cached-result
freshness, polling, unload during Apply and confirmation export, and reload with
no replay. Browser cases cover confirmation/cancel, separation from Send,
success/lost reply/rollback, disconnect and EN/RU light/dark at 320/1280px.

Next add guarded Discard/recovery to this same small flow, then separately
authorize installed-HA/ESP32 acceptance. Host tests and local archives do not
publish a release, update the user's HA or perform an OTA/household action.
