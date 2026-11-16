"""Actual HA 2026.11 registries and authenticated WS; no device/service calls."""

import json

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.home_panel.const import DOMAIN
from custom_components.home_panel.entity_catalog import MAX_AREAS
from custom_components.home_panel.websocket_api import PREFIX
from support import DEVICE_ID


@pytest.fixture
async def catalog(hass, hass_ws_client):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_ID, title="Offline", data={})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client()

    async def query(**filters):
        await client.send_json_auto_id({"type": PREFIX + "entities", "entry_id": entry.entry_id, **filters})
        return await client.receive_json()

    yield entry, query
    await client.close()
    await hass.async_block_till_done()


async def test_registry_state_union_and_effective_area(hass, catalog, panel):
    entry, query = catalog
    areas, devices, entities = ar.async_get(hass), dr.async_get(hass), er.async_get(hass)
    bedroom = areas.async_create("Спальня")
    kitchen = areas.async_create("Кухня")
    device = devices.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, "demo")}, name="Demo")
    devices.async_update_device(device.id, area_id=bedroom.id)
    action = entities.async_get_or_create("button", DOMAIN, "demo", suggested_object_id="demo",
                                          device_id=device.id, original_name="Original")
    entities.async_update_entity(action.entity_id, name="Моя кнопка")
    hass.states.async_set(action.entity_id, "unavailable", {"friendly_name":"Stale", "secret":"PRIVATE"})
    hass.states.async_set("scene.evening", "2026-11-07", {"friendly_name":"Вечер", "secret":"PRIVATE"})
    hass.states.async_set("light.private", "on", {"friendly_name":"PRIVATE"})
    before = len(panel.calls)
    result = await query()
    assert result["success"]
    rows = result["result"]["items"]
    assert [row["entity_id"] for row in rows] == [action.entity_id, "scene.evening"]
    assert rows[0] == {"entity_id": action.entity_id, "name":"Demo Моя кнопка", "domain":"button",
                       "area_id":bedroom.id, "area_name":"Спальня", "availability":"unavailable",
                       "disabled":False, "hidden":False}
    assert rows[1]["area_id"] is None and rows[1]["availability"] == "available"
    assert "PRIVATE" not in json.dumps(result) and device.id not in json.dumps(result)
    assert len(panel.calls) == before == 0
    assert (await query(area_id=bedroom.id))["result"]["total"] == 1
    assert (await query(area_id=None))["result"]["items"][0]["entity_id"] == "scene.evening"
    entities.async_update_entity(action.entity_id, area_id=kitchen.id)
    assert (await query(area_id=bedroom.id))["result"]["total"] == 0
    assert (await query(area_id=kitchen.id, query="МОЯ"))["result"]["total"] == 1
    assert (await query(domain="scene", query="EVENING"))["result"]["total"] == 1
    assert (await query(domain="script"))["result"]["total"] == 0


async def test_disabled_hidden_missing_unknown_and_fresh_names(hass, catalog):
    _, query = catalog
    entities = er.async_get(hass)
    for key, extra in (("disabled", {"disabled_by": er.RegistryEntryDisabler.USER}),
                       ("hidden", {"hidden_by": er.RegistryEntryHider.USER}), ("missing", {})):
        entities.async_get_or_create("script", DOMAIN, key, suggested_object_id=key, **extra)
    hass.states.async_set("script.unknown", "unknown", {"friendly_name":"Before"})
    rows = (await query())["result"]["items"]
    assert [row["entity_id"] for row in rows] == ["script.missing", "script.unknown"]
    assert [row["availability"] for row in rows] == ["missing", "unknown"]
    rows = (await query(include_inactive=True))["result"]["items"]
    assert len(rows) == 4 and rows[0]["disabled"] and rows[1]["hidden"]
    hass.states.async_set("script.unknown", "off", {"friendly_name":"After"})
    assert (await query(query="After"))["result"]["items"][0]["name"] == "After"


async def test_bounded_paging_and_area_list(hass, catalog):
    _, query = catalog
    for index in reversed(range(61)):
        hass.states.async_set(f"input_button.test_{index:03}", "unknown", {"friendly_name":"X" * 400})
    for index in range(MAX_AREAS + 1):
        ar.async_get(hass).async_create(f"Area {index}")
    seen, offset = [], 0
    while offset is not None:
        data = (await query(offset=offset))["result"]
        assert len(data["items"]) <= 25 and data["total"] == 61
        assert len(data["areas"]) == MAX_AREAS and data["areas_truncated"]
        assert all(len(row["name"]) == 256 for row in data["items"])
        seen.extend(row["entity_id"] for row in data["items"])
        offset = data["next_offset"]
    assert len(seen) == len(set(seen)) == 61 and seen == sorted(seen)
    assert (await query(offset=100000))["result"]["items"] == []


@pytest.mark.parametrize("filters", [{"domain":"light"}, {"limit":51}, {"limit":0}, {"offset":-1},
                                    {"query":"x" * 129}, {"area_id":"x" * 129},
                                    {"include_inactive":"yes"}, {"service":"script.turn_on"},
                                    {"scope":"light"}, {"scope":"sensor", "domain":"script"},
                                    {"domain":"sensor"}])
async def test_catalog_schema_rejects_before_query(catalog, filters):
    _, query = catalog
    response = await query(**filters)
    assert not response["success"] and response["error"]["code"] == "invalid_format"


async def test_unknown_entry_rejected_without_device_io(hass, catalog, panel):
    _, query = catalog
    before = len(panel.calls)
    other = MockConfigEntry(domain="other")
    unpaired = MockConfigEntry(domain=DOMAIN, data={})
    other.add_to_hass(hass)
    unpaired.add_to_hass(hass)
    for entry_id in ("missing", other.entry_id, unpaired.entry_id):
        response = await query(entry_id=entry_id)
        assert response["error"]["code"] == "panel_unavailable"
    assert len(panel.calls) == before


async def test_sensor_catalog_isolated_scope_and_allowlisted_defaults(hass, catalog, panel):
    _, query = catalog
    hass.states.async_set("sensor.temperature", "25.1", {"friendly_name":"Temperature",
        "unit_of_measurement":"\u00b0C", "device_class":"temperature", "secret":"PRIVATE"})
    hass.states.async_set("sensor.humidity", "unavailable", {"friendly_name":"Humidity",
        "unit_of_measurement":"%", "device_class":"humidity", "secret":"PRIVATE"})
    hass.states.async_set("scene.evening", "unknown", {"friendly_name":"Evening"})
    hass.states.async_set("binary_sensor.private", "on", {"friendly_name":"PRIVATE"})
    before = len(panel.calls)
    data = (await query(scope="sensor"))["result"]
    assert data["scope"] == "sensor_entities" and data["domains"] == ["sensor"]
    assert [row["entity_id"] for row in data["items"]] == ["sensor.humidity", "sensor.temperature"]
    assert data["items"][0]["defaults"] == {"unit":"%", "device_class":"humidity"}
    assert data["items"][0]["availability"] == "unavailable"
    assert data["items"][1]["defaults"] == {"unit":"\u00b0C", "device_class":"temperature"}
    assert "25.1" not in json.dumps(data) and "PRIVATE" not in json.dumps(data)
    assert (await query())["result"]["domains"] == ["script", "scene", "button", "input_button"]
    assert (await query(scope="sensor", query="HUM", domain="sensor"))["result"]["total"] == 1
    assert len(panel.calls) == before == 0


@pytest.mark.parametrize("attributes", [
    {"unit_of_measurement":None, "device_class":None},
    {"unit_of_measurement":42, "device_class":False},
    {"unit_of_measurement":"x" * 33, "device_class":"bad class"},
    {"unit_of_measurement":"bad\nunit", "device_class":"\ud800"},
])
async def test_bad_sensor_metadata_is_not_used_for_defaults(hass, catalog, attributes):
    _, query = catalog
    hass.states.async_set("sensor.unknown", "unknown", attributes)
    row = (await query(scope="sensor"))["result"]["items"][0]
    assert row["defaults"] == {} and row["availability"] == "unknown"
