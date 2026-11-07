"""Bounded transport framing; widget/schema validation stays in the shared model."""

from dataclasses import dataclass, field
from enum import StrEnum
import json
import math
import re
from typing import Mapping, Protocol

API = "/panel/runtime/api/"
MAX_DOCUMENT_BYTES = 65536
MAX_METADATA_BYTES = 16384
UINT32_MAX = 4294967295
_DIGEST = re.compile(r"[0-9a-f]{64}")
_NONCE = re.compile(r"[0-9a-f]{32}")
_FEATURE = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_DEVICE_ID = re.compile(r"esp32-efuse-([0-9a-f]{12})")


class PanelError(Exception):
    """Errors contain fixed descriptions, never device text, URLs or credentials."""


class ProtocolError(PanelError):
    pass


class TransportError(PanelError):
    pass


class IdentityMismatch(PanelError):
    pass


class OutcomeUnknown(PanelError):
    """An ephemeral job may have run; do not automatically resubmit it."""


class PanelHTTPError(PanelError):
    def __init__(self, status: int):
        self.status = status
        super().__init__(f"Panel API returned HTTP {status}")


class Source(StrEnum):
    ACTIVE = "active"
    CANDIDATE = "candidate"
    BACKUP = "backup"


@dataclass(frozen=True)
class HTTPResponse:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes = field(repr=False)

    def header(self, name: str) -> str | None:
        values = [value for key, value in self.headers if key.lower() == name.lower()]
        if len(values) > 1:
            raise ProtocolError("Duplicate protocol response header")
        return values[0] if values else None


class Transport(Protocol):
    async def request(self, method: str, path: str, *, headers: Mapping[str, str],
                      body: bytes | None, max_bytes: int) -> HTTPResponse: ...


def integer(value, label: str, minimum=0, maximum=UINT32_MAX - 1) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ProtocolError(f"Invalid {label}")
    return value


def boolean(value, label: str) -> bool:
    if type(value) is not bool:
        raise ProtocolError(f"Invalid {label}")
    return value


def digest(value) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ProtocolError("Invalid content digest")
    return value


def nonce(value) -> str:
    if not isinstance(value, str) or not _NONCE.fullmatch(value):
        raise ProtocolError("Invalid runtime session")
    return value


def device_identifier(value) -> str:
    match = _DEVICE_ID.fullmatch(value) if isinstance(value, str) else None
    if not match or int(match[1][:2], 16) & 1 or int(match[1], 16) == 0:
        raise ProtocolError("Invalid stable panel identity")
    return value


def names(value, label: str, maximum=256) -> tuple[str, ...]:
    if (not isinstance(value, list) or len(value) > maximum or
            any(not isinstance(item, str) or not _FEATURE.fullmatch(item) for item in value) or
            len(set(value)) != len(value)):
        raise ProtocolError(f"Invalid {label}")
    return tuple(value)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("Duplicate JSON key")
        result[key] = value
    return result


def _constant(_value):
    raise ProtocolError("Non-finite JSON value")


def json_object(data: bytes, maximum: int = MAX_METADATA_BYTES) -> dict:
    if not isinstance(data, bytes) or not data or len(data) > maximum:
        raise ProtocolError("Empty or oversized JSON response")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_object, parse_constant=_constant)
        pending, nodes = [(value, 0)], 0
        while pending:
            item, depth = pending.pop()
            nodes += 1
            if depth > 16 or nodes > 16384:
                raise ProtocolError("Response exceeds JSON depth/node budget")
            if isinstance(item, str):
                item.encode("utf-8")
            elif isinstance(item, dict):
                pending.extend((entry, depth + 1) for pair in item.items() for entry in pair)
            elif isinstance(item, list):
                pending.extend((entry, depth + 1) for entry in item)
            elif isinstance(item, float) and not math.isfinite(item):
                raise ProtocolError("Non-finite JSON value")
    except (ValueError, UnicodeError, RecursionError):
        raise ProtocolError("Invalid JSON response") from None
    if not isinstance(value, dict):
        raise ProtocolError("Expected JSON object")
    return value


@dataclass(frozen=True)
class FileInfo:
    present: bool
    valid: bool
    status: int
    model_status: int
    bytes: int
    revision: int
    sha256: str

    @classmethod
    def parse(cls, value, maximum: int):
        if not isinstance(value, dict):
            raise ProtocolError("Missing file metadata")
        present = boolean(value.get("present"), "file presence")
        valid = boolean(value.get("valid"), "file validity")
        size = integer(value.get("bytes"), "file bytes", maximum=2**64 - 1)
        revision = integer(value.get("revision"), "document revision", maximum=UINT32_MAX)
        sha = value.get("sha256")
        if sha != "":
            digest(sha)
        if valid and (not present or not 0 < size <= maximum or not revision or not sha):
            raise ProtocolError("Inconsistent valid file metadata")
        return cls(present, valid, integer(value.get("status"), "file status"),
                   integer(value.get("model_status"), "model status"), size, revision, sha)


@dataclass(frozen=True)
class RuntimeStatus:
    session_id: str = field(repr=False)
    revision: int
    max_bytes: int
    features: frozenset[str]
    sd_ready: bool
    busy: bool
    restarting: bool
    dispatch_enabled: bool
    loaded_source: str
    loaded_revision: int
    export_lifetime_ms: int | None
    files: tuple[FileInfo, ...]
    device_id: str | None = None

    @property
    def management_ready(self) -> bool:
        return False

    @property
    def authority(self) -> str:
        return "unreported"

    def file(self, source: Source) -> FileInfo:
        return self.files[list(Source).index(Source(source))]

    @classmethod
    def parse(cls, value: dict):
        if type(value.get("version")) is not int or value["version"] != 1:
            raise ProtocolError("Unsupported runtime API version")
        session = nonce(value.get("session_id"))
        if value.get("csrf") != session:
            raise ProtocolError("Runtime session and nonce disagree")
        maximum = integer(value.get("max_bytes"), "input ceiling", 1, MAX_DOCUMENT_BYTES)
        features = names(value.get("features", []), "API features", 64)
        device_id = None
        if "capabilities.v1" in features and value.get("device_id") is not None:
            device_id = device_identifier(value["device_id"])
        lifetime = value.get("export_lifetime_ms")
        if "export.v1" in features:
            lifetime = integer(lifetime, "export lifetime", 1)
        loaded = value.get("loaded_source")
        if not isinstance(loaded, str) or loaded not in {"builtin", "file", "backup"}:
            raise ProtocolError("Invalid loaded source")
        return cls(session, integer(value.get("revision"), "operation revision"), maximum,
                   frozenset(features), boolean(value.get("sd_ready"), "SD status"),
                   boolean(value.get("busy"), "busy status"), boolean(value.get("restarting"), "restart status"),
                   boolean(value.get("dispatch_enabled"), "dispatch status"), loaded,
                   integer(value.get("loaded_revision"), "loaded document revision", maximum=UINT32_MAX), lifetime,
                   tuple(FileInfo.parse(value.get(key), maximum) for key in (*Source, "temporary")), device_id)


@dataclass(frozen=True)
class DecoderInventory:
    action_icons: tuple[str, ...]
    interactions: tuple[str, ...]
    font_sizes: tuple[int, ...]
    layout_keys: tuple[str, ...]
    theme_keys: tuple[str, ...]

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict):
            raise ProtocolError("Missing decoder inventory")
        fonts = value.get("font_sizes")
        if not isinstance(fonts, list) or not 1 <= len(fonts) <= 16:
            raise ProtocolError("Invalid font inventory")
        fonts = tuple(integer(size, "font size", 1, 128) for size in fonts)
        if len(set(fonts)) != len(fonts):
            raise ProtocolError("Duplicate font size")
        return cls(names(value.get("action_icons"), "action icons", 64),
                   names(value.get("interactions"), "action interactions", 16), fonts,
                   names(value.get("layout_keys"), "layout keys"), names(value.get("theme_keys"), "theme keys"))


@dataclass(frozen=True)
class RuntimeCapabilities:
    device_id: str
    session_id: str = field(repr=False)
    schema_versions: tuple[int, ...]
    features: frozenset[str]
    widget_types: tuple[str, ...]
    room_kinds: tuple[str, ...]
    width: int
    height: int
    limits: tuple[tuple[str, int], ...]
    limits_measured_on_device: bool
    validation: DecoderInventory
    preview_compiled: bool
    assets_inventory_complete: bool

    @property
    def management_ready(self) -> bool:
        return False

    @property
    def deployment_ready(self) -> bool:
        return False

    @property
    def authority(self) -> str:
        return "unmanaged"

    def limit(self, name: str) -> int:
        return dict(self.limits)[name]

    @classmethod
    def parse(cls, value):
        if (value.get("format") != "home-panel-capabilities" or
                integer(value.get("metadata_version"), "metadata version", 1) != 1 or
                integer(value.get("protocol_version"), "protocol version", 1) != 1 or
                value.get("target") != "esp32-action-preview" or value.get("config_format") != "home-panel-runtime" or
                value.get("identity_source") != "esp32-efuse-mac48"):
            raise ProtocolError("Unsupported capability profile")
        schemas = value.get("schema_versions")
        if not isinstance(schemas, list) or not 1 <= len(schemas) <= 8:
            raise ProtocolError("Invalid schema inventory")
        schemas = tuple(integer(version, "schema version", 1) for version in schemas)
        if len(set(schemas)) != len(schemas):
            raise ProtocolError("Duplicate schema version")
        display, limits, runtime = value.get("display"), value.get("limits"), value.get("runtime")
        assets, authority = value.get("assets"), value.get("authority")
        if not all(isinstance(item, dict) for item in (display, limits, runtime, assets, authority)):
            raise ProtocolError("Missing capability sections")
        preview = boolean(runtime.get("preview_compiled"), "preview compilation")
        for state in (runtime.get("production_rooms"), runtime.get("dispatch_enabled"), value.get("management_ready"),
                      value.get("deployment_ready"), authority.get("enforced"), assets.get("upload")):
            if boolean(state, "unsupported management/dispatch flag"):
                raise ProtocolError("Unsupported managed/production capability profile")
        if authority.get("mode") != "unmanaged" or assets.get("source") != "firmware":
            raise ProtocolError("Unsupported authority/asset profile")
        fields = ("document_bytes", "scratch_bytes", "model_bytes", "presentation_bytes", "rooms", "room_pages",
                  "widgets", "entity_bindings", "subscriptions", "views", "attention_sources", "string_bytes",
                  "id_bytes", "depth", "nodes")
        parsed_limits = tuple((key, integer(limits.get(key), "capability limit")) for key in fields)
        if not 0 < limits["document_bytes"] <= MAX_DOCUMENT_BYTES:
            raise ProtocolError("Unsupported document ceiling")
        return cls(device_identifier(value.get("device_id")), nonce(value.get("session_id")), schemas,
                   frozenset(names(value.get("features"), "configuration features", 64)),
                   names(value.get("widget_types"), "widget types", 64), names(value.get("room_kinds"), "room kinds", 16),
                   integer(display.get("width"), "display width", 1, 4096),
                   integer(display.get("height"), "display height", 1, 4096), parsed_limits,
                   boolean(value.get("limits_measured_on_device"), "measured limits flag"),
                   DecoderInventory.parse(value.get("validation")), preview,
                   boolean(assets.get("inventory_complete"), "asset inventory flag"))


@dataclass(frozen=True)
class RuntimeSnapshot:
    status: RuntimeStatus
    capabilities: RuntimeCapabilities


@dataclass(frozen=True)
class ExportedDocument:
    source: Source
    revision: int
    sha256: str
    data: bytes = field(repr=False)


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    status: int
    model_status: int
    model_error: int
    document_revision: int
    rooms: int
