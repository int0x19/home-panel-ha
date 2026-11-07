"""Common diagnostic device identity without ESPHome private integration APIs."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PanelCoordinator


class PanelEntity(CoordinatorEntity[PanelCoordinator]):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PanelCoordinator, key: str) -> None:
        super().__init__(coordinator)
        device_id = coordinator.data.capabilities.device_id
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=coordinator.config_entry.title,
            manufacturer="Home Panel",
            model="ESP32 LVGL panel",
        )
