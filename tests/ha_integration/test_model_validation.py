"""Shared full host validation on actual HA WS, without device or file I/O."""

import asyncio
from copy import deepcopy
import hashlib
import json
import threading
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.setup import async_setup_component

from custom_components.home_panel.const import DOMAIN
from custom_components.home_panel import draft_validation as checks
from custom_components.home_panel.websocket_api import PREFIX
from support import DEVICE_ID, TOKEN
from custom_components.home_panel._core import validate_document
from support import DOCUMENT


def action_document():
    document = deepcopy(DOCUMENT)
    room = deepcopy(document["rooms"][1])
    room.pop("kind", None)
    room["widgets"] = room["widgets"][:1]
    document["rooms"] = [room]
    return document


@pytest.fixture
async def model_entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_ID, title="Offline panel", data={})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    return entry


@pytest.fixture
async def model_ws(hass, hass_ws_client, model_entry):
    client = await hass_ws_client()
    yield client
    await client.close()
    await hass.async_block_till_done()


async def command(ws, entry, document, **extra):
    await ws.send_json_auto_id({"type": PREFIX + "model_check", "entry_id": entry.entry_id,
                               "document": document, **extra})
    return await ws.receive_json()


async def test_full_host_check_offline_exact_digest_no_device_io(model_ws, model_entry, panel, hass):
    document = action_document()
    document["rooms"][0]["widgets"].append({"id":"climate_test", "type":"climate",
        "settings":{"entity":"climate.test", "name":"Test climate"}})
    document["requires"].append("widget.climate")
    raw = " \r\n" + json.dumps(document, ensure_ascii=False, indent=2) + "\r\n"
    before = len(panel.calls)
    result = (await command(model_ws, model_entry, raw))["result"]
    assert result["valid"] and result["scope"] == "host_model"
    assert result["validator"] == "shared_python"
    assert result["report"] == validate_document(document)
    assert result["input_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert result["input_bytes"] == len(raw.encode())
    assert not result["device_checked"] and not result["deployment_ready"]
    assert not result["limits_measured_on_device"]
    assert result["report"]["sha256"] != result["input_sha256"]
    assert len(panel.calls) == before and DOMAIN + "_drafts" not in hass.data
    assert TOKEN not in json.dumps(result) and DEVICE_ID not in json.dumps(result)


@pytest.mark.parametrize("change", ["duplicate_id", "geometry", "reference", "features", "executable", "wrong_type"])
async def test_full_semantic_rejection_is_not_just_storage_shape(model_ws, model_entry, panel, change):
    doc = action_document()
    if change == "duplicate_id": doc["rooms"] *= 2
    if change == "geometry": doc["style"]["layout"]["nav_button_height"] = 1
    if change == "reference": doc["rooms"][0]["widgets"][0]["settings"]["entity"] = "light.not_action"
    if change == "features": doc["requires"] = []
    if change == "executable": doc["rooms"][0]["widgets"][0]["settings"]["lambda"] = TOKEN
    if change == "wrong_type": doc["style"]["layout"]["page_gap"] = True
    before = len(panel.calls)
    result = (await command(model_ws, model_entry, json.dumps(doc)))["result"]
    assert not result["valid"] and result["error"] == "invalid_model" and result["report"] is None
    assert TOKEN not in json.dumps(result) and len(panel.calls) == before


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}', "[", "[]", '"scalar"'])
async def test_malformed_finite_and_object_checks(model_ws, model_entry, raw):
    result = (await command(model_ws, model_entry, raw))["result"]
    assert not result["valid"] and result["report"] is None


@pytest.mark.parametrize("raw", ["", "x" * 65537, "Я" * 32769])
async def test_bounded_input(model_ws, model_entry, raw):
    result = await command(model_ws, model_entry, raw)
    assert result["error"]["code"] == "invalid_document"


def test_surrogate_direct_boundary():
    with pytest.raises(checks.ModelCheckInput): checks.check_model("\ud800")


async def test_nonadmin_before_executor_or_io(hass, hass_ws_client, hass_read_only_access_token, model_entry, panel):
    client = await hass_ws_client(access_token=hass_read_only_access_token)
    try:
        before = len(panel.calls)
        with patch.object(checks, "check_model", side_effect=AssertionError("must not execute")):
            result = await command(client, model_entry, "broken")
        assert result["error"]["code"] == "unauthorized"
        assert checks.DATA_KEY not in hass.data and len(panel.calls) == before
    finally:
        await client.close()


@pytest.mark.parametrize("extra", [{"url": "http://other.test"}, {"path": "../secrets.yaml"}, {"capabilities": {}}])
async def test_no_address_paths_or_client_limit_overrides(model_ws, model_entry, extra):
    result = await command(model_ws, model_entry, "broken", **extra)
    assert result["error"]["code"] == "invalid_format"


async def test_cancelled_waiter_does_not_queue_parallel_executor_work(hass):
    entered, release = threading.Event(), threading.Event()

    def slow(document):
        entered.set()
        if not release.wait(5): raise AssertionError("release timeout")
        return {"valid": False}

    with patch.object(checks, "check_model", slow):
        pending = asyncio.create_task(checks.async_check_model(hass, "entry", "broken"))
        try:
            assert await hass.async_add_executor_job(entered.wait, 3)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError): await pending
            with pytest.raises(checks.ModelCheckBusy): await checks.async_check_model(hass, "entry", "other")
        finally:
            release.set()
            await hass.async_block_till_done()
    assert not hass.data[checks.DATA_KEY]


async def test_entry_removed_during_check_discards_result(hass, model_ws, model_entry):
    entered, release = asyncio.Event(), asyncio.Event()

    async def slow(*args):
        entered.set()
        await release.wait()
        return {"valid": True}

    with patch("custom_components.home_panel.websocket_api.async_check_model", slow):
        await model_ws.send_json_auto_id({"type": PREFIX + "model_check", "entry_id": model_entry.entry_id,
                                         "document": "broken"})
        await entered.wait()
        await hass.config_entries.async_remove(model_entry.entry_id)
        release.set()
        assert (await model_ws.receive_json())["error"]["code"] == "panel_unavailable"
