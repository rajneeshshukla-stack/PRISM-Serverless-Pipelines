# Reproduction targets. See README.md for expected run times (single CPU core).
PY ?= python3
SEEDS ?= 101 102 103 104 105
.PHONY: test demo experiments analyze manifest verify all
test:
	$(PY) -m unittest discover -s tests -v
demo:
	$(PY) scripts/demo.py
experiments:
	bash scripts/run_all.sh
analyze:
	$(PY) scripts/analyze.py
# rewrites RUN_MANIFEST.json (records runs); use only when recording new runs
manifest:
	$(PY) scripts/build_manifest.py
verify:
	$(PY) scripts/build_manifest.py --verify
all: test experiments analyze verify
