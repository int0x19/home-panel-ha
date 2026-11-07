"""Release artifacts must carry their exact dependency and need no source tree."""

from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = spec_from_file_location("home_panel_release_builder", ROOT / "tools/build_release.py")
builder = module_from_spec(_spec)
_spec.loader.exec_module(builder)


@pytest.fixture
def wheel():
    value = os.environ.get("HOME_PANEL_CORE_WHEEL", "")
    if not value or not Path(value).is_file():
        pytest.skip("Set HOME_PANEL_CORE_WHEEL to verify an actual release artifact")
    return Path(value)


def test_deterministic_bundle_contains_core_and_shared_asset(wheel, tmp_path):
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    receipt = builder.build_release(wheel, first)
    assert receipt["core_version"] == "0.1.0"
    builder.build_release(wheel, second)
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive, zipfile.ZipFile(wheel) as source:
        target = "custom_components/home_panel/_vendor/home_panel_core/assets/runtime-draft.mjs"
        assert archive.read(target) == source.read("home_panel_core/assets/runtime-draft.mjs")
        assert not any("__pycache__" in name or name.endswith("secrets.yaml") for name in archive.namelist())


@pytest.mark.parametrize("case", ["version", "traversal", "missing", "alias", "metadata_size"])
def test_reject_incompatible_or_unsafe_wheel_without_output(tmp_path, case):
    wheel, output = tmp_path / "bad.whl", tmp_path / "result.zip"
    version = "0.2.0" if case == "version" else "0.1.0"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("home_panel_core-0.1.0.dist-info/METADATA", f"Name: home-panel-core\nVersion: {version}\n")
        if case == "traversal": archive.writestr("../outside.py", "bad")
        if case == "alias": archive.writestr("home_panel_core/./alias.py", "bad")
        if case == "metadata_size":
            archive.writestr("extra.dist-info/METADATA", "x" * 65537)
    with pytest.raises(ValueError): builder.build_release(wheel, output)
    assert not output.exists()


def test_release_import_does_not_use_installed_core_or_sibling_checkout(wheel, tmp_path):
    archive = tmp_path / "release.zip"
    builder.build_release(wheel, archive)
    with zipfile.ZipFile(archive) as bundle: bundle.extractall(tmp_path / "ha")
    code = """
import importlib.abc, pathlib, sys
class BlockStandalone(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'home_panel_core' or fullname.startswith('home_panel_core.'):
            raise AssertionError('Release used external core')
sys.meta_path.insert(0, BlockStandalone())
sys.path.insert(0, sys.argv[1])
from custom_components.home_panel import _core
assert '._vendor.home_panel_core' in _core._package.__name__
assert _core._package.__version__ == '0.1.0'
assert _core.asset_path('runtime-draft.mjs').is_file()
assert _core.PanelReadBackend is _core.read_backend.PanelReadBackend
print('Offline release import passed')
"""
    result = subprocess.run([sys.executable, "-I", "-c", code, str(tmp_path / "ha")], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "Offline release import passed" in result.stdout


def test_wrong_bundled_version_never_falls_back_to_installed_core(wheel, tmp_path):
    archive = tmp_path / "release.zip"
    builder.build_release(wheel, archive)
    with zipfile.ZipFile(archive) as bundle: bundle.extractall(tmp_path / "ha")
    module = tmp_path / "ha/custom_components/home_panel/_vendor/home_panel_core/__init__.py"
    module.write_text(module.read_text().replace('__version__ = "0.1.0"', '__version__ = "0.2.0"'))
    code = "import sys; sys.path.insert(0, sys.argv[1]); import custom_components.home_panel._core"
    result = subprocess.run([sys.executable, "-I", "-c", code, str(tmp_path / "ha")], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0 and "requires home-panel-core==0.1.0" in result.stderr
