"""Real HA administrative Apply and explicit inspection, synthetic flash only."""

import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil

import pytest

from activation_panel import ActivationPanel
from custom_components.home_panel._core import TransportError
from custom_components.home_panel.websocket_api import PREFIX
from support import DEVICE_ID, TOKEN
from test_candidate_send import prepare
from test_websocket_api import command, connect_ws, entry, ws


@pytest.fixture
def panel():
    return ActivationPanel()


async def stage(ws, entry):
    token, document = await prepare(ws, entry)
    result = await command(ws, entry, "send", import_id=token, document=document)
    assert result["success"]
    return result["result"]


def applies(panel):
    return [call for call in panel.calls if call[:2] == ("POST", "/panel/runtime/api/apply")]


async def test_explicit_apply_receipt_trial_and_confirmed_are_distinct(ws, entry, panel):
    sent = await stage(ws, entry)
    assert sent["activation"]["state"] == "ready" and len(sent["apply_id"]) == 32
    assert not applies(panel)
    status = (await command(ws, entry, "status"))["result"]
    assert "apply_id" not in status
    assert status["activation"]["state"] == "ready"
    result = await command(ws, entry, "apply", apply_id=sent["apply_id"])
    assert result["success"] and result["result"]["apply_accepted"]
    assert result["result"]["activation"]["state"] == "restarting"
    assert not result["result"]["deployment_ready"]
    assert entry.runtime_data.read_backend.apply_id is None
    panel.reboot()
    status = (await command(ws, entry, "status"))["result"]
    assert status["activation"]["state"] == "confirming"
    panel.confirm()
    status = (await command(ws, entry, "status"))["result"]
    assert status["activation"]["state"] == "confirmed"
    assert status["status"]["files"]["active"]["sha256"] == sent["candidate"]["sha256"]
    before = len(panel.calls)
    result = await command(ws, entry, "apply", apply_id=sent["apply_id"])
    assert result["error"]["code"] == "candidate_conflict" and len(panel.calls) == before
    assert len(applies(panel)) == 1
    for secret in (TOKEN, DEVICE_ID, panel.state["session_id"], panel.state["write_base_sha256"], "http://panel.test"):
        assert secret not in json.dumps(status)


async def test_lost_apply_reply_retains_intent_but_never_permission(ws, entry, panel):
    sent = await stage(ws, entry)
    def lose(method, suffix, result):
        if suffix == "apply": raise TransportError("PRIVATE " + TOKEN)
        return result
    panel.change = lose
    result = await command(ws, entry, "apply", apply_id=sent["apply_id"])
    assert result["error"]["code"] == "outcome_unknown" and TOKEN not in json.dumps(result)
    assert entry.runtime_data.read_backend.requires_status_refresh
    assert entry.runtime_data.read_backend.apply_id is None
    assert len(applies(panel)) == 1
    panel.change = lambda method, suffix, result: result
    panel.reboot(); panel.confirm()
    result = await command(ws, entry, "status")
    assert result["success"] and result["result"]["activation"]["state"] == "confirmed"
    assert not entry.runtime_data.read_backend.requires_status_refresh
    result = await command(ws, entry, "apply", apply_id=sent["apply_id"])
    assert result["error"]["code"] == "candidate_conflict" and len(applies(panel)) == 1


async def test_rollback_never_reports_confirmed(ws, entry, panel):
    sent = await stage(ws, entry)
    assert (await command(ws, entry, "apply", apply_id=sent["apply_id"]))["success"]
    panel.reboot(); panel.rollback()
    result = await command(ws, entry, "status")
    assert result["success"] and result["result"]["activation"]["state"] == "rolled_back"
    assert len(applies(panel)) == 1


async def test_failed_inspection_removes_cached_confirmation_until_new_verification(ws, entry, panel):
    sent = await stage(ws, entry)
    assert (await command(ws, entry, "apply", apply_id=sent["apply_id"]))["success"]
    panel.reboot(); panel.confirm()
    assert (await command(ws, entry, "status"))["result"]["activation"]["state"] == "confirmed"
    def lost(method, suffix, result):
        if suffix == "status": raise TransportError("PRIVATE " + TOKEN)
        return result
    panel.change = lost
    result = await command(ws, entry, "status")
    assert result["error"]["code"] == "cannot_connect" and TOKEN not in json.dumps(result)
    assert entry.runtime_data.read_backend._activation.state == "unknown"
    panel.change = lambda method, suffix, result: result
    assert (await command(ws, entry, "status"))["result"]["activation"]["state"] == "confirmed"
    assert len(applies(panel)) == 1


async def test_new_import_invalidates_another_tabs_approval(ws, entry, panel, connect_ws):
    sent = await stage(ws, entry)
    other = await connect_ws()
    imported = await command(other, entry, "import", source="candidate")
    assert imported["success"] and imported["result"]["apply_id"] != sent["apply_id"]
    before = len(panel.calls)
    result = await command(ws, entry, "apply", apply_id=sent["apply_id"])
    assert result["error"]["code"] == "candidate_conflict" and len(panel.calls) == before
    assert (await command(other, entry, "apply", apply_id=imported["result"]["apply_id"]))["success"]
    assert len(applies(panel)) == 1


@pytest.mark.parametrize("change", [{"write_base_sha256":"a" * 64}, {"storage_generation":"10"}])
async def test_changed_base_is_not_rebound(ws, entry, panel, change):
    sent = await stage(ws, entry)
    panel.state.update(change)
    result = await command(ws, entry, "apply", apply_id=sent["apply_id"])
    assert result["error"]["code"] == "candidate_conflict"
    assert entry.runtime_data.read_backend.apply_id is None and not applies(panel)


async def test_disabled_trials_keep_send_but_cannot_prepare_apply(ws, entry, panel):
    panel.state["apply_enabled"] = False
    sent = await stage(ws, entry)
    assert sent["apply_id"] is None and sent["activation"] is None
    result = await command(ws, entry, "apply", apply_id="a" * 32)
    assert result["error"]["code"] == "candidate_conflict" and not applies(panel)


@pytest.mark.parametrize("extra", [{"document":"{}"}, {"sha256":"a" * 64}, {"revision":1}, {"url":"http://other.test"}])
async def test_apply_fields_are_allowlisted(ws, entry, panel, extra):
    sent = await stage(ws, entry)
    before = len(panel.calls)
    result = await command(ws, entry, "apply", apply_id=sent["apply_id"], **extra)
    assert result["error"]["code"] == "invalid_format" and len(panel.calls) == before


async def test_background_poll_does_not_inspect_or_replay_activation(hass, ws, entry, panel):
    sent = await stage(ws, entry)
    assert (await command(ws, entry, "apply", apply_id=sent["apply_id"]))["success"]
    panel.reboot(); panel.confirm()
    before = len(panel.calls)
    await entry.runtime_data.async_refresh()
    assert all(method == "GET" for method, *_ in panel.calls[before:])
    assert (await command(ws, entry, "status"))["result"]["activation"]["state"] == "confirmed"
    # A later unrelated change cannot reuse the previous green result in an import response.
    panel.state["write_base_sha256"] = "a" * 64
    result = await command(ws, entry, "import", source="active")
    assert result["success"] and result["result"]["activation"]["state"] == "unknown"
    assert len(applies(panel)) == 1


async def test_unload_during_apply_cancels_and_forgets_intent(hass, ws, entry, panel, connect_ws):
    sent = await stage(ws, entry)
    started = asyncio.Event()
    request = panel.request
    async def hold(method, path, **fields):
        result = await request(method, path, **fields)
        if path.endswith("/apply"):
            started.set(); await asyncio.Event().wait()
        return result
    panel.request = hold
    await ws.send_json_auto_id({"type":PREFIX + "apply", "entry_id":entry.entry_id, "apply_id":sent["apply_id"]})
    await asyncio.wait_for(started.wait(), 2)
    backend = entry.runtime_data.read_backend
    other = await connect_ws()
    before = len(panel.calls)
    assert (await command(other, entry, "status"))["error"]["code"] == "panel_busy"
    await entry.runtime_data.async_refresh()
    assert len(panel.calls) == before
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert (await ws.receive_json())["error"]["code"] == "panel_unavailable"
    assert backend.closed and not backend.busy and backend._activation is None
    assert len(applies(panel)) == 1


async def test_unload_during_confirmation_export_cannot_resurrect_intent(hass, ws, entry, panel):
    sent = await stage(ws, entry)
    assert (await command(ws, entry, "apply", apply_id=sent["apply_id"]))["success"]
    panel.reboot(); panel.confirm()
    started = asyncio.Event()
    request = panel.request
    async def hold(method, path, **fields):
        if "/downloads/" in path:
            started.set(); await asyncio.Event().wait()
        return await request(method, path, **fields)
    panel.request = hold
    await ws.send_json_auto_id({"type":PREFIX + "status", "entry_id":entry.entry_id})
    await asyncio.wait_for(started.wait(), 2)
    backend = entry.runtime_data.read_backend
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert (await ws.receive_json())["error"]["code"] == "panel_unavailable"
    assert backend.closed and not backend.busy and backend._activation is None
    assert len(applies(panel)) == 1


async def test_reload_loses_permission_and_never_replays_apply(hass, ws, entry, panel):
    sent = await stage(ws, entry)
    assert (await command(ws, entry, "apply", apply_id=sent["apply_id"]))["success"]
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await command(ws, entry, "status")
    assert result["success"] and result["result"]["activation"] is None
    before = len(panel.calls)
    result = await command(ws, entry, "apply", apply_id=sent["apply_id"])
    assert result["error"]["code"] == "candidate_conflict" and len(panel.calls) == before
    assert len(applies(panel)) == 1


async def test_real_ha_http_apply_and_inspection(hass, panel, monkeypatch, aiohttp_server, socket_enabled, hass_ws_client):
    from aiohttp import web
    from pytest_homeassistant.common import MockConfigEntry
    from custom_components.home_panel import coordinator
    from custom_components.home_panel._core import AiohttpTransport
    from custom_components.home_panel.const import CONF_ACCESS_KEY, CONF_URL, DOMAIN
    monkeypatch.setattr(coordinator, "AiohttpTransport", AiohttpTransport)
    async def handler(request):
        result = await panel.request(request.method, request.path, headers=request.headers,
                                     body=await request.read(), max_bytes=16384)
        return web.Response(status=result.status, body=result.body, headers=result.headers)
    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handler)
    server = await aiohttp_server(app)
    configured = MockConfigEntry(domain=DOMAIN, title="Panel", unique_id=DEVICE_ID,
        data={CONF_URL:str(server.make_url("/")).rstrip("/"), CONF_ACCESS_KEY:TOKEN})
    configured.add_to_hass(hass)
    assert await hass.config_entries.async_setup(configured.entry_id)
    socket = await hass_ws_client()
    try:
        sent = await stage(socket, configured)
        assert (await command(socket, configured, "apply", apply_id=sent["apply_id"]))["success"]
        panel.reboot(); panel.confirm()
        result = await command(socket, configured, "status")
        assert result["success"] and result["result"]["activation"]["state"] == "confirmed"
        assert len(applies(panel)) == 1
    finally:
        await socket.close()
        await hass.async_block_till_done()


@pytest.mark.skipif(not shutil.which("node") or (os.environ.get("HA_BROWSER_MANAGED_PLAYWRIGHT") != "1" and
                    not Path("/usr/bin/chromium").exists()), reason="Chromium/Node required")
@pytest.mark.parametrize("outcome", ["confirmed", "lost", "rollback"])
async def test_apply_in_chromium(hass, entry, panel, hass_client, hass_access_token, outcome):
    from homeassistant.components.http import StaticPathConfig
    from homeassistant.setup import async_setup_component
    from custom_components.home_panel.frontend import async_setup_panel
    root = Path(__file__).resolve().parents[2]
    panel.auto = "rollback" if outcome == "rollback" else "confirm"
    assert await async_setup_component(hass, "frontend", {})
    assert await async_setup_panel(hass)
    await hass.http.async_register_static_paths([
        StaticPathConfig("/home_panel_browser_fixture", str(root / "tests/fixtures/ha_frontend"), False)])
    client = await hass_client()
    process = await asyncio.create_subprocess_exec("node", str(root / "tests/ha_frontend_apply.cjs"), cwd=root,
        env={**os.environ, "HA_BROWSER_ORIGIN":str(client.make_url("/")).rstrip("/"),
             "HA_BROWSER_TOKEN":hass_access_token, "HA_BROWSER_ENTRY":entry.entry_id,
             "HA_APPLY_OUTCOME":outcome}, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), 120)
        assert process.returncode == 0, stdout.decode()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        await hass.async_block_till_done()
    assert len(applies(panel)) == 1 and not panel.state["dispatch_enabled"]
    assert {path for method, path, *_ in panel.calls if method == "POST"} == {
        "/panel/runtime/api/upload", "/panel/runtime/api/apply", "/panel/runtime/api/validate", "/panel/runtime/api/export"}
