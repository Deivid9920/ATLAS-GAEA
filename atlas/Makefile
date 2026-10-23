# ATLAS orchestration. CLI contracts fixed here (implementations honor them).

PYTHON ?= python3
VENV := .venv
PY := $(VENV)/bin/python
TASK ?= "Write and verify a function that merges two sorted lists."
PROFILE ?= code_qa
BUDGET ?= standard
ROUND ?= 1
MODE ?= dup_flood
STAGE ?= all

.PHONY: setup bridge-check chat run-task mcp-serve rft lineage bench audit-verify demo test lint clean

setup:
	test -f requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt

bridge-check:
	$(PY) scripts/bridge_check.py --config config.yaml

chat:
	$(PY) scripts/chat.py --config config.yaml --profile $(PROFILE)

run-task:
	$(PY) scripts/run_task.py --config config.yaml --profile $(PROFILE) \
	     --task "$(TASK)" --budget $(BUDGET)

mcp-serve:
	$(PY) scripts/mcp_server.py --config config.yaml

rft:
	$(PY) scripts/rft_round.py $(STAGE) --round $(ROUND)

lineage:
	$(PY) scripts/lineage_round.py $(STAGE) --round $(ROUND)

bench:
	$(PY) scripts/bench.py --config config.yaml --profile $(PROFILE)

audit-verify:
	$(PY) scripts/audit_verify.py --logs logs/audit.jsonl

demo: bridge-check
	$(PY) scripts/run_task.py --config config.yaml --profile $(PROFILE) \
	  --task "$(TASK)" --budget standard --with-crash-test

test:
	$(PY) -m pytest tests -v

lint:
	$(PY) -m compileall -q atlas_ns scripts

clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
