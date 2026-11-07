"""Optional HA-hosted administrative panel; no data or keys in static assets."""

import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from ._core import asset_path

PANEL_PATH = "home-panel-config"
STATIC_PATH = "/home_panel_static"
MODULE_URL = STATIC_PATH + "/home-panel.js?v=1"
_REGISTERED = "home_panel_frontend_registered"
_LOGGER = logging.getLogger(__name__)


async def async_setup_panel(hass: HomeAssistant) -> bool:
    """Keep the read/check backend usable on headless HA too."""
    if "frontend" not in hass.config.components:
        return False
    if hass.data.get(_REGISTERED):
        return True
    if frontend.async_panel_exists(hass, PANEL_PATH):
        _LOGGER.error("Home Panel frontend path is already in use; leaving the existing panel unchanged")
        return False
    await hass.http.async_register_static_paths([
        StaticPathConfig(STATIC_PATH + "/runtime-draft.mjs", str(asset_path("runtime-draft.mjs")), False),
        StaticPathConfig(STATIC_PATH, str(Path(__file__).parent / "www"), False),
    ])
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_PATH,
        webcomponent_name="home-panel-config",
        sidebar_title="Home Panel",
        sidebar_icon="mdi:view-dashboard-outline",
        module_url=MODULE_URL,
        require_admin=True,
        embed_iframe=False,
        trust_external=False,
        config_panel_domain="home_panel",
    )
    hass.data[_REGISTERED] = True
    return True
