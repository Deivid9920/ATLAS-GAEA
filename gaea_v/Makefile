PY := .venv/bin/python

.PHONY: setup test audit-verify bridge-check pilot eval zoo rft bench package lint clean

setup:
	python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt

test:
	$(PY) -m pytest -q

audit-verify:
	$(PY) scripts/audit_verify.py

bridge-check:
	$(PY) scripts/bridge_check.py

pilot:
	$(PY) scripts/run_pilot_power.py rows-nano
	$(PY) scripts/run_pilot_power.py rows-atlas
	$(PY) scripts/run_pilot_power.py finalize

eval:
	$(PY) scripts/run_eval.py

zoo:
	$(PY) scripts/run_zoo.py

rft:
	$(PY) scripts/run_fase5.py

bench:
	$(PY) scripts/bench_star.py

package:
	$(PY) scripts/package_release.py

lint:
	$(PY) -m pytest tests/test_structure.py -q

clean:
	rm -rf .pytest_cache .venv
