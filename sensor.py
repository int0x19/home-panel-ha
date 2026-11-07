"""Read-only metadata entities, not imported household device controls."""

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PanelConfigEntry, PanelCoordinator
from .entity import PanelEntity

DESCRIPTIONS = (
    SensorEntityDescription(key="loaded_revision", translation_key="loaded_revision", icon="mdi:counter"),
    SensorEntityDescription(key="loaded_source", translation_key="loaded_source", icon="mdi:file-document"),
    SensorEntityDescription(key="max_bytes", translation_key="max_bytes", native_unit_of_measurement="B", icon="mdi:file-code"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PanelConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(PanelSensor(entry.runtime_data, description) for description in DESCRIPTIONS)


class PanelSensor(PanelEntity, SensorEntity):
    def __init__(self, coordinator: PanelCoordinator, description: SensorEntityDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int | str:
        return getattr(self.coordinator.data.status, self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict | None:
        if self.entity_description.key != "loaded_source":
            return None
        caps = self.coordinator.data.capabilities
        return {
            "runtime_scope": "action_preview_only",
            "configuration_authority": caps.authority,
            "managed_deployment": caps.deployment_ready,
            "limits_measured_on_device": caps.limits_measured_on_device,
            "assets_inventory_complete": caps.assets_inventory_complete,
            "supported_widget_types": list(caps.widget_types),
        }
