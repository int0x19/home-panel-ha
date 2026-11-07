"""Custom integrations need packaged translations, not strings.json alone."""

import json
from pathlib import Path


def test_packaged_translation_catalogs():
    root = Path(__file__).resolve().parents[2] / "custom_components/home_panel"
    source = json.loads((root / "strings.json").read_text())
    english = json.loads((root / "translations/en.json").read_text())
    russian = json.loads((root / "translations/ru.json").read_text())
    assert source == english

    def keys(value, prefix=()):
        return {path for key, child in value.items() for path in (
            keys(child, (*prefix, key)) if isinstance(child, dict) else {(*prefix, key)}
        )}

    assert keys(english) == keys(russian)
