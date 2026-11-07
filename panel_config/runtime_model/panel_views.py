"""Bounded declarative views shared by both panel generators."""

from dataclasses import dataclass, replace
from typing import Any

from .panel_model import SocketReading, display_name, parse_socket_profile, safe_id, socket_float
from .panel_plant import Plant, parse_plant, plant_min_height, validate_plant_style

MAX_VIEWS, MAX_VIEW_WIDGETS, MAX_VIEW_SOURCES = 8, 3, 128
VIEW_HOST_STYLE_FIELDS = """bg_color text_color control_color control_border_color accent_color
page_padding page_gap control_gap control_height back_button_width back_icon_size control_radius
control_border_width normal_text_height view_popup_inset view_popup_vertical_inset view_popup_radius""".split()
VIEW_STYLE_FIELDS = """text_color muted_text_color divider_color view_readings_max_rows
view_readings_row_height view_readings_row_gap view_readings_name_width_pct view_widget_gap
small_text_height normal_text_height nav_button_width nav_button_height nav_icon_size""".split()


@dataclass(frozen=True)
class ViewReading:
    binding: SocketReading
    simulator: float | str | bool | None = None


@dataclass(frozen=True)
class ViewWidget:
    id: str
    name: str
    sensors: tuple[ViewReading, ...] = ()
    plant: Plant | None = None

    @property
    def kind(self):
        return "plant" if self.plant else "readings"

    @property
    def controls(self):
        return ("data", "problems", "prev", "next", "summary") if self.plant else ("prev", "next")


@dataclass(frozen=True)
class View:
    id: str
    name: str
    widgets: tuple[ViewWidget, ...]
    presentations: tuple[str, ...]

    def host_id(self, presentation):
        return f"{presentation}_view_{self.id}"


def parse_views(config: dict[str, Any], rooms=()) -> tuple[View, ...]:
    raw = config.get("views", {})
    if not isinstance(raw, dict) or len(raw) > MAX_VIEWS:
        raise ValueError(f"views must be a mapping of at most {MAX_VIEWS} definitions")
    result, ids, mocks = [], set(), {}
    reserved = {"page_system_info", *(f"page_{p.safe_id}" for p in rooms),
                *(f"page_detail_{e.safe_id}" for p in rooms for e in p.entities)}
    total = 0
    for key, value in raw.items():
        if not isinstance(key, str) or not key or "\0" in key:
            raise ValueError("View IDs must be nonempty strings without NUL")
        view_id = safe_id(key)
        if view_id in ids:
            raise ValueError(f"Duplicate normalized view ID: {view_id}")
        ids.add(view_id)
        if not isinstance(value, dict) or set(value) - {"name", "widgets", "presentations"}:
            raise ValueError("A view supports name, widgets and presentations")
        name = display_name(value.get("name", key), f"View {key} name")
        if len(name) > 128:
            raise ValueError("View names must not exceed 128 characters")
        presentations = value.get("presentations", ["page", "popup"])
        if (not isinstance(presentations, list) or not presentations or
                any(p not in ("page", "popup") for p in presentations) or len(set(presentations)) != len(presentations)):
            raise ValueError("View presentations must be a unique nonempty list of page/popup")
        widgets = value.get("widgets")
        if not isinstance(widgets, list) or not 1 <= len(widgets) <= MAX_VIEW_WIDGETS:
            raise ValueError(f"A view requires 1..{MAX_VIEW_WIDGETS} widgets")
        parsed, widget_ids = [], set()
        for index, widget in enumerate(widgets):
            if not isinstance(widget, dict) or widget.get("type") not in ("readings", "plant"):
                raise ValueError("View widgets support type: readings or plant")
            kind = widget["type"]
            allowed = {"id", "type", "name", "sensors"} if kind == "readings" else {"id", "type", "name", "entity", "measurements", "simulator"}
            if set(widget) - allowed:
                raise ValueError("Unknown view widget fields")
            local_id = widget.get("id", f"{kind}_{index}")
            if not isinstance(local_id, str) or not local_id or "\0" in local_id:
                raise ValueError("View widget IDs must be nonempty strings without NUL")
            local_id = safe_id(local_id)
            if local_id in widget_ids:
                raise ValueError(f"Duplicate view widget ID: {local_id}")
            widget_ids.add(local_id)
            title = display_name(widget["name"], "View widget name") if "name" in widget else ""
            if len(title) > 128:
                raise ValueError("View widget names must not exceed 128 characters")
            if kind == "plant":
                parsed.append(ViewWidget(local_id, title, plant=parse_plant(widget)))
                continue
            sensors = widget.get("sensors")
            if not isinstance(sensors, list) or not 1 <= len(sensors) <= 12:
                raise ValueError("A readings widget requires 1..12 sensors")
            readings = []
            for sensor in sensors:
                data = {"entity": sensor} if isinstance(sensor, str) else sensor
                if not isinstance(data, dict):
                    raise ValueError("A view sensor requires an entity binding")
                binding = parse_socket_profile({"sensors": [{k: v for k, v in data.items() if k != "simulator"}]}).sensors[0]
                mock = data.get("simulator")
                if mock is not None:
                    if binding.kind == "numeric":
                        socket_float(mock, "View simulator value")
                        socket_float(mock * binding.scale, "Scaled view simulator value")
                    elif binding.kind == "binary":
                        if type(mock) is not bool and mock not in ("on", "off", "unknown", "unavailable"):
                            raise ValueError("Binary view simulator values require booleans or HA states")
                    elif not isinstance(mock, str) or "\0" in mock or len(mock.encode()) > 127:
                        raise ValueError("Text view simulator values require strings of at most 127 UTF-8 bytes without NUL")
                    previous = mocks.setdefault(binding.import_id, mock)
                    if previous != mock:
                        raise ValueError(f"Conflicting view simulator values for {binding.entity}")
                readings.append(ViewReading(binding, mock))
            total += len(readings)
            parsed.append(ViewWidget(local_id, title, tuple(readings)))
        view = View(view_id, name, tuple(parsed), tuple(presentations))
        for presentation in presentations:
            if view.host_id(presentation) in reserved:
                raise ValueError(f"Reserved view host ID: {view.host_id(presentation)}")
            reserved.add(view.host_id(presentation))
        result.append(view)
    plants = {}
    for v in result:
        for w in v.widgets:
            if w.plant:
                old = plants.get(w.plant.entity)
                if old and replace(old, simulator=w.plant.simulator) != w.plant:
                    raise ValueError("Repeated Plant entities require identical names and measurement metadata")
                if old and old.simulator is not None and w.plant.simulator is not None and old.simulator != w.plant.simulator:
                    raise ValueError("Conflicting Plant simulator samples")
                if not old or w.plant.simulator is not None:
                    plants[w.plant.entity] = w.plant
    total += sum(3 + sum(bool(source) for m in p.measurements for source in (m.entity, m.min_entity, m.max_entity))
                 for p in plants.values())
    if total > MAX_VIEW_SOURCES:
        raise ValueError(f"Views support at most {MAX_VIEW_SOURCES} reading bindings in total")
    # Missing mock samples inherit an explicit sample of the same shared source.
    return tuple(replace(v, widgets=tuple(replace(w, plant=plants[w.plant.entity]) if w.plant else
        replace(w, sensors=tuple(ViewReading(r.binding, mocks.get(r.binding.import_id)) for r in w.sensors))
        for w in v.widgets)) for v in result)


def validate_views_layout(views, style):
    if not views:
        return
    if not 1 <= style["view_readings_max_rows"] <= 8:
        raise ValueError("view_readings_max_rows must be between 1 and 8")
    if style["view_readings_row_height"] < style["normal_text_height"]:
        raise ValueError("View rows must fit the normal text height")
    if not 35 <= style["view_readings_name_width_pct"] <= 65:
        raise ValueError("view_readings_name_width_pct must be between 35 and 65")
    if not 0 <= style["view_popup_radius"] <= 8 or any(not 0 <= style[k] <= 40 for k in ("view_popup_inset", "view_popup_vertical_inset")):
        raise ValueError("View popup insets must be 0..40px and radius 0..8px")
    for view in views:
        if any(w.plant for w in view.widgets):
            validate_plant_style(style)
        inset = style["view_popup_vertical_inset"] if "popup" in view.presentations else 0
        height = 480 - 2 * (inset + style["page_padding"] + style["control_border_width"])
        body = height - style["control_height"] - style["page_gap"]
        # A conservative minimum, not a second layout engine: the C renderer
        # chooses the actual row count from each parent's measured dimensions.
        minimum_slot = max(plant_min_height(style) if w.plant else style["view_readings_row_height"] +
            (style["nav_button_height"] + style["view_widget_gap"] if len(w.sensors) > 1 else 0) +
            (style["normal_text_height"] + style["view_widget_gap"] if w.name else 0) for w in view.widgets)
        minimum = len(view.widgets) * minimum_slot + (len(view.widgets) - 1) * style["view_widget_gap"]
        if minimum > body:
            raise ValueError(f"View {view.id} does not fit without scrolling; reduce widgets or template dimensions")
        horizontal = style["view_popup_inset"] if "popup" in view.presentations else 0
        width = 320 - 2 * (horizontal + style["page_padding"] + style["control_border_width"])
        if style["back_button_width"] + style["control_gap"] + style["normal_text_height"] > width:
            raise ValueError(f"View {view.id} header does not fit its Back control and title")
