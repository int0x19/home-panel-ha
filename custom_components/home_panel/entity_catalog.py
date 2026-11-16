"""Bounded, read-only action catalog from HA's public registry/state APIs."""

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, entity_registry as er

ACTION_DOMAINS = ("script", "scene", "button", "input_button")
MAX_AREAS = 256


@callback
def async_catalog(hass: HomeAssistant, *, domain: str = "", area_id: str | None = "",
                  query: str = "", include_inactive: bool = False, offset: int = 0,
                  limit: int = 25) -> dict:
    """Return only display metadata, never arbitrary state attributes or services.

    Empty area means all areas; None means no effective area. Each explicit
    request is a fresh snapshot, not a subscription or stable pagination cursor.
    """
    registry = er.async_get(hass)
    domains = (domain,) if domain else ACTION_DOMAINS
    states = {state.entity_id: state for state in hass.states.async_all(domains)}
    entries = {entry.entity_id: entry for entry in registry.entities.values()
               if entry.domain in domains}
    areas = ar.async_get(hass)
    needle = query.strip().casefold()
    rows = []
    total = 0
    for entity_id in sorted(entries.keys() | states.keys()):
        entry, state = entries.get(entity_id), states.get(entity_id)
        disabled = entry is not None and entry.disabled_by is not None
        hidden = entry is not None and entry.hidden_by is not None
        if (disabled or hidden) and not include_inactive:
            continue
        effective_area = er.async_get_effective_area_id(hass, entry) if entry else None
        if area_id != "" and effective_area != area_id:
            continue
        name = er.async_get_full_entity_name(hass, entry) if entry else ""
        if not name and state:
            name = state.attributes.get("friendly_name", "")
        name = name if isinstance(name, str) and name else entity_id
        if needle and needle not in entity_id.casefold() and needle not in name.casefold():
            continue
        total += 1
        if not offset < total <= offset + limit:
            continue
        area = areas.async_get_area(effective_area) if effective_area else None
        availability = ("missing" if state is None else "unavailable" if state.state == STATE_UNAVAILABLE
                        else "unknown" if state.state == STATE_UNKNOWN else "available")
        rows.append({"entity_id": entity_id, "name": name[:256],
                     "domain": entity_id.partition(".")[0], "area_id": effective_area,
                     "area_name": area.name[:256] if area else None,
                     "availability": availability, "disabled": disabled, "hidden": hidden})
    area_list = sorted(areas.async_list_areas(), key=lambda area: area.id)
    return {"version": 1, "scope": "action_entities", "domains": list(ACTION_DOMAINS),
            "areas": [{"id": area.id, "name": area.name[:256]} for area in area_list[:MAX_AREAS]],
            "areas_truncated": len(area_list) > MAX_AREAS,
            "items": rows, "total": total, "offset": offset,
            "next_offset": offset + limit if offset + limit < total else None}
