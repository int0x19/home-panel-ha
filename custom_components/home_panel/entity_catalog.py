"""Bounded, read-only action/sensor catalog from public registry/state APIs."""

import re

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, entity_registry as er

ACTION_DOMAINS = ("script", "scene", "button", "input_button")
CATALOG_DOMAINS = {"action": ACTION_DOMAINS, "sensor": ("sensor",)}
MAX_AREAS = 256


@callback
def async_catalog(hass: HomeAssistant, *, scope: str = "action", domain: str = "", area_id: str | None = "",
                  query: str = "", include_inactive: bool = False, offset: int = 0,
                  limit: int = 25) -> dict:
    """Return only display metadata, never arbitrary state attributes or services.

    Empty area means all areas; None means no effective area. Each explicit
    request is a fresh snapshot, not a subscription or stable pagination cursor.
    """
    registry = er.async_get(hass)
    domains = (domain,) if domain else CATALOG_DOMAINS[scope]
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
        if scope == "sensor":
            defaults = {}
            attributes = state.attributes if state else {}
            unit, device_class = attributes.get("unit_of_measurement"), attributes.get("device_class")
            if (isinstance(unit, str) and len(unit) <= 32 and
                    not any(ord(c) < 32 or 127 <= ord(c) <= 159 or 0xD800 <= ord(c) <= 0xDFFF for c in unit)):
                defaults["unit"] = unit
            if isinstance(device_class, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", device_class):
                defaults["device_class"] = device_class
            rows[-1]["defaults"] = defaults
    area_list = sorted(areas.async_list_areas(), key=lambda area: area.id)
    return {"version": 1, "scope": scope + "_entities", "domains": list(CATALOG_DOMAINS[scope]),
            "areas": [{"id": area.id, "name": area.name[:256]} for area in area_list[:MAX_AREAS]],
            "areas_truncated": len(area_list) > MAX_AREAS,
            "items": rows, "total": total, "offset": offset,
            "next_offset": offset + limit if offset + limit < total else None}
