"""Bounded Plant presentation data and optional Native API measurement bindings."""

from dataclasses import dataclass
import math
import re

from .panel_model import display_name, socket_float

PLANT_METRICS = ("moisture", "temperature", "humidity", "conductivity", "illuminance", "co2", "soil_temperature", "dli", "vpd")
PLANT_NAMES = ("Soil moisture", "Temperature", "Air humidity", "Conductivity", "Illuminance", "CO2", "Soil temp.", "DLI", "VPD")
PLANT_UNITS = ("%", "°C", "%", "uS/cm", "lx", "ppm", "°C", "mol/d*m2", "kPa")
PLANT_ICONS = ("droplet", "thermometer", "droplet", "gauge", "sun", "gauge", "thermometer", "sun", "droplet")
PLANT_STYLE_FIELDS = """bg_color card_color text_color muted_text_color accent_color status_error_color
control_border_color plant_identity_height plant_tab_height plant_row_height plant_row_gap plant_text_gap
plant_padding plant_columns plant_max_rows plant_value_width plant_icon_size small_text_height normal_text_height
title_text_height nav_button_height nav_button_width nav_icon_size control_radius control_border_width""".split()
PLANT_TILE_STYLE_FIELDS = """card_color control_color text_color muted_text_color accent_color
attention_warning_color status_error_color light_card_height card_radius plant_tile_padding plant_tile_gap
plant_tile_heading_height plant_tile_line_height plant_tile_icon_size plant_tile_metric_icon_size""".split()


@dataclass(frozen=True)
class PlantTileBinding:
    model: int
    host: int
    popup: str
    critical: bool


def collect_plants(views):
    return list({w.plant.entity: w.plant for v in views for w in v.widgets if w.plant}.values())


def plant_tile_bindings(pages, views, style=None):
    plants = collect_plants(views)
    hosts = [(v, p) for v in views for p in v.presentations]
    result = {}
    for page in pages:
        for entity in page.entities:
            if not entity.is_plant:
                continue
            candidates = [v for v in views if "popup" in v.presentations and
                (not entity.plant.view or v.id == entity.plant.view) and
                any(w.plant and w.plant.entity == entity.entity_id for w in v.widgets)]
            if len(candidates) != 1:
                raise ValueError(f"Plant tile {entity.entity_id} requires one matching popup view; set plant.view explicitly")
            view = candidates[0]
            index = next(i for i, p in enumerate(plants) if p.entity == entity.entity_id)
            result[entity.safe_id] = PlantTileBinding(index, hosts.index((view, "popup")),
                view.host_id("popup"), entity.plant.severity == "critical")
    if len(result) > 32:
        raise ValueError("At most 32 Plant room-tile instances are supported")
    if result and style:
        validate_plant_tile_style(style)
    return result


def validate_plant_tile_style(style):
    s = style
    if s["plant_tile_heading_height"] < s["small_text_height"] or s["plant_tile_line_height"] < s["normal_text_height"]:
        raise ValueError("Plant tile lines must fit the existing 14/18px fonts")
    if not 12 <= s["plant_tile_icon_size"] <= 32 or not 12 <= s["plant_tile_metric_icon_size"] <= s["plant_tile_line_height"]:
        raise ValueError("Plant tile icon sizes are invalid")
    minimum = 2 * s["plant_tile_padding"] + max(s["plant_tile_heading_height"], s["plant_tile_icon_size"]) + 2 * s["plant_tile_line_height"] + 2 * s["plant_tile_gap"]
    if s["light_card_height"] < minimum:
        raise ValueError("Plant tile content does not fit light_card_height")
    width = (320 - 2 * s["page_padding"] - (s["light_tile_columns"] - 1) * s["control_gap"]) // s["light_tile_columns"]
    if width - 2 * s["plant_tile_padding"] - max(s["plant_tile_icon_size"], s["plant_tile_metric_icon_size"]) - s["plant_tile_gap"] < 48:
        raise ValueError("Plant tile is too narrow for name and readings")


@dataclass(frozen=True)
class PlantMetric:
    key: str
    name: str
    unit: str
    precision: int
    entity: str = ""
    min_entity: str = ""
    max_entity: str = ""
    scale: float = 1.0
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class PlantSample:
    species: str = ""
    available: bool = False
    problems_known: bool = False
    measurements: tuple = ()
    problems: tuple = ()


@dataclass(frozen=True)
class Plant:
    entity: str
    name: str
    measurements: tuple[PlantMetric, ...]
    simulator: PlantSample | None


def plant_number(value):
    if value is None or value in ("unknown", "unavailable"):
        return None
    if type(value) is bool or not isinstance(value, (str, int, float)):
        raise ValueError("Plant values require finite numbers or unknown/null")
    try:
        result = float(value)
    except ValueError as error:
        raise ValueError("Plant values require finite numbers") from error
    if not math.isfinite(result) or abs(result) > 3.4e38:
        raise ValueError("Plant values must fit a finite float")
    return result


def plant_values(raw):
    values = tuple(plant_number(raw.get(key)) for key in ("current", "min", "max"))
    if values[1] is not None and values[2] is not None and values[1] > values[2]:
        raise ValueError("Plant min must not exceed max")
    return values


def plant_sample(raw):
    if raw is None:
        return PlantSample()
    if not isinstance(raw, dict) or set(raw) - {"species", "available", "measurements", "problems"}:
        raise ValueError("Plant simulator supports species, available, measurements and problems")
    species = raw.get("species", "")
    if not isinstance(species, str) or len(species.encode()) > 127 or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in species):
        raise ValueError("Plant species requires at most 127 UTF-8 bytes without controls")
    available = raw.get("available", True)
    if type(available) is not bool:
        raise ValueError("Plant available requires a boolean")
    measurements = raw.get("measurements", {})
    if not isinstance(measurements, dict) or set(measurements) - set(PLANT_METRICS):
        raise ValueError("Unknown Plant measurements")
    parsed = []
    for key, value in measurements.items():
        if value is None:
            continue # Unsupported measurement; distinct from current: null.
        if not isinstance(value, dict) or set(value) - {"current", "min", "max"}:
            raise ValueError("Plant measurements support current, min and max")
        parsed.append((key, *plant_values(value)))
    problems = raw.get("problems")
    reasons, ids = [], set()
    if problems is not None:
        if not isinstance(problems, list) or len(problems) > len(PLANT_METRICS):
            raise ValueError("Plant problems require at most nine records")
        for value in problems:
            if not isinstance(value, dict) or set(value) - {"sensor_type", "status", "current", "min", "max"}:
                raise ValueError("Unknown Plant problem fields")
            key, status = value.get("sensor_type"), value.get("status")
            if key not in PLANT_METRICS or key in ids or status not in ("Low", "High"):
                raise ValueError("Plant problems require unique known sensor_type and Low/High status")
            ids.add(key); reasons.append((key, status, *plant_values(value)))
    return PlantSample(species, available, problems is not None, tuple(parsed), tuple(reasons))


def parse_plant(raw):
    entity = raw.get("entity")
    if not isinstance(entity, str) or not re.fullmatch(r"plant\.[a-z0-9_]+", entity):
        raise ValueError("A Plant widget requires a plant.* entity")
    name = display_name(raw.get("name", entity.split(".", 1)[1].replace("_", " ")), "Plant name")
    if len(name.encode()) > 127:
        raise ValueError("Plant names must not exceed 127 UTF-8 bytes")
    entries = raw.get("measurements", {})
    if not isinstance(entries, dict) or set(entries) - set(PLANT_METRICS):
        raise ValueError("Plant measurements requires a mapping of known metric names")
    metrics = []
    for index, key in enumerate(PLANT_METRICS):
        data = entries.get(key, {})
        if isinstance(data, str):
            data = {"entity": data}
        if not isinstance(data, dict) or set(data) - {"name", "unit", "precision", "entity", "min_entity", "max_entity", "scale", "min", "max"}:
            raise ValueError("Plant measurements support name, unit, precision, entity, min/max or min_entity/max_entity, scale")
        label = display_name(data.get("name", PLANT_NAMES[index]), "Plant measurement name")
        unit = data.get("unit", PLANT_UNITS[index])
        precision = data.get("precision", 1 if key in ("temperature", "soil_temperature", "vpd", "dli") else 0)
        if len(label.encode()) > 127 or not isinstance(unit, str) or len(unit.encode()) > 24 or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in unit):
            raise ValueError("Plant metric name/unit is invalid or too long")
        if type(precision) is not int or not 0 <= precision <= 3:
            raise ValueError("Plant precision must be 0..3")
        bindings = []
        for field in ("entity", "min_entity", "max_entity"):
            source = data.get(field, "")
            domains = "sensor" if field == "entity" else "sensor|number|input_number"
            if field in data and (not isinstance(source, str) or not re.fullmatch(rf"(?:{domains})\.[a-z0-9_]+", source)):
                raise ValueError(f"Plant {field} requires a numeric {domains} entity")
            bindings.append(source)
        scale = socket_float(data.get("scale", 1.0), "Plant scale")
        if scale <= 0 or ("scale" in data and not any(bindings)):
            raise ValueError("Plant scale requires an entity binding and a positive finite value")
        limits = []
        for field in ("min", "max"):
            if field in data and field + "_entity" in data:
                raise ValueError(f"Plant {field} and {field}_entity are mutually exclusive")
            limits.append(socket_float(data[field], f"Plant {field}") if field in data else None)
        if all(value is not None for value in limits) and limits[0] > limits[1]:
            raise ValueError("Plant min must not exceed max")
        metrics.append(PlantMetric(key, label, unit, precision, *bindings, scale, *limits))
    return Plant(entity, name, tuple(metrics), plant_sample(raw["simulator"]) if raw.get("simulator") is not None else None)


def validate_plant_style(style):
    if style["plant_columns"] != 2 or not 1 <= style["plant_max_rows"] <= 3:
        raise ValueError("Plant uses two columns and 1..3 rows per page")
    if style["plant_identity_height"] < style["normal_text_height"] + style["small_text_height"]:
        raise ValueError("Plant identity must fit name and species")
    if style["plant_tab_height"] < style["small_text_height"] + 2 * style["control_border_width"]:
        raise ValueError("Plant tabs must fit their labels")
    minimum = max(style["normal_text_height"], style["plant_icon_size"]) + style["title_text_height"] + style["small_text_height"] + 2 * style["plant_text_gap"] + 2 * (style["plant_padding"] + style["control_border_width"])
    if style["plant_row_height"] < minimum or style["plant_value_width"] < 72:
        raise ValueError("Plant rows must fit name, value/status and range")
    width = 320 - 2 * (style["view_popup_inset"] + style["page_padding"] + style["control_border_width"])
    if width - 2 * (style["plant_padding"] + style["control_border_width"]) - style["plant_value_width"] - style["plant_row_gap"] < 80:
        raise ValueError("Plant problem value leaves insufficient status width")


def plant_min_height(style):
    return (style["plant_identity_height"] + style["plant_tab_height"] + style["plant_row_height"] +
            style["nav_button_height"] + 3 * style["plant_row_gap"])
