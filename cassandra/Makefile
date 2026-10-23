# CASSANDRA build orchestration.
#
# CLI contracts fixed by this Makefile (implementations must honor them
# exactly; notebooks import the package API, the Makefile drives the CLI):
#
#   scripts/prepare_data.py         --config config.yaml
#   scripts/extract_activations.py  --config config.yaml --model NAME
#   scripts/train_probes.py         --config config.yaml
#   scripts/evaluate_probes.py      --config config.yaml [--figures-only]
#   scripts/generate_and_score.py   --config config.yaml --model NAME
#   scripts/ensemble_eval.py        --config config.yaml
#   scripts/make_notebooks.py       [--out notebooks]   (idempotent)
#   scripts/run_notebooks.py        --config config.yaml
#   scripts/colab_setup.py          --print-cell

PYTHON ?= python3
VENV   := .venv
PY     := $(VENV)/bin/python
MODELS := gpt2 pythia-410m

.PHONY: setup data extract probe report figures generate ensemble notebooks colab test lint clean

setup:
	test -f requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install "torch>=2.3,<2.5" --index-url https://download.pytorch.org/whl/cpu
	$(PY) -m pip install -r requirements.txt
	$(PY) -m spacy download en_core_web_sm

data:
	$(PY) scripts/prepare_data.py --config config.yaml

extract:
	for m in $(MODELS); do \
	  $(PY) scripts/extract_activations.py --config config.yaml --model $$m; \
	done

probe:
	$(PY) scripts/train_probes.py --config config.yaml

report:
	$(PY) scripts/evaluate_probes.py --config config.yaml

figures:
	$(PY) scripts/evaluate_probes.py --config config.yaml --figures-only

generate:
	for m in $(MODELS); do \
	  $(PY) scripts/generate_and_score.py --config config.yaml --model $$m; \
	done

ensemble:
	$(PY) scripts/ensemble_eval.py --config config.yaml

notebooks:
	$(PY) scripts/make_notebooks.py --out notebooks
	$(PY) scripts/run_notebooks.py --config config.yaml

colab:
	$(PY) scripts/colab_setup.py --print-cell

test:
	$(PY) -m pytest tests -v

lint:
	$(PY) -m compileall -q cassandra_ns scripts
	@command -v ruff >/dev/null 2>&1 && ruff check cassandra_ns scripts tests \
	  || echo "ruff not installed: syntax check only"

clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
