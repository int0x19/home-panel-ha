"""Load the exact shared core from a release bundle or a developer installation."""

from importlib import import_module
from pathlib import Path

from .const import CORE_VERSION

_bundled = Path(__file__).parent / "_vendor/home_panel_core/__init__.py"
_package = import_module("._vendor.home_panel_core", __package__) if _bundled.is_file() else import_module("home_panel_core")
if _package.__version__ != CORE_VERSION:
    raise ImportError(f"Home Panel requires home-panel-core=={CORE_VERSION}")

globals().update({name: getattr(_package, name) for name in _package.__all__})
protocol = import_module(_package.__name__ + ".protocol")
read_backend = import_module(_package.__name__ + ".read_backend")
model = import_module(_package.__name__ + ".runtime_model.panel_runtime")
encode_document = import_module(_package.__name__ + ".json_codec").encode_document
AiohttpTransport = import_module(_package.__name__ + ".aiohttp_transport").AiohttpTransport
asset_path = _package.asset_path
for _name in ("MAX_DOCUMENT_BYTES", "MAX_METADATA_BYTES", "boolean", "device_identifier",
              "digest", "integer", "json_object", "names"):
    globals()[_name] = getattr(protocol, _name)
for _name in ("BackendBusy", "BackendClosed", "InvalidImport", "InvalidInput", "ReadConflict", "RefreshRequired",
              "PanelReadBackend"):
    globals()[_name] = getattr(read_backend, _name)
DEFAULT_LIMITS, decode_document, validate_document = model.DEFAULT_LIMITS, model.decode_document, model.validate_document
