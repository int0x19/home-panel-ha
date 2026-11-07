"""Read-only storage and busy flags."""

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PanelConfigEntry, PanelCoordinator
from .entity import PanelEntity

DESCRIPTIONS = (
    BinarySensorEntityDescription(key="sd_ready", translation_key="sd_ready", icon="mdi:micro-sd"),
    BinarySensorEntityDescription(key="busy", translation_key="busy", icon="mdi:progress-clock"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PanelConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(PanelBinarySensor(entry.runtime_data, description) for description in DESCRIPTIONS)


class PanelBinarySensor(PanelEntity, BinarySensorEntity):
    def __init__(self, coordinator: PanelCoordinator, description: BinarySensorEntityDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return getattr(self.coordinator.data.status, self.entity_description.key)
