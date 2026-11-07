"""One serialized client and a bounded read-only snapshot per config entry."""

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ACCESS_KEY, CONF_POLL_INTERVAL, CONF_URL, DEFAULT_POLL_INTERVAL
from .panel_config import (
    IdentityMismatch,
    PanelConfigClient,
    PanelError,
    PanelHTTPError,
    ProtocolError,
    RuntimeSnapshot,
)
from .panel_config.aiohttp_transport import AiohttpTransport
from .panel_config.read_backend import PanelReadBackend

_LOGGER = logging.getLogger(__name__)


def create_client(
    hass: HomeAssistant, data: Mapping[str, Any], expected_device_id: str | None = None
) -> PanelConfigClient:
    """Use HA's shared session without assuming its ownership."""
    return PanelConfigClient(
        AiohttpTransport(async_get_clientsession(hass), data[CONF_URL]),
        data[CONF_ACCESS_KEY],
        expected_device_id=expected_device_id,
    )


class PanelCoordinator(DataUpdateCoordinator[RuntimeSnapshot]):
    """Poll only metadata; never export, validate, upload or control a device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        if entry.unique_id is None:
            raise ConfigEntryError("Panel identity is missing; add the panel again")
        try:
            self.client = create_client(hass, entry.data, entry.unique_id)
        except (KeyError, ValueError):
            raise ConfigEntryError("Invalid panel connection configuration") from None
        self.read_backend = PanelReadBackend(self.client)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Home Panel configuration",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
            ),
            always_update=False,
        )

    async def _async_update_data(self) -> RuntimeSnapshot:
        # Explicit read/check transactions own the same client; do not queue polls
        # between their export/validation/boot guards or clear recovery flags.
        if self.read_backend.busy:
            if not self.last_update_success:
                raise UpdateFailed("Panel read/check transaction is in progress")
            return self.data
        try:
            return await self.client.snapshot()
        except PanelHTTPError as err:
            if err.status in (401, 403):
                raise ConfigEntryAuthFailed("Panel access key was rejected") from None
            raise UpdateFailed("Panel metadata request failed") from None
        except IdentityMismatch:
            raise UpdateFailed("Paired panel identity changed; check the configured address") from None
        except ProtocolError:
            raise UpdateFailed("Panel firmware metadata is missing or incompatible") from None
        except PanelError:
            raise UpdateFailed("Unable to read panel metadata") from None

    async def async_shutdown(self) -> None:
        await self.read_backend.async_close()
        await super().async_shutdown()


type PanelConfigEntry = ConfigEntry[PanelCoordinator]
