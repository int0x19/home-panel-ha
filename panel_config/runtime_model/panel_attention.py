"""Versioned presentation bindings for HA conditions and short-lived events."""

from dataclasses import dataclass
import re

from .panel_model import SocketReading, display_name, safe_id

MAX_ATTENTION_SOURCES = 16
SEVERITIES = ("info", "warning", "critical")
ATTENTION_UI_STYLE_FIELDS = """text_color muted_text_color accent_color attention_warning_color status_error_color
attention_badge_width attention_badge_gap attention_badge_icon_size header_height small_text_height normal_text_height
attention_row_height attention_row_gap attention_max_rows attention_filter_height attention_status_width
nav_button_width nav_button_height nav_icon_size""".split()


@dataclass(frozen=True)
class AttentionSource:
    id: str
    name: str
    entity: str | None
    room: str
    view: str
    severity: str
    auto_popup: bool
    wake: bool
    simulator: str | dict | None
    kind: str = "condition"
    ttl: int = 60

    @property
    def import_id(self):
        if self.kind != "condition":
            raise ValueError("Only condition sources import HA states directly")
        return SocketReading(self.entity, kind="binary").import_id


@dataclass(frozen=True)
class Attention:
    sources: tuple[AttentionSource, ...] = ()
    popup_cooldown: int = 10
    version: int = 1


def state_sample(value):
    if type(value) is bool:
        return "on" if value else "off"
    if isinstance(value, str) and value in ("on", "off", "unknown", "unavailable"):
        return value
    raise ValueError("Attention simulator values require a boolean or on/off/unknown/unavailable")


def event_sample(value, ttl):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {"event_id", "message", "age"}:
        raise ValueError("Event simulator supports event_id, message and age")
    event_id, message, age = value.get("event_id"), value.get("message", ""), value.get("age", 0)
    if not isinstance(event_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", event_id):
        raise ValueError("Event IDs require 1..64 ASCII letters/digits/_.:-")
    if not isinstance(message, str) or len(message.encode("utf-8")) > 128 or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in message):
        raise ValueError("Event message requires at most 128 UTF-8 bytes without control characters")
    if type(age) is not int or not 0 <= age < ttl:
        raise ValueError("Event simulator age must be nonnegative and less than ttl")
    return {"event_id": event_id, "message": message, "age": age}


def parse_attention(config, rooms, views):
    raw = config.get("attention")
    if raw is None and "attention" not in config:
        return Attention()
    if not isinstance(raw, dict) or set(raw) - {"version", "popup_cooldown", "sources"}:
        raise ValueError("attention supports version, popup_cooldown and sources")
    if type(raw.get("version")) is not int or raw["version"] not in (1, 2):
        raise ValueError("attention.version must be 1 or 2")
    version = raw["version"]
    cooldown = raw.get("popup_cooldown", 10)
    if type(cooldown) is not int or not 1 <= cooldown <= 3600:
        raise ValueError("attention.popup_cooldown must be 1..3600 seconds")
    sources = raw.get("sources")
    if not isinstance(sources, dict) or not 1 <= len(sources) <= MAX_ATTENTION_SOURCES:
        raise ValueError(f"attention.sources requires 1..{MAX_ATTENTION_SOURCES} definitions")
    room_ids, view_ids = {p.safe_id for p in rooms}, {v.id: v for v in views}
    if "attention" in room_ids:
        raise ValueError("Room ID attention is reserved when attention sources are configured")
    result, ids, samples = [], set(), {}
    for v in views:
        for w in v.widgets:
            for r in w.sensors:
                if r.binding.kind == "binary" and r.simulator is not None:
                    samples[r.binding.import_id] = state_sample(r.simulator)
    for key, source in sources.items():
        if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", key):
            raise ValueError("Attention IDs require 1..48 lowercase ASCII letters/digits/underscores, starting with a letter")
        allowed = {"name", "entity", "room", "view", "severity", "auto_popup", "wake", "simulator"}
        if version == 2:
            allowed |= {"kind", "ttl"}
        if not isinstance(source, dict) or set(source) - allowed:
            raise ValueError("Unknown attention source fields")
        kind = source.get("kind", "condition")
        if kind not in ("condition", "event", "plant"):
            raise ValueError("Attention kind must be condition, event or plant")
        entity = source.get("entity")
        ttl = source.get("ttl", 60)
        if kind in ("condition", "plant"):
            domain = "binary_sensor" if kind == "condition" else "plant"
            if "ttl" in source or not isinstance(entity, str) or not re.fullmatch(domain + r"\.[a-z0-9_]+", entity):
                raise ValueError(f"Attention {kind} sources require {domain}.* and no ttl")
            if entity in ids:
                raise ValueError("Each attention entity must have a single stable source ID")
            ids.add(entity)
        elif "entity" in source or type(ttl) is not int or not 1 <= ttl <= 3600:
            raise ValueError("Attention events require ttl 1..3600 seconds and no entity")
        name = display_name(source.get("name", key), "Attention name")
        if len(name) > 128:
            raise ValueError("Attention names must not exceed 128 characters")
        room, view = safe_id(source.get("room")), safe_id(source.get("view"))
        if room not in room_ids or view not in view_ids:
            raise ValueError("Attention room/view must reference a configured room/view")
        severity = source.get("severity", "warning")
        if not isinstance(severity, str) or severity not in SEVERITIES:
            raise ValueError("Attention severity must be info, warning or critical")
        auto, wake = source.get("auto_popup", False), source.get("wake", False)
        if type(auto) is not bool or type(wake) is not bool or (wake and not auto):
            raise ValueError("Attention auto_popup/wake require booleans; wake requires auto_popup")
        if "popup" not in view_ids[view].presentations:
            raise ValueError("Attention targets require a popup presentation")
        if kind == "plant" and not any(w.plant and w.plant.entity == entity for w in view_ids[view].widgets):
            raise ValueError("Plant attention target must contain the same plant entity")
        if kind == "condition":
            import_id = SocketReading(entity, kind="binary").import_id
            sample = state_sample(source["simulator"]) if "simulator" in source else samples.get(import_id, "unknown")
            if import_id in samples and samples[import_id] != sample:
                raise ValueError(f"Conflicting attention/view simulator values for {entity}")
        elif kind == "plant":
            if "simulator" in source:
                raise ValueError("Plant attention reuses the view's simulator data")
            sample = None
        else:
            sample = event_sample(source.get("simulator"), ttl)
        result.append(AttentionSource(key, name, entity, room, view, severity, auto, wake, sample, kind, ttl))
    return Attention(tuple(result), cooldown, version)


def validate_attention_layout(attention, style):
    if not attention.sources:
        return
    try:
        color = int(str(style["attention_warning_color"]), 0)
    except ValueError as error:
        raise ValueError("attention_warning_color requires a 24-bit color") from error
    if not 0 <= color <= 0xFFFFFF:
        raise ValueError("attention_warning_color requires a 24-bit color")
    if not 1 <= style["attention_max_rows"] <= 6:
        raise ValueError("attention_max_rows must be 1..6")
    if not 12 <= style["attention_badge_icon_size"] <= style["header_height"]:
        raise ValueError("Attention badge icon must fit the header")
    if style["attention_badge_width"] < style["attention_badge_icon_size"] + style["attention_badge_gap"] + 20:
        raise ValueError("Attention badge must fit its icon and a two-digit count")
    status = style["header_clock_width"] + 3 * (style["header_icon_size"] + style["header_status_gap"])
    if 320 - 2 * style["page_padding"] - status - style["attention_badge_width"] - 2 * style["control_gap"] < style["normal_text_height"]:
        raise ValueError("Attention badge leaves insufficient room title width")
    minimum_row = style["normal_text_height"] + style["small_text_height"] + 2 * (style["control_gap"] + style["control_border_width"])
    if style["attention_row_height"] < minimum_row or style["attention_status_width"] < 68:
        raise ValueError("Attention rows must fit name, room and status")
    if style["attention_filter_height"] < style["small_text_height"] + 2 * style["control_border_width"]:
        raise ValueError("Attention filters must fit their captions")
    body = 480 - 2 * style["page_padding"] - style["control_height"] - style["page_gap"]
    needed = style["attention_filter_height"] + style["small_text_height"] + style["attention_row_height"] + style["nav_button_height"] + 3 * style["page_gap"]
    if needed > body:
        raise ValueError("Attention list does not fit without scrolling")
    if any(s.kind == "event" for s in attention.sources):
        width = style["attention_event_dismiss_width"]
        # Match the fixed 14 px caption and icon spacing in attention_dismiss.h.
        minimum = 56 + style["attention_badge_icon_size"] + style["control_gap"] // 2 + 2 * (style["control_gap"] + style["control_border_width"])
        header = 320 - 2 * (style["view_popup_inset"] + style["page_padding"] + style["control_border_width"])
        if width < minimum or header - style["back_button_width"] - 2 * style["control_gap"] - width < 96:
            raise ValueError("Event Dismiss control must fit its caption and leave room for the frozen event title")
        if style["control_height"] < max(style["normal_text_height"], style["attention_badge_icon_size"]) + 2 * (style["control_gap"] + style["control_border_width"]):
            raise ValueError("Event Dismiss icon and caption do not fit the header height")
