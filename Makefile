PYTHON ?= .venv/bin/python
CORE_WHEEL ?=

.PHONY: release marketplace test core-install
core-install:
	@test -f "$(CORE_WHEEL)" || { printf '%s\n' 'Set CORE_WHEEL to the pinned core wheel.' >&2; exit 1; }
	"$(PYTHON)" -m pip install --no-deps --no-index "$(CORE_WHEEL)"

release:
	@test -f "$(CORE_WHEEL)" || { printf '%s\n' 'Set CORE_WHEEL to the pinned core wheel.' >&2; exit 1; }
	"$(PYTHON)" tools/build_release.py --wheel "$(CORE_WHEEL)"

marketplace:
	@test -f "$(CORE_WHEEL)" || { printf '%s\n' 'Set CORE_WHEEL to the pinned core wheel.' >&2; exit 1; }
	"$(PYTHON)" tools/build_release.py --wheel "$(CORE_WHEEL)" --layout marketplace

test:
	HOME_PANEL_CORE_WHEEL="$(CORE_WHEEL)" "$(PYTHON)" -m pytest -c tests/ha_integration/pytest.ini tests/ha_integration
