"""Allowlisted diagnostic output: no credentials, origin, hardware ID or boot nonce."""

from homeassistant.core import HomeAssistant

from .coordinator import PanelConfigEntry
from .panel_config import Source


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: PanelConfigEntry) -> dict:
    coordinator = entry.runtime_data
    snapshot = coordinator.data
    status, caps = snapshot.status, snapshot.capabilities
    return {
        "last_update_success": coordinator.last_update_success,
        "runtime_scope": "action_preview_only",
        "loaded_source": status.loaded_source,
        "loaded_revision": status.loaded_revision,
        "sd_ready": status.sd_ready,
        "busy": status.busy,
        "restarting": status.restarting,
        "authority": caps.authority,
        "management_ready": caps.management_ready,
        "deployment_ready": caps.deployment_ready,
        "limits": dict(caps.limits),
        "limits_measured_on_device": caps.limits_measured_on_device,
        "assets_inventory_complete": caps.assets_inventory_complete,
        "schema_versions": list(caps.schema_versions),
        "widget_types": list(caps.widget_types),
        "files": {source.value: {
            "present": info.present, "valid": info.valid, "bytes": info.bytes,
            "revision": info.revision, "status": info.status, "model_status": info.model_status,
        } for source in Source for info in (status.file(source),)},
    }
