"""Use the same core variant as the component, including release-bundle tests."""

from importlib import import_module

from custom_components.home_panel._core import _package

_testing = import_module(_package.__name__ + ".testing")
for _name in ("DEVICE_ID", "TOKEN", "DOCUMENT", "FakeTransport", "capability_document", "metadata", "response"):
    globals()[_name] = getattr(_testing, _name)
