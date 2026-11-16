"""Actual authenticated HA WebSocket boundary with no household connections."""

import asyncio
from copy import deepcopy
import hashlib
import json
from unittest.mock import Mock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.home_panel.const import CONF_ACCESS_KEY, CONF_URL, DOMAIN
from custom_components.home_panel._core import TransportError
from custom_components.home_panel._core import read_backend
from custom_components.home_panel.websocket_api import PREFIX
from custom_components.home_panel import websocket_api as panel_ws
from support import DEVICE_ID, TOKEN, metadata, response


@pytest.fixture
async def entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, title="Panel", unique_id=DEVICE_ID,
                            data={CONF_URL: "http://panel.test", CONF_ACCESS_KEY: TOKEN})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


@pytest.fixture
async def connect_ws(hass, hass_ws_client):
    clients = []

    async def connect(**kwargs):
        client = await hass_ws_client(**kwargs)
        clients.append(client)
        return client

    yield connect
    for client in clients:
        await client.close()
    await hass.async_block_till_done()


@pytest.fixture
async def ws(connect_ws, entry):
    return await connect_ws()


async def command(ws, entry, operation, **data):
    await ws.send_json_auto_id({"type": PREFIX + operation, "entry_id": entry.entry_id, **data})
    return await ws.receive_json()


async def test_list_status_and_credential_redaction(hass, ws, entry, panel):
    before = len(panel.calls)
    await ws.send_json_auto_id({"type": PREFIX + "panels"})
    result = await ws.receive_json()
    assert result["success"]
    assert result["result"] == {"version": 1, "panels": [
        {"entry_id": entry.entry_id, "name": "Panel", "state": "loaded"}]}
    assert len(panel.calls) == before
    result = await command(ws, entry, "status")
    assert result["success"]
    data = result["result"]
    assert data["status"]["files"]["active"]["revision"] == 31
    assert data["capabilities"]["limits"]["document_bytes"] == 16384
    assert data["authority"] == {"mode": "unmanaged", "enforced": False}
    assert not data["management_ready"] and not data["deployment_ready"]
    assert data["scope"] == "action_preview_only"
    text = json.dumps(result)
    for secret in (TOKEN, "http://panel.test", DEVICE_ID, panel.state["session_id"]):
        assert secret not in text
    assert all(method == "GET" for method, *_ in panel.calls)


@pytest.mark.parametrize("operation", ["panels", "status", "import", "validate", "entities"])
async def test_non_admin_is_rejected_before_any_device_io(connect_ws, hass_read_only_access_token, entry, panel, operation):
    ws = await connect_ws(access_token=hass_read_only_access_token)
    data = {"type": PREFIX + operation}
    if operation != "panels":
        data["entry_id"] = entry.entry_id
    if operation == "import":
        data["source"] = "active"
    if operation == "validate":
        data["document"] = "broken"
    before = len(panel.calls)
    await ws.send_json_auto_id(data)
    result = await ws.receive_json()
    assert not result["success"]
    assert result["error"]["code"] == "unauthorized"
    assert len(panel.calls) == before


def test_anonymous_guard_rejects_before_scheduling_io(hass, entry, panel):
    connection = Mock(user=None)
    before = len(panel.calls)
    for handler in (panel_ws.ws_panels, panel_ws.ws_status, panel_ws.ws_import, panel_ws.ws_validate,
                    panel_ws.ws_draft_get, panel_ws.ws_draft_save, panel_ws.ws_draft_delete, panel_ws.ws_model_check,
                    panel_ws.ws_entities, panel_ws.ws_model_changes, panel_ws.ws_draft_history_get):
        with pytest.raises(Unauthorized):
            handler(hass, connection, {"id": 1, "entry_id": entry.entry_id})
    assert len(panel.calls) == before
    connection.send_result.assert_not_called()


@pytest.mark.parametrize("source", ["active", "candidate", "backup"])
async def test_exact_import_and_device_validation(ws, entry, panel, source):
    before = deepcopy(panel.documents)
    result = await command(ws, entry, "import", source=source)
    assert result["success"]
    data = result["result"]
    raw = data["document"].encode()
    assert raw == panel.documents[source]
    assert data["source"] == source
    assert len(raw) == data["bytes"]
    assert hashlib.sha256(raw).hexdigest() == data["sha256"]
    assert data["validation"]["valid"]
    assert data["validation"]["document_revision"] == data["revision"]
    assert data["validator"] == "panel_shared"
    assert not data["deployment_ready"]
    assert {path for method, path, *_ in panel.calls if method == "POST"} == {
        "/panel/runtime/api/export", "/panel/runtime/api/validate"}
    assert panel.documents == before


async def test_check_valid_and_invalid_documents_without_save(ws, entry, panel):
    for document, valid in ((panel.documents["active"].decode(), True), ("broken", False)):
        result = await command(ws, entry, "validate", document=document)
        assert result["success"]
        assert result["result"]["validation"]["valid"] is valid
        assert "document" not in result["result"]
    assert {path for method, path, *_ in panel.calls if method == "POST"} == {"/panel/runtime/api/validate"}


@pytest.mark.parametrize("document", ["", "a" * 65537, "\u042f" * 32769, "a" * 16385])
async def test_character_utf8_and_device_byte_limits_before_post(ws, entry, panel, document):
    result = await command(ws, entry, "validate", document=document)
    assert not result["success"]
    assert result["error"]["code"] == "invalid_document"
    assert not any(method == "POST" for method, *_ in panel.calls)
    assert not entry.runtime_data.read_backend.requires_status_refresh


@pytest.mark.parametrize("payload", [
    {"source": "../../secrets.yaml"}, {"source": "temporary"},
    {"source": "active", "url": "http://other.test"},
])
async def test_source_and_request_fields_are_allowlisted(ws, entry, panel, payload):
    before = len(panel.calls)
    result = await command(ws, entry, "import", **payload)
    assert not result["success"]
    assert result["error"]["code"] == "invalid_format"
    assert len(panel.calls) == before


@pytest.mark.parametrize("operation", ["status", "import", "validate"])
async def test_unloaded_wrong_domain_and_missing_entries(hass, ws, entry, panel, operation):
    extra = {"source": "active"} if operation == "import" else {"document": "broken"} if operation == "validate" else {}
    unknown = MockConfigEntry(domain="other_domain")
    unknown.add_to_hass(hass)
    for entry_id in ("missing", unknown.entry_id):
        before = len(panel.calls)
        await ws.send_json_auto_id({"type": PREFIX + operation, "entry_id": entry_id, **extra})
        result = await ws.receive_json()
        assert result["error"]["code"] == "panel_unavailable"
        assert len(panel.calls) == before
    assert await hass.config_entries.async_unload(entry.entry_id)
    result = await command(ws, entry, operation, **extra)
    assert result["error"]["code"] == "panel_unavailable"


async def test_lost_submission_requires_explicit_status_refresh_without_retry(ws, entry, panel):
    request = panel.request

    async def lost(method, path, **kwargs):
        result = await request(method, path, **kwargs)
        if method == "POST":
            raise TransportError("Synthetic lost reply " + TOKEN)
        return result

    panel.request = lost
    result = await command(ws, entry, "import", source="active")
    assert result["error"]["code"] == "outcome_unknown"
    assert TOKEN not in json.dumps(result)
    assert sum(method == "POST" for method, *_ in panel.calls) == 1
    before = len(panel.calls)
    result = await command(ws, entry, "validate", document="broken")
    assert result["error"]["code"] == "status_refresh_required"
    assert len(panel.calls) == before
    panel.request = request
    await entry.runtime_data.async_refresh()
    assert entry.runtime_data.read_backend.requires_status_refresh
    panel.state["busy"] = True
    result = await command(ws, entry, "status")
    assert result["result"]["requires_status_refresh"]
    panel.state["busy"] = False
    result = await command(ws, entry, "status")
    assert not result["result"]["requires_status_refresh"]
    result = await command(ws, entry, "validate", document="broken")
    assert result["success"] and not result["result"]["validation"]["valid"]


@pytest.mark.parametrize("previously_available", [True, False])
async def test_parallel_requests_rejected_and_unload_cancels_active_request(hass, connect_ws, ws, entry, panel, previously_available):
    other = await connect_ws()
    started = asyncio.Event()
    request = panel.request

    async def hold(method, path, **kwargs):
        if method == "POST":
            started.set()
            await asyncio.Event().wait()
        return await request(method, path, **kwargs)

    panel.request = hold
    if not previously_available:
        entry.runtime_data.async_set_update_error(UpdateFailed("Synthetic earlier failure"))
    await ws.send_json_auto_id({"type": PREFIX + "import", "entry_id": entry.entry_id, "source": "active"})
    await asyncio.wait_for(started.wait(), 2)
    backend = entry.runtime_data.read_backend
    before = len(panel.calls)
    result = await command(other, entry, "status")
    assert result["error"]["code"] == "panel_busy"
    assert len(panel.calls) == before
    await entry.runtime_data.async_refresh()
    assert len(panel.calls) == before
    assert entry.runtime_data.last_update_success is previously_available
    assert await hass.config_entries.async_unload(entry.entry_id)
    result = await ws.receive_json()
    assert result["error"]["code"] == "panel_unavailable"
    assert backend.closed and not backend.busy


@pytest.mark.parametrize("change", ["boot", "file", "validator", "receipt", "digest"])
async def test_changed_or_invalid_import_never_returns_a_document(ws, entry, panel, change):
    def mutate(method, suffix, result):
        if suffix == "downloads/1":
            if change == "boot":
                panel.state["session_id"] = panel.state["csrf"] = "3" * 32
            elif change == "file":
                doc = json.loads(panel.documents["active"])
                doc["revision"] += 1
                panel.state["active"] = metadata(json.dumps(doc).encode())
            elif change == "digest":
                return response(result.body + b" ", extra=tuple(result.headers[2:]))
        if suffix == "jobs/2" and change in ("validator", "receipt"):
            value = json.loads(result.body)
            if change == "validator":
                value["status"] = 400
                value["validation"]["status"] = 1
            else:
                value["validation"]["revision"] += 1
            return response(value)
        return result

    panel.change = mutate
    result = await command(ws, entry, "import", source="active")
    assert not result["success"]
    assert result["error"]["code"] in {"read_conflict", "incompatible_response", "invalid_import"}
    assert "document" not in result
    assert entry.runtime_data.read_backend.requires_status_refresh


async def test_outer_deadline_no_job_replay(ws, entry, panel, monkeypatch):
    monkeypatch.setattr(read_backend, "OPERATION_TIMEOUT", 0.5)
    request = panel.request

    async def hold(method, path, **kwargs):
        result = await request(method, path, **kwargs)
        if method == "POST":
            await asyncio.Event().wait()
        return result

    panel.request = hold
    result = await command(ws, entry, "import", source="active")
    assert result["error"]["code"] == "outcome_unknown"
    assert sum(method == "POST" for method, *_ in panel.calls) == 1
    assert not entry.runtime_data.read_backend.busy


async def test_manual_status_auth_failure_requests_reauthentication(hass, ws, entry, panel):
    async def rejected(*args, **kwargs):
        return response({}, status=401)

    panel.request = rejected
    result = await command(ws, entry, "status")
    await hass.async_block_till_done()
    assert result["error"]["code"] == "invalid_auth"
    assert not entry.runtime_data.last_update_success
    assert any(flow["context"]["source"] == "reauth" for flow in hass.config_entries.flow.async_progress())


@pytest.mark.parametrize(("status", "code"), [
    (404, "not_found"), (409, "read_conflict"), (410, "expired"), (429, "panel_busy"),
    (503, "panel_unavailable"), (302, "panel_error"),
])
async def test_job_http_errors_are_bounded_and_redacted(ws, entry, panel, status, code):
    def fail(method, suffix, result):
        if suffix == "export":
            return response({"error": TOKEN}, status=status)
        return result

    panel.change = fail
    result = await command(ws, entry, "import", source="active")
    assert result["error"]["code"] == code
    assert TOKEN not in json.dumps(result)
    assert sum(method == "POST" for method, *_ in panel.calls) == 1
    assert entry.runtime_data.read_backend.requires_status_refresh


async def test_validation_without_sd_and_import_absent_files(ws, entry, panel):
    panel.state["sd_ready"] = False
    result = await command(ws, entry, "validate", document="broken")
    assert result["success"] and not result["result"]["validation"]["valid"]
    assert not result["result"]["status"]["sd_ready"]
    result = await command(ws, entry, "import", source="active")
    assert result["error"]["code"] == "panel_unavailable"
    assert sum(method == "POST" for method, *_ in panel.calls) == 1


async def test_identity_mismatch_cannot_import_or_validate(ws, entry, panel):
    panel.state["device_id"] = "esp32-efuse-020000000046"
    for operation, data in (("status", {}), ("import", {"source": "active"}), ("validate", {"document": "broken"})):
        result = await command(ws, entry, operation, **data)
        assert result["error"]["code"] == "identity_mismatch"
    assert not any(method == "POST" for method, *_ in panel.calls)


async def test_no_write_or_actuator_commands_registered(ws, entry, panel):
    before = len(panel.calls)
    for operation in ("upload", "apply", "restore", "discard", "call_service", "press"):
        result = await command(ws, entry, operation)
        assert result["error"]["code"] == "unknown_command"
    assert len(panel.calls) == before


async def test_list_does_not_accept_connection_overrides(ws, panel):
    before = len(panel.calls)
    await ws.send_json_auto_id({"type": PREFIX + "panels", "url": "http://other.test"})
    result = await ws.receive_json()
    assert result["error"]["code"] == "invalid_format"
    assert len(panel.calls) == before


async def test_unexpected_transport_exception_is_sanitized(ws, entry, panel, caplog):
    request = panel.request

    async def unexpected(method, path, **kwargs):
        result = await request(method, path, **kwargs)
        if method == "POST":
            raise RuntimeError(TOKEN)
        return result

    panel.request = unexpected
    result = await command(ws, entry, "validate", document="broken")
    assert result["error"]["code"] == "internal_error"
    assert TOKEN not in json.dumps(result)
    assert TOKEN not in caplog.text
    assert entry.runtime_data.read_backend.requires_status_refresh
