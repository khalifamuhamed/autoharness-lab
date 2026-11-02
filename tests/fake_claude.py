#!/usr/bin/env python3
"""A STUB standing in for the `claude` CLI. It exists ONLY to test this repo's plumbing (preflight,
command construction, waiting for the background drain, report writing). It is not Claude and not
Autoharness; whatever it writes is test fixture data."""
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
if args[:1] == ["--version"]:
    print("0.0.0-stub (Claude Code)")
elif args[:2] == ["auth", "status"]:
    print(json.dumps({"loggedIn": os.environ.get("STUB_LOGGED_IN", "1") == "1", "authMethod": "stub"}))
elif args[:1] == ["plugin"]:
    print("stub ok")
elif "-p" in args:
    assert "--allowedTools" in args and "--permission-mode" in args and "--max-budget-usd" in args
    assert os.environ.get("AUTOHARNESS_REFLECT_EVERY_N") == "3"
    root = Path.cwd() / ".claude"
    d = root / "skills" / "stub-skill"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text('---\nname: stub-skill\ndescription: "Use when testing the stub."\ncategory: testing\n---\nBody\n')
    (d / ".sidecar.json").write_text(json.dumps({"created_by": "agent", "use": 0, "view": 0, "patch": 0, "anchor": 0}))
    (d / ".ledger.jsonl").write_text(json.dumps({"action": "create", "reason": "stub", "evidence": ""}) + "\n")
    (root / "autoharness" / "runs").mkdir(parents=True, exist_ok=True)
    (root / "autoharness" / "runs" / "stub-1.json").write_text(json.dumps({"run_id": "stub-1", "verdicts": [{"action": "create", "name": "stub-skill", "ok": True, "findings": [], "notes": []}]}))
    print(json.dumps({"result": "done"}))
else:
    sys.exit(3)
