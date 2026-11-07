"""Manual pairing and identity-preserving connection changes."""

from typing import Any

import probatio as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_ACCESS_KEY,
    CONF_POLL_INTERVAL,
    CONF_URL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)
from .coordinator import create_client
from .panel_config import IdentityMismatch, PanelError, PanelHTTPError, ProtocolError


class HomePanelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Require the stable hardware ID, not a mutable address or boot nonce."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._async_connection("user", user_input)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._async_connection("reconfigure", user_input, self._get_reconfigure_entry())

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._async_connection("reauth_confirm", user_input, self._get_reauth_entry())

    async def _async_connection(
        self, step_id: str, user_input: dict[str, Any] | None, entry: ConfigEntry | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_URL: entry.data[CONF_URL]} if step_id == "reauth_confirm" and entry else {}
            data.update(user_input)
            try:
                if entry is not None and entry.unique_id is None:
                    raise IdentityMismatch("Missing paired identity")
                client = create_client(self.hass, data, entry.unique_id if entry else None)
                snapshot = await client.snapshot()
            except (KeyError, ValueError):
                errors["base"] = "invalid_connection"
            except IdentityMismatch:
                errors["base"] = "wrong_device"
            except PanelHTTPError as err:
                errors["base"] = "invalid_auth" if err.status in (401, 403) else "cannot_connect"
            except ProtocolError:
                errors["base"] = "unsupported_firmware"
            except PanelError:
                errors["base"] = "cannot_connect"
            else:
                # Normalize only the trailing slash, never credentials or the paired ID.
                data[CONF_URL] = data[CONF_URL].rstrip("/")
                if entry is not None:
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates=data,
                        reason="reauth_successful" if step_id == "reauth_confirm" else "reconfigure_successful",
                    )
                await self.async_set_unique_id(snapshot.capabilities.device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Home Panel " + snapshot.capabilities.device_id[-6:], data=data
                )

        fields = {}
        if step_id != "reauth_confirm":
            default_url = entry.data[CONF_URL] if entry else vol.UNDEFINED
            if user_input and errors.get("base") != "invalid_connection":
                default_url = user_input[CONF_URL]
            fields[vol.Required(CONF_URL, default=default_url)] = selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
            )
        # Never prefill or return the stored/submitted key when validation fails.
        fields[vol.Required(CONF_ACCESS_KEY)] = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        )
        return self.async_show_form(step_id=step_id, data_schema=vol.Schema(fields), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HomePanelOptionsFlow()


class HomePanelOptionsFlow(OptionsFlow):
    """Only polling cadence is an integration option; connection data uses reconfigure."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required(CONF_POLL_INTERVAL, default=self.config_entry.options.get(
                CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
            )): vol.All(vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL)),
        }))
