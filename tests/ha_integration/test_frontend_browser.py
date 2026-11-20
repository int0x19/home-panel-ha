"""Chromium component acceptance against real HA auth/WS, fake device only."""

import asyncio
import os
from pathlib import Path
import shutil

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.home_panel.const import CONF_ACCESS_KEY, CONF_URL, DOMAIN
from support import DEVICE_ID, TOKEN, metadata

ROOT = Path(__file__).resolve().parents[2]
MANAGED_BROWSER = os.environ.get("HA_BROWSER_MANAGED_PLAYWRIGHT") == "1"


@pytest.mark.skipif(not shutil.which("node") or (not MANAGED_BROWSER and not Path("/usr/bin/chromium").exists()),
                    reason="Node, distro Playwright and Chromium required for browser acceptance")
async def test_admin_frontend_in_chromium(hass, hass_client, hass_access_token, panel):
    assert await async_setup_component(hass, "frontend", {})
    # Preserve non-canonical whitespace and CRLF in the export/download round trip.
    panel.documents["active"] = b" \r\n" + panel.documents["active"] + b"\r\n"
    panel.state["active"] = metadata(panel.documents["active"])
    entry = MockConfigEntry(domain=DOMAIN, title="Bedroom / Спальня", unique_id=DEVICE_ID,
                            data={CONF_URL: "http://panel.test", CONF_ACCESS_KEY: TOKEN})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    areas, entities = ar.async_get(hass), er.async_get(hass)
    bedroom, kitchen = areas.async_create("Спальня"), areas.async_create("Кухня")
    for domain, key, name, area, extra in (
        ("scene", "evening", "Вечер", bedroom, {}),
        ("script", "good_night", "Ночь", kitchen, {}),
        ("scene", "hidden", "Hidden", bedroom, {"hidden_by":er.RegistryEntryHider.USER}),
        ("button", "missing", "Missing", bedroom, {}),
    ):
        entity = entities.async_get_or_create(domain, DOMAIN, key, suggested_object_id=key,
                                              original_name=name, **extra)
        entities.async_update_entity(entity.entity_id, area_id=area.id)
        hass.states.async_set(entity.entity_id, "unavailable" if key == "missing" else "unknown")
    for index in range(30):
        hass.states.async_set(f"button.extra_{index:02}", "unknown", {"friendly_name":f"Extra {index}"})
    hass.states.async_set("sensor.bedroom_temperature", "25.1", {"friendly_name":"Bedroom temperature",
        "unit_of_measurement":"\u00b0C", "device_class":"temperature"})
    hass.states.async_set("sensor.bedroom_humidity", "unavailable", {"friendly_name":"Bedroom humidity",
        "unit_of_measurement":"%", "device_class":"humidity"})
    hass.states.async_set("binary_sensor.plug_problem", "on", {"friendly_name":"Plug fault", "device_class":"problem"})
    unloaded = MockConfigEntry(domain=DOMAIN, title='<img src=x onerror="window.injected=1">',
                               unique_id="unloaded-preview", data={})
    unloaded.add_to_hass(hass)
    await hass.http.async_register_static_paths([
        StaticPathConfig("/home_panel_browser_fixture", str(ROOT / "tests/fixtures/ha_frontend"), False)])
    client = await hass_client()
    output = ROOT / "build/ha-frontend"
    output.mkdir(parents=True, exist_ok=True)
    process = await asyncio.create_subprocess_exec(
        "node", str(ROOT / "tests/ha_frontend_web.cjs"), cwd=ROOT,
        env={**os.environ, "HA_BROWSER_ORIGIN": str(client.make_url("/")).rstrip("/"),
             "HA_BROWSER_TOKEN": hass_access_token, "HA_BROWSER_ENTRY": entry.entry_id,
             "HA_BROWSER_UNLOADED": unloaded.entry_id,
             "PLANT_SETTINGS_DISTRO_PLAYWRIGHT": "0" if MANAGED_BROWSER else "1"},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), 220)
        assert process.returncode == 0, stdout.decode()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        await hass.async_block_till_done()
    assert {path for method, path, *_ in panel.calls if method == "POST"} == {
        "/panel/runtime/api/export", "/panel/runtime/api/validate"}
    assert (output / "download.json").read_bytes() == panel.documents["active"]
