"""Build an offline-installable HA bundle from one explicitly pinned core wheel."""

import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path, PurePosixPath
import runpy
import zipfile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/home_panel"


def build_release(wheel: Path, output: Path) -> dict:
    expected = runpy.run_path(str(COMPONENT / "const.py"))["CORE_VERSION"]
    if wheel.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Core wheel exceeds release budget")
    entries = {}
    with zipfile.ZipFile(wheel) as archive:
        metadata = [i for i in archive.infolist() if i.filename.endswith(".dist-info/METADATA")]
        if len(metadata) != 1 or metadata[0].file_size > 65536:
            raise ValueError("Expected one core distribution")
        info = BytesParser().parsebytes(archive.read(metadata[0]))
        if info["Name"] != "home-panel-core" or info["Version"] != expected:
            raise ValueError("Core wheel name/version does not match the integration pin")
        total = 0
        for item in archive.infolist():
            name = PurePosixPath(item.filename)
            if (name.is_absolute() or ".." in name.parts or "\\" in item.filename or
                    item.filename.rstrip("/") != name.as_posix()):
                raise ValueError("Unsafe wheel member")
            if name.parts[0] != "home_panel_core" or item.is_dir():
                continue
            total += item.file_size
            if total > 8 * 1024 * 1024 or item.filename in entries:
                raise ValueError("Oversized or duplicate core member")
            entries[item.filename] = archive.read(item)
    required = {"home_panel_core/__init__.py", "home_panel_core/assets/runtime-draft.mjs",
                "home_panel_core/runtime_model/panel_runtime.py"}
    if not required <= entries.keys():
        raise ValueError("Core wheel is missing required modules/assets")
    payload = {}
    for file in COMPONENT.rglob("*"):
        relative = file.relative_to(COMPONENT)
        if not file.is_file() or "__pycache__" in relative.parts or "_vendor" in relative.parts:
            continue
        if file.suffix not in {".py", ".json", ".js", ".css"}:
            continue
        payload["custom_components/home_panel/" + relative.as_posix()] = file.read_bytes()
    prefix = "custom_components/home_panel/_vendor/"
    payload[prefix + "__init__.py"] = b'"""Generated release dependencies; do not edit."""\n'
    for name, data in entries.items():
        payload[prefix + name] = data
    receipt = {"core_version": expected, "core_wheel": wheel.name,
               "core_wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()}
    payload["custom_components/home_panel/core-release.json"] = json.dumps(receipt, sort_keys=True).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            entry = zipfile.ZipInfo(name, (2000, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/home-panel-ha.zip")
    args = parser.parse_args()
    print(json.dumps(build_release(args.wheel, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
