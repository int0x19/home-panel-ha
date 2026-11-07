"""Actual HA session -> loopback aiohttp -> synthetic device protocol."""

from aiohttp import web

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.home_panel import coordinator
from custom_components.home_panel.const import CONF_ACCESS_KEY, CONF_URL, DOMAIN
from custom_components.home_panel._core import AiohttpTransport
from support import DEVICE_ID, TOKEN


async def test_setup_poll_and_unload_over_real_http(hass, panel, monkeypatch, aiohttp_server, socket_enabled, hass_ws_client):
    monkeypatch.setattr(coordinator, "AiohttpTransport", AiohttpTransport)
    seen = []

    async def handler(request):
        seen.append((request.method, request.path))
        result = await panel.request(request.method, request.path, headers=request.headers,
                                     body=await request.read(), max_bytes=16384)
        return web.Response(status=result.status, body=result.body, headers=result.headers)

    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handler)
    server = await aiohttp_server(app)
    origin = str(server.make_url("/")).rstrip("/")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: origin, CONF_ACCESS_KEY: TOKEN})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == DEVICE_ID
    assert len(seen) == 4
    panel.state["loaded_revision"] = 42
    await entry.runtime_data.async_refresh()
    assert entry.runtime_data.data.status.loaded_revision == 42
    assert len(seen) == 6
    assert {path for _, path in seen} == {"/panel/runtime/api/status", "/panel/runtime/api/capabilities"}
    assert all(method == "GET" for method, _ in seen)
    ws = await hass_ws_client()
    try:
        await ws.send_json_auto_id({"type": "home_panel/config/import", "entry_id": entry.entry_id, "source": "active"})
        result = await ws.receive_json()
        assert result["success"]
        assert result["result"]["document"].encode() == panel.documents["active"]
        assert result["result"]["validation"]["valid"]
        assert len(seen) == 17
        assert {path for method, path in seen if method == "POST"} == {
            "/panel/runtime/api/export", "/panel/runtime/api/validate"}
    finally:
        await ws.close()
        await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not async_get_clientsession(hass).closed
