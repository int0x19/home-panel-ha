"""Real HA framework with synthetic wire data; never contacts a real HA or ESP32."""

import pytest
from homeassistant.helpers import storage

from custom_components.home_panel import coordinator
from support import FakeTransport, TOKEN, response

_REAL_STORE_IO = storage._FileStoreIO


@pytest.fixture
def hass_config_dir(tmp_path):
    return str(tmp_path)


@pytest.fixture(autouse=True)
def real_draft_file_io(hass, monkeypatch):
    """Real HA Store/files only for our namespace; other HA fixtures stay mocked."""
    fixture_io = storage._FileStoreIO

    def file_io(hass, key, *args, **kwargs):
        cls = _REAL_STORE_IO if key.startswith("home_panel.draft.") else fixture_io
        return cls(hass, key, *args, **kwargs)

    monkeypatch.setattr(storage, "_FileStoreIO", file_io)

@pytest.fixture
def custom_integrations_enabled():
    """Allow HA to load the actual custom_components package from this repository."""
    return True


@pytest.fixture
def panel():
    return FakeTransport(with_capabilities=True)


@pytest.fixture(autouse=True)
def panel_wire(monkeypatch, panel):
    original = coordinator.AiohttpTransport
    transports = []

    def create_transport(session, origin):
        # Keep production origin validation and the HA-owned session, replace only I/O.
        transport = original(session, origin)

        async def request(method, path, *, headers, body, max_bytes):
            if headers.get("Authorization") != "Bearer " + TOKEN:
                return response({}, status=401)
            return await panel.request(method, path, headers=headers, body=body, max_bytes=max_bytes)

        transport.request = request
        transports.append(transport)
        return transport

    monkeypatch.setattr(coordinator, "AiohttpTransport", create_transport)
    return transports
