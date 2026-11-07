"""Bounded read/check transactions shared by all HA sessions for one panel."""

import asyncio
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass

from .client import PanelConfigClient
from .protocol import (
    MAX_DOCUMENT_BYTES, OutcomeUnknown, PanelError, ProtocolError, RuntimeSnapshot,
    Source, TransportError, ValidationResult, ExportedDocument, json_object,
)

OPERATION_TIMEOUT = 45.0


class BackendBusy(PanelError):
    pass


class BackendClosed(PanelError):
    pass


class RefreshRequired(PanelError):
    pass


class ReadConflict(PanelError):
    pass


class InvalidInput(PanelError):
    pass


class InvalidImport(PanelError):
    pass


@dataclass(frozen=True)
class CheckedExport:
    document: ExportedDocument
    validation: ValidationResult
    snapshot: RuntimeSnapshot


@dataclass(frozen=True)
class CheckedInput:
    validation: ValidationResult
    snapshot: RuntimeSnapshot


class PanelReadBackend:
    """No persistent writes, automatic job retry or retained document buffers."""

    def __init__(self, client: PanelConfigClient):
        self._client = client
        self._task: asyncio.Task | None = None
        self._job_attempted = False
        self.requires_status_refresh = False
        self.closed = False

    @property
    def busy(self) -> bool:
        return self._task is not None

    @asynccontextmanager
    async def _operation(self, *, job=False):
        if self.closed:
            raise BackendClosed("Panel integration is unloaded")
        if self.busy:
            raise BackendBusy("Another read/check operation is in progress")
        if job and self.requires_status_refresh:
            raise RefreshRequired("Refresh status before another read/check job")
        self._task = asyncio.current_task()
        self._job_attempted = False
        try:
            async with asyncio.timeout(OPERATION_TIMEOUT):
                yield
        except TimeoutError:
            if self._job_attempted:
                self.requires_status_refresh = True
                raise OutcomeUnknown("Read/check timed out; refresh status, do not retry") from None
            raise TransportError("Panel metadata timed out") from None
        except (Exception, asyncio.CancelledError):
            if self._job_attempted:
                self.requires_status_refresh = True
            raise
        finally:
            self._task = None
            self._job_attempted = False

    async def async_close(self):
        self.closed = True
        task = self._task
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def inspect(self) -> RuntimeSnapshot:
        async with self._operation():
            snapshot = await self._client.snapshot()
            if not snapshot.status.busy and not snapshot.status.restarting:
                self.requires_status_refresh = False
            return snapshot

    @staticmethod
    def _same_boot(before: RuntimeSnapshot, after: RuntimeSnapshot):
        if before.capabilities != after.capabilities:
            raise ReadConflict("Panel boot or capabilities changed during read/check")

    @staticmethod
    def _check_report(data: bytes, report: ValidationResult):
        if not report.valid:
            return
        document = json_object(data, MAX_DOCUMENT_BYTES)
        if (document.get("format") != "home-panel-runtime" or
                type(document.get("schema_version")) is not int or document["schema_version"] != 1 or
                type(document.get("revision")) is not int or document["revision"] != report.document_revision or
                report.document_revision < 1 or report.rooms < 1 or
                not isinstance(document.get("rooms"), list) or len(document["rooms"]) != report.rooms):
            raise ProtocolError("Validator report and document envelope disagree")

    async def import_document(self, source: Source) -> CheckedExport:
        source = Source(source)
        async with self._operation(job=True):
            before = await self._client.snapshot()
            self._job_attempted = True
            exported = await self._client.export(source)
            validation = await self._client.validate(exported.data)
            self._check_report(exported.data, validation)
            if not validation.valid:
                raise InvalidImport("Export failed the panel shared validator")
            after = await self._client.snapshot()
            self._same_boot(before, after)
            info = before.status.file(source)
            if (info != after.status.file(source) or not info.valid or info.bytes != len(exported.data) or
                    info.sha256 != exported.sha256 or info.revision != exported.revision):
                raise ReadConflict("Source changed during import")
            return CheckedExport(exported, validation, after)

    async def check_document(self, data: bytes) -> CheckedInput:
        if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_DOCUMENT_BYTES:
            raise InvalidInput("Expected nonempty UTF-8 text within the hard byte limit")
        async with self._operation(job=True):
            before = await self._client.snapshot()
            if len(data) > before.status.max_bytes:
                raise InvalidInput("Input exceeds the panel byte limit")
            self._job_attempted = True
            validation = await self._client.validate(data)
            self._check_report(data, validation)
            after = await self._client.snapshot()
            self._same_boot(before, after)
            return CheckedInput(validation, after)
