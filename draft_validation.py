"""Explicit bounded host-model checks, never device validation or storage."""

import asyncio
from dataclasses import asdict
import hashlib

from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .panel_config.runtime_model.panel_runtime import DEFAULT_LIMITS, decode_document, validate_document

DATA_KEY = DOMAIN + "_model_checks"


class ModelCheckBusy(Exception):
    """One model check is already running for this entry."""


class ModelCheckInput(Exception):
    """Input exceeds the bounded UTF-8 transport envelope."""


def check_model(document: str) -> dict:
    if not isinstance(document, str) or not 1 <= len(document) <= DEFAULT_LIMITS.document_bytes:
        raise ModelCheckInput
    try:
        raw = document.encode("utf-8")
    except UnicodeError:
        raise ModelCheckInput from None
    if len(raw) > DEFAULT_LIMITS.document_bytes:
        raise ModelCheckInput
    result = {"version": 1, "validator": "shared_python", "scope": "host_model",
              "input_sha256": hashlib.sha256(raw).hexdigest(), "input_bytes": len(raw),
              "limits": asdict(DEFAULT_LIMITS), "limits_measured_on_device": False,
              "device_checked": False, "deployment_ready": False}
    try:
        model = decode_document(raw)
        report = validate_document(model)
    except ValueError:
        # Shared validator messages may interpolate untrusted JSON fields.
        return {**result, "valid": False, "error": "invalid_model", "report": None}
    return {**result, "valid": True, "error": None, "report": report}


async def async_check_model(hass: HomeAssistant, entry_id: str, document: str) -> dict:
    tasks = hass.data.setdefault(DATA_KEY, {})
    if entry_id in tasks:
        raise ModelCheckBusy

    async def run():
        return await hass.async_add_executor_job(check_model, document)

    task = hass.async_create_task(run(), "Home Panel shared model check")
    tasks[entry_id] = task

    def finished(completed):
        if tasks.get(entry_id) is completed:
            tasks.pop(entry_id)
        if not completed.cancelled():
            completed.exception()

    task.add_done_callback(finished)
    # A disconnected waiter must not permit an unbounded second executor job.
    return await asyncio.shield(task)
