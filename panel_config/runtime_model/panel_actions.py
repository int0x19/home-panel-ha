"""Allowlisted momentary action profiles, independent of transport and renderer."""

ACTION_SERVICES = {"script": "script.turn_on", "scene": "scene.turn_on",
                   "button": "button.press", "input_button": "input_button.press"}
ACTION_ICONS = ("refresh-cw", "palette", "power", "bell", "moon", "sun", "house", "save", "fan", "sprout")
ACTION_INTERACTIONS = ("tap", "hold", "confirm")
ACTION_STYLE_FIELDS = """card_color text_color muted_text_color accent_color control_color disabled_color status_error_color
control_border_color control_border_width control_gap card_radius light_card_height light_tile_padding light_tile_gap
light_icon_size light_tile_name_height room_name_font_size small_text_height normal_text_height""".split()
MAX_RUNTIME_ACTIONS = 12
SCRIPT_CONTROLS_FEATURE = "script-controls.v1"


def action_profile(entity, settings):
    domain = entity.split(".", 1)[0] if isinstance(entity, str) else ""
    if domain not in ACTION_SERVICES:
        raise ValueError("Action tiles require script, scene, button or input_button entities")
    if not isinstance(settings, dict) or set(settings) - {"icon", "enabled", "interaction", "allow_stop"}:
        raise ValueError("Action settings only support icon, enabled, interaction and script allow_stop")
    if "allow_stop" in settings and (domain != "script" or type(settings["allow_stop"]) is not bool):
        raise ValueError("allow_stop requires a script entity and a boolean")
    icon = settings.get("icon", ACTION_ICONS[list(ACTION_SERVICES).index(domain)])
    interaction = settings.get("interaction", "tap")
    enabled = settings.get("enabled", True)
    if not isinstance(icon, str) or icon not in ACTION_ICONS:
        raise ValueError("Action icon must be a bundled supported icon")
    if not isinstance(interaction, str) or interaction not in ACTION_INTERACTIONS or type(enabled) is not bool:
        raise ValueError("Action interaction must be tap/hold/confirm and enabled must be boolean")
    result = {"icon": icon, "interaction": interaction, "enabled": enabled}
    if "allow_stop" in settings:
        result["allow_stop"] = settings["allow_stop"]
    return result
