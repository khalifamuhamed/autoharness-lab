"""Fixed locations inside this repo + the pinned-dependency file reader."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME = REPO_ROOT / "runtime"                 # gitignored: everything generated lives here
SAMPLE_PROJECT = RUNTIME / "sample" / "project"  # offline example store (clearly labelled)
REAL_DIR = RUNTIME / "real"
REAL_PROJECT = REAL_DIR / "toy-repo"             # the toy repo real sessions run in
REAL_INFO = REAL_DIR / "info.json"
TOY_TEMPLATE = REPO_ROOT / "toy_repo_template"
PIN_FILE = REPO_ROOT / "autoharness.pin.json"
MARKETPLACE_FILE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
SAMPLE_REPORT = REPO_ROOT / "docs" / "sample-report.ar.html"
SAMPLE_MARKER = "SAMPLE_DATA.txt"  # lives in <project>/.claude/ ; makes the report show the sample banner


def load_pin() -> dict:
    return json.loads(PIN_FILE.read_text(encoding="utf-8"))
