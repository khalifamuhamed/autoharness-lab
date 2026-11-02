PY ?= python3

.PHONY: demo demo-real sample-report check test where list doctor

demo:            ## one command: run the demo (real if a Claude login exists, else labelled SAMPLE data) -> runtime/report.*.ar.html
	$(PY) -m autoharness_lab demo

demo-real:       ## force real headless Claude Code sessions (needs `claude auth login` or ANTHROPIC_API_KEY)
	$(PY) -m autoharness_lab demo --mode real

sample-report:   ## regenerate the committed SAMPLE report docs/sample-report.ar.html
	$(PY) -m autoharness_lab demo --mode sample --out docs/sample-report.ar.html

check:           ## fast offline self-checks
	$(PY) -m autoharness_lab check

test: check      ## self-checks + unit tests (stdlib unittest, no installs needed)
	$(PY) -m unittest discover -s tests -q

where list doctor:
	$(PY) -m autoharness_lab $@
