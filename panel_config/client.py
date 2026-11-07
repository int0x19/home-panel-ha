"""Read/check-only async client. There are deliberately no persistent write methods."""

import asyncio
import hashlib
import json
import math

from .protocol import (
    API, MAX_METADATA_BYTES, UINT32_MAX, ExportedDocument, IdentityMismatch, OutcomeUnknown, PanelHTTPError,
    ProtocolError, RuntimeCapabilities, RuntimeSnapshot, RuntimeStatus, Source, Transport, TransportError,
    ValidationResult, boolean, device_identifier, digest, integer, json_object,
)


class PanelConfigClient:
    def __init__(self, transport: Transport, token: str, *, operation_timeout=15.0,
                 poll_interval=0.05, max_polls=200, expected_device_id: str | None = None):
        if (not isinstance(token, str) or not 1 <= len(token) <= 256 or
                any(not 33 <= ord(c) <= 126 for c in token)):
            raise ValueError("Missing or invalid panel access key")
        if (not math.isfinite(operation_timeout) or operation_timeout <= 0 or
                not math.isfinite(poll_interval) or poll_interval <= 0 or
                type(max_polls) is not int or not 1 <= max_polls <= 1000):
            raise ValueError("Invalid client time/poll budgets")
        self._transport = transport
        self._token = token
        self._timeout = operation_timeout
        self._poll_interval = poll_interval
        self._max_polls = max_polls
        self._expected_device_id = device_identifier(expected_device_id) if expected_device_id is not None else None
        self._lock = asyncio.Lock()

    async def _request(self, method, suffix, *, state=None, body=None, raw=False,
                       maximum=MAX_METADATA_BYTES, expected=200):
        headers = {"Authorization": "Bearer " + self._token, "Accept": "application/json"}
        if state is not None:
            headers["X-Panel-Settings"] = state.session_id
        if body is not None:
            headers["Content-Type"] = "application/json"
            if raw:
                headers["X-Panel-Revision"] = str(state.revision)
            else:
                body = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
        response = await self._transport.request(method, API + suffix, headers=headers,
                                                 body=body, max_bytes=maximum)
        if type(response.status) is not int or not 100 <= response.status <= 599:
            raise ProtocolError("Invalid HTTP status")
        if response.status != expected:
            raise PanelHTTPError(response.status)
        if not isinstance(response.body, bytes) or len(response.body) > maximum:
            raise ProtocolError("Oversized response")
        if (response.header("Content-Type") or "").split(";", 1)[0].strip().lower() != "application/json":
            raise ProtocolError("Expected JSON content type")
        if response.header("Content-Encoding") not in (None, "identity"):
            raise ProtocolError("Compressed responses are not supported")
        length = response.header("Content-Length")
        if length is not None and (not length.isascii() or not length.isdecimal() or
                                   len(length) > 10 or int(length) != len(response.body)):
            raise ProtocolError("Response byte count mismatch")
        return response

    async def _status(self):
        response = await self._request("GET", "status")
        state = RuntimeStatus.parse(json_object(response.body))
        if self._expected_device_id is not None and state.device_id != self._expected_device_id:
            raise IdentityMismatch("Paired panel identity unavailable or changed")
        return state

    async def status(self) -> RuntimeStatus:
        try:
            async with asyncio.timeout(self._timeout), self._lock:
                return await self._status()
        except TimeoutError:
            raise TransportError("Panel status timed out") from None

    async def capabilities(self) -> RuntimeCapabilities:
        return (await self.snapshot()).capabilities

    async def snapshot(self) -> RuntimeSnapshot:
        """Read status/metadata under one lock and verify they describe the same boot."""
        try:
            async with asyncio.timeout(self._timeout), self._lock:
                state = await self._status()
                if "capabilities.v1" not in state.features:
                    raise ProtocolError("Capability metadata is unavailable on this firmware")
                response = await self._request("GET", "capabilities", state=state)
                result = RuntimeCapabilities.parse(json_object(response.body))
                if (result.device_id != state.device_id or result.session_id != state.session_id or
                        result.limit("document_bytes") != state.max_bytes):
                    raise ProtocolError("Capability identity/session/byte-limit guards disagree")
                return RuntimeSnapshot(state, result)
        except TimeoutError:
            raise TransportError("Panel capability request timed out") from None

    @staticmethod
    def _ready(state: RuntimeStatus, feature: str):
        if feature not in state.features:
            raise ProtocolError("Required read/check API feature is unavailable")
        if state.busy or state.restarting:
            raise PanelHTTPError(429)

    async def _job(self, kind, state, body, *, raw=False):
        try:
            response = await self._request("POST", kind, state=state, body=body, raw=raw, expected=202)
        except TransportError:
            raise OutcomeUnknown("Job submission outcome unknown; refresh status, do not retry") from None
        accepted = json_object(response.body)
        job_id = integer(accepted.get("id"), "job id", 1)
        if (not self._identity_matches(accepted, state) or accepted.get("session_id") != state.session_id or
                integer(accepted.get("revision"), "operation revision") != state.revision or
                boolean(accepted.get("done"), "job completion") or
                integer(accepted.get("status"), "job status", 100, 599) != 202):
            raise ProtocolError("Job acceptance guards disagree")
        for _ in range(self._max_polls):
            try:
                result = json_object((await self._request("GET", "jobs/" + str(job_id))).body)
            except TransportError:
                raise OutcomeUnknown("Job receipt unavailable; refresh status, do not retry") from None
            if (not self._identity_matches(result, state) or integer(result.get("id"), "job id", 1) != job_id or
                    result.get("session_id") != state.session_id or
                    integer(result.get("revision"), "operation revision") != state.revision):
                raise ProtocolError("Job identity/session/revision changed")
            done = boolean(result.get("done"), "job completion")
            status = integer(result.get("status"), "job status", 100, 599)
            if done:
                if status == 202:
                    raise ProtocolError("Completed job is still pending")
                return job_id, result
            if status != 202:
                raise ProtocolError("Pending job has a final status")
            await asyncio.sleep(self._poll_interval)
        raise OutcomeUnknown("Job polling limit reached; refresh status, do not retry")

    @staticmethod
    def _identity_matches(value, state):
        return "capabilities.v1" not in state.features or ("device_id" in value and value["device_id"] == state.device_id)

    async def export(self, source: Source = Source.ACTIVE) -> ExportedDocument:
        try:
            source = Source(source)
        except (ValueError, TypeError):
            raise ValueError("Unknown export source") from None
        try:
            async with asyncio.timeout(self._timeout), self._lock:
                state = await self._status()
                self._ready(state, "export.v1")
                info = state.file(source)
                if not state.sd_ready:
                    raise PanelHTTPError(503)
                if not info.valid:
                    raise PanelHTTPError(409 if info.present else 404)
                job_id, result = await self._job("export", state, {
                    "revision": state.revision, "source": source, "sha256": info.sha256})
                if result["status"] != 200:
                    raise PanelHTTPError(result["status"])
                path = API + "downloads/" + str(job_id)
                if (result.get("download") != path or result.get("source") != source or
                        digest(result.get("sha256")) != info.sha256 or
                        integer(result.get("bytes"), "export bytes", 1, state.max_bytes) != info.bytes):
                    raise ProtocolError("Export receipt guards disagree")
                response = await self._request("GET", "downloads/" + str(job_id), state=state,
                                               maximum=state.max_bytes)
                if (response.header("X-Panel-Session") != state.session_id or
                        response.header("X-Panel-SHA256") != info.sha256 or
                        response.header("Content-Disposition") != f"attachment; filename=panel-{source}.json" or
                        response.header("Content-Length") is None or len(response.body) != info.bytes or
                        hashlib.sha256(response.body).hexdigest() != info.sha256):
                    raise ProtocolError("Export content/header guards disagree")
                document = json_object(response.body, state.max_bytes)
                if (document.get("format") != "home-panel-runtime" or
                        type(document.get("schema_version")) is not int or document["schema_version"] != 1 or
                        integer(document.get("revision"), "document revision", 1, UINT32_MAX) != info.revision):
                    raise ProtocolError("Unsupported or inconsistent document envelope")
                return ExportedDocument(source, info.revision, info.sha256, response.body)
        except TimeoutError:
            raise OutcomeUnknown("Export timed out; refresh status, do not retry") from None

    async def validate(self, data: bytes) -> ValidationResult:
        if not isinstance(data, bytes) or not data:
            raise ValueError("Validation input must be nonempty bytes")
        try:
            async with asyncio.timeout(self._timeout), self._lock:
                state = await self._status()
                self._ready(state, "validate.v1")
                if len(data) > state.max_bytes:
                    raise ValueError("Validation input exceeds the device byte limit")
                _, result = await self._job("validate", state, data, raw=True)
                if result["status"] not in {200, 400}:
                    raise PanelHTTPError(result["status"])
                report = result.get("validation")
                if not isinstance(report, dict):
                    raise ProtocolError("Missing shared-validator report")
                model_status = integer(report.get("status"), "validation status")
                valid = result["status"] == 200
                if valid != (model_status == 0):
                    raise ProtocolError("Validation status disagrees with shared-validator report")
                return ValidationResult(valid, result["status"], model_status,
                    integer(report.get("model_error"), "model error"),
                    integer(report.get("revision"), "document revision", maximum=UINT32_MAX),
                    integer(report.get("rooms"), "room count"))
        except TimeoutError:
            raise OutcomeUnknown("Validation timed out; refresh status, do not retry") from None
