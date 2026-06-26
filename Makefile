# ALIA — dev makefile.
#
# The venv is created with --system-site-packages so the distro's GTK4
# PyGObject (python3-gobject) is visible without compiling it into the venv.

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: install test run shortcut clean

install: $(VENV)/.stamp

$(VENV)/.stamp: pyproject.toml
	python3 -m venv --system-site-packages $(VENV)
	-$(PIP) install -U pip
	# dev: editable local engine stack (beaver <- lingo <- lovelaice)
	$(PIP) install -e ../beaver -e ../lingo -e ../lovelaice
	$(PIP) install -e .
	$(PIP) install pytest pytest-asyncio
	touch $@

test: install
	$(PY) -m pytest -q

run: install
	$(PY) -m alia

# Bind a GNOME shortcut (default <Super>a) that summons ALIA.
shortcut: install
	./scripts/install-shortcut.sh

clean:
	rm -rf $(VENV)
