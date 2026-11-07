"""Shared display-backlight defaults and control definitions."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class BacklightSettings:
    brightness: int = 100
    auto_off: bool = False
    timeout: int = 60
    idle_mode: str = "off"
    dim_brightness: int = 10

    def timeouts(self):
        return sorted({15, 30, 60, 120, 300, 600, self.timeout})


BACKLIGHT_WIDGETS = {
    "brightness": "system_backlight_brightness",
    "brightness_label": "system_backlight_brightness_label",
    "auto_off": "system_backlight_auto",
    "timeout": "system_backlight_timeout",
    "idle_mode": "system_backlight_mode",
    "dim_brightness": "system_backlight_dim",
    "dim_label": "system_backlight_dim_label",
}


def parse_backlight_settings(config):
    panel = config.get("panel") or {}
    if not isinstance(panel, dict):
        raise ValueError("panel must be a mapping")
    value = panel.get("backlight", {})
    if not isinstance(value, dict):
        raise ValueError("panel.backlight must be a mapping")
    defaults = asdict(BacklightSettings())
    if set(value) - set(defaults):
        raise ValueError("Unknown panel.backlight fields")
    settings = {**defaults, **value}
    for key, low, high in (("brightness", 5, 100), ("dim_brightness", 1, 100), ("timeout", 1, 3600)):
        if type(settings[key]) is not int or not low <= settings[key] <= high:
            raise ValueError(f"panel.backlight.{key} must be an integer between {low} and {high}")
    if type(settings["auto_off"]) is not bool:
        raise ValueError("panel.backlight.auto_off must be a boolean")
    if not isinstance(settings["idle_mode"], str) or settings["idle_mode"] not in {"off", "dim"}:
        raise ValueError("panel.backlight.idle_mode must be 'off' or 'dim'")
    return BacklightSettings(**settings)


def timeout_label(seconds):
    return f"{seconds // 60} min" if seconds % 60 == 0 else f"{seconds} s"
