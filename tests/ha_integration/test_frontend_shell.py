"""Installed HA frontend acceptance, with real auth/router and fake device I/O."""

import asyncio
import os
from pathlib import Path
import shutil

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.onboarding.const import STEPS
from homeassistant.setup import async_setup_component

from custom_components.home_panel.const import CONF_ACCESS_KEY, CONF_URL, DOMAIN
from support import DEVICE_ID, TOKEN

ROOT = Path(__file__).resolve().parents[2]
MANAGED_BROWSER = os.environ.get("HA_BROWSER_MANAGED_PLAYWRIGHT") == "1"


@pytest.fixture
def mock_recorder_before_hass(async_test_recorder):
    """Install the official recorder fixture's mocks before HA is created."""


@pytest.mark.skipif(not shutil.which("node") or (not MANAGED_BROWSER and not Path("/usr/bin/chromium").exists()),
                    reason="Node, distro Playwright and Chromium required for browser acceptance")
async def test_installed_ha_shell_navigation(hass, hass_client, hass_access_token, panel, hass_storage, recorder_mock):
    hass_storage["onboarding"] = {"version": 4, "minor_version": 1,
                                  "key": "onboarding", "data": {"done": list(STEPS)}}
    assert await async_setup_component(hass, "frontend", {})
    for component in ("brands", "persistent_notification", "labs"):
        assert await async_setup_component(hass, component, {})
    entry = MockConfigEntry(domain=DOMAIN, title="Panel", unique_id=DEVICE_ID,
                            data={CONF_URL: "http://panel.test", CONF_ACCESS_KEY: TOKEN})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    client = await hass_client()
    process = await asyncio.create_subprocess_exec(
        "node", str(ROOT / "tests/ha_frontend_shell.cjs"), cwd=ROOT,
        env={**os.environ, "HA_BROWSER_ORIGIN": str(client.make_url("/")).rstrip("/"),
             "HA_BROWSER_TOKEN": hass_access_token, "HA_BROWSER_ENTRY": entry.entry_id,
             "PLANT_SETTINGS_DISTRO_PLAYWRIGHT": "0" if MANAGED_BROWSER else "1"},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), 120)
        assert process.returncode == 0, stdout.decode()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        await hass.async_block_till_done()
    assert {path for method, path, *_ in panel.calls if method == "POST"} == {
        "/panel/runtime/api/export", "/panel/runtime/api/validate"}
