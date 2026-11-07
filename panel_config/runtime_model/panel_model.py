"""Shared panel config model for ESPHome and simulator generators."""

from __future__ import annotations

import re
import hashlib
import math
import struct
import unicodedata
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any

from .style_fields import LAYOUT_FIELDS, THEME_FIELDS



MAX_ID_LENGTH = 64
SIM_MAX_CLIMATE_CONTROLLERS = 16
SIM_MAX_LIGHT_CONTROLLERS = 24
MAX_CLIMATE_OPTIONS = 8
CLIMATE_STYLE_FIELDS = """accent_color back_button_width back_icon_size bg_color card_color card_gap card_radius
climate_card_header_height climate_card_height climate_card_icon_size climate_card_mode_width
climate_card_padding climate_card_power_gap climate_card_power_width climate_card_step_width
climate_choice_columns climate_choice_gap climate_choice_height climate_step_button_width
climate_temperature_height control_border_color control_border_width control_color control_gap
control_height control_padding control_radius control_row_padding detail_power_width
device_card_control_height device_card_control_padding device_card_mode_font_size
device_card_name_font_size device_card_value_font_size large_text_height muted_text_color
normal_text_height page_gap page_padding room_value_font_size scrollbar_inset scrollbar_width
small_text_height text_color text_gap""".split()
HUMIDIFIER_STYLE_FIELDS = """bg_color card_color text_color muted_text_color accent_color control_color
status_error_color disabled_color control_border_color page_padding page_gap control_height control_gap control_radius card_radius
normal_text_height small_text_height back_button_width humidifier_card_height humidifier_card_padding
humidifier_reading_height humidifier_row_gap humidifier_mode_columns scrollbar_width scrollbar_inset
humidifier_status_height humidifier_icon_size humidifier_value_width humidifier_water_width
room_name_font_size room_value_font_size back_icon_size humidifier_step_icon_size control_border_width control_padding
device_card_name_font_size device_card_value_font_size device_card_mode_font_size
device_card_control_height device_card_control_padding""".split()
CLIMATE_MODE_ICONS = {
    "cool": "snowflake", "heat": "sun", "fan_only": "fan", "dry": "droplet",
    "auto": "refresh-cw", "heat_cool": "refresh-cw", "off": "power",
}
CLIMATE_MODE_COLORS = {
    "cool": "climate_cool_color", "heat": "climate_heat_color", "fan_only": "climate_fan_color",
    "dry": "climate_dry_color", "auto": "climate_auto_color", "heat_cool": "climate_auto_color",
    "off": "muted_text_color",
}
CLIMATE_FAN_ICONS = {
    "auto": "refresh-cw", "low": "signal-low", "min": "signal-low", "1": "signal-low",
    "medium": "signal-medium", "mid": "signal-medium", "2": "signal-medium",
    "high": "signal-high", "max": "signal-high", "3": "signal-high",
    "quiet": "moon", "silent": "moon", "sleep": "moon",
    "turbo": "wind", "boost": "wind", "off": "power",
}


def climate_fan_icon(value: str) -> str:
    return CLIMATE_FAN_ICONS.get(value.casefold(), "fan")


def temperature_display_unit(unit: str) -> str:
    normalized = unit.strip().removeprefix("\N{DEGREE SIGN}").removeprefix("deg ")
    return "\N{DEGREE SIGN}" + normalized if normalized in {"C", "F"} else unit

_RUSSIAN_ASCII = dict(zip(
    "\u0430\u0431\u0432\u0433\u0434\u0435\u0451\u0436\u0437\u0438\u0439\u043a\u043b\u043c\u043d\u043e\u043f\u0440\u0441\u0442\u0443\u0444\u0445\u0446\u0447\u0448\u0449\u044a\u044b\u044c\u044d\u044e\u044f",
    ("a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya"),
))


@dataclass(frozen=True)
class SimValues:
    state: str
    fan_mode: str
    current_temperature: float
    target_temperature: float
    has_value: bool
    value: float
    brightness: int
    color_temperature: int
    red: int
    green: int
    blue: int
    white: int
    last_on_mode: str = ""
    current_humidity: float | None = None
    target_humidity: float | None = None
    humidity_mode: str = ""
    water_level: float | None = None
    extra_states: tuple[str, ...] = ()
    light_known: int = 0
    light_color_mode: str = ""
    power: float | None = None
    voltage: float | None = None
    current: float | None = None
    energy: float | None = None
    socket_sensors: tuple[float | str | bool | None, ...] = ()


@dataclass(frozen=True)
class ClimateChoice:
    label: str
    value: str

    @property
    def safe_id(self) -> str:
        return safe_id(self.value)


@dataclass(frozen=True)
class ClimateProfile:
    temperature_min: float = 16.0
    temperature_max: float = 30.0
    temperature_step: float = 0.5
    temperature_unit: str = "C"
    hvac_modes: tuple[ClimateChoice, ...] = (
        ClimateChoice("Auto", "auto"), ClimateChoice("Cool", "cool"),
        ClimateChoice("Heat", "heat"), ClimateChoice("Fan", "fan_only"),
    )
    fan_modes: tuple[ClimateChoice, ...] = (
        ClimateChoice("Auto", "auto"), ClimateChoice("Min", "low"),
        ClimateChoice("Mid", "medium"), ClimateChoice("Max", "high"),
    )

    @property
    def operating_modes(self) -> tuple[ClimateChoice, ...]:
        """Power controls handle off; mode choices only select operating modes."""
        return tuple(choice for choice in self.hvac_modes if choice.value != "off")

    @property
    def display_unit(self) -> str:
        return temperature_display_unit(self.temperature_unit)

    @property
    def temperature_precision(self) -> int:
        return min(6, max(0, *(-Decimal(str(value)).normalize().as_tuple().exponent
                              for value in (self.temperature_step, self.temperature_min))))


def parse_climate_profile(config: Any) -> ClimateProfile:
    if not isinstance(config, dict):
        raise ValueError("Entity climate settings must be a mapping")
    defaults = ClimateProfile()
    if set(config) - set(defaults.__dataclass_fields__):
        raise ValueError("Unknown entity climate settings")
    numbers = {}
    for key in ("temperature_min", "temperature_max", "temperature_step"):
        value = config.get(key, getattr(defaults, key))
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"climate.{key} must be a finite number")
        numbers[key] = float(value)
    if numbers["temperature_min"] >= numbers["temperature_max"] or not (
            0 < numbers["temperature_step"] <= numbers["temperature_max"] - numbers["temperature_min"]):
        raise ValueError("Climate temperature range/step is invalid")
    unit = config.get("temperature_unit", defaults.temperature_unit)
    if unit not in ("C", "F"):
        raise ValueError("climate.temperature_unit must be C or F")
    choices = {}
    names = {"auto": "Auto", "cool": "Cool", "heat": "Heat", "heat_cool": "Heat/cool",
             "fan_only": "Fan", "dry": "Dry", "off": "Off"}
    for key in ("hvac_modes", "fan_modes"):
        value = config.get(key)
        if value is None:
            if key in config:
                raise ValueError(f"climate.{key} must be a list or label/value mapping")
            choices[key] = getattr(defaults, key)
            continue
        if isinstance(value, list):
            pairs = [(names.get(item, item) if isinstance(item, str) else item, item) for item in value]
        elif isinstance(value, dict):
            pairs = list(value.items())
        else:
            raise ValueError(f"climate.{key} must be a list or label/value mapping")
        if not (1 if key == "hvac_modes" else 0) <= len(pairs) <= MAX_CLIMATE_OPTIONS:
            raise ValueError(f"climate.{key} has an invalid number of choices (maximum {MAX_CLIMATE_OPTIONS})")
        ids = set()
        entries = []
        for label, mode in pairs:
            if any(not isinstance(text, str) or not text.strip() or "\0" in text or "\n" in text
                   for text in (label, mode)):
                raise ValueError(f"climate.{key} choices require non-empty labels and values")
            if key == "hvac_modes" and mode not in names:
                raise ValueError(f"Unsupported HVAC mode: {mode!r}")
            mode_id = safe_id(mode)
            if mode_id in ids:
                raise ValueError(f"Duplicate climate.{key} value or ID collision")
            ids.add(mode_id)
            entries.append(ClimateChoice(label, mode))
        choices[key] = tuple(entries)
    if all(choice.value == "off" for choice in choices["hvac_modes"]):
        raise ValueError("climate.hvac_modes must include an operating mode")
    return ClimateProfile(**numbers, temperature_unit=unit, **choices)


@dataclass(frozen=True)
class HumidifierExtra:
    entity: str
    name: str
    attribute: str = ""
    unit: str = ""


@dataclass(frozen=True)
class HumidifierProfile:
    humidity_min: int = 0
    humidity_max: int = 100
    humidity_step: int = 5
    modes: tuple[ClimateChoice, ...] = ()
    card_modes: tuple[str, ...] = ()
    water_entity: str = ""
    water_attribute: str = ""
    water_low: int = 0
    water_normal: int = 1
    water_full: int = 2
    extras: tuple[HumidifierExtra, ...] = ()

    @property
    def quick_modes(self) -> tuple[ClimateChoice, ...]:
        by_value = {choice.value: choice for choice in self.modes}
        return tuple(by_value[value] for value in self.card_modes)

    @property
    def card_mode_indices(self) -> tuple[int, ...]:
        return tuple(next(index for index, choice in enumerate(self.modes) if choice.value == value)
                     for value in self.card_modes)


def parse_humidifier_profile(config: Any) -> HumidifierProfile:
    if not isinstance(config, dict) or set(config) - set(HumidifierProfile.__dataclass_fields__):
        raise ValueError("Unknown or invalid humidifier settings")
    values = {**HumidifierProfile().__dict__, **config}
    for key in ("humidity_min", "humidity_max", "humidity_step", "water_low", "water_normal", "water_full"):
        if type(values[key]) is not int:
            raise ValueError(f"humidifier.{key} must be an integer")
    if not 0 <= values["humidity_min"] < values["humidity_max"] <= 100 or not 1 <= values["humidity_step"] <= values["humidity_max"] - values["humidity_min"]:
        raise ValueError("Invalid humidifier humidity range/step")
    if len({values[key] for key in ("water_low", "water_normal", "water_full")}) != 3:
        raise ValueError("Humidifier water states must be distinct")
    water = values["water_entity"]
    if not isinstance(water, str) or (water and not re.fullmatch(r"sensor\.[a-z0-9_]+", water)):
        raise ValueError("humidifier.water_entity must reference a sensor")
    attribute = values["water_attribute"]
    if not isinstance(attribute, str) or "\0" in attribute or "\n" in attribute or (attribute and not water):
        raise ValueError("Invalid humidifier.water_attribute")
    modes = config.get("modes", [])
    pairs = list(modes.items()) if isinstance(modes, dict) else [(mode, mode) for mode in modes] if isinstance(modes, list) else None
    if pairs is None or len(pairs) > 7:
        raise ValueError("humidifier.modes must contain at most 7 choices")
    choices, ids = [], {"off"}
    for label, value in pairs:
        if any(not isinstance(s, str) or not s.strip() or "\0" in s or "\n" in s for s in (label, value)):
            raise ValueError("Humidifier modes require non-empty labels and values")
        if value.casefold() == "off":
            continue  # Power-off is a separate standard HA action.
        mode_id = safe_id(value)
        if mode_id in ids:
            raise ValueError("Duplicate humidifier mode ID")
        ids.add(mode_id)
        choices.append(ClimateChoice(label, value))
    values["modes"] = tuple(choices)
    quick = config.get("card_modes", [choice.value for choice in choices])
    if not isinstance(quick, list) or any(not isinstance(mode, str) for mode in quick):
        raise ValueError("humidifier.card_modes must be a list of mode values")
    if len(quick) != len(set(quick)) or set(quick) - {choice.value for choice in choices}:
        raise ValueError("humidifier.card_modes must contain unique values from humidifier.modes (without Off)")
    values["card_modes"] = tuple(quick)
    extras = config.get("extras", [])
    if not isinstance(extras, list) or len(extras) > 8:
        raise ValueError("humidifier.extras must be a list of at most 8 entities")
    entries = []
    seen = set()
    for extra in extras:
        if not isinstance(extra, dict) or set(extra) - {"entity", "name", "attribute", "unit"}:
            raise ValueError("Invalid humidifier extra settings")
        source = extra.get("entity", "")
        if not isinstance(source, str) or not re.fullmatch(r"(?:sensor|binary_sensor|switch)\.[a-z0-9_]+", source):
            raise ValueError("Humidifier extras support sensor, binary_sensor and switch")
        strings = {key: extra.get(key, "") for key in ("name", "attribute", "unit")}
        if any(not isinstance(s, str) or "\0" in s or "\n" in s for s in strings.values()):
            raise ValueError("Invalid humidifier extra label/attribute/unit")
        if source.startswith("switch.") and strings["attribute"]:
            raise ValueError("Switch extras control the entity state, not attributes")
        source_key = (source, strings["attribute"])
        if source_key in seen:
            raise ValueError("Duplicate humidifier extra")
        seen.add(source_key)
        strings["name"] = strings["name"] or title_from_object_id(source.split(".", 1)[1])
        entries.append(HumidifierExtra(source, **strings))
    values["extras"] = tuple(entries)
    return HumidifierProfile(**values)


SOCKET_READINGS = ("power", "voltage", "current")
SOCKET_DETAIL_READINGS = (*SOCKET_READINGS, "energy")
MAX_SOCKET_SENSORS = 12
SOCKET_DETAIL_STYLE_FIELDS = """bg_color text_color muted_text_color accent_color control_color
control_border_color divider_color page_padding page_gap control_gap control_height control_radius
control_border_width back_button_width back_icon_size detail_power_width socket_icon_size nav_button_width nav_button_height nav_icon_size
socket_detail_rows socket_detail_row_height socket_detail_row_gap socket_detail_name_width_pct
small_text_height normal_text_height view_popup_inset view_popup_vertical_inset view_popup_radius""".split()
SOCKET_STYLE_FIELDS = """card_color text_color muted_text_color accent_color control_color
disabled_color light_card_height card_radius control_gap socket_card_padding socket_name_height
socket_icon_size socket_row_gap room_name_font_size room_value_font_size
small_text_height normal_text_height""".split()


@dataclass(frozen=True)
class SocketReading:
    entity: str
    attribute: str = ""
    scale: float = 1.0
    name: str = ""
    unit: str = ""
    precision: int = 1
    kind: str = "numeric"

    @property
    def import_id(self) -> str:
        if not self.attribute and (self.kind == "numeric" or not self.entity.startswith("sensor.")):
            return "ha_" + safe_id(self.entity)
        key = (self.entity + "\0" + self.attribute + ("\0text" if self.kind != "numeric" else "")).encode()
        return "ha_socket_" + hashlib.sha256(key).hexdigest()[:16]


@dataclass(frozen=True)
class SocketProfile:
    power: SocketReading | None = None
    voltage: SocketReading | None = None
    current: SocketReading | None = None
    energy: SocketReading | None = None
    sensors: tuple[SocketReading, ...] = ()

    @property
    def metric_items(self) -> tuple[tuple[str, SocketReading], ...]:
        return tuple((name, binding) for name in SOCKET_DETAIL_READINGS if (binding := getattr(self, name)) is not None) + tuple(
            (f"extra_{i}", binding) for i, binding in enumerate(self.sensors))

    @property
    def mask(self) -> int:
        return sum(1 << i for i, name in enumerate(SOCKET_READINGS) if getattr(self, name) is not None)


def socket_float(value: Any, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    try:
        represented = struct.unpack("f", struct.pack("f", value))[0]
    except (OverflowError, struct.error) as error:
        raise ValueError(f"{label} must fit a 32-bit float") from error
    if not math.isfinite(represented) or (value != 0 and represented == 0):
        raise ValueError(f"{label} must fit a nonzero 32-bit float")
    return float(value)


def parse_socket_profile(config: Any) -> SocketProfile:
    if not isinstance(config, dict) or set(config) - {*SOCKET_DETAIL_READINGS, "sensors"}:
        raise ValueError("socket supports power, voltage, current, energy and sensors")
    readings = {}
    def parse_binding(binding, name, extra=False):
        if isinstance(binding, str):
            binding = {"entity": binding}
        if not isinstance(binding, dict) or set(binding) - {"entity", "attribute", "scale", "name", "unit", "precision", "kind"}:
            raise ValueError(f"socket.{name} requires an entity/attribute/scale binding")
        entity, attribute = binding.get("entity"), binding.get("attribute", "")
        if not isinstance(entity, str) or not re.fullmatch(r"[a-z_][a-z0-9_]*\.[a-z0-9_]+", entity):
            raise ValueError(f"socket.{name} requires a valid entity")
        if not isinstance(attribute, str) or any(ord(c) < 32 or ord(c) == 127 for c in attribute):
            raise ValueError(f"socket.{name} attribute must be a single-line string")
        kind = binding.get("kind", "binary" if extra and entity.startswith("binary_sensor.") else "numeric")
        if kind not in ("numeric", "binary", "text") or (not extra and kind != "numeric"):
            raise ValueError("Socket sensors support numeric, binary or text kinds; standard readings must be numeric")
        if kind == "numeric" and not attribute and not entity.startswith("sensor."):
            raise ValueError(f"socket.{name} requires a sensor state or a numeric attribute")
        scale = socket_float(binding.get("scale", 1.0), f"socket.{name} scale")
        if scale <= 0:
            raise ValueError(f"socket.{name} scale must be finite and positive")
        if kind != "numeric" and (scale != 1 or "precision" in binding or binding.get("unit")):
            raise ValueError("Text/binary socket sensors do not use scale, precision or unit")
        default_name, default_unit, default_precision = {
            "power": ("Power", "W", 1), "voltage": ("Voltage", "V", 1),
            "current": ("Current", "A", 2), "energy": ("Total energy", "kWh", 3),
        }.get(name, (title_from_object_id(entity.split(".", 1)[1]), "", 1))
        label, unit = binding.get("name", default_name), binding.get("unit", default_unit)
        for value in (label, unit):
            if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value) or len(value) > 128:
                raise ValueError("Socket sensor name/unit must be single-line strings of at most 128 characters")
        if not label.strip():
            raise ValueError("Socket sensor name must not be empty")
        if not extra and unit != default_unit:
            raise ValueError("Use scale to convert standard socket readings to W/V/A/kWh")
        precision = binding.get("precision", default_precision)
        if type(precision) is not int or not 0 <= precision <= 6:
            raise ValueError("Socket precision must be between 0 and 6")
        return SocketReading(entity, attribute, scale, label, unit, precision, kind)
    for name in SOCKET_DETAIL_READINGS:
        if name in config:
            readings[name] = parse_binding(config[name], name)
    sensors = config.get("sensors", [])
    if not isinstance(sensors, list) or len(sensors) > MAX_SOCKET_SENSORS:
        raise ValueError(f"socket.sensors must contain at most {MAX_SOCKET_SENSORS} bindings")
    readings["sensors"] = tuple(parse_binding(binding, f"sensors[{i}]", True) for i, binding in enumerate(sensors))
    return SocketProfile(**readings)


def socket_mock_value(entity: Entity, field: str):
    values = entity.simulator
    if field.startswith("extra_"):
        index = int(field[6:])
        return values.socket_sensors[index] if index < len(values.socket_sensors) else None
    return getattr(values, field)


def validate_socket_layout(pages: list[Page], style: dict[str, Any]) -> None:
    if not any(e.is_socket for page in pages for e in page.entities):
        return
    name_height = style["normal_text_height"] if style["room_name_font_size"] == 18 else style["small_text_height"]
    value_height = max(name_height, style["normal_text_height"] if style["room_value_font_size"] == 18 else style["small_text_height"])
    header = max(style["socket_name_height"], style["socket_icon_size"])
    if not 12 <= style["socket_icon_size"] <= 32 or style["socket_name_height"] < name_height:
        raise ValueError("Socket header must fit its icon and name")
    minimum = 2 * style["socket_card_padding"] + header + value_height + style["small_text_height"] + 2 * style["socket_row_gap"]
    if minimum > style["light_card_height"]:
        raise ValueError("Socket content does not fit light_card_height; reduce socket padding/gaps or increase tile height")
    width = (320 - 2 * style["page_padding"] - (style["light_tile_columns"] - 1) * style["control_gap"]) // style["light_tile_columns"]
    if width - 2 * style["socket_card_padding"] - style["socket_icon_size"] - style["control_gap"] < name_height:
        raise ValueError("Socket tile has insufficient width for its name")
    if not 1 <= style["socket_detail_rows"] <= 8 or not 35 <= style["socket_detail_name_width_pct"] <= 65:
        raise ValueError("Socket details require 1..8 rows and 35..65 percent name width")
    if style["socket_detail_row_height"] < style["normal_text_height"]:
        raise ValueError("Socket detail rows must fit the value font")
    detail_height = (2 * style["page_padding"] + style["control_height"] + style["normal_text_height"] +
                     style["nav_button_height"] + 3 * style["page_gap"] +
                     style["socket_detail_rows"] * style["socket_detail_row_height"] +
                     (style["socket_detail_rows"] - 1) * style["socket_detail_row_gap"])
    if detail_height > 480:
        raise ValueError("Socket details do not fit 480px; reduce rows, row height or gaps")
    if style["back_button_width"] + style["detail_power_width"] + 2 * style["control_gap"] + style["normal_text_height"] > 320 - 2 * style["page_padding"]:
        raise ValueError("Socket details header must fit Back, name and power button")
    if not 0 <= style["view_popup_radius"] <= 8:
        raise ValueError("view_popup_radius must be between 0 and 8")
    if not 0 <= style["view_popup_inset"] <= 40 or not 0 <= style["view_popup_vertical_inset"] <= 40:
        raise ValueError("Popup insets must be between 0 and 40")


@dataclass(frozen=True)
class PlantTileProfile:
    view: str = ""
    severity: str = "warning"


@dataclass(frozen=True)
class Entity:
    entity_id: str
    name: str
    domain: str
    object_id: str
    safe_id: str
    page_safe_id: str
    group: str = ""
    group_name: str = ""
    unit: str | None = None
    device_class: str | None = None
    light_type: str = "dimmer"
    min_color_temperature: int = 2700
    max_color_temperature: int = 6500
    climate: ClimateProfile = ClimateProfile()
    humidifier: HumidifierProfile = HumidifierProfile()
    widget: str = ""
    socket: SocketProfile = SocketProfile()
    plant: PlantTileProfile = PlantTileProfile()
    simulator: SimValues | None = None

    @property
    def source_safe_id(self) -> str:
        return safe_id(self.entity_id)

    @property
    def is_socket(self) -> bool:
        return self.widget == "socket"

    @property
    def is_tile(self) -> bool:
        return self.domain == "light" or self.is_socket or self.is_plant

    @property
    def is_plant(self) -> bool:
        return self.domain == "plant"

    @property
    def has_color_temperature(self) -> bool:
        return self.light_type in {"color_temp", "rgb_color_temp"}

    @property
    def has_rgb(self) -> bool:
        return self.light_type in {"rgb", "rgbw", "rgb_color_temp"}

    @property
    def display_unit(self) -> str:
        unit = self.unit or ""
        if self.device_class not in (None, "temperature"):
            return unit
        return temperature_display_unit(unit)

    @property
    def sensor_icon(self) -> str:
        if self.device_class is not None:
            return {"temperature": "thermometer", "humidity": "droplet"}.get(self.device_class, "gauge")
        if (self.unit or "").strip().lstrip("\N{DEGREE SIGN}") in {"C", "F", "deg C", "deg F"}:
            return "thermometer"
        if "humidity" in self.object_id.split("_"):
            return "droplet"
        return "gauge"


@dataclass(frozen=True)
class Page:
    name: str
    safe_id: str
    entities: list[Entity]


SENSOR_STYLE_FIELDS = """card_color text_color muted_text_color accent_color divider_color
sensor_group_height sensor_group_padding sensor_icon_size sensor_divider_height sensor_value_gap
control_gap card_radius small_text_height normal_text_height""".split()
ROOM_CHROME_STYLE_FIELDS = """text_color muted_text_color control_color control_border_color
page_padding header_height header_clock_width header_clock_font_size header_icon_size header_status_gap
small_text_height normal_text_height title_text_height large_text_height control_gap control_radius
control_padding control_border_width nav_button_width nav_button_height nav_icon_size control_row_padding""".split()
ENTITY_CARD_STYLE_FIELDS = """card_color text_color muted_text_color accent_color
entity_card_height card_padding card_radius control_gap text_gap small_text_height normal_text_height
entity_name_width_pct entity_value_width_pct""".split()
ROOM_PAGE_STYLE_FIELDS = """bg_color muted_text_color page_padding page_gap navigation_gap card_gap
scrollbar_width scrollbar_inset""".split()
LIGHT_ROW_STYLE_FIELDS = "light_card_height light_tile_columns control_gap".split()
SYSTEM_STYLE_FIELDS = """bg_color text_color muted_text_color accent_color status_error_color
control_color control_border_color divider_color disabled_color
page_padding page_gap card_gap text_gap control_gap control_height control_row_padding
control_padding control_border_width control_radius back_button_width back_icon_size
small_text_height normal_text_height system_info_height system_name_width_pct
system_value_width_pct system_separator_width system_separator_height system_row_gap
system_slider_height system_slider_heading_height system_slider_value_width_pct
system_row_height system_option_label_width_pct system_option_value_width_pct
system_option_height system_switch_width system_switch_height slider_row_height
slider_inset slider_height slider_knob_padding scrollbar_width scrollbar_inset""".split()


def sensor_group_rows(entities: list[Entity], columns: int) -> dict[int, list[list[int]]]:
    """Place all rows of a room-local group at its first occurrence, retaining sensor order."""
    if type(columns) is not int or not 1 <= columns <= 6:
        raise ValueError("sensor_group_columns must be between 1 and 6")
    groups: dict[str, list[int]] = {}
    for index, entity in enumerate(entities):
        if entity.domain == "sensor" and entity.group:
            groups.setdefault(entity.group, []).append(index)
    result = {}
    for indices in groups.values():
        width = min(2, columns) if entities[indices[0]].group_name else columns
        result[indices[0]] = [indices[start:start + width] for start in range(0, len(indices), width)]
    return result


def light_tile_rows(entities: list[Entity], columns: int, *, is_tile=None) -> dict[int, int]:
    """Plan adjacent light/socket/plant tiles without reordering other device types."""
    if type(columns) is not int or columns not in (1, 2):
        raise ValueError("light_tile_columns must be 1 or 2")
    is_tile = is_tile or (lambda entity: entity.is_tile)
    rows = {}
    index = 0
    while index < len(entities):
        if not is_tile(entities[index]):
            index += 1
            continue
        start = index
        while index < len(entities) and is_tile(entities[index]) and index - start < columns:
            index += 1
        rows[start] = index - start
    return rows


def safe_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("IDs require a non-empty string")
    transliterated = "".join(_RUSSIAN_ASCII.get(char, char) for char in value.strip().casefold())
    normalized = unicodedata.normalize("NFKD", transliterated)
    normalized = "".join(
        char if char.isascii() else (f"_u{ord(char):x}_" if char.isalnum() else "_")
        for char in normalized if not unicodedata.combining(char)
    )
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", normalized)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        raise ValueError("Cannot build an id from an empty value")
    if cleaned[0].isdigit():
        cleaned = f"id_{cleaned}"
    if len(cleaned) > MAX_ID_LENGTH:
        digest = hashlib.sha256(cleaned.encode("ascii")).hexdigest()[:12]
        cleaned = cleaned[:MAX_ID_LENGTH - 13].rstrip("_") + "_" + digest
    return cleaned


def title_from_object_id(object_id: str) -> str:
    return object_id.replace("_", " ").replace("-", " ").title()


def display_name(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"{context} must be a non-empty single-line string without control characters")
    return value


def system_page_name(config: dict[str, Any]) -> str:
    panel = config.get("panel", {})
    if not isinstance(panel, dict):
        raise ValueError("panel must be a mapping")
    settings = panel.get("system", {})
    if not isinstance(settings, dict) or set(settings) - {"name"}:
        raise ValueError("panel.system only supports name")
    return display_name(settings.get("name", "System"), "panel.system.name")


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


_COMPONENT_LISTS = {
    "sensor", "text_sensor", "binary_sensor", "output", "light", "switch",
    "button", "number", "select", "fan", "climate", "cover", "script",
    "interval", "display", "touchscreen", "external_components", "spi", "i2c", "uart",
}


def component_list(value: Any, section: str) -> list[dict[str, Any]]:
    items = value if isinstance(value, list) else [value]
    if not all(isinstance(item, dict) for item in items):
        raise ValueError(f"ESPHome section {section!r} must be a mapping or list of mappings")
    if any("id" in item and (not isinstance(item["id"], str) or not item["id"]) for item in items):
        raise ValueError(f"ESPHome section {section!r} requires non-empty string IDs")
    ids = [item["id"] for item in items if "id" in item]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate IDs within ESPHome section {section!r}")
    return items


def validate_component_ids(config: dict[str, Any]) -> None:
    """Check declarations, not references inside automations and action payloads."""
    seen: dict[str, str] = {}
    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            declared = value.get("id")
            if isinstance(declared, str):
                if declared in seen:
                    raise ValueError(f"Duplicate ESPHome ID {declared!r}: {seen[declared]} and {path}")
                seen[declared] = path
            for key, child in value.items():
                if str(key).startswith("on_") or key in {"then", "else", "parameters", "variables", "data", "data_template"}:
                    continue
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
    for section, value in config.items():
        if section != "substitutions":
            visit(value, str(section))


def merge_esphome_config(base: dict[str, Any], overlay: dict[str, Any], *, generated: bool = False) -> dict[str, Any]:
    """Add components; hardware definitions with the same explicit ID are overrides."""
    result = deepcopy(base)
    for key, value in overlay.items():
        if key in _COMPONENT_LISTS:
            component_list(value, key)
        if generated and key == "lvgl":
            if not isinstance(value, dict):
                raise ValueError("The panel generator requires a single LVGL mapping")
            if "pages" in value:
                raise ValueError("lvgl.pages is generated; define pages in panel.yaml")
        if key in _COMPONENT_LISTS and key in result:
            # The generator's placeholder is not an additional physical display.
            if generated and key == "display":
                result[key] = deepcopy(value)
                continue
            items = deepcopy(component_list(result[key], key))
            extra = component_list(value, key)
            if key in {"spi", "i2c", "uart"} and any("id" not in item for item in items + extra):
                if len(items) == len(extra) == 1 and items[0].get("id") == extra[0].get("id"):
                    result[key] = [deep_merge(items[0], extra[0])]
                    continue
                raise ValueError(f"Multiple {key} buses require explicit IDs and matching device bus references")
            by_id = {item["id"]: index for index, item in enumerate(items) if "id" in item}
            for item in extra:
                item_id = item.get("id")
                if item_id is not None and item_id in by_id:
                    if generated:
                        raise ValueError(f"Device {key} ID {item_id!r} conflicts with a generated component")
                    index = by_id[item_id]
                    if items[index].get("platform") != item.get("platform", items[index].get("platform")):
                        raise ValueError(f"Cannot change platform for {key} ID {item_id!r}")
                    items[index] = deep_merge(items[index], item)
                else:
                    if item_id is not None:
                        by_id[item_id] = len(items)
                    items.append(deepcopy(item))
            result[key] = items
        elif key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def system_section_heights(style: dict[str, Any]) -> tuple[int, int]:
    network = 3 * style["system_info_height"] + 2 * style["text_gap"]
    settings = (2 * style["system_slider_height"] + 3 * style["system_row_height"] +
                4 * style["system_row_gap"])
    return network, settings


def validate_resolved_style(theme: dict[str, Any], layout: dict[str, Any]) -> dict[str, Any]:
    """Validate resolved geometry without templates or filesystem access."""
    for key, value in layout.items():
        if type(value) is not int:
            raise ValueError(f"Template layout {key} must be an integer")
        if value < 0:
            raise ValueError(f"Template layout {key} must not be negative")
        if key.endswith("_pct") and value > 100:
            raise ValueError(f"Template layout {key} must be between 0 and 100")
    if not 1 <= layout["sensor_group_columns"] <= 6:
        raise ValueError("sensor_group_columns must be between 1 and 6")
    if any(layout[key] not in (14, 18) for key in ("room_name_font_size", "room_value_font_size")):
        raise ValueError("Room widget fonts must be 14 or 18")
    if any(layout[key] not in (14, 18) for key in ("device_card_name_font_size", "device_card_mode_font_size")) or layout["device_card_value_font_size"] not in (14, 18, 24):
        raise ValueError("Device names/modes must be 14/18 and readings 14/18/24")
    device_heights = {14: layout["small_text_height"], 18: layout["normal_text_height"], 24: layout["title_text_height"]}
    device_header_min = max(device_heights[layout["device_card_name_font_size"]], device_heights[layout["device_card_value_font_size"]], device_heights[layout["device_card_mode_font_size"]])
    room_inset = 2 * (layout["device_card_control_padding"] + layout["control_border_width"])
    if min(layout["climate_card_header_height"], layout["humidifier_status_height"]) < device_header_min or layout["device_card_control_height"] < room_inset + max(layout["climate_step_icon_size"], device_heights[layout["device_card_value_font_size"]], device_heights[layout["device_card_mode_font_size"]]):
        raise ValueError("Device card rows must fit their fonts and icons")
    icon_clearance = 2 * (layout["control_padding"] + layout["control_border_width"])
    if not 18 <= layout["back_icon_size"] <= min(layout["back_button_width"], layout["control_height"]) - icon_clearance:
        raise ValueError("back_icon_size must fit the back button")
    if not 18 <= layout["humidifier_step_icon_size"] <= layout["control_height"] - icon_clearance:
        raise ValueError("humidifier_step_icon_size must fit the humidity buttons")
    light_value_height = layout["normal_text_height"] if layout["room_value_font_size"] == 18 else layout["small_text_height"]
    if layout["light_card_height"] < (2 * layout["light_tile_padding"] + max(layout["light_tile_name_height"], layout["light_icon_size"]) +
            light_value_height + layout["light_tile_meter_height"] + 2 * layout["light_tile_gap"]):
        raise ValueError("Light card must fit its header, readings and brightness meter")
    if not 1 <= layout["light_tile_meter_height"] <= 6 or not 6 <= layout["light_tile_swatch_size"] <= layout["small_text_height"]:
        raise ValueError("Invalid light meter/swatch size")
    if not 1 <= layout["humidifier_mode_columns"] <= 4:
        raise ValueError("humidifier_mode_columns must be between 1 and 4")
    minimum_humidifier = (2 * layout["humidifier_card_padding"] + layout["humidifier_status_height"] +
        layout["humidifier_row_gap"] + layout["device_card_control_height"])
    if layout["humidifier_card_height"] < minimum_humidifier or layout["humidifier_reading_height"] < layout["small_text_height"] + layout["normal_text_height"] + 3:
        raise ValueError("Humidifier card is too small for its readings and controls")
    if not 12 <= layout["humidifier_icon_size"] <= layout["humidifier_status_height"] or layout["humidifier_status_height"] < layout["normal_text_height"]:
        raise ValueError("Humidifier status row must fit its icons and readings")
    if layout["humidifier_value_width"] < {14: 40, 18: 52, 24: 68}[layout["device_card_value_font_size"]] or layout["humidifier_water_width"] < 12 or (
            layout["humidifier_value_width"] + layout["humidifier_icon_size"] + 2 +
            layout["humidifier_water_width"] + 2 * layout["humidifier_row_gap"] + 64 >
            320 - 2 * (layout["page_padding"] + layout["humidifier_card_padding"])):
        raise ValueError("Humidifier status row has insufficient width")
    if (320 - 2 * (layout["page_padding"] + layout["humidifier_card_padding"]) -
            (layout["humidifier_mode_columns"] - 1) * layout["control_gap"]) // layout["humidifier_mode_columns"] < 44:
        raise ValueError("Humidifier mode buttons must be at least 44 pixels wide")
    if not 1 <= layout["light_tile_columns"] <= 2:
        raise ValueError("light_tile_columns must be 1 or 2 on a 320px panel")
    if not 16 <= layout["light_icon_size"] <= 40:
        raise ValueError("light_icon_size must be between 16 and 40")
    if layout["light_tile_name_height"] < layout["small_text_height"]:
        raise ValueError("light_tile_name_height must fit at least one text line")
    if not 2 <= layout["light_preset_columns"] <= 4:
        raise ValueError("light_preset_columns must be between 2 and 4")
    preset_width = (320 - 2 * layout["page_padding"] -
                    (layout["light_preset_columns"] - 1) * layout["control_gap"]) // layout["light_preset_columns"]
    if not 32 <= layout["light_preset_size"] <= 60 or preset_width < layout["light_preset_size"] + 8:
        raise ValueError("Light presets need room for their swatch and selection outline")
    if layout["light_preset_row_height"] < layout["light_preset_size"] + 8:
        raise ValueError("light_preset_row_height must fit the selection outline")
    if not 128 <= layout["light_picker_size"] <= 320 - 2 * layout["page_padding"]:
        raise ValueError("light_picker_size must fit the content width")
    if not 12 <= layout["light_picker_ring_width"] <= 32 or layout["light_picker_padding"] < 6:
        raise ValueError("The light picker needs a usable ring and knob clearance")
    if not 32 <= layout["light_picker_preview_size"] <= layout["light_picker_size"] - 2 * (
            layout["light_picker_padding"] + layout["light_picker_ring_width"]) - 8:
        raise ValueError("The light picker preview must fit inside the ring")
    if not 12 <= layout["light_detail_icon_size"] <= min(32, layout["control_height"] - 10):
        raise ValueError("light_detail_icon_size must fit the controls")
    if not 16 <= layout["light_current_swatch_size"] <= layout["control_height"] - 8:
        raise ValueError("light_current_swatch_size must fit the color row")
    tile_width = (320 - 2 * layout["page_padding"] -
                  (layout["light_tile_columns"] - 1) * layout["control_gap"]) // layout["light_tile_columns"]
    if tile_width - 2 * layout["light_tile_padding"] - layout["light_icon_size"] - layout["control_gap"] < layout["small_text_height"]:
        raise ValueError("Light tile has insufficient width for its icon and name")
    if layout["slider_inset"] < layout["slider_height"] // 2 + layout["slider_knob_padding"] + 2:
        raise ValueError("slider_inset is too small for the slider knob")
    if layout["slider_row_height"] < layout["slider_height"] + 2 * layout["slider_knob_padding"] + 4:
        raise ValueError("slider_row_height is too small for the slider knob")
    clock_font = layout["header_clock_font_size"]
    clock_heights = {14: "small_text_height", 18: "normal_text_height", 24: "title_text_height", 36: "large_text_height"}
    if clock_font not in clock_heights:
        raise ValueError("header_clock_font_size must be 14, 18, 24 or 36")
    minimum_heights = {
        "header_height": max(layout["header_icon_size"], layout["normal_text_height"], layout["small_text_height"],
                             layout[clock_heights[clock_font]]),
        "system_slider_height": layout["system_slider_heading_height"] + layout["control_gap"] + layout["slider_row_height"],
        "system_info_height": layout["normal_text_height"],
        "system_row_height": max(layout["system_option_height"], layout["system_switch_height"]),
        "sensor_group_height": 2 * layout["sensor_group_padding"] + max(layout["sensor_divider_height"],
            layout["sensor_icon_size"], layout["normal_text_height"]),
        "nav_button_height": 2 * (layout["control_padding"] + layout["control_border_width"]) +
            max(layout["small_text_height"], layout["nav_icon_size"]),
    }
    for key, minimum in minimum_heights.items():
        if layout[key] < minimum:
            raise ValueError(f"Template layout {key} is too small for its content (minimum {minimum})")
    if not 1 <= layout["system_separator_width"] <= 4 or not 1 <= layout["system_separator_height"] <= layout["system_info_height"]:
        raise ValueError("System separator must fit its connection status row")
    network_height, settings_height = system_section_heights(layout)
    system_available = (480 - 2 * layout["page_padding"] - layout["control_height"] -
                        2 * layout["control_row_padding"] - layout["page_gap"])
    if network_height + settings_height + layout["card_gap"] > system_available:
        raise ValueError("System controls do not fit without scrolling; reduce system dimensions or spacing")
    minimum_card_height = 2 * layout["climate_card_padding"] + layout["climate_card_header_height"] + layout["text_gap"] + layout["device_card_control_height"]
    if layout["climate_card_height"] < minimum_card_height:
        raise ValueError("climate_card_height is too small for the climate controls")
    card_width = 320 - 2 * (layout["page_padding"] + layout["climate_card_padding"])
    if card_width < 2 * layout["climate_card_step_width"] + layout["climate_card_power_width"] + 2 * layout["control_gap"] + layout["climate_card_power_gap"] + 64:
        raise ValueError("Climate card has insufficient width for temperature and controls")
    if layout["climate_card_power_gap"] < layout["control_gap"]:
        raise ValueError("climate_card_power_gap must not be smaller than control_gap")
    if layout["climate_card_mode_width"] < layout["climate_card_icon_size"] + layout["control_gap"] + 32 or card_width < layout["climate_card_mode_width"] + layout["climate_card_icon_size"] + 2 * layout["control_gap"] + 32:
        raise ValueError("Climate card has insufficient width for its name and mode")
    if min(layout["climate_card_step_width"], layout["climate_card_power_width"]) < 32:
        raise ValueError("Climate card buttons must be at least 32 pixels wide")
    if not 12 <= layout["climate_card_icon_size"] <= min(32, layout["normal_text_height"]):
        raise ValueError("climate_card_icon_size must fit the climate card heading")
    control_inset = 2 * (layout["control_padding"] + layout["control_border_width"])
    if not 16 <= layout["climate_step_icon_size"] <= min(
            layout["control_height"], layout["climate_card_step_width"], layout["climate_step_button_width"]) - control_inset:
        raise ValueError("climate_step_icon_size must fit the temperature buttons")
    if not 12 <= layout["climate_choice_icon_size"] <= 32:
        raise ValueError("climate_choice_icon_size must be between 12 and 32")
    if layout["climate_choice_height"] < control_inset + layout["climate_choice_icon_size"] + layout["climate_choice_gap"] + layout["small_text_height"]:
        raise ValueError("climate_choice_height must fit its icon and label")
    if not 1 <= layout["climate_choice_columns"] <= 4:
        raise ValueError("climate_choice_columns must be between 1 and 4")
    choice_width = (320 - 2 * layout["page_padding"] - (layout["climate_choice_columns"] - 1) * layout["control_gap"]) // layout["climate_choice_columns"]
    if choice_width < control_inset + max(layout["climate_choice_icon_size"], 32):
        raise ValueError("Climate choices have insufficient width for icons and labels")
    if layout["page_padding"] < layout["scrollbar_inset"] + layout["scrollbar_width"] + 1:
        raise ValueError("page_padding must leave room for the left scrollbar and its inset")
    if not 12 <= layout["sensor_icon_size"] <= 32 or not 12 <= layout["nav_icon_size"] <= 32:
        raise ValueError("sensor_icon_size and nav_icon_size must be between 12 and 32")
    if layout["nav_button_width"] < 2 * (layout["control_padding"] + layout["control_border_width"]) + max(
            layout["nav_icon_size"], layout["small_text_height"]):
        raise ValueError("nav_button_width is too small for its label or icon")
    if 3 * layout["nav_button_width"] + 4 * layout["control_gap"] + 64 > 320 - 2 * layout["page_padding"]:
        raise ValueError("Navigation has insufficient width for three buttons and its counter")
    if not 12 <= layout["header_icon_size"] <= 32:
        raise ValueError("header_icon_size must be between 12 and 32")
    clock_width = {14: 40, 18: 56, 24: 76, 36: 112}[clock_font]
    if layout["header_clock_width"] < clock_width:
        raise ValueError(f"header_clock_width must fit HH:MM at font size {clock_font} (minimum {clock_width})")
    header_status_width = layout["header_clock_width"] + 3 * (layout["header_icon_size"] + layout["header_status_gap"])
    if 320 - 2 * layout["page_padding"] - header_status_width - layout["control_gap"] < layout["normal_text_height"]:
        raise ValueError("Header has insufficient width for its title and status indicators")
    for left, right in (("entity_name_width_pct", "entity_value_width_pct"),
                        ("climate_name_width_pct", "climate_value_width_pct"),
                        ("system_name_width_pct", "system_value_width_pct"),
                        ("system_option_label_width_pct", "system_option_value_width_pct")):
        if layout[left] + layout[right] > 100:
            raise ValueError(f"Template layout {left} + {right} exceeds 100 percent")
    return {**theme, **layout}


def layout_keys():
    return LAYOUT_FIELDS


def theme_keys():
    return THEME_FIELDS


def parse_simulator_values(item: str | dict[str, Any], domain: str) -> SimValues:
    settings = item.get("simulator", {}) if isinstance(item, dict) else {}
    if not isinstance(settings, dict):
        raise ValueError("Entity 'simulator' settings must be a mapping")

    item_config = item if isinstance(item, dict) else {}
    default_state = "off" if domain == "climate" else "unknown"
    rgb = settings.get("rgb", [255, 255, 255])
    if not isinstance(rgb, list) or len(rgb) != 3:
        raise ValueError("Entity simulator.rgb must contain exactly three values")

    brightness = int(settings.get("brightness", 100))
    if not 1 <= brightness <= 100:
        raise ValueError("Entity simulator.brightness must be between 1 and 100")

    channels = {
        "red": int(rgb[0]),
        "green": int(rgb[1]),
        "blue": int(rgb[2]),
        "white": int(settings.get("white", 0)),
    }
    for name, value in channels.items():
        if not 0 <= value <= 255:
            raise ValueError(f"Entity simulator {name} channel must be between 0 and 255")

    min_color_temperature = int(item_config.get("min_color_temperature", 2700))
    max_color_temperature = int(item_config.get("max_color_temperature", 6500))
    if min_color_temperature >= max_color_temperature:
        raise ValueError("min_color_temperature must be lower than max_color_temperature")

    extra_states = settings.get("extra_states", [])
    if not isinstance(extra_states, list) or len(extra_states) > 8 or any(not isinstance(s, str) or "\0" in s for s in extra_states):
        raise ValueError("simulator.extra_states must contain at most 8 strings without NUL")
    result = SimValues(
        state=str(settings.get("state", default_state)),
        fan_mode=str(settings.get("fan_mode", "auto")),
        current_temperature=float(settings.get("current_temperature", 0.0)),
        target_temperature=float(settings.get("target_temperature", 0.0)),
        has_value="value" in settings,
        value=float(settings.get("value", 0.0)),
        brightness=brightness,
        color_temperature=int(settings.get("color_temperature", 4000)),
        red=channels["red"],
        green=channels["green"],
        blue=channels["blue"],
        white=channels["white"],
        last_on_mode=settings.get("last_on_mode", ""),
        current_humidity=settings.get("current_humidity"),
        target_humidity=settings.get("target_humidity"),
        humidity_mode=settings.get("mode", ""),
        water_level=settings.get("water_level"),
        extra_states=tuple(extra_states),
        light_known=int("brightness" in settings) | (int("color_temperature" in settings) << 1) | (int("rgb" in settings) << 2) | (int("white" in settings) << 3),
        light_color_mode=settings.get("color_mode", "rgb" if "rgb" in settings and "color_temperature" not in settings else "color_temp" if "color_temperature" in settings else ""),
        **{key: settings.get(key) for key in SOCKET_READINGS},
        energy=settings.get("energy"),
        socket_sensors=tuple(settings.get("socket_sensors", [])) if isinstance(settings.get("socket_sensors", []), list) else (),
    )
    if result.light_color_mode not in ("", "color_temp", "rgb", "rgbw", "hs", "xy"):
        raise ValueError("Invalid simulator.color_mode")
    if not isinstance(settings.get("socket_sensors", []), list) or len(result.socket_sensors) > MAX_SOCKET_SENSORS:
        raise ValueError(f"simulator.socket_sensors must be a list of at most {MAX_SOCKET_SENSORS} values")
    for key in SOCKET_DETAIL_READINGS:
        value = getattr(result, key)
        if value is not None:
            socket_float(value, f"simulator.{key}")
    for key in ("current_humidity", "target_humidity", "water_level"):
        value = getattr(result, key)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
            raise ValueError(f"simulator.{key} must be a finite number")
        if key != "water_level" and value is not None and not 0 <= value <= 100:
            raise ValueError(f"simulator.{key} must be between 0 and 100")
    if not isinstance(result.humidity_mode, str) or "\0" in result.humidity_mode:
        raise ValueError("simulator.mode must be a string without NUL")
    if not isinstance(result.last_on_mode, str) or "\0" in result.last_on_mode:
        raise ValueError("simulator.last_on_mode must be a string without NUL")
    if not all(math.isfinite(value) for value in (result.value, result.current_temperature, result.target_temperature)):
        raise ValueError("Simulator numeric values must be finite")
    return result


def parse_entity(item: str | dict[str, Any], page_name: str) -> Entity:
    climate = parse_climate_profile(item.get("climate", {})) if isinstance(item, dict) else ClimateProfile()
    humidifier = parse_humidifier_profile(item.get("humidifier", {})) if isinstance(item, dict) else HumidifierProfile()
    device_class = item.get("device_class") if isinstance(item, dict) else None
    if device_class is not None and (not isinstance(device_class, str) or not device_class or "\0" in device_class):
        raise ValueError("Entity device_class must be a non-empty string without NUL")
    if isinstance(item, str):
        entity_id = item
        name = None
        unit = None
        group = ""
        light_type = "dimmer"
        min_color_temperature = 2700
        max_color_temperature = 6500
    elif isinstance(item, dict):
        entity_id = item.get("entity")
        name = item.get("name")
        unit = item.get("unit")
        group = str(item.get("group", ""))
        light_type = str(item.get("light_type", "dimmer"))
        min_color_temperature = int(item.get("min_color_temperature", 2700))
        max_color_temperature = int(item.get("max_color_temperature", 6500))
    else:
        raise ValueError(f"Unsupported entity item on page {page_name!r}: {item!r}")

    if not isinstance(entity_id, str) or not re.fullmatch(r"[a-z_][a-z0-9_]*\.[a-z0-9_]+", entity_id):
        raise ValueError(f"Invalid Home Assistant entity id on page {page_name!r}: {entity_id!r}")

    domain, object_id = entity_id.split(".", 1)
    widget = item.get("widget", "") if isinstance(item, dict) else ""
    if widget not in ("", "socket", "plant") or (widget == "socket" and domain != "switch") or (widget == "plant" and domain != "plant"):
        raise ValueError("widget: socket requires switch.*, widget: plant requires plant.*")
    if isinstance(item, dict) and "socket" in item and widget != "socket":
        raise ValueError("socket bindings require widget: socket")
    socket = parse_socket_profile(item.get("socket", {})) if isinstance(item, dict) else SocketProfile()
    plant_config = item.get("plant", {}) if isinstance(item, dict) else {}
    if isinstance(item, dict) and "plant" in item and domain != "plant":
        raise ValueError("Entity plant settings are only valid for plant entities")
    if not isinstance(plant_config, dict) or set(plant_config) - {"view", "severity"}:
        raise ValueError("plant room settings support view and severity")
    view, severity = plant_config.get("view", ""), plant_config.get("severity", "warning")
    if not isinstance(view, str) or "\0" in view or ("view" in plant_config and not view.strip()):
        raise ValueError("plant.view requires a nonempty view ID")
    if severity not in ("warning", "critical"):
        raise ValueError("plant.severity must be warning or critical")
    plant = PlantTileProfile(safe_id(view) if view else "", severity)
    if domain == "plant" and isinstance(item, dict) and "simulator" in item:
        raise ValueError("Plant mock data belongs to the shared views widget, not its room tile")
    if isinstance(item, dict) and "climate" in item and domain != "climate":
        raise ValueError("Entity climate settings are only valid for climate entities")
    if isinstance(item, dict) and "humidifier" in item and domain != "humidifier":
        raise ValueError("Entity humidifier settings are only valid for humidifier entities")
    if not domain or not object_id:
        raise ValueError(f"Invalid Home Assistant entity id on page {page_name!r}: {entity_id!r}")
    if light_type not in {"dimmer", "color_temp", "rgb", "rgbw", "rgb_color_temp"}:
        raise ValueError(f"Unsupported light_type: {light_type!r}")
    if min_color_temperature >= max_color_temperature:
        raise ValueError("min_color_temperature must be lower than max_color_temperature")
    if name is not None:
        display_name(name, f"Entity name on page {page_name!r}")
        if domain == "plant" and len(name.encode()) > 127:
            raise ValueError("Plant tile names must not exceed 127 UTF-8 bytes")
    if unit is not None and (not isinstance(unit, str) or "\0" in unit):
        raise ValueError(f"Entity unit on page {page_name!r} must be a string without NUL")

    simulator = parse_simulator_values(item, domain)
    if widget == "socket":
        if len(simulator.socket_sensors) > len(socket.sensors):
            raise ValueError("simulator.socket_sensors has more values than socket.sensors")
        for field, binding in socket.metric_items:
            value = (simulator.socket_sensors[int(field[6:])] if int(field[6:]) < len(simulator.socket_sensors) else None) if field.startswith("extra_") else getattr(simulator, field)
            if value is not None and binding is not None:
                if binding.kind == "numeric":
                    socket_float(value, f"simulator.{field}")
                    socket_float(value * binding.scale, f"Scaled simulator.{field}")
                elif binding.kind == "binary" and not (type(value) is bool or value in ("on", "off", "unknown", "unavailable")):
                    raise ValueError("Binary socket mock values require booleans or HA states")
                elif binding.kind == "text" and (not isinstance(value, str) or len(value.encode()) > 127 or "\0" in value):
                    raise ValueError("Socket text mock values must be at most 127 UTF-8 bytes without NUL")

    entity_safe_id = safe_id(entity_id)
    return Entity(
        entity_id=entity_id,
        name=name or title_from_object_id(object_id),
        domain=domain,
        object_id=object_id,
        safe_id=entity_safe_id,
        page_safe_id=safe_id(page_name),
        group=group,
        unit=unit,
        device_class=device_class,
        light_type=light_type,
        min_color_temperature=min_color_temperature,
        max_color_temperature=max_color_temperature,
        climate=climate,
        humidifier=humidifier,
        widget=widget,
        socket=socket,
        plant=plant,
        simulator=simulator,
    )


def parse_pages(config: dict[str, Any]) -> list[Page]:
    if not isinstance(config.get("pages"), dict) or not config["pages"]:
        raise ValueError("Panel config must contain at least one page in a 'pages' mapping")
    pages: list[Page] = []
    page_names: dict[str, str] = {}
    sources: dict[str, list[Entity]] = defaultdict(list)
    mock_values: dict[str, SimValues] = {}
    for page_key, page_config in config["pages"].items():
        page_id = safe_id(page_key)
        if "\0" in page_key:
            raise ValueError("Page names must not contain NUL")
        if page_id in page_names:
            raise ValueError(f"Page ID collision: {page_names[page_id]!r} and {page_key!r} normalize to {page_id!r}")
        page_names[page_id] = page_key
        page_name, items = page_key, page_config
        groups = {}
        if isinstance(page_config, dict):
            if set(page_config) - {"name", "entities", "groups"}:
                raise ValueError(f"Page {page_key!r} only supports name, entities and groups")
            page_name = page_config.get("name", page_key)
            items = page_config.get("entities")
            groups = page_config.get("groups", {})
        display_name(page_name, f"Page {page_key!r} name")
        if not isinstance(items, list):
            raise ValueError(f"Page {page_key!r} must contain a list of entities")
        entities = [parse_entity(item, page_key) for item in items]
        if not isinstance(groups, dict):
            raise ValueError(f"Page {page_key!r} groups must be a mapping")
        sensor_groups = {entity.group for entity in entities if entity.domain == "sensor" and entity.group}
        for group_id, group_config in groups.items():
            if not isinstance(group_id, str) or group_id not in sensor_groups:
                raise ValueError(f"Unknown sensor group {group_id!r} on page {page_key!r}")
            if not isinstance(group_config, dict) or set(group_config) - {"name"}:
                raise ValueError(f"Sensor group {group_id!r} only supports name")
            title = group_config.get("name", "")
            if "name" in group_config:
                display_name(title, f"Sensor group {group_id!r} name")
            entities = [replace(entity, group_name=title) if entity.domain == "sensor" and entity.group == group_id
                        else entity for entity in entities]
        seen = set()
        for entity, item in zip(entities, items):
            if entity.entity_id in seen:
                raise ValueError(f"Duplicate entity {entity.entity_id!r} on page {page_name!r}")
            seen.add(entity.entity_id)
            sources[entity.entity_id].append(entity)
            if isinstance(item, dict) and "simulator" in item:
                previous = mock_values.setdefault(entity.entity_id, entity.simulator)
                if previous != entity.simulator:
                    raise ValueError(f"Conflicting simulator values for {entity.entity_id!r}")
        pages.append(
            Page(
                name=page_name,
                safe_id=page_id,
                entities=entities,
            )
        )
    source_ids: dict[str, str] = {}
    for entity_id, instances in sources.items():
        source_id = instances[0].source_safe_id
        if source_id in source_ids:
            raise ValueError(f"Entity ID collision: {source_ids[source_id]!r} and {entity_id!r}")
        source_ids[source_id] = entity_id
        if instances[0].domain == "light" and len({
            (entity.light_type, entity.min_color_temperature, entity.max_color_temperature) for entity in instances
        }) != 1:
            raise ValueError(f"Conflicting light profiles for repeated entity {entity_id!r}")
        if instances[0].domain == "climate" and len({entity.climate for entity in instances}) != 1:
            raise ValueError(f"Conflicting climate profiles for repeated entity {entity_id!r}")
        if instances[0].domain == "humidifier" and len({entity.humidifier for entity in instances}) != 1:
            raise ValueError(f"Conflicting humidifier profiles for repeated entity {entity_id!r}")
    ui_ids = set()
    page_ids = {"page_system_info"}
    for page in pages:
        page_id = f"page_{page.safe_id}"
        if page_id in page_ids:
            raise ValueError(f"Reserved or duplicate page ID: {page_id}")
        page_ids.add(page_id)
        page.entities[:] = [replace(entity,
            safe_id=(safe_id(f"{entity.source_safe_id}_in_{page.safe_id}")
                     if len(sources[entity.entity_id]) > 1 else entity.safe_id),
            simulator=mock_values.get(entity.entity_id, entity.simulator),
        ) for entity in page.entities]
        for entity in page.entities:
            if entity.safe_id in ui_ids:
                raise ValueError(f"Widget instance ID collision: {entity.safe_id}")
            ui_ids.add(entity.safe_id)
    for page in pages:
        for entity in page.entities:
            if entity.domain in {"light", "climate", "humidifier"} or entity.is_socket:
                detail_id = f"page_detail_{entity.safe_id}"
                if detail_id in page_ids:
                    raise ValueError(f"Reserved or duplicate detail page ID: {detail_id}")
                page_ids.add(detail_id)
    return pages


def widget_controller_capacities(pages: list[Page]) -> dict[str, int]:
    """Size static storage per placement, with one slot for empty C arrays."""
    counts = Counter(entity.domain for page in pages for entity in page.entities)
    return {f"PANEL_MAX_{domain.upper()}_CONTROLLERS": max(1, counts[domain])
            for domain in ("light", "humidifier")}


def validate_simulator_capacity(pages: list[Page]) -> None:
    counts = Counter(entity.domain for page in pages for entity in page.entities)
    for domain, limit in (("climate", SIM_MAX_CLIMATE_CONTROLLERS), ("light", SIM_MAX_LIGHT_CONTROLLERS), ("humidifier", 16)):
        if counts[domain] > limit:
            raise ValueError(f"Simulator supports at most {limit} {domain} widget instances; configured {counts[domain]}")
