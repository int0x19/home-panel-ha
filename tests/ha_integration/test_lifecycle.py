"""Read-only entities, refresh failures, redaction and full unload on real HA."""

from datetime import timedelta
import json

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from custom_components.home_panel.const import CONF_ACCESS_KEY, CONF_URL, DOMAIN
from custom_components.home_panel.diagnostics import async_get_config_entry_diagnostics
from custom_components.home_panel._core import TransportError
from support import DEVICE_ID, TOKEN, response

DATA = {CONF_URL: "http://panel.test", CONF_ACCESS_KEY: TOKEN}


async def setup(hass, data=None, identity=DEVICE_ID):
    entry = MockConfigEntry(domain=DOMAIN, title="Panel", data=data or DATA, unique_id=identity)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_metadata_entities_and_unload_do_not_close_shared_session(hass, panel):
    session = async_get_clientsession(hass)
    entry = await setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entities) == 5
    expected = {"loaded_revision": "17", "loaded_source": "builtin", "max_bytes": "16384", "sd_ready": "on", "busy": "off"}
    for key, value in expected.items():
        entity_id = next(entity.entity_id for entity in entities if entity.unique_id == f"{DEVICE_ID}_{key}")
        assert hass.states.get(entity_id).state == value
        assert registry.async_get(entity_id).entity_category.value == "diagnostic"
        assert hass.states.get(entity_id).attributes["friendly_name"] != "Panel"
    coordinator = entry.runtime_data
    assert coordinator.update_interval == timedelta(seconds=60)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not session.closed
    assert not list(coordinator.async_contexts())
    assert all((state := hass.states.get(entity.entity_id)) is None or state.state == "unavailable" for entity in entities)
    before = len(panel.calls)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done()
    assert len(panel.calls) == before
    assert all(method == "GET" for method, *_ in panel.calls)


async def test_redacted_diagnostics_and_state_attributes(hass, panel):
    entry = await setup(hass)
    diagnostic = await async_get_config_entry_diagnostics(hass, entry)
    encoded = json.dumps(diagnostic)
    state_dump = json.dumps([state.as_dict() for state in hass.states.async_all()], default=str)
    for forbidden in (TOKEN, DATA[CONF_URL], panel.state["session_id"]):
        assert forbidden not in encoded
        assert forbidden not in state_dump
    assert DEVICE_ID not in encoded
    assert diagnostic["authority"] == "unmanaged"
    assert diagnostic["management_ready"] is False
    assert diagnostic["limits"]["document_bytes"] == 16384
    assert diagnostic["files"]["active"]["valid"] is True


async def test_russian_entity_names_are_loaded_by_ha(hass):
    await hass.config.async_update(language="ru")
    entry = await setup(hass)
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    revision = next(entity for entity in entities if entity.unique_id == f"{DEVICE_ID}_loaded_revision")
    assert hass.states.get(revision.entity_id).attributes["friendly_name"] == "Panel Ревизия runtime-конфигурации"


async def test_disconnect_and_changed_identity_mark_entities_unavailable_then_recover(hass, panel):
    entry = await setup(hass)
    coordinator = entry.runtime_data
    request = panel.request

    async def offline(*args, **kwargs):
        raise TransportError("Synthetic disconnection")

    panel.request = offline
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert not coordinator.last_update_success
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert all(hass.states.get(entity.entity_id).state == "unavailable" for entity in entities)
    panel.request = request
    panel.state["device_id"] = "esp32-efuse-020000000046"
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert entry.unique_id == DEVICE_ID
    panel.state["device_id"] = DEVICE_ID
    panel.state["session_id"] = panel.state["csrf"] = "2" * 32
    panel.state["loaded_revision"] = 32
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success
    assert coordinator.data.status.loaded_revision == 32
    assert entry.unique_id == DEVICE_ID


async def test_auth_failure_during_poll_starts_reauthentication(hass, panel):
    entry = await setup(hass)

    async def denied(*args, **kwargs):
        return response({}, status=401)

    panel.request = denied
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert not entry.runtime_data.last_update_success
    assert any(flow["context"]["source"] == "reauth" for flow in hass.config_entries.flow.async_progress())


@pytest.mark.parametrize("status", [429, 503])
async def test_transient_http_errors_do_not_start_reauthentication(hass, panel, status):
    entry = await setup(hass)

    async def temporary_failure(*args, **kwargs):
        return response({}, status=status)

    panel.request = temporary_failure
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert not entry.runtime_data.last_update_success
    assert not hass.config_entries.flow.async_progress()


async def test_stale_snapshot_is_not_published_and_option_reload_stops_old_poller(hass, panel):
    entry = await setup(hass)
    coordinator = entry.runtime_data
    original = coordinator.data
    original_change = panel.change

    def stale(method, suffix, result):
        if suffix == "capabilities":
            value = json.loads(result.body)
            value["session_id"] = "9" * 32
            return response(value)
        return result

    panel.change = stale
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert coordinator.data is original
    panel.change = original_change
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], {"poll_interval": 120})
    await hass.async_block_till_done()
    assert entry.runtime_data is not coordinator
    assert entry.runtime_data.update_interval == timedelta(seconds=120)
    assert not list(coordinator.async_contexts())
    assert entry.runtime_data.last_update_success


@pytest.mark.parametrize("reason", ["offline", "auth", "replacement", "missing_pairing", "invalid_connection"])
async def test_setup_failures_never_register_entities(hass, panel, reason):
    data = DATA
    identity = DEVICE_ID
    if reason == "offline":
        async def offline(*args, **kwargs):
            raise TransportError("Synthetic disconnection")
        panel.request = offline
    elif reason == "auth":
        data = {**DATA, CONF_ACCESS_KEY: "incorrect-test-key"}
    elif reason == "missing_pairing":
        identity = None
    elif reason == "invalid_connection":
        data = {**DATA, CONF_URL: "http://panel.test/invalid"}
    else:
        panel.state["device_id"] = "esp32-efuse-020000000046"
    entry = await setup(hass, data, identity)
    assert entry.state in (ConfigEntryState.SETUP_RETRY, ConfigEntryState.SETUP_ERROR)
    assert not er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert not hass.states.async_all()
