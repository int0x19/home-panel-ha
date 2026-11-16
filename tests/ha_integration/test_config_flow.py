"""HA 2026.11 config entry manager and actual client/protocol, synthetic transport."""

from copy import deepcopy

import pytest
import probatio as vol
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from custom_components.home_panel.const import CONF_ACCESS_KEY, CONF_POLL_INTERVAL, CONF_URL, DOMAIN
from custom_components.home_panel._core import TransportError
from support import DEVICE_ID, TOKEN

URL = "http://panel.test"
DATA = {CONF_URL: URL, CONF_ACCESS_KEY: TOKEN}


async def start_user(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    return result


def add_entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, title="Panel", data=DATA, unique_id=DEVICE_ID)
    entry.add_to_hass(hass)
    return entry


async def test_manual_pair_and_duplicate_does_not_change_connection(hass, panel):
    first = await start_user(hass)
    result = await hass.config_entries.flow.async_configure(first["flow_id"], {**DATA, CONF_URL: URL + "/"})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id == DEVICE_ID
    assert dict(entry.data) == DATA
    assert entry.runtime_data.data.capabilities.authority == "unmanaged"
    assert not entry.runtime_data.data.capabilities.deployment_ready

    second = await start_user(hass)
    result = await hass.config_entries.flow.async_configure(second["flow_id"], {**DATA, CONF_URL: "http://other.test"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert dict(entry.data) == DATA
    assert all(method == "GET" for method, *_ in panel.calls)


@pytest.mark.parametrize(("data", "expected"), [
    ({**DATA, CONF_ACCESS_KEY: "incorrect-test-key"}, "invalid_auth"),
    ({**DATA, CONF_URL: "http://user:key@panel.test"}, "invalid_connection"),
    ({**DATA, CONF_URL: "http://panel.test/path"}, "invalid_connection"),
    ({**DATA, CONF_ACCESS_KEY: ""}, "invalid_connection"),
])
async def test_bad_connection_does_not_echo_access_key(hass, data, expected):
    first = await start_user(hass)
    result = await hass.config_entries.flow.async_configure(first["flow_id"], data)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}
    key_field = next(field for field in result["data_schema"].schema if field.schema == CONF_ACCESS_KEY)
    assert key_field.default is vol.UNDEFINED
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize("mode", ["legacy", "missing_id", "offline", "bad_metadata"])
async def test_incompatible_or_unreachable_panel(hass, panel, mode):
    if mode == "legacy":
        panel.state["features"].remove("capabilities.v1")
    elif mode == "missing_id":
        panel.state["device_id"] = None
    elif mode == "bad_metadata":
        panel.state["version"] = 999
    else:
        async def offline(*args, **kwargs):
            raise TransportError("Test offline")
        panel.request = offline
    first = await start_user(hass)
    result = await hass.config_entries.flow.async_configure(first["flow_id"], DATA)
    assert result["errors"] == {"base": "cannot_connect" if mode == "offline" else "unsupported_firmware"}
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_reconfigure_rejects_replacement_and_accepts_new_address(hass, panel):
    entry = add_entry(hass)
    before = deepcopy(dict(entry.data))
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id})
    panel.state["device_id"] = "esp32-efuse-020000000046"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**DATA, CONF_URL: "http://new.test"})
    assert result["errors"] == {"base": "wrong_device"}
    assert dict(entry.data) == before
    panel.state["device_id"] = DEVICE_ID
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**DATA, CONF_URL: "http://new.test"})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == DEVICE_ID
    assert entry.data[CONF_URL] == "http://new.test"


async def test_reauthentication_retains_id_and_address(hass, panel):
    entry = add_entry(hass)
    hass.config_entries.async_update_entry(entry, data={**DATA, CONF_ACCESS_KEY: "old-test-key"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id}, data=dict(entry.data))
    assert result["step_id"] == "reauth_confirm"
    assert [field.schema for field in result["data_schema"].schema] == [CONF_ACCESS_KEY]
    panel.state["device_id"] = "esp32-efuse-020000000046"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_ACCESS_KEY: TOKEN})
    assert result["errors"] == {"base": "wrong_device"}
    assert entry.data[CONF_ACCESS_KEY] == "old-test-key"
    panel.state["device_id"] = DEVICE_ID
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_ACCESS_KEY: TOKEN})
    await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"
    assert entry.unique_id == DEVICE_ID
    assert dict(entry.data) == DATA


async def test_reconfigure_cannot_bootstrap_an_unpinned_entry(hass):
    entry = add_entry(hass)
    hass.config_entries.async_update_entry(entry, unique_id=None)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    assert result["errors"] == {"base": "wrong_device"}
    assert entry.unique_id is None


async def test_options_polling_interval(hass):
    entry = add_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    schema = result["data_schema"]
    for value in (0, 29, 601):
        with pytest.raises(vol.Invalid):
            schema({CONF_POLL_INTERVAL: value})
    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_POLL_INTERVAL: 120})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert dict(entry.options) == {CONF_POLL_INTERVAL: 120}


async def test_pairing_without_sd_is_allowed_but_never_writable(hass, panel):
    panel.state["sd_ready"] = False
    panel.state["busy"] = True
    first = await start_user(hass)
    result = await hass.config_entries.flow.async_configure(first["flow_id"], DATA)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    snapshot = result["result"].runtime_data.data
    assert not snapshot.status.sd_ready
    assert snapshot.status.busy
    assert not snapshot.capabilities.deployment_ready


async def test_pairing_flash_confirmed_without_sd(hass, panel):
    panel.state.update(storage="flash-nvs", storage_ready=True, sd_ready=False, loaded_source="flash-confirmed", storage_generation="62")
    panel.state["features"].append("flash-maintenance.v1")
    first = await start_user(hass)
    result = await hass.config_entries.flow.async_configure(first["flow_id"], DATA)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id == DEVICE_ID
    state = entry.runtime_data.data.status
    assert state.loaded_source == "flash-confirmed"
    assert state.storage_ready and not state.sd_ready
    assert not entry.runtime_data.data.capabilities.management_ready
    assert all(method == "GET" for method, *_ in panel.calls)
