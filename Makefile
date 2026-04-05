# Development Makefile — local dev convenience (CI uses its own workflow)
#
# Quick start:
#   make test        # create venv if needed, run tests with coverage
#   make lint        # ruff + bandit + mypy
#   make check       # lint + test (full pre-PR check)
#   make clean       # remove venv and caches

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/python -m pytest
RUFF := $(VENV)/bin/ruff
BANDIT := $(VENV)/bin/bandit
MYPY := $(VENV)/bin/mypy

# Phony targets (not files)
.PHONY: test lint check clean help

# Default target
help:
	@echo "Usage:"
	@echo "  make test     Run tests with coverage (creates venv if needed)"
	@echo "  make lint     Run ruff, bandit, and mypy"
	@echo "  make check    Run lint + test (full pre-PR check)"
	@echo "  make clean    Remove venv and caches"
	@echo "  make venv     Create/update venv only"

# Create venv and install deps (re-runs if requirements change)
$(VENV)/bin/activate: requirements.txt requirements-test.txt
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt -r requirements-test.txt
	touch $(VENV)/bin/activate

venv: $(VENV)/bin/activate

test: $(VENV)/bin/activate
	$(PYTEST) tests/ -v --tb=short \
		--cov=tools --cov=servers \
		--cov-report=term-missing \
		--cov-fail-under=75

lint: $(VENV)/bin/activate
	$(RUFF) check tools/ servers/
	$(BANDIT) -r tools/ servers/ -ll -q -s B108
	$(MYPY)

check: lint test

clean:
	rm -rf $(VENV) .pytest_cache coverage-html .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
