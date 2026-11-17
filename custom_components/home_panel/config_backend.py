"""One imported baseline and checked digest, sharing the existing panel job gate."""

import asyncio
from dataclasses import dataclass, replace
import hashlib
import secrets

from homeassistant.core import HomeAssistant

from ._core import (
    CandidateConflict, InvalidInput, MAX_DOCUMENT_BYTES, PanelReadBackend,
    RuntimeSnapshot, Source, decode_document, encode_document, validate_document,
)


def candidate_available(snapshot: RuntimeSnapshot) -> bool:
    state = snapshot.status
    return (state.storage == "flash-nvs" and state.storage_ready and not state.busy and
            not state.restarting and state.flash_write is not None and state.flash_write.ready and
            state.write_base_sha256 is not None and
            {"capabilities.v1", "flash-maintenance.v1", "write-base.v1", "export.v1"} <= state.features)


def _canonical(data: bytes) -> bytes:
    try:
        model = decode_document(data)
        validate_document(model)
        return encode_document(model)
    except ValueError:
        raise InvalidInput("Invalid candidate model") from None


@dataclass(frozen=True)
class ImportedBase:
    token: str
    snapshot: RuntimeSnapshot
    checked_sha256: str | None = None


@dataclass(frozen=True)
class ActivationIntent:
    snapshot: RuntimeSnapshot
    token: str | None
    state: str = "ready"
    observed: RuntimeSnapshot | None = None


def apply_available(snapshot: RuntimeSnapshot) -> bool:
    boot = snapshot.status.flash_boot
    return (candidate_available(snapshot) and boot is not None and boot.apply_enabled and
            boot.phase in {1, 4} and snapshot.status.file(Source.CANDIDATE).valid and
            int(snapshot.status.storage_generation) <= 2**64 - 5)


class PanelConfigBackend(PanelReadBackend):
    """One per entry; explicit configuration jobs, no automatic write replay."""

    def __init__(self, hass: HomeAssistant, client):
        super().__init__(client)
        self._hass = hass
        self._imported: ImportedBase | None = None
        self._activation: ActivationIntent | None = None

    @property
    def import_id(self) -> str | None:
        return self._imported.token if self._imported else None

    @property
    def apply_id(self) -> str | None:
        return self._activation.token if self._activation else None

    def activation(self, current: RuntimeSnapshot) -> dict | None:
        if self._activation is None:
            return None
        target = self._activation.snapshot.status.file(Source.CANDIDATE)
        state = self._activation.state if current == self._activation.observed else "unknown"
        return {"state":state, "revision":target.revision,
                "sha256":target.sha256, "bytes":target.bytes}

    def _prepare_apply(self, snapshot):
        self._activation = (ActivationIntent(snapshot, secrets.token_urlsafe(24), observed=snapshot)
                            if apply_available(snapshot) else None)

    async def import_document(self, source):
        checked = await super().import_document(source)
        self._imported = (ImportedBase(secrets.token_urlsafe(24), checked.snapshot)
                          if candidate_available(checked.snapshot) else None)
        if Source(source) == Source.CANDIDATE and apply_available(checked.snapshot):
            self._prepare_apply(checked.snapshot)
        elif self._activation is not None and self._activation.token is not None:
            self._activation = None
        return checked

    def _base(self, import_id: str) -> ImportedBase:
        if self._imported is None or import_id != self._imported.token:
            raise CandidateConflict("Import the panel configuration again before sending")
        return self._imported

    @staticmethod
    def _unchanged(base, actual):
        if base.snapshot != actual:
            raise CandidateConflict("Imported panel snapshot changed; import and review again")

    async def prepare_candidate(self, data: bytes, import_id: str):
        if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_DOCUMENT_BYTES:
            raise InvalidInput("Candidate input exceeds its byte limit")
        async with self._operation(job=True):
            base = self._base(import_id)
            self._imported = replace(base, checked_sha256=None)
            before = await self._client.snapshot()
            self._unchanged(base, before)
            if len(data) > before.status.max_bytes:
                raise InvalidInput("Candidate exceeds the panel byte limit")
            canonical = await self._hass.async_add_executor_job(_canonical, data)
            if len(canonical) > before.status.max_bytes:
                raise InvalidInput("Candidate exceeds the panel byte limit")
            self._job_attempted = True
            validation = await self._client.validate(canonical)
            self._check_report(canonical, validation)
            after = await self._client.snapshot()
            self._unchanged(base, after)
            if validation.valid:
                self._imported = replace(base, checked_sha256=hashlib.sha256(canonical).hexdigest())
            return canonical, validation, after

    async def send_candidate(self, data: bytes, import_id: str):
        if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_DOCUMENT_BYTES:
            raise InvalidInput("Candidate input exceeds its byte limit")
        async with self._operation(job=True):
            base = self._base(import_id)
            if base.checked_sha256 is None or hashlib.sha256(data).hexdigest() != base.checked_sha256:
                raise CandidateConflict("Check these exact candidate bytes on the panel before sending")
            # Single-use import: cancellation/lost replies must not revive an old write.
            self._imported = None
            self._job_attempted = True
            try:
                result = await self._client.send_candidate(data, expected=base.snapshot)
            except ValueError:
                raise InvalidInput("Candidate failed negotiated model checks") from None
            self._prepare_apply(result.snapshot)
            return result

    async def apply_candidate(self, apply_id: str):
        async with self._operation(job=True):
            intent = self._activation
            if intent is None or intent.token is None or intent.token != apply_id:
                raise CandidateConflict("Import and review the saved candidate before Apply")
            # Keep intent, never permission, after starting a potentially persistent request.
            self._activation = replace(intent, token=None, state="unknown")
            self._imported = None
            self._job_attempted = True
            try:
                receipt = await self._client.apply_candidate(expected=intent.snapshot)
            except ValueError:
                raise InvalidInput("Saved candidate failed negotiated model checks") from None
            self._activation = replace(self._activation, state="restarting", observed=receipt.snapshot)
            return receipt

    async def inspect(self) -> RuntimeSnapshot:
        intent = self._activation
        if intent is None or intent.token is not None:
            return await super().inspect()
        async with self._operation():
            self._job_attempted = True  # Inspection may verify the active export job.
            try:
                result = await self._client.inspect_activation(expected=intent.snapshot)
            except (Exception, asyncio.CancelledError):
                self._activation = None if self.closed else replace(intent, token=None, state="unknown", observed=None)
                raise
            self._activation = replace(intent, token=None, state=result.state.value, observed=result.snapshot)
            if not result.snapshot.status.busy and not result.snapshot.status.restarting:
                self.requires_status_refresh = False
            return result.snapshot

    async def async_close(self):
        self._imported = None
        self._activation = None
        await super().async_close()
