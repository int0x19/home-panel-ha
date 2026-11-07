"""Shared clock source selection for panel headers."""

from copy import deepcopy
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .panel_model import component_list

HEADER_ICONS = {"wifi": "wifi", "ha": "home-assistant", "mqtt": "mqtt"}


def header_timezone(panel_config):
    timezone = (panel_config.get("panel") or {}).get("timezone", "UTC")
    if not isinstance(timezone, str) or not timezone:
        raise ValueError("panel.timezone must be an IANA timezone name")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError(f"Unknown panel.timezone: {timezone}") from error
    return timezone


def header_clock(panel_config, device):
    timezone = header_timezone(panel_config)
    sources = deepcopy(component_list(device.get("time", []), "time"))
    if not sources and ("api" in device or "wifi" in device or "ethernet" in device):
        sources = [{"platform": "homeassistant" if "api" in device else "sntp"}]
    if not sources:
        return [], None, timezone
    sources[0].setdefault("id", "panel_clock")
    sources[0].setdefault("timezone", timezone)
    selected_timezone = sources[0]["timezone"]
    if not isinstance(selected_timezone, str) or not selected_timezone:
        raise ValueError("The header clock's timezone must be a nonempty string")
    return sources, sources[0]["id"], selected_timezone
