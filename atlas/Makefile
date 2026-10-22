# ATLAS orchestration. CLI contracts fixed here (implementations honor them).

PYTHON ?= python3
VENV := .venv
PY := $(VENV)/bin/python
TASK ?= "Write and verify a function that merges two sorted lists."
PROFILE ?= code_qa
BUDGET ?= standard
ROUND ?= 1
MODE ?= dup_flood

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
	@echo "PENDIENTE declarado (v1.0.2): scripts/rft_round.py es un esqueleto fail-loud."
	@echo "FASE 5 se midio via harness gaea_v: ../gaea_v/scripts/run_fase5.py (prereg_20261020_rft_rondas_v2)."
	@echo "Ver README raiz (Pendientes declarados) y docs/ANEXO_CIERRE_fase7_atlas.md."
	@exit 2

lineage:
	@echo "PENDIENTE declarado (v1.0.2): scripts/lineage_round.py es un esqueleto fail-loud."
	@echo "FASE 6 se midio via harness gaea_v: ../gaea_v/scripts/lineage_measured.py (lineage_defs_20261021)."
	@echo "Ver README raiz (Pendientes declarados) y docs/ANEXO_CIERRE_fase7_atlas.md."
	@exit 2

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
