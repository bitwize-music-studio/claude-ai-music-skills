# Development Makefile — local dev convenience (CI uses its own workflow)
#
# Quick start:
#   make test        # create venv if needed, run tests with coverage
#   make lint        # ruff + bandit + mypy
#   make check       # lint + test (full pre-PR check)
#   make clean       # remove venv and caches

VENV := .venv
PYTHON := $(VENV)/bin/python
PYTEST := $(PYTHON) -m pytest
RUFF := $(VENV)/bin/ruff
BANDIT := $(VENV)/bin/bandit
MYPY := $(VENV)/bin/mypy

# Phony targets (not files)
.PHONY: test lint check clean help venv

# Default target
help:
	@echo "Usage:"
	@echo "  make test     Run tests with coverage (creates venv if needed)"
	@echo "  make lint     Run ruff, bandit, and mypy"
	@echo "  make check    Run lint + test (full pre-PR check)"
	@echo "  make clean    Remove venv and caches"
	@echo "  make venv     Create/update venv only"

# The python3 the venv is built from, recorded in a stamp file's name, so a
# new python3 (a Homebrew upgrade, say) rebuilds the venv as surely as a
# change to the requirements does.
PY_VERSION := $(shell python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
VENV_STAMP := $(VENV)/.built-with-python$(PY_VERSION)

# Create the venv and install deps. Re-runs when the requirements change or
# python3 is not the version the venv was built with.
#
# --clear rebuilds from nothing, and the installs go through $(PYTHON) -m pip
# so packages land where the tests run. Re-running `python3 -m venv` over a
# venv made by an older Python adds the new interpreter but leaves bin/python
# pointing at the old one: pip then installed the pins for the new interpreter
# while every test ran on the old one, against packages months out of date.
$(VENV_STAMP): requirements.txt requirements-test.txt
	python3 -m venv --clear $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt -r requirements-test.txt
	touch $(VENV_STAMP)

venv: $(VENV_STAMP)

# Deliberately a LOWER bar than CI's 80. This runs on one OS, so it can never
# execute the win32/darwin branches and can never reach the combined number the
# `coverage` job in test.yml gates on. Raising it to 80 to "match CI" would make
# local runs fail for a reason no local change can fix.
test: $(VENV_STAMP)
	$(PYTEST) tests/ -v --tb=short -n auto \
		--cov=tools --cov=servers \
		--cov-report=term-missing \
		--cov-fail-under=75

lint: $(VENV_STAMP)
	# hooks/ is in scope: it auto-executes on every Write/Edit in every user
	# session, so it gets the same lint gate as tools/ and servers/
	$(RUFF) check tools/ servers/ hooks/
	# PLW1514 (unspecified-encoding) is preview-only, so it runs as a
	# dedicated scoped invocation instead of enabling preview repo-wide
	$(RUFF) check tools/ servers/ hooks/ tests/ --select PLW1514 --preview
	# -s B108: tmpfile paths (reviewed manually)
	# -s B608: SQL string construction (all callsites use %s params; nosec
	#         markers remain as documentation but bandit noise at -ll level
	#         is suppressed here)
	$(BANDIT) -r tools/ servers/ -ll -q -s B108,B608
	$(MYPY)

check: lint test

clean:
	rm -rf $(VENV) .pytest_cache coverage-html .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
