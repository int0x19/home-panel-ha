"""Shared no-scroll page planning, independent of storage, transport and LVGL."""

ACTION_PAGES_FEATURE = "action-pages.v1"


def room_available_height(style):
    return (480 - 2 * style["page_padding"] - style["header_height"] - style["nav_button_height"] -
            2 * style["control_row_padding"] - style["page_gap"] - style["navigation_gap"])


def action_page_capacity(style):
    rows = max(0, (room_available_height(style) + style["card_gap"]) //
               (style["light_card_height"] + style["card_gap"]))
    return rows * style["light_tile_columns"]


def room_page_slices(room, style):
    count = len(room["widgets"])
    if room.get("kind", "room") != "actions" or not count:
        return [(0, count)]
    capacity = action_page_capacity(style)
    if not capacity:
        raise ValueError("No action tile fits the configured page geometry")
    return [(start, min(capacity, count - start)) for start in range(0, count, capacity)]


def room_page_plan(document):
    """Plan physical pages without changing logical IDs, order, entities or settings."""
    style = document["style"]["layout"]
    result, offset = [], 0
    for room in document["rooms"]:
        slices = room_page_slices(room, style)
        for page_index, (start, count) in enumerate(slices):
            suffix = f" [{page_index + 1}/{len(slices)}]" if len(slices) > 1 else ""
            # Only the display title is bounded; the stored full name is preserved.
            title = room["name"].encode("utf-8")[:256 - len(suffix)].decode("utf-8", "ignore") + suffix
            result.append({"room_id": room["id"], "name": title, "page_index": page_index,
                           "page_count": len(slices), "first": offset + start, "count": count})
        offset += len(room["widgets"])
    return result
