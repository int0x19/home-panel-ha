# Action Entity Catalog

The structured action form has a registry-backed entity picker. It uses public
HA 2026.11 APIs and the existing authenticated connection; ESP32 does not gain a
token, registry client or web editor. This is an action-family pilot, not an
importer for lights, climate, sockets, sensors or Plant.

## Selection

- Open the magnifier next to Entity. Search by name or `entity_id`, optionally
  filtering by `script`, `scene`, `button`, `input_button` and HA area.
- Entity area overrides the device's effective area, including inherited child
  device areas as resolved by HA. State-only entities without registry entries
  remain selectable under No area. Areas never create or rearrange panel rooms.
- Hidden and disabled registry entries are excluded unless explicitly requested.
  Unavailable, unknown and missing states remain visible with separate labels.
  HA's computed registry name takes precedence over a stale state's name.
- Choosing sets only the open form's entity field. An empty label is initialized
  from HA; an existing custom label is preserved. Update draft still performs
  the shared atomic model edit. Cancel/Escape never changes the document.
- Renames and disappearing entities never rewrite existing draft bindings.
  Manual entry remains available; validity/capability checks still apply.

## Boundary

Administrator-only WS command `home_panel/config/entities` accepts `entry_id`,
optional `domain`, `query` (at most 128 characters), `area_id`,
`include_inactive`, `offset` and `limit` (1..50, default 25). Empty area string
means all; null means no effective area. Unknown fields/domains are rejected.
The paired entry must exist, but need not be loaded or reachable.

Each explicit request returns a fresh sorted snapshot: bounded display names,
entity/domain/area identifiers, availability and disabled/hidden flags. It does
not return arbitrary attributes, state values, device IDs, services, credentials
or device metadata. Only the requested page allocates display rows. At most 256
areas are listed; a truncation warning directs users to search across all areas.
Pagination is not a retained snapshot/cursor; concurrent registry changes may
shift later pages. Reopening/searching reads current HA metadata without polling.

The parent serializes requests and guards connection/user/entry epochs; the
picker independently guards request IDs and modal lifetime. A closed picker or
old connection cannot accept a late selection. Search failures preserve local
form fields, checkpoint revision and ESP32 validation freshness. Retry is always
explicit. No storage, device I/O, service dispatch, SD write or Apply is involved.

## Acceptance

Tests use actual HA 2026.11 registry/state and admin/non-admin WS boundaries.
Chromium covers filtering/paging, no results, inactive entries, label preservation,
cancelled late replies, failed search, keyboard cancellation and EN/RU light/dark
layouts at 320/390/1280px. This is component acceptance with real HA auth/WS,
not a claim of full installed-HA-shell or physical device acceptance.
