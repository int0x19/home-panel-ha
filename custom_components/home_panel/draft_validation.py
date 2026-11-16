"""Explicit bounded host-model checks, never device validation or storage."""

from dataclasses import asdict
import hashlib

from homeassistant.core import HomeAssistant

from ._core import DEFAULT_LIMITS, decode_document, validate_document
from .draft_jobs import DATA_KEY, ModelCheckBusy, async_model_job


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
    return await async_model_job(hass, entry_id, check_model, document)
