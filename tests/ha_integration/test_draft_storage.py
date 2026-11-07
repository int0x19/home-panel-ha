"""Actual HA Store/WS with temporary disk, optimistic conflicts, zero device I/O."""

import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.util.file import WriteError

from custom_components.home_panel.const import DOMAIN
from custom_components.home_panel.draft_storage import (
    DraftConflict, DraftInvalid, DraftRepository, DraftStorageError, prepare_record, repository,
)
from custom_components.home_panel.websocket_api import PREFIX
from support import DEVICE_ID


@pytest.fixture
async def draft_entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_ID, title="Offline panel", data={})
    entry.add_to_hass(hass)
    from homeassistant.setup import async_setup_component
    assert await async_setup_component(hass, DOMAIN, {})
    return entry


@pytest.fixture
def draft_payload(panel):
    from dataclasses import asdict
    from custom_components.home_panel._core import RuntimeCapabilities
    from support import capability_document
    caps = RuntimeCapabilities.parse(capability_document(panel.state))
    view = {"schema_versions":list(caps.schema_versions), "features":sorted(caps.features),
            "widget_types":list(caps.widget_types), "room_kinds":list(caps.room_kinds),
            "display":{"width":caps.width,"height":caps.height}, "limits":dict(caps.limits),
            "validation":asdict(caps.validation), "preview_compiled":caps.preview_compiled,
            "limits_measured_on_device":caps.limits_measured_on_device,
            "assets_inventory_complete":caps.assets_inventory_complete}
    # Convert tuples as real WS serialization does.
    view = json.loads(json.dumps(view))
    raw = b" \r\n" + panel.documents["active"] + b"\r\n"
    document = json.loads(raw); document["revision"] += 1
    return {"document":json.dumps(document, ensure_ascii=False, indent=2),
            "original":{"source":"active", "revision":31, "sha256":hashlib.sha256(raw).hexdigest(), "document":raw.decode()},
            "capabilities":view}


@pytest.fixture
async def draft_ws(hass, hass_ws_client, draft_entry):
    ws = await hass_ws_client()
    yield ws
    await ws.close()
    await hass.async_block_till_done()


async def command(ws, entry, operation, **data):
    await ws.send_json_auto_id({"type":PREFIX + "draft_" + operation, "entry_id":entry.entry_id, **data})
    return await ws.receive_json()


async def test_save_read_restart_exact_original_and_no_device_io(hass, draft_entry, draft_payload, draft_ws, panel):
    initial = (await command(draft_ws, draft_entry, "get"))["result"]
    assert initial["generation"] == 0 and initial["record"] is None
    before = len(panel.calls)
    saved = await command(draft_ws, draft_entry, "save", expected_revision=initial["revision"], **draft_payload)
    assert saved["success"]
    record = saved["result"]["record"]
    assert record["original"] == draft_payload["original"]
    assert record["document"] != draft_payload["document"]
    assert json.loads(record["document"])["revision"] == 32
    assert record["sha256"] == hashlib.sha256(record["document"].encode()).hexdigest()
    assert not saved["result"]["model_validated"] and not saved["result"]["deployment_ready"]
    owner = repository(hass, draft_entry)
    path = Path(owner.store.path)
    assert path.is_file() and path.stat().st_mode & 0o077 == 0
    assert DEVICE_ID not in json.dumps(saved)
    # New owner simulates HA restart: disk survives, old editor token does not.
    restarted = DraftRepository(hass, draft_entry.entry_id, DEVICE_ID)
    loaded = await restarted.get()
    assert loaded["record"] == record and loaded["generation"] == 1
    assert loaded["revision"] != saved["result"]["revision"]
    with pytest.raises(DraftConflict):
        await restarted.write(saved["result"]["revision"], None)
    assert len(panel.calls) == before


async def test_two_editors_and_delete_tombstone_reject_stale_tokens(hass, draft_entry, draft_payload, draft_ws):
    empty = (await command(draft_ws, draft_entry, "get"))["result"]
    saved = (await command(draft_ws, draft_entry, "save", expected_revision=empty["revision"], **draft_payload))["result"]
    conflict = await command(draft_ws, draft_entry, "save", expected_revision=empty["revision"], **draft_payload)
    assert conflict["error"]["code"] == "draft_conflict"
    deleted = (await command(draft_ws, draft_entry, "delete", expected_revision=saved["revision"]))["result"]
    assert deleted["record"] is None and deleted["generation"] == 2
    assert Path(repository(hass, draft_entry).store.path).is_file()
    assert (await command(draft_ws, draft_entry, "delete", expected_revision=saved["revision"]))["error"]["code"] == "draft_conflict"
    assert (await command(draft_ws, draft_entry, "save", expected_revision=empty["revision"], **draft_payload))["error"]["code"] == "draft_conflict"


@pytest.mark.parametrize("change", ["duplicate", "nonfinite", "oversize", "hash", "revision", "capabilities"])
async def test_invalid_input_does_not_create_storage(hass, draft_entry, draft_payload, draft_ws, change):
    empty = (await command(draft_ws, draft_entry, "get"))["result"]
    if change == "duplicate": draft_payload["document"] = '{"revision":1,"revision":2}'
    if change == "nonfinite": draft_payload["document"] = '{"bad":NaN}'
    if change == "oversize": draft_payload["document"] = "Я" * 32769
    if change == "hash": draft_payload["original"]["sha256"] = "0" * 64
    if change == "revision": draft_payload["original"]["revision"] += 1
    if change == "capabilities": draft_payload["capabilities"]["secret"] = "not-allowed"
    result = await command(draft_ws, draft_entry, "save", expected_revision=empty["revision"], **draft_payload)
    assert result["error"]["code"] in ("invalid_draft", "invalid_format")
    assert not Path(repository(hass, draft_entry).store.path).exists()


def test_unpaired_surrogate_rejected_before_storage(draft_payload):
    # HA's WS decoder rejects raw surrogate frames before dispatch; exercise
    # our explicit UTF-8 boundary directly, without an upstream close/timer probe.
    draft_payload["document"] = "\ud800"
    with pytest.raises(DraftInvalid): prepare_record(**draft_payload)


@pytest.mark.parametrize("kind", ["corrupt", "future", "checksum", "identity", "large"])
async def test_bad_disk_is_preserved_without_overwrite(hass, draft_entry, draft_payload, kind):
    owner = repository(hass, draft_entry)
    saved = await owner.write((await owner.get())["revision"], prepare_record(**draft_payload))
    path = Path(owner.store.path)
    def corrupt():
        envelope = json.loads(path.read_bytes())
        if kind == "future": envelope["version"] += 1
        if kind == "checksum": envelope["data"]["checksum"] = "0" * 64
        if kind == "identity": envelope["data"]["panel_id"] = "esp32-efuse-020000000046"
        path.write_bytes(b"bad" if kind == "corrupt" else b" " * (512 * 1024 + 1) if kind == "large" else json.dumps(envelope).encode())
        return path.read_bytes()
    raw = await hass.async_add_executor_job(corrupt)
    with pytest.raises(DraftStorageError): await owner.get()
    with pytest.raises(DraftStorageError): await owner.write(saved["revision"], None)
    assert await hass.async_add_executor_job(path.read_bytes) == raw


async def test_swallowed_ha_write_failure_is_not_acknowledged(hass, draft_entry, draft_payload, caplog):
    owner = repository(hass, draft_entry)
    empty = await owner.get()
    with patch.object(owner.store._io, "async_write", side_effect=WriteError("synthetic disk full")):
        with pytest.raises(DraftStorageError):
            await owner.write(empty["revision"], prepare_record(**draft_payload))
    assert "Error writing config" in caplog.text
    assert (await owner.get())["generation"] == 0


async def test_cancelled_waiter_does_not_cancel_commit(hass, draft_entry, draft_payload):
    owner = repository(hass, draft_entry)
    empty = await owner.get()
    started, release = asyncio.Event(), asyncio.Event()
    write = owner.store.async_save
    async def held(data):
        started.set(); await release.wait(); await write(data)
    with patch.object(owner.store, "async_save", side_effect=held):
        task = asyncio.create_task(owner.write(empty["revision"], prepare_record(**draft_payload)))
        await started.wait(); task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        release.set()
        result = await owner.get()
    assert result["generation"] == 1 and result["record"] is not None
    await hass.async_block_till_done()


async def test_non_admin_cannot_read_save_or_delete(hass, hass_ws_client, hass_read_only_access_token, draft_entry, panel):
    ws = await hass_ws_client(access_token=hass_read_only_access_token)
    try:
        for operation in ("get", "delete"):
            data = {"expected_revision":"ignored"} if operation == "delete" else {}
            result = await command(ws, draft_entry, operation, **data)
            assert result["error"]["code"] == "unauthorized"
        result = await command(ws, draft_entry, "save", expected_revision="ignored", document="{}", original={}, capabilities={})
        assert result["error"]["code"] == "unauthorized"
        assert not panel.calls
    finally:
        await ws.close(); await hass.async_block_till_done()


async def test_failed_update_keeps_previous_checkpoint(hass, draft_entry, draft_payload):
    owner = repository(hass, draft_entry)
    saved = await owner.write((await owner.get())["revision"], prepare_record(**draft_payload))
    path = Path(owner.store.path)
    before = await hass.async_add_executor_job(path.read_bytes)
    with patch.object(owner.store._io, "async_write", side_effect=WriteError("synthetic update failure")):
        with pytest.raises(DraftStorageError): await owner.write(saved["revision"], None)
    assert (await owner.get())["record"] == saved["record"]
    assert await hass.async_add_executor_job(path.read_bytes) == before


async def test_original_factory_identity_is_required_after_restart(hass, draft_entry, draft_payload):
    owner = repository(hass, draft_entry)
    await owner.write((await owner.get())["revision"], prepare_record(**draft_payload))
    replacement = DraftRepository(hass, draft_entry.entry_id, "esp32-efuse-020000000046")
    with pytest.raises(DraftStorageError): await replacement.get()


async def test_removal_deletes_only_this_entry_checkpoint(hass, draft_entry, draft_payload):
    owner = repository(hass, draft_entry)
    await owner.write((await owner.get())["revision"], prepare_record(**draft_payload))
    other = MockConfigEntry(domain=DOMAIN, unique_id="esp32-efuse-020000000046", title="Other", data={})
    other.add_to_hass(hass)
    retained = repository(hass, other)
    await retained.write((await retained.get())["revision"], prepare_record(**draft_payload))
    assert await hass.config_entries.async_remove(draft_entry.entry_id)
    assert not Path(owner.store.path).exists()
    assert Path(retained.store.path).exists()
    with pytest.raises(DraftStorageError): await owner.get()


async def test_parallel_save_refused_without_queuing_a_second_write(hass, draft_entry, draft_payload, draft_ws, hass_ws_client):
    owner = repository(hass, draft_entry)
    initial = await owner.get()
    other = await hass_ws_client()
    started, release = asyncio.Event(), asyncio.Event()
    write = owner.store.async_save
    async def held(data):
        started.set(); await release.wait(); await write(data)
    try:
        with patch.object(owner.store, "async_save", side_effect=held):
            await draft_ws.send_json_auto_id({"type":PREFIX + "draft_save", "entry_id":draft_entry.entry_id,
                                              "expected_revision":initial["revision"], **draft_payload})
            await asyncio.wait_for(started.wait(), 2)
            second = await command(other, draft_entry, "save", expected_revision=initial["revision"], **draft_payload)
            assert second["error"]["code"] == "draft_busy"
            release.set()
            assert (await draft_ws.receive_json())["success"]
        assert (await owner.get())["generation"] == 1
    finally:
        release.set(); await other.close(); await hass.async_block_till_done()


@pytest.mark.parametrize("operation", ["get", "save", "delete"])
async def test_path_and_connection_overrides_are_rejected(hass, draft_entry, draft_payload, draft_ws, operation):
    extra = {"expected_revision":"unused"} if operation != "get" else {}
    if operation == "save": extra.update(draft_payload)
    result = await command(draft_ws, draft_entry, operation, path="/tmp/unowned", url="http://other.invalid", **extra)
    assert result["error"]["code"] == "invalid_format"
    assert not Path(hass.config.path(".storage", f"home_panel.draft.{draft_entry.entry_id}")).exists()
