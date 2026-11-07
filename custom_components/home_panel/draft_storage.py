"""Bounded HA-only draft checkpoint, optimistic concurrency, no device I/O."""

import asyncio
from copy import deepcopy
import hashlib
from pathlib import Path
import re
import secrets
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from ._core import encode_document
from ._core import (
    DecoderInventory, MAX_DOCUMENT_BYTES, MAX_METADATA_BYTES, ProtocolError, Source,
    boolean, device_identifier, digest, integer, json_object, names,
)

DATA_KEY = DOMAIN + "_drafts"
MAX_STORAGE_BYTES = 512 * 1024
MAX_GENERATION = 2**53 - 1
_ID = re.compile(r"[a-z_][a-z0-9_]{0,63}")
_ENVELOPE = {"format", "schema_version", "revision", "requires", "panel", "style", "rooms", "views", "attention"}
_CAPS = {"schema_versions", "features", "widget_types", "room_kinds", "display", "limits", "validation",
         "limits_measured_on_device", "preview_compiled", "assets_inventory_complete"}


class DraftError(Exception):
    """Fixed error codes only, never document/credential/exception text."""
    code = "draft_error"


class DraftConflict(DraftError):
    code = "draft_conflict"


class DraftBusy(DraftError):
    code = "draft_busy"


class DraftInvalid(DraftError):
    code = "invalid_draft"


class DraftStorageError(DraftError):
    code = "draft_storage_error"


def _text(value: Any) -> bytes:
    if not isinstance(value, str) or not 0 < len(value) <= MAX_DOCUMENT_BYTES:
        raise DraftInvalid
    try:
        data = value.encode("utf-8")
    except UnicodeError:
        raise DraftInvalid from None
    if len(data) > MAX_DOCUMENT_BYTES:
        raise DraftInvalid
    return data


def _envelope(data: bytes) -> dict:
    """Framing/UI shape only; never claim shared native model validation here."""
    value = json_object(data, MAX_DOCUMENT_BYTES)
    if (set(value) != _ENVELOPE or value["format"] != "home-panel-runtime" or
            type(value["schema_version"]) is not int or value["schema_version"] != 1):
        raise DraftInvalid
    integer(value["revision"], "draft model revision", 1, 0xFFFFFFFF)
    names(value["requires"], "required features", 64)
    if (not isinstance(value["rooms"], list) or not 1 <= len(value["rooms"]) <= 128 or
            not isinstance(value["views"], list) or not isinstance(value["attention"], dict) or
            not isinstance(value["panel"], dict) or not isinstance(value["style"], dict)):
        raise DraftInvalid
    for room in value["rooms"]:
        if (not isinstance(room, dict) or not isinstance(room.get("id"), str) or not _ID.fullmatch(room["id"]) or
                not isinstance(room.get("name"), str) or not isinstance(room.get("groups"), dict) or
                not isinstance(room.get("widgets"), list)):
            raise DraftInvalid
        for widget in room["widgets"]:
            if (not isinstance(widget, dict) or not isinstance(widget.get("id"), str) or not _ID.fullmatch(widget["id"]) or
                    not isinstance(widget.get("type"), str) or not isinstance(widget.get("settings"), dict) or
                    not isinstance(widget["settings"].get("name"), str)):
                raise DraftInvalid
    return value


def _capabilities(value: Any) -> dict:
    if not isinstance(value, dict) or set(value) != _CAPS or len(encode_document(value)) > MAX_METADATA_BYTES:
        raise DraftInvalid
    if (not isinstance(value["schema_versions"], list) or not 1 <= len(value["schema_versions"]) <= 8 or
            any(type(v) is not int or v != 1 for v in value["schema_versions"])):
        raise DraftInvalid
    for key, maximum in (("features", 64), ("widget_types", 64), ("room_kinds", 16)):
        names(value[key], key, maximum)
    display, limits = value["display"], value["limits"]
    if not isinstance(display, dict) or display != {"width": 320, "height": 480} or not isinstance(limits, dict):
        raise DraftInvalid
    for key in ("document_bytes", "rooms", "widgets", "room_pages", "string_bytes"):
        integer(limits.get(key), key, 1, MAX_DOCUMENT_BYTES)
    DecoderInventory.parse(value["validation"])
    for key in ("limits_measured_on_device", "preview_compiled", "assets_inventory_complete"):
        boolean(value[key], key)
    return deepcopy(value)


def prepare_record(document: str, original: dict, capabilities: dict) -> dict:
    """Checkpoint unvalidated model text; original digest is integrity, not attestation."""
    try:
        model = _envelope(_text(document))
        caps = _capabilities(capabilities)
        if not isinstance(original, dict) or set(original) != {"source", "revision", "sha256", "document"}:
            raise DraftInvalid
        Source(original["source"])
        raw = _text(original["document"])
        source = _envelope(raw)
        digest(original["sha256"])
        integer(original["revision"], "original revision", 1, 0xFFFFFFFF)
        if (source["revision"] != original["revision"] or
                hashlib.sha256(raw).hexdigest() != original["sha256"]):
            raise DraftInvalid
        encoded = encode_document(model)
        if len(encoded) > caps["limits"]["document_bytes"]:
            raise DraftInvalid
        return {"document": encoded.decode(), "sha256": hashlib.sha256(encoded).hexdigest(),
                "original": deepcopy(original), "capabilities": caps}
    except (ValueError, TypeError, KeyError, ProtocolError, RecursionError):
        raise DraftInvalid from None


def _checksum(payload: dict) -> str:
    return hashlib.sha256(encode_document(payload)).hexdigest()


def _read(path: str, key: str) -> dict | None:
    """Bound disk reads before Store's loader; preserve corrupt/future files in place."""
    try:
        with Path(path).open("rb") as file:
            raw = file.read(MAX_STORAGE_BYTES + 1)
    except FileNotFoundError:
        return None
    value = json_object(raw, MAX_STORAGE_BYTES)
    if (set(value) != {"version", "minor_version", "key", "data"} or
            type(value["version"]) is not int or value["version"] != 1 or
            type(value["minor_version"]) is not int or value["minor_version"] != 1 or value["key"] != key):
        raise DraftStorageError
    return value["data"]


class DraftRepository:
    def __init__(self, hass: HomeAssistant, entry_id: str, panel_id: str):
        self.hass = hass
        self.panel_id = device_identifier(panel_id)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", entry_id):
            raise DraftStorageError
        self.store: Store[dict] = Store(hass, 1, f"{DOMAIN}.draft.{entry_id}", private=True,
                                         atomic_writes=True, serialize_in_event_loop=False)
        self._session = secrets.token_hex(16)
        self._state = None
        self._observed_generation = 0
        self._lock = asyncio.Lock()
        self._pending = None
        self._removed = False

    def _validate_state(self, state: Any) -> dict:
        if not isinstance(state, dict) or set(state) != {"panel_id", "generation", "record", "checksum"}:
            raise DraftStorageError
        payload = {k: v for k, v in state.items() if k != "checksum"}
        integer(state["generation"], "HA draft generation", 0, MAX_GENERATION)
        if state["panel_id"] != self.panel_id or state["checksum"] != _checksum(payload):
            raise DraftStorageError
        if state["record"] is not None:
            record = state["record"]
            if not isinstance(record, dict) or set(record) != {"document", "sha256", "original", "capabilities"}:
                raise DraftStorageError
            expected = prepare_record(record["document"], record["original"], record["capabilities"])
            if expected != record:
                raise DraftStorageError
        return state

    async def _load(self) -> None:
        if self._removed:
            raise DraftStorageError
        try:
            before = await self.hass.async_add_executor_job(_read, self.store.path, self.store.key)
            if before is None:
                if self._observed_generation:
                    raise DraftStorageError
                payload = {"panel_id": self.panel_id, "generation": 0, "record": None}
                self._state = {**payload, "checksum": _checksum(payload)}
                return
            await self.hass.async_add_executor_job(self._validate_state, before)
            if before["generation"] < self._observed_generation:
                raise DraftStorageError
            loaded = await self.store.async_load()
            if loaded != before:
                raise DraftStorageError
            self._state = before
            self._observed_generation = before["generation"]
        except (OSError, ValueError, TypeError, KeyError, ProtocolError, DraftInvalid):
            raise DraftStorageError from None

    def _snapshot(self) -> dict:
        return {"version": 1, "generation": self._state["generation"],
                "revision": f"{self._session}:{self._state['generation']}",
                "record": deepcopy(self._state["record"]), "model_validated": False, "deployment_ready": False}

    async def get(self) -> dict:
        async with self._lock:
            await self._load()
            return self._snapshot()

    async def write(self, revision: str, record: dict | None) -> dict:
        if self._pending is not None:
            raise DraftBusy
        # The tracked commit owns the lock even if its WS waiter disconnects.
        self._pending = self.hass.async_create_task(self._commit(revision, record), "Home Panel HA draft checkpoint")
        task = self._pending
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                self._pending = None
            else:
                task.add_done_callback(self._finished)

    def _finished(self, task):
        if not task.cancelled():
            task.exception()
        if self._pending is task:
            self._pending = None

    async def _commit(self, revision: str, record: dict | None) -> dict:
        async with self._lock:
            await self._load()
            if revision != f"{self._session}:{self._state['generation']}":
                raise DraftConflict
            if self._state["generation"] >= MAX_GENERATION:
                raise DraftStorageError
            payload = {"panel_id": self.panel_id, "generation": self._state["generation"] + 1, "record": deepcopy(record)}
            next_state = {**payload, "checksum": _checksum(payload)}
            await self.hass.async_add_executor_job(self._validate_state, next_state)
            try:
                # Detect out-of-band modification/deletion before overwriting it.
                disk = await self.hass.async_add_executor_job(_read, self.store.path, self.store.key)
                if disk != self._state and not (disk is None and self._state["generation"] == 0):
                    raise DraftStorageError
                await self.store.async_save(next_state)
                actual = await self.hass.async_add_executor_job(_read, self.store.path, self.store.key)
                if actual != next_state:
                    raise DraftStorageError
            except (OSError, ValueError, TypeError, KeyError, ProtocolError, DraftInvalid):
                raise DraftStorageError from None
            self._state = next_state
            self._observed_generation = next_state["generation"]
            return self._snapshot()

    async def remove(self) -> None:
        async with self._lock:
            await self.store.async_remove()
            self._removed = True


def repository(hass: HomeAssistant, entry) -> DraftRepository:
    owners = hass.data.setdefault(DATA_KEY, {})
    if entry.entry_id not in owners:
        owners[entry.entry_id] = DraftRepository(hass, entry.entry_id, entry.unique_id)
    owner = owners[entry.entry_id]
    if owner.panel_id != entry.unique_id:
        raise DraftStorageError
    return owner


async def remove_repository(hass: HomeAssistant, entry) -> None:
    owners = hass.data.get(DATA_KEY, {})
    if owner := owners.get(entry.entry_id):
        await owner.remove()
        owners.pop(entry.entry_id, None)
    elif re.fullmatch(r"[A-Za-z0-9_-]{1,64}", entry.entry_id):
        await Store(hass, 1, f"{DOMAIN}.draft.{entry.entry_id}").async_remove()
