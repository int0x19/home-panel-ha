"""Host-side versioned logical configuration contract; not an ESP32 loader yet."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re

from .panel_attention import parse_attention, validate_attention_layout
from .panel_actions import ACTION_SERVICES, SCRIPT_CONTROLS_FEATURE, action_profile
from .panel_runtime_pages import (ACTION_PAGES_FEATURE, action_page_capacity, room_available_height,
                                 room_page_slices)
from .panel_backlight import parse_backlight_settings
from .panel_header import header_timezone
from .panel_model import (layout_keys, light_tile_rows, parse_pages,
                         display_name, validate_resolved_style, safe_id, sensor_group_rows, system_page_name,
                         theme_keys, validate_socket_layout)
from .panel_plant import collect_plants, plant_tile_bindings
from .panel_views import parse_views, validate_views_layout
from ..json_codec import encode_document

FORMAT = "home-panel-runtime"
SCHEMA_VERSION = 1
PROTOCOL_VERSION = 1
ROOM_WIDGET_TYPES = ("sensor", "status", "light", "socket", "climate", "humidifier", "plant", "action")
VIEW_WIDGET_TYPES = ("readings", "plant")
WIDGET_TYPES = (*ROOM_WIDGET_TYPES, "readings")
FEATURES = frozenset({"rooms.v1", "style.v1", "sensor-groups.v1", "views.v1",
                      "attention.v1", "attention.v2", ACTION_PAGES_FEATURE, SCRIPT_CONTROLS_FEATURE,
                      *(f"widget.{kind}" for kind in WIDGET_TYPES)})
_ID = re.compile(r"[a-z_][a-z0-9_]{0,63}")
_ENTITY_FIELDS = {"entity", "name", "unit", "device_class", "group", "light_type",
                  "min_color_temperature", "max_color_temperature", "climate", "humidifier",
                  "widget", "socket", "plant", "action"}
_TYPE_FIELDS = {
    "sensor": {"unit", "device_class", "group"}, "status": {"unit", "device_class"},
    "light": {"light_type", "min_color_temperature", "max_color_temperature"},
    "socket": {"widget", "socket"}, "climate": {"climate"},
    "humidifier": {"humidifier"}, "plant": {"widget", "plant"},
    "action": {"icon", "enabled", "interaction", "allow_stop"},
}


@dataclass(frozen=True)
class RuntimeLimits:
    """Provisional host rejection budgets, NOT measured ESP32 capacity claims."""

    document_bytes: int = 65536
    rooms: int = 12
    room_pages: int = 128
    widgets: int = 128
    views: int = 8
    attention_sources: int = 16
    bindings: int = 128
    string_bytes: int = 256
    depth: int = 16
    nodes: int = 16384


DEFAULT_LIMITS = RuntimeLimits()


def capabilities(limits=DEFAULT_LIMITS, features=FEATURES):
    return {"format": "home-panel-capabilities", "protocol_version": PROTOCOL_VERSION,
            "schema_versions": [SCHEMA_VERSION], "target": "host-contract",
            "deployment_ready": False, "features": sorted(features),
            "widget_types": [kind for kind in WIDGET_TYPES if f"widget.{kind}" in features],
            "room_widget_types": [kind for kind in ROOM_WIDGET_TYPES if f"widget.{kind}" in features],
            "view_widget_types": [kind for kind in VIEW_WIDGET_TYPES if f"widget.{kind}" in features],
            "room_kinds": ["room", "actions"] if ACTION_PAGES_FEATURE in features else ["room"],
            "display": {"width": 320, "height": 480},
            "limits": asdict(limits), "limits_measured_on_device": False}


def _mapping(value, allowed, label, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError(f"{label}: unknown, missing or invalid fields")


def _identifier(value, label):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{label}: expected an ASCII identifier of 1..64 characters")
    return value


def _sequence(value, maximum, label, minimum=0):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{label}: expected {minimum}..{maximum} entries")


def _check_tree(document, limits):
    pending, nodes = [(document, 0)], 0
    while pending:
        value, depth = pending.pop()
        nodes += 1
        if depth > limits.depth or nodes > limits.nodes:
            raise ValueError("Configuration exceeds depth/node budget")
        if isinstance(value, str):
            try:
                size = len(value.encode("utf-8"))
            except UnicodeError as error:
                raise ValueError("Configuration contains invalid UTF-8") from error
            if size > limits.string_bytes or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value):
                raise ValueError("Configuration text exceeds UTF-8 budget or contains control characters")
        elif isinstance(value, dict):
            if any(not isinstance(key, str) for key in value):
                raise ValueError("Configuration object keys must be strings")
            pending.extend((item, depth + 1) for pair in value.items() for item in pair)
        elif isinstance(value, list):
            pending.extend((item, depth + 1) for item in value)
        elif type(value) not in (int, float, bool, type(None)) or (type(value) is float and not math.isfinite(value)):
            raise ValueError("Configuration must contain finite JSON values")
    if len(encode_document(document)) > limits.document_bytes:
        raise ValueError("Configuration exceeds document byte budget")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def decode_document(data, limits=DEFAULT_LIMITS):
    if not isinstance(data, bytes) or len(data) > limits.document_bytes:
        raise ValueError("Configuration exceeds document byte budget or is not bytes")
    try:
        document = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (UnicodeError, RecursionError) as error:
        raise ValueError("Invalid UTF-8 or excessive JSON nesting") from error
    _check_tree(document, limits)
    return document


def _kind(entity):
    kind = "socket" if entity.is_socket else "status" if entity.domain == "binary_sensor" else entity.domain
    if entity.domain in ACTION_SERVICES:
        kind = "action"
    if kind not in ROOM_WIDGET_TYPES:
        raise ValueError(f"Unsupported runtime widget domain: {entity.domain}; firmware support is required")
    return kind


def _required_features(document):
    features = {"rooms.v1", "style.v1"}
    for room in document["rooms"]:
        if room.get("kind", "room") == "actions":
            features.add(ACTION_PAGES_FEATURE)
        if room["groups"]:
            features.add("sensor-groups.v1")
        features.update("widget." + widget["type"] for widget in room["widgets"])
        if any(w["type"] == "action" and "allow_stop" in w["settings"] for w in room["widgets"]):
            features.add(SCRIPT_CONTROLS_FEATURE)
    for view in document["views"]:
        features.add("views.v1")
        features.update("widget." + widget["type"] for widget in view["definition"]["widgets"])
    if document["attention"]["sources"]:
        features.add(f"attention.v{document['attention']['version']}")
    return features


def to_panel_config(document):
    """Legacy adapter; call validate_document on untrusted documents first."""
    if any(r.get("kind") == "actions" or any(w["type"] == "action" for w in r["widgets"]) for r in document["rooms"]):
        raise ValueError("Action tiles require the runtime renderer; legacy firmware does not implement them")
    return _legacy_panel_config(document)


def _legacy_panel_config(document):
    result = {"panel": deepcopy(document["panel"]), **deepcopy(document["style"]), "pages": {}, "views": {}}
    for room in document["rooms"]:
        result["pages"][room["id"]] = {"name": room["name"], "groups": deepcopy(room["groups"]),
                                       "entities": [_legacy_settings(w) for w in room["widgets"]]}
    result["views"] = {view["id"]: deepcopy(view["definition"]) for view in document["views"]}
    attention = document["attention"]
    if attention["sources"]:
        result["attention"] = {"version": attention["version"], "popup_cooldown": attention["popup_cooldown"],
                               "sources": {s["id"]: {k: deepcopy(v) for k, v in s.items() if k != "id"}
                                           for s in attention["sources"]}}
    return result


def _legacy_settings(widget):
    settings = deepcopy(widget["settings"])
    kind = widget["type"]
    if kind == "action":
        return {key: settings[key] for key in ("entity", "name")}
    if kind in ("climate", "humidifier") and kind in settings:
        fields = ("hvac_modes", "fan_modes") if kind == "climate" else ("modes",)
        profile = settings[kind]
        if not isinstance(profile, dict):
            raise ValueError("Widget profile must be an object")
        for field in fields:
            if field not in profile:
                raise ValueError("Runtime mode choices must be explicit ordered arrays")
            choices = profile[field]
            _sequence(choices, 8, field)
            result = {}
            for choice in choices:
                _mapping(choice, {"label", "value"}, field, {"label", "value"})
                if not isinstance(choice["label"], str) or choice["label"] in result:
                    raise ValueError("Mode labels must be unique strings")
                result[choice["label"]] = choice["value"]
            profile[field] = result
    return settings


def _room_height(page, style):
    grouped = sensor_group_rows(page.entities, style["sensor_group_columns"])
    grouped_members = {i for rows in grouped.values() for row in rows for i in row}
    tiles = light_tile_rows(page.entities, style["light_tile_columns"],
                            is_tile=lambda e: e.is_tile or e.domain in ACTION_SERVICES)
    tile_members = {i for start, count in tiles.items() for i in range(start, start + count)}
    heights = []
    for index, entity in enumerate(page.entities):
        if index in grouped:
            heights.extend([style["sensor_group_height"]] * len(grouped[index]))
        elif index in grouped_members:
            continue
        elif index in tiles:
            heights.append(style["light_card_height"])
        elif index in tile_members:
            continue
        elif entity.domain == "humidifier":
            rows = (len(entity.humidifier.card_modes) + style["humidifier_mode_columns"]) // style["humidifier_mode_columns"]
            heights.append(style["humidifier_card_height"] + (rows - 1) *
                           (style["device_card_control_height"] + style["humidifier_row_gap"]))
        else:
            heights.append(style["climate_card_height"] if entity.domain == "climate" else style["entity_card_height"])
    return sum(heights) + max(0, len(heights) - 1) * style["card_gap"]


def _bindings(pages, views, attention):
    """Count distinct logical HA entity/attribute sources, shared across consumers."""
    bindings = set()
    def add(entity, attribute=""):
        if entity:
            bindings.add((entity, attribute))
    for page in pages:
        for e in page.entities:
            add(e.entity_id)
            if e.is_socket:
                for _, reading in e.socket.metric_items:
                    add(reading.entity, reading.attribute)
            elif e.domain == "light":
                add(e.entity_id, "brightness")
                if e.has_color_temperature:
                    add(e.entity_id, "color_temp_kelvin")
                if e.has_rgb:
                    add(e.entity_id, "rgbw_color" if e.light_type == "rgbw" else "rgb_color")
                if e.light_type == "rgb_color_temp":
                    add(e.entity_id, "color_mode")
            elif e.domain == "climate":
                for attr in ("current_temperature", "temperature", "last_on_mode"):
                    add(e.entity_id, attr)
                if e.climate.fan_modes:
                    add(e.entity_id, "fan_mode")
            elif e.domain == "humidifier":
                for attr in ("current_humidity", "humidity", "mode"):
                    add(e.entity_id, attr)
                add(e.humidifier.water_entity, e.humidifier.water_attribute)
                for extra in e.humidifier.extras:
                    add(extra.entity, extra.attribute)
    for view in views:
        for widget in view.widgets:
            for reading in widget.sensors:
                add(reading.binding.entity, reading.binding.attribute)
    for plant in collect_plants(views):
        for attr in ("", "species", "problems"):
            add(plant.entity, attr)
        for metric in plant.measurements:
            for entity in (metric.entity, metric.min_entity, metric.max_entity):
                add(entity)
    for source in attention.sources:
        if source.kind == "condition":
            add(source.entity)
    return bindings


def validate_document(document, *, limits=DEFAULT_LIMITS, supported_features=FEATURES):
    try:
        return _validate_document(document, limits, supported_features)
    except (TypeError, KeyError, AttributeError, OverflowError) as error:
        raise ValueError("Malformed configuration field or reference") from error


def _validate_document(document, limits, supported_features):
    _check_tree(document, limits)
    _mapping(document, {"format", "schema_version", "revision", "requires", "panel", "style", "rooms", "views", "attention"},
             "document", {"format", "schema_version", "revision", "requires", "panel", "style", "rooms", "views", "attention"})
    if document["format"] != FORMAT or type(document["schema_version"]) is not int or document["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported configuration format/schema version; explicit migration is required")
    if type(document["revision"]) is not int or not 1 <= document["revision"] <= 0xFFFFFFFF:
        raise ValueError("revision must be an integer between 1 and 4294967295")
    requires = document["requires"]
    _sequence(requires, 64, "requires")
    if any(not isinstance(f, str) for f in requires) or len(set(requires)) != len(requires):
        raise ValueError("requires must contain unique feature names")
    if set(requires) - set(supported_features):
        raise ValueError("Unsupported required features; firmware support is required: " + ", ".join(sorted(set(requires) - set(supported_features))))
    _mapping(document["panel"], {"timezone", "system", "backlight"}, "panel", {"timezone", "system", "backlight"})
    _mapping(document["style"], {"theme", "layout"}, "style", {"theme", "layout"})
    _mapping(document["style"]["theme"], theme_keys(), "theme", theme_keys())
    _mapping(document["style"]["layout"], layout_keys(), "layout", layout_keys())
    if any(type(color) is not int or not 0 <= color <= 0xFFFFFF for color in document["style"]["theme"].values()):
        raise ValueError("Theme colors must be 24-bit integers")
    _sequence(document["rooms"], limits.rooms, "rooms", 1)
    _sequence(document["views"], limits.views, "views")
    ids, widget_count = set(), 0
    for room in document["rooms"]:
        _mapping(room, {"id", "name", "kind", "groups", "widgets"}, "room", {"id", "name", "groups", "widgets"})
        if room.get("kind", "room") not in ("room", "actions"):
            raise ValueError("Room kind must be room or actions")
        if room.get("kind") == "actions" and (room["groups"] or any(
                isinstance(w, dict) and w.get("type") != "action" for w in room.get("widgets", []))):
            raise ValueError("Actions pages only support action tiles without sensor groups")
        identity = _identifier(room["id"], "room.id")
        if identity in ids:
            raise ValueError("Duplicate room ID")
        ids.add(identity)
        _sequence(room["widgets"], limits.widgets, "room.widgets")
        local = set()
        for widget in room["widgets"]:
            _mapping(widget, {"id", "type", "settings"}, "widget", {"id", "type", "settings"})
            identity = _identifier(widget["id"], "widget.id")
            if identity in local:
                raise ValueError("Duplicate room-local widget ID")
            local.add(identity)
            kind = widget["type"]
            if not isinstance(kind, str) or kind not in _TYPE_FIELDS:
                raise ValueError("Unsupported widget type; firmware support is required")
            _mapping(widget["settings"], {"entity", "name"} | _TYPE_FIELDS[kind], "widget.settings", {"entity", "name"})
            display_name(widget["settings"]["name"], "widget name")
            if kind == "action":
                action_profile(widget["settings"]["entity"], {key: value for key, value in widget["settings"].items()
                                                             if key not in ("entity", "name")})
            for field in ("min_color_temperature", "max_color_temperature"):
                if field in widget["settings"] and type(widget["settings"][field]) is not int:
                    raise ValueError(f"{field} must be an integer")
            widget_count += 1
    ids = set()
    for view in document["views"]:
        _mapping(view, {"id", "definition"}, "view", {"id", "definition"})
        identity = _identifier(view["id"], "view.id")
        if identity in ids:
            raise ValueError("Duplicate view ID")
        ids.add(identity)
        _mapping(view["definition"], {"name", "widgets", "presentations"}, "view.definition", {"name", "widgets", "presentations"})
        _sequence(view["definition"]["widgets"], 3, "view.widgets", 1)
        for widget in view["definition"]["widgets"]:
            _mapping(widget, {"id", "type", "name", "entity", "measurements", "sensors"},
                     "runtime view widget", {"id", "type"})
            _identifier(widget["id"], "view widget.id")
            if "sensors" in widget:
                _sequence(widget["sensors"], 12, "view sensors", 1)
            for reading in widget.get("sensors", []):
                if isinstance(reading, dict) and "simulator" in reading:
                    raise ValueError("Runtime readings must not contain simulator data")
        widget_count += len(view["definition"]["widgets"])
    if widget_count > limits.widgets:
        raise ValueError("Configuration exceeds widget budget")
    attention = document["attention"]
    _mapping(attention, {"version", "popup_cooldown", "sources"}, "attention", {"version", "popup_cooldown", "sources"})
    if type(attention["version"]) is not int or attention["version"] not in (1, 2):
        raise ValueError("attention.version must be 1 or 2")
    if type(attention["popup_cooldown"]) is not int or not 1 <= attention["popup_cooldown"] <= 3600:
        raise ValueError("attention.popup_cooldown must be 1..3600")
    _sequence(attention["sources"], limits.attention_sources, "attention.sources")
    ids = set()
    for source in attention["sources"]:
        if not isinstance(source, dict) or "simulator" in source or "id" not in source:
            raise ValueError("Invalid runtime attention source")
        identity = _identifier(source["id"], "attention.id")
        if identity in ids:
            raise ValueError("Duplicate attention source ID")
        ids.add(identity)
    config = _legacy_panel_config(document)
    header_timezone(config)
    system_page_name(config)
    parse_backlight_settings(config)
    style = validate_resolved_style(document["style"]["theme"], document["style"]["layout"])
    pages = parse_pages(config)
    views = parse_views(config, pages)
    parsed_attention = parse_attention(config, pages, views)
    required = _required_features(document)
    if required - set(requires):
        raise ValueError("Missing required feature declarations: " + ", ".join(sorted(required - set(requires))))
    plant_tile_bindings(pages, views, style)
    validate_views_layout(views, style)
    validate_socket_layout(pages, style)
    validate_attention_layout(parsed_attention, style)
    for room, page in zip(document["rooms"], pages):
        for widget, entity in zip(room["widgets"], page.entities):
            if widget["type"] != _kind(entity):
                raise ValueError("Widget type and entity/profile do not match")
    available = room_available_height(style)
    room_heights = {page.safe_id: _room_height(page, style) for page in pages}
    page_heights = {}
    for room, page in zip(document["rooms"], pages):
        slices = room_page_slices(room, style)
        if room.get("kind") == "actions":
            columns = style["light_tile_columns"]
            rows = [(count + columns - 1) // columns for _, count in slices]
            heights = [n * style["light_card_height"] + max(0, n - 1) * style["card_gap"] for n in rows]
        else:
            heights = [room_heights[page.safe_id]]
        if max(heights) > available:
            raise ValueError(f"Room {page.safe_id} does not fit without scrolling: {max(heights)} > {available} px; use an Actions page for excess actions")
        page_heights[room["id"]] = heights
    rendered_pages = sum(len(heights) for heights in page_heights.values())
    if rendered_pages > limits.room_pages:
        raise ValueError("Configuration exceeds rendered room page budget")
    bindings = _bindings(pages, views, parsed_attention)
    if len(bindings) > limits.bindings:
        raise ValueError("Configuration exceeds coalesced binding budget")
    data = encode_document(document)
    return {"schema_version": SCHEMA_VERSION, "revision": document["revision"], "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "rooms": len(pages), "widgets": widget_count,
            "views": len(views), "attention_sources": len(parsed_attention.sources), "bindings": len(bindings),
            "room_content_height": room_heights, "room_available_height": available,
            "room_page_heights": page_heights, "room_pages": rendered_pages,
            "max_actions_per_page": action_page_capacity(style),
            "deployment_ready": False}
