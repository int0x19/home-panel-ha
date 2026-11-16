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
from homeassistant.helpers.storage import Store

from custom_components.home_panel.const import DOMAIN
from custom_components.home_panel import draft_storage as drafts
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


def revision_record(payload, revision, name=None):
    data = deepcopy(payload)
    doc = json.loads(data["document"])
    doc["revision"] = revision
    if name is not None:
        doc["rooms"][0]["name"] = name
    data["document"] = json.dumps(doc, ensure_ascii=False)
    return prepare_record(**data)


async def test_history_rolls_distinct_checkpoints_and_survives_restart(hass, draft_entry, draft_payload, panel):
    owner = repository(hass, draft_entry)
    snapshot = await owner.get()
    saved = {}
    for index in range(6):
        record = revision_record(draft_payload, 32 + index, f"Version {index}")
        snapshot = await owner.write(snapshot["revision"], record)
        saved[snapshot["generation"]] = record
    assert [item["generation"] for item in snapshot["history"]] == [5, 4, 3]
    assert snapshot["history_limits"] == {"entries":3, "bytes":256 * 1024}
    assert snapshot["document_high_water"] == 37
    assert all(type(item["saved_at"]) is int for item in snapshot["history"])
    assert "document" not in snapshot["history"][0] and "capabilities" not in snapshot["history"][0]
    path = Path(owner.store.path)
    before = await hass.async_add_executor_job(path.read_bytes)
    archived = await owner.history(snapshot["revision"], 5)
    assert archived["record"] == saved[5] and archived["record"]["original"] == draft_payload["original"]
    assert archived["revision"] == snapshot["revision"] and archived["history_generation"] == 5
    assert not archived["model_validated"] and not archived["deployment_ready"]
    assert await hass.async_add_executor_job(path.read_bytes) == before
    restarted = DraftRepository(hass, draft_entry.entry_id, DEVICE_ID)
    current = await restarted.get()
    assert current["history"] == snapshot["history"] and current["revision"] != snapshot["revision"]
    assert (await restarted.history(current["revision"], 3))["record"] == saved[3]
    with pytest.raises(DraftConflict): await restarted.history(snapshot["revision"], 5)
    with pytest.raises(drafts.DraftHistoryMissing): await owner.history(snapshot["revision"], 1)
    with pytest.raises(drafts.DraftHistoryMissing): await owner.history(snapshot["revision"], 6)
    assert not panel.calls and DEVICE_ID not in json.dumps(snapshot)


async def test_identical_save_does_not_fill_history(hass, draft_entry, draft_payload):
    owner = repository(hass, draft_entry)
    first = revision_record(draft_payload, 32)
    snapshot = await owner.write((await owner.get())["revision"], first)
    snapshot = await owner.write(snapshot["revision"], first)
    assert snapshot["generation"] == 2 and snapshot["history"] == []
    second = revision_record(draft_payload, 33)
    snapshot = await owner.write(snapshot["revision"], second)
    snapshot = await owner.write(snapshot["revision"], second)
    assert [item["generation"] for item in snapshot["history"]] == [2]


@pytest.mark.parametrize("budget", ["history_bytes", "store_bytes", "nodes"])
async def test_history_trims_before_publication_to_fit_all_read_budgets(hass, draft_entry, draft_payload, monkeypatch, budget):
    if budget == "nodes":
        nested = "leaf"
        for _ in range(10): nested = {"nested":nested}
        draft_payload["capabilities"]["limits"]["extra"] = nested
    owner = repository(hass, draft_entry)
    first = revision_record(draft_payload, 32, "A")
    snapshot = await owner.write((await owner.get())["revision"], first)
    if budget == "history_bytes": monkeypatch.setattr(drafts, "MAX_HISTORY_BYTES", 2)
    if budget == "store_bytes":
        size = await hass.async_add_executor_job(lambda: Path(owner.store.path).stat().st_size)
        monkeypatch.setattr(drafts, "MAX_STORAGE_BYTES", size + 100)
    snapshot = await owner.write(snapshot["revision"], revision_record(draft_payload, 33, "B"))
    assert snapshot["history"] == []
    raw = await hass.async_add_executor_job(Path(owner.store.path).read_bytes)
    assert len(raw) <= drafts.MAX_STORAGE_BYTES
    assert (await owner.get())["record"] == snapshot["record"]


async def test_delete_erases_history_but_preserves_revision_high_water(hass, draft_entry, draft_payload):
    owner = repository(hass, draft_entry)
    snapshot = await owner.write((await owner.get())["revision"], revision_record(draft_payload, 100))
    snapshot = await owner.write(snapshot["revision"], revision_record(draft_payload, 32))
    assert snapshot["document_high_water"] == 100 and len(snapshot["history"]) == 1
    deleted = await owner.write(snapshot["revision"], None)
    assert deleted["record"] is None and deleted["history"] == [] and deleted["document_high_water"] == 100
    restarted = DraftRepository(hass, draft_entry.entry_id, DEVICE_ID)
    assert (await restarted.get())["document_high_water"] == 100


@pytest.mark.parametrize("delete", [False, True])
async def test_legacy_read_has_no_side_effect_and_explicit_commit_upgrades(hass, draft_entry, draft_payload, delete):
    owner = repository(hass, draft_entry)
    record = revision_record(draft_payload, 32)
    payload = {"panel_id":DEVICE_ID, "generation":7, "record":record}
    legacy = {**payload, "checksum":drafts._checksum(payload)}
    await Store(hass, 1, owner.store.key, private=True, atomic_writes=True).async_save(legacy)
    path = Path(owner.store.path)
    before = await hass.async_add_executor_job(path.read_bytes)
    snapshot = await owner.get()
    assert snapshot["generation"] == 7 and snapshot["history"] == [] and snapshot["saved_at"] is None
    assert snapshot["document_high_water"] == 32
    assert await hass.async_add_executor_job(path.read_bytes) == before
    snapshot = await owner.write(snapshot["revision"], None if delete else revision_record(draft_payload, 33))
    assert json.loads(await hass.async_add_executor_job(path.read_bytes))["version"] == 2
    assert snapshot["generation"] == 8
    if delete:
        assert snapshot["history"] == [] and snapshot["record"] is None
    else:
        assert snapshot["history"][0]["generation"] == 7 and snapshot["history"][0]["saved_at"] is None
        assert (await owner.history(snapshot["revision"], 7))["record"] == record


@pytest.mark.parametrize("kind", ["record_hash", "future_generation", "negative_time", "too_many", "high_water", "unknown"])
async def test_corrupt_history_is_preserved_not_silently_discarded(hass, draft_entry, draft_payload, kind):
    owner = repository(hass, draft_entry)
    snapshot = await owner.write((await owner.get())["revision"], revision_record(draft_payload, 32))
    snapshot = await owner.write(snapshot["revision"], revision_record(draft_payload, 33))
    path = Path(owner.store.path)
    def corrupt():
        envelope = json.loads(path.read_bytes())
        state = envelope["data"]
        if kind == "record_hash": state["history"][0]["record"]["sha256"] = "0" * 64
        if kind == "future_generation": state["history"][0]["generation"] = state["generation"]
        if kind == "negative_time": state["history"][0]["saved_at"] = -1
        if kind == "too_many": state["history"] *= 4
        if kind == "high_water": state["document_high_water"] = 1
        if kind == "unknown": state["history"][0]["extra"] = True
        state["checksum"] = drafts._checksum({key:value for key,value in state.items() if key != "checksum"})
        path.write_text(json.dumps(envelope), encoding="utf-8")
        return path.read_bytes()
    raw = await hass.async_add_executor_job(corrupt)
    with pytest.raises(DraftStorageError): await owner.get()
    with pytest.raises(DraftStorageError): await owner.write(snapshot["revision"], None)
    assert await hass.async_add_executor_job(path.read_bytes) == raw


async def test_failed_update_preserves_current_and_history(hass, draft_entry, draft_payload):
    owner = repository(hass, draft_entry)
    snapshot = await owner.write((await owner.get())["revision"], revision_record(draft_payload, 32))
    snapshot = await owner.write(snapshot["revision"], revision_record(draft_payload, 33))
    before = await hass.async_add_executor_job(Path(owner.store.path).read_bytes)
    with patch.object(owner.store._io, "async_write", side_effect=WriteError("synthetic update failure")):
        with pytest.raises(DraftStorageError): await owner.write(snapshot["revision"], revision_record(draft_payload, 34))
    restored = await owner.get()
    assert restored["record"] == snapshot["record"] and restored["history"] == snapshot["history"]
    assert await hass.async_add_executor_job(Path(owner.store.path).read_bytes) == before


async def test_history_ws_is_read_only_cas_guarded_and_admin_only(hass, hass_ws_client, hass_read_only_access_token,
                                                               draft_entry, draft_payload, draft_ws, panel):
    owner = repository(hass, draft_entry)
    first = await owner.write((await owner.get())["revision"], revision_record(draft_payload, 32))
    current = await owner.write(first["revision"], revision_record(draft_payload, 33))
    result = await command(draft_ws, draft_entry, "history_get", expected_revision=current["revision"], history_generation=1)
    assert result["success"] and result["result"]["record"] == first["record"] and not panel.calls
    assert (await owner.get())["generation"] == 2
    result = await command(draft_ws, draft_entry, "history_get", expected_revision=first["revision"], history_generation=1)
    assert result["error"]["code"] == "draft_conflict"
    result = await command(draft_ws, draft_entry, "history_get", expected_revision=current["revision"], history_generation=2)
    assert result["error"]["code"] == "draft_history_missing"
    result = await command(draft_ws, draft_entry, "history_get", expected_revision=current["revision"], history_generation=1, path="../private")
    assert result["error"]["code"] == "invalid_format"
    ws = await hass_ws_client(access_token=hass_read_only_access_token)
    try:
        result = await command(ws, draft_entry, "history_get", expected_revision=current["revision"], history_generation=1)
        assert result["error"]["code"] == "unauthorized"
    finally:
        await ws.close()


@pytest.mark.parametrize("generation", [0, -1, True, "1", 1.5, drafts.MAX_GENERATION + 1])
async def test_history_generation_is_strict_and_bounded_without_file_creation(hass, draft_entry, draft_ws, generation):
    result = await command(draft_ws, draft_entry, "history_get", expected_revision="unused", history_generation=generation)
    assert result["error"]["code"] in ("invalid_format", "invalid_draft")
    assert not Path(repository(hass, draft_entry).store.path).exists()


@pytest.mark.parametrize("rollback", ["version", "high_water"])
async def test_observed_storage_version_and_high_water_cannot_go_backwards(hass, draft_entry, draft_payload, rollback):
    owner = repository(hass, draft_entry)
    snapshot = await owner.write((await owner.get())["revision"], revision_record(draft_payload, 100))
    for index in range(4):
        snapshot = await owner.write(snapshot["revision"], revision_record(draft_payload, 100 if rollback == "version" else 32, str(index)))
    path = Path(owner.store.path)
    def modify():
        envelope = json.loads(path.read_bytes())
        if rollback == "version":
            envelope["version"] = 1
            envelope["data"] = {key:value for key,value in envelope["data"].items()
                                if key in ("panel_id", "generation", "record", "checksum")}
        else:
            envelope["data"]["document_high_water"] = 99
        state = envelope["data"]
        state["checksum"] = drafts._checksum({key:value for key,value in state.items() if key != "checksum"})
        path.write_text(json.dumps(envelope), encoding="utf-8")
        return path.read_bytes()
    raw = await hass.async_add_executor_job(modify)
    with pytest.raises(DraftStorageError): await owner.get()
    with pytest.raises(DraftStorageError): await owner.write(snapshot["revision"], None)
    assert await hass.async_add_executor_job(path.read_bytes) == raw


async def test_oversized_single_current_record_never_replaces_previous_file(hass, draft_entry, draft_payload, monkeypatch):
    owner = repository(hass, draft_entry)
    saved = await owner.write((await owner.get())["revision"], revision_record(draft_payload, 32))
    path = Path(owner.store.path)
    before = await hass.async_add_executor_job(path.read_bytes)
    monkeypatch.setattr(drafts, "MAX_STORAGE_BYTES", len(before) + 100)
    with pytest.raises(DraftStorageError):
        await owner.write(saved["revision"], revision_record(draft_payload, 33, "X" * 4000))
    assert (await owner.get())["record"] == saved["record"]
    assert await hass.async_add_executor_job(path.read_bytes) == before


async def test_legacy_delete_tombstone_reads_without_migration(hass, draft_entry, draft_payload):
    owner = repository(hass, draft_entry)
    payload = {"panel_id":DEVICE_ID, "generation":7, "record":None}
    await Store(hass, 1, owner.store.key, private=True, atomic_writes=True).async_save({**payload, "checksum":drafts._checksum(payload)})
    path = Path(owner.store.path)
    before = await hass.async_add_executor_job(path.read_bytes)
    current = await owner.get()
    assert current["record"] is None and current["history"] == []
    assert await hass.async_add_executor_job(path.read_bytes) == before
    saved = await owner.write(current["revision"], revision_record(draft_payload, 32))
    assert saved["generation"] == 8 and saved["history"] == []
