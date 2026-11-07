"""Administrator-only read/check API; credentials and nonces stay in the backend."""

import asyncio
from dataclasses import asdict
import logging
from typing import Any

import probatio as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN
from .coordinator import PanelConfigEntry, PanelCoordinator
from .draft_storage import DraftError, prepare_record, repository
from .draft_validation import ModelCheckBusy, ModelCheckInput, async_check_model
from .panel_config import IdentityMismatch, OutcomeUnknown, PanelError, PanelHTTPError, ProtocolError, Source
from .panel_config.protocol import MAX_DOCUMENT_BYTES, RuntimeSnapshot
from .panel_config.read_backend import (
    BackendBusy, BackendClosed, InvalidImport, InvalidInput, ReadConflict, RefreshRequired,
)

_LOGGER = logging.getLogger(__name__)
PREFIX = DOMAIN + "/config/"


@callback
def async_register(hass: HomeAssistant) -> None:
    for command in (ws_panels, ws_status, ws_import, ws_validate, ws_draft_get, ws_draft_save, ws_draft_delete,
                    ws_model_check):
        websocket_api.async_register_command(hass, command)


def _entry(hass: HomeAssistant, entry_id: str) -> PanelConfigEntry | None:
    entry = hass.config_entries.async_get_entry(entry_id)
    if (entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED or
            not isinstance(getattr(entry, "runtime_data", None), PanelCoordinator)):
        return None
    return entry


def _snapshot(entry: PanelConfigEntry, value: RuntimeSnapshot) -> dict[str, Any]:
    """Allowlist fields: never serialize config entry/client/status objects wholesale."""
    state, caps = value.status, value.capabilities
    return {
        "version": 1,
        "entry_id": entry.entry_id,
        "scope": "action_preview_only",
        "requires_status_refresh": entry.runtime_data.read_backend.requires_status_refresh,
        "status": {
            "sd_ready": state.sd_ready, "busy": state.busy, "restarting": state.restarting,
            "loaded_source": state.loaded_source, "loaded_revision": state.loaded_revision,
            "max_bytes": state.max_bytes, "features": sorted(state.features),
            "files": {str(source): asdict(info) for source, info in
                      zip((*Source, "temporary"), state.files, strict=True)},
        },
        "capabilities": {
            "schema_versions": list(caps.schema_versions), "features": sorted(caps.features),
            "widget_types": list(caps.widget_types), "room_kinds": list(caps.room_kinds),
            "display": {"width": caps.width, "height": caps.height},
            "limits": dict(caps.limits), "limits_measured_on_device": caps.limits_measured_on_device,
            "validation": asdict(caps.validation), "preview_compiled": caps.preview_compiled,
            "assets_inventory_complete": caps.assets_inventory_complete,
        },
        "authority": {"mode": caps.authority, "enforced": False},
        "management_ready": caps.management_ready,
        "deployment_ready": caps.deployment_ready,
    }


def _error(error: Exception) -> tuple[str, str]:
    if isinstance(error, BackendBusy):
        return "panel_busy", "Another read/check operation is in progress"
    if isinstance(error, BackendClosed):
        return "panel_unavailable", "Panel integration is unloaded"
    if isinstance(error, RefreshRequired):
        return "status_refresh_required", "Refresh status before another read/check job"
    if isinstance(error, OutcomeUnknown):
        return "outcome_unknown", "Read/check result unknown; refresh status, do not retry automatically"
    if isinstance(error, ReadConflict):
        return "read_conflict", "Panel boot, capabilities or source changed; refresh status"
    if isinstance(error, InvalidInput):
        return "invalid_document", "Expected UTF-8 text within the panel input limit"
    if isinstance(error, InvalidImport):
        return "invalid_import", "Export failed the panel shared validator"
    if isinstance(error, IdentityMismatch):
        return "identity_mismatch", "The endpoint is not the paired panel"
    if isinstance(error, ProtocolError):
        return "incompatible_response", "Panel response is missing, stale or incompatible"
    if isinstance(error, PanelHTTPError):
        return {
            401: ("invalid_auth", "Panel access key was rejected"),
            403: ("invalid_auth", "Panel access key was rejected"),
            404: ("not_found", "Requested file or receipt is unavailable"),
            409: ("read_conflict", "Source metadata changed or the file is invalid"),
            410: ("expired", "Read/check receipt expired; refresh status"),
            429: ("panel_busy", "Panel is busy or restarting"),
            503: ("panel_unavailable", "Panel metadata, SD or validator is unavailable"),
        }.get(error.status, ("panel_error", "Panel request failed"))
    return "cannot_connect", "Unable to complete the panel read/check request"


async def _run(hass: HomeAssistant, connection: websocket_api.ActiveConnection,
               msg: dict[str, Any], operation: str) -> None:
    entry = _entry(hass, msg["entry_id"])
    if entry is None:
        connection.send_error(msg["id"], "panel_unavailable", "Loaded panel integration not found")
        return
    coordinator = entry.runtime_data
    backend = coordinator.read_backend
    try:
        if operation == "status":
            snapshot = await backend.inspect()
            result = {}
        elif operation == "import":
            checked = await backend.import_document(Source(msg["source"]))
            snapshot = checked.snapshot
            result = {"source": checked.document.source.value,
                      "revision": checked.document.revision, "sha256": checked.document.sha256,
                      "bytes": len(checked.document.data), "document": checked.document.data.decode("utf-8"),
                      "validation": asdict(checked.validation), "validator": "panel_shared"}
        else:
            document = msg["document"]
            # Check character count before UTF-8 allocation; the device byte ceiling
            # is checked again after fresh negotiated metadata, before any POST.
            if not 1 <= len(document) <= MAX_DOCUMENT_BYTES:
                raise InvalidInput("Input character limit exceeded")
            try:
                data = document.encode("utf-8")
            except UnicodeError:
                raise InvalidInput("Invalid UTF-8 input") from None
            checked = await backend.check_document(data)
            snapshot = checked.snapshot
            result = {"validation": asdict(checked.validation), "validator": "panel_shared"}
        current = _entry(hass, entry.entry_id)
        if backend.closed or current is None or current.runtime_data is not coordinator:
            raise BackendClosed("Panel integration changed during the operation")
        coordinator.async_set_updated_data(snapshot)
        connection.send_result(msg["id"], {**_snapshot(entry, snapshot), **result})
    except asyncio.CancelledError:
        if not backend.closed:
            raise
        connection.send_error(msg["id"], "panel_unavailable", "Panel integration was unloaded")
    except PanelError as error:
        if operation == "status" and not isinstance(error, BackendBusy):
            coordinator.async_set_update_error(UpdateFailed("Panel read/check status is unavailable"))
        if isinstance(error, PanelHTTPError) and error.status in (401, 403):
            entry.async_start_reauth(hass)
        connection.send_error(msg["id"], *_error(error))
    except Exception:
        # Do not pass a document or arbitrary transport exception to HA's generic
        # WS exception logger, which may include request/credential text.
        _LOGGER.error("Unexpected failure in Home Panel read/check handler")
        connection.send_error(msg["id"], "internal_error", "Internal read/check error")


@websocket_api.websocket_command(vol.All(vol.Schema({"type": PREFIX + "panels"})))
@websocket_api.require_admin
@callback
def ws_panels(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    connection.send_result(msg["id"], {"version": 1, "panels": [
        {"entry_id": entry.entry_id, "name": entry.title, "state": entry.state.value}
        for entry in hass.config_entries.async_entries(DOMAIN)
    ]})


@websocket_api.websocket_command({"type": PREFIX + "status", vol.Required("entry_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_status(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    await _run(hass, connection, msg, "status")


@websocket_api.websocket_command({"type": PREFIX + "import", vol.Required("entry_id"): str,
                                 vol.Required("source"): vol.In([source.value for source in Source])})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_import(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    await _run(hass, connection, msg, "import")


@websocket_api.websocket_command({"type": PREFIX + "validate", vol.Required("entry_id"): str,
                                 vol.Required("document"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_validate(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    await _run(hass, connection, msg, "validate")


@websocket_api.websocket_command({"type": PREFIX + "model_check", vol.Required("entry_id"): str,
                                 vol.Required("document"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_model_check(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN or not entry.unique_id:
        connection.send_error(msg["id"], "panel_unavailable", "Panel configuration not found")
        return
    try:
        result = await async_check_model(hass, entry.entry_id, msg["document"])
        if hass.config_entries.async_get_entry(entry.entry_id) is not entry:
            connection.send_error(msg["id"], "panel_unavailable", "Panel configuration changed")
            return
        connection.send_result(msg["id"], result)
    except asyncio.CancelledError:
        raise
    except ModelCheckBusy:
        connection.send_error(msg["id"], "model_check_busy", "Another model check is in progress")
    except ModelCheckInput:
        connection.send_error(msg["id"], "invalid_document", "Expected bounded UTF-8 model text")
    except Exception:
        _LOGGER.error("Unexpected failure in Home Panel shared model check")
        connection.send_error(msg["id"], "internal_error", "Internal model check error")


async def _draft(hass, connection, msg, operation):
    # HA checkpoints remain available when the panel is offline or unloaded.
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN or not entry.unique_id:
        connection.send_error(msg["id"], "panel_unavailable", "Panel configuration not found")
        return
    try:
        owner = repository(hass, entry)
        if operation == "get":
            result = await owner.get()
        else:
            record = None
            if operation == "save":
                record = await hass.async_add_executor_job(prepare_record, msg["document"], msg["original"], msg["capabilities"])
            result = await owner.write(msg["expected_revision"], record)
        if hass.config_entries.async_get_entry(entry.entry_id) is not entry:
            connection.send_error(msg["id"], "panel_unavailable", "Panel configuration changed")
            return
        connection.send_result(msg["id"], result)
    except DraftError as error:
        connection.send_error(msg["id"], error.code, "HA draft operation did not complete; read current draft before retrying")
    except ProtocolError:
        connection.send_error(msg["id"], "panel_unavailable", "Paired panel identity is unavailable")
    except asyncio.CancelledError:
        raise
    except Exception:
        _LOGGER.error("Unexpected failure in Home Panel HA draft handler")
        connection.send_error(msg["id"], "draft_storage_error", "HA draft storage unavailable")


@websocket_api.websocket_command({"type": PREFIX + "draft_get", vol.Required("entry_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_draft_get(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    await _draft(hass, connection, msg, "get")


@websocket_api.websocket_command({"type": PREFIX + "draft_save", vol.Required("entry_id"): str,
                                 vol.Required("expected_revision"): vol.All(str, vol.Length(max=64)),
                                 vol.Required("document"): vol.All(str, vol.Length(max=MAX_DOCUMENT_BYTES)),
                                 vol.Required("original"): dict, vol.Required("capabilities"): dict})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_draft_save(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    await _draft(hass, connection, msg, "save")


@websocket_api.websocket_command({"type": PREFIX + "draft_delete", vol.Required("entry_id"): str,
                                 vol.Required("expected_revision"): vol.All(str, vol.Length(max=64))})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_draft_delete(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    await _draft(hass, connection, msg, "delete")
