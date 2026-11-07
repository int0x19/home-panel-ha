"""Chromium component acceptance against real HA auth/WS, fake device only."""

import asyncio
import os
from pathlib import Path
import shutil

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.http import StaticPathConfig
from homeassistant.setup import async_setup_component

from custom_components.home_panel.const import CONF_ACCESS_KEY, CONF_URL, DOMAIN
from support import DEVICE_ID, TOKEN, metadata

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(not shutil.which("node") or not Path("/usr/bin/chromium").exists(),
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
             "HA_BROWSER_UNLOADED": unloaded.entry_id, "PLANT_SETTINGS_DISTRO_PLAYWRIGHT": "1"},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), 150)
        assert process.returncode == 0, stdout.decode()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        await hass.async_block_till_done()
    assert {path for method, path, *_ in panel.calls if method == "POST"} == {
        "/panel/runtime/api/export", "/panel/runtime/api/validate"}
    assert (output / "download.json").read_bytes() == panel.documents["active"]
