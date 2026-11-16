"""Bounded HA-only structural comparisons with real authenticated HA WS."""

import asyncio
from copy import deepcopy
import hashlib
import json
import threading
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.setup import async_setup_component

from custom_components.home_panel import draft_changes as changes, draft_validation as checks
from custom_components.home_panel.const import DOMAIN
from custom_components.home_panel.draft_storage import DATA_KEY as STORAGE_KEY, DraftInvalid
from custom_components.home_panel.websocket_api import PREFIX
from support import DEVICE_ID, DOCUMENT, TOKEN


def model():
    doc = deepcopy(DOCUMENT)
    first = deepcopy(doc["rooms"][1])
    first["id"] = "first"
    second = {"id":"second", "name":"Second", "groups":{}, "widgets":[]}
    doc["rooms"] = [first, second]
    return doc


def text(doc):
    return json.dumps(doc, ensure_ascii=False)


def compare(before, after):
    return changes.summarize_changes(text(before), text(after))


def test_formatting_revision_and_exact_input_hashes_are_not_model_validation():
    before = model()
    after = deepcopy(before)
    after["revision"] += 1
    base = " \r\n" + text(before) + "\r\n"
    document = json.dumps(after, ensure_ascii=False, indent=2)
    report = changes.summarize_changes(base, document)
    assert report["total"] == 0 and report["items"] == [] and not report["truncated"]
    assert report["base_sha256"] == hashlib.sha256(base.encode()).hexdigest()
    assert report["document_sha256"] == hashlib.sha256(document.encode()).hexdigest()
    assert report["base_bytes"] == len(base.encode())
    assert report["base_revision"] + 1 == report["document_revision"]
    assert report["scope"] == "ha_structural_changes"
    assert not report["model_validated"] and not report["device_checked"] and not report["deployment_ready"]
    assert compare(before, before)["total"] == 0


def test_room_and_widget_changes_moves_sections_and_order():
    before = model()
    after = deepcopy(before)
    first, second = after["rooms"]
    first["name"] = "Детская"
    first["groups"] = {"opaque":{}}
    moved = first["widgets"].pop(0)
    second["widgets"].append(moved)
    first["widgets"][0]["settings"].update(name="Сцена", entity="scene.changed", icon="moon")
    first["widgets"].pop()
    added = deepcopy(moved)
    added["id"] = "new_action"
    first["widgets"].append(added)
    after["rooms"].reverse()
    after["rooms"].append({"id":"new_room", "name":"New", "groups":{}, "widgets":[]})
    for section in ("panel", "style", "attention"):
        after[section]["PRIVATE"] = TOKEN
    after["views"].append({"opaque":TOKEN})
    after["requires"].append("opaque.v1")
    report = compare(before, after)
    assert report["counts"] == {"room_changed":1, "room_added":1, "room_order":1,
                                "widget_removed":1, "widget_moved":1, "widget_changed":1,
                                "widget_added":1, "section_changed":5}
    assert next(item for item in report["items"] if item["kind"] == "widget_moved")["from_room"] == "first"
    assert next(item for item in report["items"] if item["kind"] == "widget_changed")["fields"] == ["name", "entity", "settings"]
    assert TOKEN not in json.dumps(report) and "PRIVATE" not in json.dumps(report)
    assert before == model(), "Comparison does not mutate either document"
    assert report == compare(before, after), "Ordering is deterministic"


def test_insertions_removals_and_reordering_are_distinct():
    before = model()
    after = deepcopy(before)
    after["rooms"][0]["widgets"].pop(0)
    assert compare(before, after)["counts"] == {"widget_removed":1}
    after["rooms"][0]["widgets"].reverse()
    assert compare(before, after)["counts"] == {"widget_removed":1, "widget_order":1}
    after["rooms"].pop(1)
    assert compare(before, after)["counts"]["room_removed"] == 1


def test_room_local_repeated_ids_are_not_guessed_as_moves():
    before = model()
    repeated = deepcopy(before["rooms"][0]["widgets"][0])
    before["rooms"][1]["widgets"].append(repeated)
    after = deepcopy(before)
    after["rooms"][0]["widgets"].pop(0)
    after["rooms"].append({"id":"third", "name":"Third", "groups":{}, "widgets":[repeated]})
    report = compare(before, after)
    assert report["counts"] == {"room_added":1, "widget_removed":1, "widget_added":1}


def test_json_types_are_distinct_without_claiming_semantic_validation():
    before = model()
    after = deepcopy(before)
    after["rooms"][0]["widgets"][0]["settings"]["enabled"] = 1
    after["panel"]["backlight"]["auto_off"] = 0
    report = compare(before, after)
    assert report["counts"] == {"widget_changed":1, "section_changed":1}
    assert not report["model_validated"]


@pytest.mark.parametrize("duplicate", ["room", "widget"])
def test_ambiguous_duplicate_ids_rejected(duplicate):
    doc = model()
    if duplicate == "room": doc["rooms"].append(deepcopy(doc["rooms"][0]))
    else: doc["rooms"][0]["widgets"].append(deepcopy(doc["rooms"][0]["widgets"][0]))
    with pytest.raises(DraftInvalid): compare(model(), doc)


@pytest.mark.parametrize("unicode_names", [False, True])
def test_count_and_utf8_output_budgets(unicode_names):
    before = model()
    before["rooms"][0]["widgets"] = []
    after = deepcopy(before)
    prototype = model()["rooms"][0]["widgets"][0]
    count = 40 if unicode_names else 80
    for index in range(count):
        widget = deepcopy(prototype)
        widget["id"] = f"action_{index}"
        widget["settings"]["name"] = "\U0001f331" * 240 if unicode_names else "X" * 200
        after["rooms"][0]["widgets"].append(widget)
    assert len(text(after).encode()) <= 65536
    report = compare(before, after)
    assert report["total"] == count and report["truncated"]
    assert len(report["items"]) < count and len(report["items"]) <= changes.MAX_CHANGES
    assert len(json.dumps(report, ensure_ascii=False, separators=(",", ":")).encode()) <= changes.MAX_RESULT_BYTES


@pytest.mark.parametrize("raw", ["", "x" * 65537, "Я" * 32769, "\ud800", "[", "[]", '{"x":NaN}', '{"x":1,"x":2}'])
def test_invalid_and_oversized_inputs(raw):
    good = text(model())
    for base, document in ((raw, good), (good, raw)):
        with pytest.raises(DraftInvalid): changes.summarize_changes(base, document)


@pytest.fixture
async def changes_entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_ID, title="Offline", data={})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    return entry


@pytest.fixture
async def changes_ws(hass, hass_ws_client, changes_entry):
    ws = await hass_ws_client()
    yield ws
    await ws.close()
    await hass.async_block_till_done()


async def command(ws, entry, **extra):
    await ws.send_json_auto_id({"type":PREFIX + "model_changes", "entry_id":entry.entry_id,
                               "base":text(model()), "document":text(model()), **extra})
    return await ws.receive_json()


async def test_actual_offline_ws_no_device_storage_or_identity_exposure(hass, changes_ws, changes_entry, panel):
    result = await command(changes_ws, changes_entry)
    assert result["success"] and result["result"]["total"] == 0
    assert STORAGE_KEY not in hass.data and not panel.calls
    assert DEVICE_ID not in json.dumps(result) and TOKEN not in json.dumps(result)
    result = await command(changes_ws, changes_entry, document="broken " + TOKEN)
    assert result["error"]["code"] == "invalid_document"
    assert TOKEN not in json.dumps(result) and not panel.calls


@pytest.mark.parametrize("extra", [{"path":"../secrets.yaml"}, {"url":"http://other.test"}, {"capabilities":{}}, {"entry_id":"missing"}])
async def test_overrides_and_unknown_entry_rejected(changes_ws, changes_entry, extra):
    result = await command(changes_ws, changes_entry, **extra)
    assert result["error"]["code"] == ("panel_unavailable" if "entry_id" in extra else "invalid_format")


async def test_non_admin_refused_before_scheduling(hass, hass_ws_client, hass_read_only_access_token, changes_entry):
    ws = await hass_ws_client(access_token=hass_read_only_access_token)
    try:
        with patch.object(changes, "summarize_changes", side_effect=AssertionError("must not run")):
            result = await command(ws, changes_entry)
        assert result["error"]["code"] == "unauthorized" and checks.DATA_KEY not in hass.data
    finally:
        await ws.close()


async def test_cancelled_comparison_holds_shared_model_slot(hass):
    entered, release = threading.Event(), threading.Event()

    def slow(*args):
        entered.set()
        assert release.wait(5)
        return {"total":0}

    with patch.object(changes, "summarize_changes", slow):
        task = asyncio.create_task(changes.async_summarize_changes(hass, "entry", "base", "document"))
        try:
            assert await hass.async_add_executor_job(entered.wait, 3)
            task.cancel()
            with pytest.raises(asyncio.CancelledError): await task
            with pytest.raises(checks.ModelCheckBusy): await checks.async_check_model(hass, "entry", "other")
            with pytest.raises(checks.ModelCheckBusy): await changes.async_summarize_changes(hass, "entry", "a", "b")
        finally:
            release.set()
            await hass.async_block_till_done()
    assert not hass.data[checks.DATA_KEY]


async def test_validation_and_comparison_share_the_same_slot(hass):
    entered, release = threading.Event(), threading.Event()

    def slow(*args):
        entered.set()
        assert release.wait(5)
        return {"valid":False}

    with patch.object(checks, "check_model", slow):
        task = asyncio.create_task(checks.async_check_model(hass, "entry", "document"))
        try:
            assert await hass.async_add_executor_job(entered.wait, 3)
            with pytest.raises(checks.ModelCheckBusy): await changes.async_summarize_changes(hass, "entry", "a", "b")
        finally:
            release.set()
            await task
            await hass.async_block_till_done()
    assert not hass.data[checks.DATA_KEY]


async def test_unexpected_worker_error_is_sanitized(changes_ws, changes_entry, caplog):
    with patch.object(changes, "summarize_changes", side_effect=RuntimeError(TOKEN)):
        result = await command(changes_ws, changes_entry)
    assert result["error"]["code"] == "internal_error"
    assert TOKEN not in json.dumps(result) and TOKEN not in caplog.text


async def test_removed_entry_discards_result(hass, changes_ws, changes_entry):
    entered, release = asyncio.Event(), asyncio.Event()

    async def slow(*args):
        entered.set()
        await release.wait()
        return {"total":0}

    with patch("custom_components.home_panel.websocket_api.async_summarize_changes", slow):
        await changes_ws.send_json_auto_id({"type":PREFIX + "model_changes", "entry_id":changes_entry.entry_id,
                                           "base":"a", "document":"b"})
        await entered.wait()
        await hass.config_entries.async_remove(changes_entry.entry_id)
        release.set()
        assert (await changes_ws.receive_json())["error"]["code"] == "panel_unavailable"
