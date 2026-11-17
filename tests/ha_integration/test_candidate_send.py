"""HA administrator Send using the installed core and synthetic flash only."""

import asyncio
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
from unittest.mock import Mock

import pytest

from custom_components.home_panel._core import TransportError
from custom_components.home_panel.websocket_api import PREFIX, _run
from custom_components.home_panel import coordinator
from custom_components.home_panel._core import AiohttpTransport
from candidate_panel import CandidatePanel
from support import DEVICE_ID, TOKEN
from test_websocket_api import command, connect_ws, entry, ws


@pytest.fixture
def panel():
    return CandidatePanel()


async def prepare(ws, entry, source="active"):
    imported = await command(ws, entry, "import", source=source)
    assert imported["success"]
    imported = imported["result"]
    doc = json.loads(imported["document"])
    if source != "candidate":
        doc["revision"] = imported["status"]["high_water_revision"] + 1
        doc["rooms"][0]["name"] = "Детская"
    checked = await command(ws, entry, "validate", document=json.dumps(doc, indent=2), import_id=imported["import_id"])
    assert checked["success"]
    assert checked["result"]["validation"]["valid"]
    return imported["import_id"], checked["result"]["candidate_document"]


def uploads(panel):
    return [call for call in panel.calls if call[:2] == ("POST", "/panel/runtime/api/upload")]


async def test_send_exact_checked_bytes_without_apply_or_changing_loaded_ui(ws, entry, panel):
    original = deepcopy(panel.state)
    token, document = await prepare(ws, entry)
    result = await command(ws, entry, "send", import_id=token, document=document)
    assert result["success"]
    sent = result["result"]
    assert sent["candidate"] == {"revision": 32, "bytes": len(document.encode()),
        "sha256": hashlib.sha256(document.encode()).hexdigest(), "changed": True, "applied": False}
    assert panel.documents["candidate"] == document.encode() == uploads(panel)[0][3]
    for key in ("loaded_revision", "loaded_source", "active", "backup", "dispatch_enabled", "pending_trial", "restarting"):
        assert panel.state[key] == original[key]
    assert not sent["management_ready"] and not sent["deployment_ready"]
    assert entry.runtime_data.read_backend.import_id is None
    assert not entry.runtime_data.read_backend.busy
    for secret in (TOKEN, DEVICE_ID, panel.state["session_id"], original["write_base_sha256"], "http://panel.test"):
        assert secret not in json.dumps(sent)
    assert {path for method, path, *_ in panel.calls if method == "POST"} <= {
        "/panel/runtime/api/upload", "/panel/runtime/api/export", "/panel/runtime/api/validate"}
    before = len(panel.calls)
    again = await command(ws, entry, "send", import_id=token, document=document)
    assert again["error"]["code"] == "candidate_conflict" and len(panel.calls) == before


async def test_unchecked_or_changed_bytes_never_upload(ws, entry, panel):
    imported = (await command(ws, entry, "import", source="active"))["result"]
    for document in (imported["document"], "broken"):
        result = await command(ws, entry, "send", import_id=imported["import_id"], document=document)
        assert result["error"]["code"] == "candidate_conflict"
    token, document = await prepare(ws, entry)
    result = await command(ws, entry, "send", import_id=token, document=document + " ")
    assert result["error"]["code"] == "candidate_conflict"
    assert not uploads(panel)


async def test_second_tab_import_invalidates_previous_baseline(ws, entry, panel, connect_ws):
    token, document = await prepare(ws, entry)
    other = await connect_ws()
    new = await command(other, entry, "import", source="active")
    assert new["result"]["import_id"] != token
    before = len(panel.calls)
    result = await command(ws, entry, "send", import_id=token, document=document)
    assert result["error"]["code"] == "candidate_conflict"
    assert len(panel.calls) == before and not uploads(panel)


@pytest.mark.parametrize("phase", ["check", "send"])
async def test_changed_panel_base_cannot_be_rebound(ws, entry, panel, phase):
    token, document = await prepare(ws, entry)
    panel.state["write_base_sha256"] = "c" * 64
    operation = "validate" if phase == "check" else "send"
    result = await command(ws, entry, operation, import_id=token, document=document)
    assert result["error"]["code"] == "candidate_conflict"
    assert not uploads(panel)


async def test_lost_reply_requires_inspection_and_import_never_replay(ws, entry, panel):
    token, document = await prepare(ws, entry)
    def lose(method, suffix, result):
        if suffix == "upload":
            raise TransportError("PRIVATE " + TOKEN)
        return result
    panel.change = lose
    result = await command(ws, entry, "send", import_id=token, document=document)
    assert result["error"]["code"] == "outcome_unknown" and TOKEN not in json.dumps(result)
    assert entry.runtime_data.read_backend.requires_status_refresh
    assert entry.runtime_data.read_backend.import_id is None
    assert panel.documents["candidate"] == document.encode() and len(uploads(panel)) == 1
    for operation in ("send", "validate"):
        result = await command(ws, entry, operation, import_id=token, document=document)
        assert result["error"]["code"] == "status_refresh_required"
    panel.change = lambda method, suffix, result: result
    assert (await command(ws, entry, "status"))["success"]
    result = await command(ws, entry, "send", import_id=token, document=document)
    assert result["error"]["code"] == "candidate_conflict"
    # Explicitly import and verify the saved candidate without a second flash write.
    token, same = await prepare(ws, entry, "candidate")
    result = await command(ws, entry, "send", import_id=token, document=same)
    assert result["success"] and not result["result"]["candidate"]["changed"]
    assert len(uploads(panel)) == 1


async def test_busy_send_blocks_other_tabs_and_poll_unload_cancels(hass, ws, entry, panel, connect_ws):
    token, document = await prepare(ws, entry)
    other = await connect_ws()
    started = asyncio.Event()
    request = panel.request
    async def hold(method, path, **kwargs):
        result = await request(method, path, **kwargs)
        if path.endswith("/upload"):
            started.set()
            await asyncio.Event().wait()
        return result
    panel.request = hold
    await ws.send_json_auto_id({"type": PREFIX + "send", "entry_id": entry.entry_id, "import_id": token, "document": document})
    await asyncio.wait_for(started.wait(), 2)
    backend = entry.runtime_data.read_backend
    before = len(panel.calls)
    result = await command(other, entry, "status")
    assert result["error"]["code"] == "panel_busy"
    await entry.runtime_data.async_refresh()
    assert len(panel.calls) == before
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert (await ws.receive_json())["error"]["code"] == "panel_unavailable"
    assert backend.closed and not backend.busy and backend.requires_status_refresh
    assert backend.import_id is None and len(uploads(panel)) == 1


async def test_later_import_invalidates_first_tab_and_changed_bytes_require_check(ws, entry, panel, connect_ws):
    token, document = await prepare(ws, entry)
    altered = json.loads(document)
    altered["rooms"][0]["name"] = "Another name"
    result = await command(ws, entry, "send", import_id=token, document=json.dumps(altered))
    assert result["error"]["code"] == "candidate_conflict"
    other = await connect_ws()
    second, _ = await prepare(other, entry)
    assert second != token
    before = len(panel.calls)
    result = await command(ws, entry, "send", import_id=token, document=document)
    assert result["error"]["code"] == "candidate_conflict" and len(panel.calls) == before
    assert not uploads(panel)


@pytest.mark.parametrize("document", ["broken", "", "a" * 65537, '{"revision":1,"revision":2}'])
async def test_prepare_rejects_invalid_or_oversized_model_before_post(ws, entry, panel, document):
    imported = (await command(ws, entry, "import", source="active"))["result"]
    panel.calls.clear()
    result = await command(ws, entry, "validate", import_id=imported["import_id"], document=document)
    assert result["error"]["code"] == "invalid_document"
    assert not any(method == "POST" for method, *_ in panel.calls)


async def test_unpaired_unicode_is_rejected_before_device_io(hass, ws, entry, panel):
    # HA's JSON WebSocket serializer itself refuses surrogate code points.
    # Exercise our independent input boundary without asking it to emit one.
    imported = (await command(ws, entry, "import", source="active"))["result"]
    connection = Mock()
    before = len(panel.calls)
    await _run(hass, connection, {"id":1, "entry_id":entry.entry_id,
        "document":"\ud800", "import_id":imported["import_id"]}, "validate")
    assert connection.send_error.call_args.args[1] == "invalid_document"
    assert len(panel.calls) == before


async def test_send_over_real_shared_ha_http_session(hass, panel, monkeypatch, aiohttp_server, socket_enabled, hass_ws_client):
    from aiohttp import web
    from pytest_homeassistant.common import MockConfigEntry
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
        token, document = await prepare(socket, configured)
        result = await command(socket, configured, "send", import_id=token, document=document)
        assert result["success"] and result["result"]["candidate"]["changed"]
        assert len(uploads(panel)) == 1
    finally:
        await socket.close()
        await hass.async_block_till_done()


@pytest.mark.skipif(not shutil.which("node") or (os.environ.get("HA_BROWSER_MANAGED_PLAYWRIGHT") != "1" and
                    not Path("/usr/bin/chromium").exists()), reason="Chromium/Node required")
@pytest.mark.parametrize("lost", [False, True])
async def test_send_in_chromium(hass, entry, panel, hass_client, hass_access_token, lost):
    from homeassistant.components.http import StaticPathConfig
    from homeassistant.setup import async_setup_component
    from custom_components.home_panel.frontend import async_setup_panel
    root = Path(__file__).resolve().parents[2]
    loaded = (panel.state["loaded_source"], panel.state["loaded_revision"])
    assert await async_setup_component(hass, "frontend", {})
    assert await async_setup_panel(hass)
    await hass.http.async_register_static_paths([
        StaticPathConfig("/home_panel_browser_fixture", str(root / "tests/fixtures/ha_frontend"), False)])
    client = await hass_client()
    process = await asyncio.create_subprocess_exec("node", str(root / "tests/ha_frontend_send.cjs"), cwd=root,
        env={**os.environ, "HA_BROWSER_ORIGIN":str(client.make_url("/")).rstrip("/"),
             "HA_BROWSER_TOKEN":hass_access_token, "HA_BROWSER_ENTRY":entry.entry_id,
             "HA_SEND_LOST":"1" if lost else "0"},
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), 120)
        assert process.returncode == 0, stdout.decode()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        await hass.async_block_till_done()
    assert len(uploads(panel)) == 1
    assert (panel.state["loaded_source"], panel.state["loaded_revision"]) == loaded
    assert not panel.state["pending_trial"]
    assert {path for method, path, *_ in panel.calls if method == "POST"} == {
        "/panel/runtime/api/validate", "/panel/runtime/api/export", "/panel/runtime/api/upload"}
