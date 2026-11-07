"""Actual HA frontend registry, HTTP assets and admin-only sidebar exposure."""

from importlib.metadata import version
from pathlib import Path

from custom_components.home_panel._core import asset_path

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components import frontend
from homeassistant.setup import async_setup_component

from custom_components.home_panel.const import CONF_ACCESS_KEY, CONF_URL, DOMAIN
from custom_components.home_panel.frontend import MODULE_URL, PANEL_PATH, STATIC_PATH, async_setup_panel
from support import DEVICE_ID, TOKEN


async def test_frontend_assets_and_sidebar_authorization(hass, hass_client, hass_ws_client, hass_read_only_access_token):
    assert version("home-assistant-frontend") == "20261028.4"
    assert await async_setup_component(hass, "frontend", {})
    entry = MockConfigEntry(domain=DOMAIN, title="Panel", unique_id=DEVICE_ID,
                            data={CONF_URL: "http://panel.test", CONF_ACCESS_KEY: TOKEN})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert frontend.async_panel_exists(hass, PANEL_PATH)
    assert await async_setup_panel(hass)  # Idempotent registration, no duplicate routes.
    admin = await hass_ws_client()
    user = await hass_ws_client(access_token=hass_read_only_access_token)
    try:
        for socket, visible in ((admin, True), (user, False)):
            await socket.send_json_auto_id({"type": "get_panels"})
            result = await socket.receive_json()
            assert result["success"]
            assert (PANEL_PATH in result["result"]) is visible
            if visible:
                panel = result["result"][PANEL_PATH]
                assert panel["require_admin"]
                assert panel["config"]["_panel_custom"]["module_url"] == MODULE_URL
                assert not panel["config"]["_panel_custom"]["embed_iframe"]
                assert TOKEN not in str(panel)
        client = await hass_client()
        for asset, content_type in (("home-panel.js", "javascript"), ("home-panel.css", "css"),
                                    ("draft-editor.js", "javascript"), ("runtime-draft.mjs", "javascript")):
            response = await client.get(STATIC_PATH + "/" + asset)
            assert response.status == 200
            assert content_type in response.content_type
            text = await response.text()
            source = Path(__file__).resolve().parents[2] / "custom_components/home_panel/www" / asset
            if asset == "runtime-draft.mjs":
                source = asset_path(asset)
            assert text == source.read_text()
            assert TOKEN not in text
        for path in (STATIC_PATH + "/../const.py", STATIC_PATH + "/secrets.yaml", STATIC_PATH + "/"):
            assert (await client.get(path)).status in (400, 403, 404)
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert frontend.async_panel_exists(hass, PANEL_PATH)
    finally:
        await admin.close()
        await user.close()
        await hass.async_block_till_done()


async def test_headless_ha_keeps_backend_without_frontend(hass):
    assert "frontend" not in hass.config.components
    assert not await async_setup_panel(hass)
    assert not frontend.async_panel_exists(hass, PANEL_PATH)


async def test_existing_panel_is_not_overwritten(hass, hass_client, caplog):
    assert await async_setup_component(hass, "frontend", {})
    frontend.async_register_built_in_panel(hass, "custom", frontend_url_path=PANEL_PATH,
                                         config={"owner": "other-integration"})
    assert not await async_setup_panel(hass)
    assert "already in use" in caplog.text
