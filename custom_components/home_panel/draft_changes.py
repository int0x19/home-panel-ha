"""HA presentation-only structural summaries, not schema validation or patches."""

from collections import Counter, defaultdict
import hashlib

from homeassistant.core import HomeAssistant

from ._core import encode_document
from .draft_jobs import async_model_job
from .draft_storage import DraftInvalid, parse_draft_document

MAX_CHANGES = 64
MAX_RESULT_BYTES = 32768


def _different(before, after) -> bool:
    # Python equality conflates true/1 and false/0; JSON types must stay distinct.
    return encode_document(before) != encode_document(after)


def _index(document: dict) -> tuple[dict, dict, dict]:
    rooms, widgets, locations = {}, {}, defaultdict(list)
    for room in document["rooms"]:
        room_id = room["id"]
        if room_id in rooms:
            raise DraftInvalid
        rooms[room_id] = room
        for widget in room["widgets"]:
            key = (room_id, widget["id"])
            if key in widgets:
                raise DraftInvalid
            widgets[key] = widget
            locations[widget["id"]].append(room_id)
    return rooms, widgets, locations


def summarize_changes(base: str, document: str) -> dict:
    """Match room-local IDs; infer cross-room moves only for unambiguous IDs."""
    before, after = parse_draft_document(base), parse_draft_document(document)
    old_rooms, old_widgets, old_locations = _index(before)
    new_rooms, new_widgets, new_locations = _index(after)
    items, counts = [], Counter()

    def add(kind, **details):
        counts[kind] += 1
        if len(items) < MAX_CHANGES:
            items.append({"kind": kind, **details})

    def label(value):
        return value[:256]

    for room_id, room in old_rooms.items():
        if room_id not in new_rooms:
            add("room_removed", room=room_id, name=label(room["name"]))
    for room_id, room in new_rooms.items():
        if room_id not in old_rooms:
            add("room_added", room=room_id, name=label(room["name"]))
            continue
        old = old_rooms[room_id]
        fields = [key for key in ("name", "kind", "groups") if _different(old.get(key), room.get(key))]
        if _different({k: v for k, v in old.items() if k not in ("name", "kind", "groups", "widgets")}, {
                k: v for k, v in room.items() if k not in ("name", "kind", "groups", "widgets")}):
            fields.append("other")
        if fields:
            add("room_changed", room=room_id, name=label(room["name"]), fields=fields)
    common_rooms = old_rooms.keys() & new_rooms.keys()
    if [key for key in old_rooms if key in common_rooms] != [key for key in new_rooms if key in common_rooms]:
        add("room_order")

    # Runtime widget IDs are room-local, not globally unique. Ambiguous repeated
    # IDs stay separate additions/removals; never guess a cross-room identity.
    pairs = {}
    for key in new_widgets:
        room_id, widget_id = key
        if key in old_widgets:
            pairs[key] = key
        elif len(old_locations[widget_id]) == len(new_locations[widget_id]) == 1:
            pairs[key] = (old_locations[widget_id][0], widget_id)
    matched_old = set(pairs.values())
    for key, widget in old_widgets.items():
        if key not in matched_old:
            add("widget_removed", room=key[0], id=key[1], name=label(widget["settings"]["name"]))
    for key, widget in new_widgets.items():
        room_id, widget_id = key
        details = {"room": room_id, "id": widget_id, "name": label(widget["settings"]["name"])}
        if key not in pairs:
            add("widget_added", **details)
            continue
        old_key = pairs[key]
        old = old_widgets[old_key]
        if old_key[0] != room_id:
            add("widget_moved", **details, from_room=old_key[0])
        fields = [key for key in ("name", "entity") if _different(old["settings"].get(key), widget["settings"].get(key))]
        if _different({k: v for k, v in old["settings"].items() if k not in ("name", "entity")}, {
                k: v for k, v in widget["settings"].items() if k not in ("name", "entity")}):
            fields.append("settings")
        if old["type"] != widget["type"]:
            fields.append("type")
        if _different({k: v for k, v in old.items() if k not in ("settings", "type")}, {
                k: v for k, v in widget.items() if k not in ("settings", "type")}):
            fields.append("other")
        if fields:
            add("widget_changed", **details, fields=fields)
    for room_id in new_rooms:
        if room_id not in old_rooms:
            continue
        common = {widget_id for (rid, widget_id), old_key in pairs.items()
                  if rid == room_id and old_key[0] == room_id}
        if [w["id"] for w in old_rooms[room_id]["widgets"] if w["id"] in common] != [
                w["id"] for w in new_rooms[room_id]["widgets"] if w["id"] in common]:
            add("widget_order", room=room_id, name=label(new_rooms[room_id]["name"]))
    for section in ("panel", "style", "requires", "views", "attention"):
        if _different(before[section], after[section]):
            add("section_changed", section=section)

    base_raw, raw = base.encode("utf-8"), document.encode("utf-8")
    result = {"version": 1, "scope": "ha_structural_changes", "base_sha256": hashlib.sha256(base_raw).hexdigest(),
              "document_sha256": hashlib.sha256(raw).hexdigest(), "base_bytes": len(base_raw), "document_bytes": len(raw),
              "base_revision": before["revision"], "document_revision": after["revision"],
              "counts": dict(counts), "total": sum(counts.values()), "items": items, "truncated": False,
              "model_validated": False, "device_checked": False, "deployment_ready": False}
    while len(encode_document(result)) > MAX_RESULT_BYTES:
        items.pop()
    result["truncated"] = len(items) < result["total"]
    return result


async def async_summarize_changes(hass: HomeAssistant, entry_id: str, base: str, document: str) -> dict:
    return await async_model_job(hass, entry_id, summarize_changes, base, document)
