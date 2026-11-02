"""Fast offline self-checks (no network, no Claude). `python -m autoharness_lab check`."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from . import report, sample
from .paths import MARKETPLACE_FILE, PIN_FILE, REPO_ROOT, SAMPLE_REPORT, TOY_TEMPLATE, load_pin
from .store import Store, build_events, rejected_proposals

SECRET_RE = re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{32,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----")
SKIP_DIRS = {".git", "runtime", "__pycache__", "node_modules", ".venv"}
REQUIRED_IGNORES = [".env", "*.pem", "*.key", "runtime/", "__pycache__/"]


def repo_files() -> list[Path]:
    out = []
    for p in REPO_ROOT.rglob("*"):
        if p.is_file() and not (set(p.relative_to(REPO_ROOT).parts) & SKIP_DIRS):
            out.append(p)
    return out


def _check_pin():
    pin, mp = load_pin(), json.loads(MARKETPLACE_FILE.read_text(encoding="utf-8"))
    entry = next(p for p in mp["plugins"] if p["name"] == pin["name"])
    src = entry["source"]
    assert re.fullmatch(r"[0-9a-f]{40}", pin["commit"]), "pin commit must be a full 40-char sha"
    assert src["sha"] == pin["commit"], "marketplace.json sha differs from autoharness.pin.json"
    assert src["url"].startswith("https://github.com/tigerless-labs/autoharness"), "unexpected upstream url"
    assert mp["name"] == pin["marketplace_name"] and pin["plugin_id"] == f"{pin['name']}@{mp['name']}"
    py = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert pin["commit"] in py and pin["plugin_version"] in py, "pyproject external-dependency table is out of sync"
    deps = re.search(r"^dependencies\s*=\s*\[(.*?)\]", py, re.S | re.M)
    assert deps is not None and "autoharness" not in deps.group(1).lower(), \
        "autoharness must NOT be a pip dependency (the PyPI 'autoharness' is a different project)"
    return f"pinned {pin['plugin_version']} @ {pin['commit'][:7]}"


IMPORT_UPSTREAM = re.compile(r"^\s*(from|import)\s+autoharness(\.|\s|$)", re.M)


def _check_not_vendored():
    bad = []
    for p in repo_files():
        rel = p.relative_to(REPO_ROOT).as_posix()
        if re.search(r"(^|/)(promoter|dispatch|stage_skill|on_session_start)(\.py|/)", rel):
            bad.append(rel)
        elif p.suffix == ".py" and IMPORT_UPSTREAM.search(p.read_text(encoding="utf-8", errors="ignore")):
            bad.append(rel + " (imports upstream)")
    assert not bad, f"upstream code must not be vendored or imported: {bad}"
    assert not (REPO_ROOT / "src" / "autoharness").exists()
    return "no upstream source in repo; nothing imports `autoharness`"


def _check_gitignore():
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").split()
    missing = [x for x in REQUIRED_IGNORES if x not in text]
    assert not missing, f".gitignore missing {missing}"
    return "ok"


def _check_no_secrets():
    hits = []
    for p in repo_files():
        if p.suffix in {".png", ".jpg", ".pyc"}:
            continue
        for m in SECRET_RE.finditer(p.read_text(encoding="utf-8", errors="ignore")):
            hits.append(f"{p.relative_to(REPO_ROOT)}: {m.group(0)[:8]}…")
    assert not hits, f"secret-looking strings: {hits}"
    return f"scanned {len(repo_files())} files"


def _check_sample_pipeline():
    with tempfile.TemporaryDirectory() as td:
        proj = sample.build(Path(td) / "p")
        store = Store(proj)
        kinds = {e.kind for e in build_events(store)}
        need = {"created", "updated", "merged", "pruned", "pruned_auto"}
        assert need <= kinds, f"sample story is missing event kinds: {need - kinds}"
        assert rejected_proposals(store), "sample story should include a rejected proposal"
        html = report.render(store, mode="sample")
        assert 'lang="ar" dir="rtl"' in html and "SAMPLE / EXAMPLE DATA" in html
        assert not report.leaks(html), f"leak in report: {report.leaks(html)}"
    return f"events: {sorted(kinds)}"


def _check_committed_report():
    assert SAMPLE_REPORT.exists(), "docs/sample-report.ar.html is missing (run: make sample-report)"
    text = SAMPLE_REPORT.read_text(encoding="utf-8")
    assert not report.leaks(text), f"committed report leaks paths/secrets: {report.leaks(text)}"
    assert "SAMPLE / EXAMPLE DATA" in text, "committed report must be labelled as sample data"
    with tempfile.TemporaryDirectory() as td:
        fresh = report.render(Store(sample.build(Path(td) / "p")), mode="sample")
    assert fresh == text, "committed report is stale (run: make sample-report)"
    return "up to date, no paths/secrets"


def _check_toy_repo():
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"], cwd=TOY_TEMPLATE,
                       capture_output=True, text=True)
    assert "Ran 3 tests" in r.stderr and "failures=1" in r.stderr, f"toy repo should have exactly 1 failing test:\n{r.stderr}"
    return "toy repo: 3 tests, 1 intentional failure"


def _check_integrations():
    json.loads((REPO_ROOT / "integrations/claude-code/settings.project.json").read_text(encoding="utf-8"))
    assert "autoharness@autoharness-lab-pins" in (REPO_ROOT / "integrations/claude-code/settings.project.json").read_text()
    for rel, needle in (("integrations/codex/README.md", "NOT supported"), ("integrations/hermes/README.md", "NOT supported")):
        assert needle in (REPO_ROOT / rel).read_text(encoding="utf-8"), f"{rel} must state the lack of support honestly"
    assert "external_dirs" in (REPO_ROOT / "integrations/hermes/config.yaml.example").read_text()
    return "claude-code/codex/hermes docs + configs present"


def _check_readme():
    t = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for needle in ("https://github.com/tigerless-labs/autoharness", "MIT", "Tigerless Labs", "English summary", "مثال", "python -m autoharness_lab demo"):
        assert needle in t, f"README missing: {needle}"
    return "ok"


def _check_git_identity():
    if not (REPO_ROOT / ".git").exists():
        return "no .git (skipped)"
    r = subprocess.run(["git", "log", "--format=%an <%ae>|%cn <%ce>"], cwd=REPO_ROOT, capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return "no commits yet (skipped)"
    for line in set(r.stdout.strip().splitlines()):
        for who in line.split("|"):
            assert who.startswith("muhamed khalifa <") and who.endswith("@users.noreply.github.com>"), f"unexpected identity: {who}"
    return "all commits by muhamed khalifa <noreply>"


CHECKS = [
    ("pinned Autoharness dependency declared consistently", _check_pin),
    ("no upstream code vendored", _check_not_vendored),
    (".gitignore covers secrets/runtime/caches", _check_gitignore),
    ("no secrets in repo files", _check_no_secrets),
    ("sample store -> events -> Arabic report", _check_sample_pipeline),
    ("committed sample report is fresh, labelled, path-free", _check_committed_report),
    ("toy repo template behaves as documented", _check_toy_repo),
    ("integration docs/configs (Claude Code, Codex, Hermes)", _check_integrations),
    ("README credits Autoharness + MIT + English summary", _check_readme),
    ("git identity", _check_git_identity),
]


def run_all() -> list[tuple[str, bool, str]]:
    results = []
    for title, fn in CHECKS:
        try:
            results.append((title, True, fn()))
        except Exception as exc:  # noqa: BLE001 - report every failure, keep going
            results.append((title, False, f"{type(exc).__name__}: {exc}"))
    return results


def run_cli() -> int:
    results = run_all()
    for title, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {title}  — {detail}")
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0
