"""Optional HA-hosted administrative panel; no data or keys in static assets."""

from hashlib import sha256
import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from ._core import asset_path

PANEL_PATH = "home-panel-config"
STATIC_PATH = "/home_panel_static"
_WWW = Path(__file__).parent / "www"
_REGISTERED = "home_panel_frontend_registered"
_LOGGER = logging.getLogger(__name__)


def _asset_routes() -> tuple[str, Path]:
    core = asset_path("runtime-draft.mjs")
    digest = sha256()
    for file in (_WWW / "home-panel.js", _WWW / "draft-editor.js", _WWW / "home-panel.css", core):
        digest.update(sha256(file.read_bytes()).digest())
    # Relative imports and styles must share the entry module's cache key.
    return f"{STATIC_PATH}/{digest.hexdigest()[:16]}", core


async def async_setup_panel(hass: HomeAssistant) -> bool:
    """Keep the read/check backend usable on headless HA too."""
    if "frontend" not in hass.config.components:
        return False
    if hass.data.get(_REGISTERED):
        return True
    if frontend.async_panel_exists(hass, PANEL_PATH):
        _LOGGER.error("Home Panel frontend path is already in use; leaving the existing panel unchanged")
        return False
    static_url, core = await hass.async_add_executor_job(_asset_routes)
    await hass.http.async_register_static_paths([
        StaticPathConfig(f"{static_url}/runtime-draft.mjs", str(core), False),
        StaticPathConfig(static_url, str(_WWW), False),
    ])
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_PATH,
        webcomponent_name="home-panel-config",
        sidebar_title="Home Panel",
        sidebar_icon="mdi:view-dashboard-outline",
        module_url=f"{static_url}/home-panel.js",
        require_admin=True,
        embed_iframe=False,
        trust_external=False,
        config_panel_domain="home_panel",
    )
    hass.data[_REGISTERED] = True
    return True
