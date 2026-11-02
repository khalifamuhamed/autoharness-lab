"""REAL mode: run scripted headless Claude Code sessions with the pinned Autoharness plugin installed.

Requires: the `claude` CLI, a login or credential (claude login / ANTHROPIC_API_KEY /
CLAUDE_CODE_OAUTH_TOKEN), network access to GitHub, and `python3` >= 3.11 on PATH (Autoharness's own
requirement). Credentials are only ever read from the environment / Claude's own login; they are never
written anywhere by this code.

Everything generated lives under runtime/ (gitignored).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .paths import REAL_INFO, REAL_PROJECT, REPO_ROOT, TOY_TEMPLATE, load_pin
from .store import Store

CLAUDE_BIN_ENV = "AUTOHARNESS_LAB_CLAUDE_BIN"  # tests point this at a stub; users normally leave it unset
CRED_ENV_VARS = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN")

# Documented Autoharness knobs (README "Configuration"/"Walkthrough"); shrunk so the whole life cycle
# is visible in a handful of short sessions. Defaults upstream are 50 / 100 / 50 / 250.
DEMO_ENV = {
    "AUTOHARNESS_DISABLE_GLOBAL": "1",        # project layer only; never touch ~/.claude skills
    "AUTOHARNESS_REFLECT_EVERY_N": "3",       # reflect after every 3 tool calls
    "AUTOHARNESS_MATURITY_PROJECT": "5",      # graduation review after 5 requests
    "AUTOHARNESS_CAPACITY_PROJECT": "2",      # at most 2 mature skills -> forces pruning
    "AUTOHARNESS_CONSOLIDATE_EVERY_N": "4",   # curator (merge pass) every 4th request
}

ALLOWED_TOOLS = ["Read", "Edit", "Write", "Glob", "Grep",
                 "Bash(python3 -m unittest *)", "Bash(python -m unittest *)",
                 "Bash(python3 -m slugkit *)", "Bash(ls *)", "Bash(cat *)"]


class RealUnavailable(RuntimeError):
    """Real mode cannot run here (no CLI / no login). The message is user-facing."""


def claude_bin() -> str | None:
    override = os.environ.get(CLAUDE_BIN_ENV)
    return override or shutil.which("claude")


def _run(argv, *, cwd=None, env=None, timeout=60, input_text=None):
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, input=input_text)


@dataclass
class Preflight:
    ok: bool
    reason: str = ""
    version: str = ""
    auth: str = ""


def preflight() -> Preflight:
    """Decide if real mode can run. Never prints or returns a secret; only reports which source exists."""
    exe = claude_bin()
    if not exe:
        return Preflight(False, "الأمر `claude` غير مثبّت (Claude Code CLI). ثبّته ثم سجّل الدخول، أو استخدم --mode sample.")
    try:
        ver = _run([exe, "--version"]).stdout.strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return Preflight(False, "تعذّر تشغيل `claude --version`.")
    py = shutil.which("python3")
    if py:
        r = _run([py, "-c", "import sys;print(sys.version_info>=(3,11))"])
        if r.stdout.strip() != "True":
            return Preflight(False, "Autoharness يحتاج python3 بإصدار 3.11+ على PATH، وإلا تتوقف خطّافاته.", ver)
    else:
        return Preflight(False, "لا يوجد python3 على PATH (يحتاجه Autoharness).", ver)
    cred = next((v for v in CRED_ENV_VARS if os.environ.get(v)), None)
    if cred:
        return Preflight(True, "", ver, f"متغيّر بيئة {cred}")
    try:
        data = json.loads(_run([exe, "auth", "status"]).stdout or "{}")
    except (ValueError, OSError, subprocess.SubprocessError):
        data = {}
    if data.get("loggedIn"):
        return Preflight(True, "", ver, f"تسجيل دخول Claude ({data.get('authMethod', '?')})")
    return Preflight(False, "لا يوجد تسجيل دخول Claude ولا مفتاح API في البيئة. نفّذ `claude auth login` أو صدّر ANTHROPIC_API_KEY، أو استخدم --mode sample.", ver)


def _merge_settings(project: Path, env: dict[str, str]) -> None:
    p = project / ".claude" / "settings.json"
    data = {}
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("env", {}).update(env)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def installed_commit(plugin_id: str) -> str | None:
    """gitCommitSha Claude Code recorded for the installed plugin (reads Claude's own bookkeeping)."""
    cfg = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
    try:
        data = json.loads((cfg / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for entry in data.get("plugins", {}).get(plugin_id, []):
        if entry.get("gitCommitSha"):
            return entry["gitCommitSha"]
    return None


@dataclass
class RealRun:
    project: Path = REAL_PROJECT
    info_path: Path = REAL_INFO
    repo_root: Path = REPO_ROOT
    sessions: list[dict] = field(default_factory=list)
    budget_usd: float = 1.0
    session_timeout: int = 900
    quiet_s: int = 40
    drain_timeout_s: int = 300
    log: object = print

    # ---------------------------------------------------------------- setup
    def prepare(self, exe: str) -> None:
        pin = load_pin()
        if self.project.exists():
            shutil.rmtree(self.project)
        shutil.copytree(TOY_TEMPLATE, self.project)
        git = ["git", "-c", "user.name=autoharness-lab", "-c", "user.email=lab@example.invalid"]
        _run(["git", "init", "-q", "-b", "main"], cwd=self.project)
        _run([*git, "add", "-A"], cwd=self.project)
        _run([*git, "commit", "-q", "-m", "toy repo baseline"], cwd=self.project)
        # Declare marketplace + plugin at PROJECT scope (writes <toy>/.claude/settings.json).
        r = _run([exe, "plugin", "marketplace", "add", str(self.repo_root), "--scope", "project"], cwd=self.project, timeout=180)
        if r.returncode != 0 and "already" not in (r.stdout + r.stderr).lower():
            raise RealUnavailable(f"فشل `plugin marketplace add`: {(r.stdout + r.stderr).strip()[-400:]}")
        r = _run([exe, "plugin", "install", pin["plugin_id"], "--scope", "project"], cwd=self.project, timeout=300)
        if r.returncode != 0 and "already" not in (r.stdout + r.stderr).lower():
            raise RealUnavailable(f"فشل `plugin install {pin['plugin_id']}`: {(r.stdout + r.stderr).strip()[-400:]}")
        sha = installed_commit(pin["plugin_id"])
        if sha and sha != pin["commit"]:
            raise RealUnavailable(f"الإضافة المثبّتة ({sha[:7]}) لا تطابق التثبيت المعلن ({pin['commit'][:7]}).")
        _merge_settings(self.project, DEMO_ENV)
        self.pinned_ok = sha == pin["commit"]

    def env(self) -> dict[str, str]:
        e = dict(os.environ)
        e.update(DEMO_ENV)
        e["AUTOHARNESS_GLOBAL_ROOT"] = str(self.project.parent / "global-root")  # sandbox, even if global is disabled
        return e

    # ---------------------------------------------------------------- one session
    def command(self, exe: str, prompt: str) -> list[str]:
        return [exe, "-p", prompt, "--permission-mode", "acceptEdits", "--allowedTools", *ALLOWED_TOOLS,
                "--output-format", "json", "--max-budget-usd", str(self.budget_usd)]

    def run_session(self, exe: str, scenario: dict, index: int) -> dict:
        logs = self.project.parent / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        started = time.time()
        try:
            r = _run(self.command(exe, scenario["prompt"]), cwd=self.project, env=self.env(), timeout=self.session_timeout)
            ok, rc, tail = r.returncode == 0, r.returncode, (r.stdout or "")
            (logs / f"session-{index:02d}-{scenario['id']}.json").write_text(tail, encoding="utf-8")
            (logs / f"session-{index:02d}-{scenario['id']}.err").write_text(r.stderr or "", encoding="utf-8")
        except subprocess.TimeoutExpired:
            ok, rc = False, -1
        return {"id": scenario["id"], "title_ar": scenario.get("title_ar", ""), "ok": ok, "returncode": rc,
                "seconds": round(time.time() - started, 1)}

    def wait_for_drain(self) -> None:
        """Autoharness reflects in a detached background job after Stop/SessionEnd. Wait until its intent
        queue is empty and no new run account has appeared for `quiet_s` seconds (bounded)."""
        state = self.project / ".claude" / "autoharness"
        deadline = time.time() + self.drain_timeout_s
        last_sig, last_change = None, time.time()
        while time.time() < deadline:
            intents = list((state / "intents").glob("*")) if (state / "intents").is_dir() else []
            runs = sorted(p.name for p in (state / "runs").glob("*.json")) if (state / "runs").is_dir() else []
            sig = (len(intents), tuple(runs))
            if sig != last_sig:
                last_sig, last_change = sig, time.time()
            if not intents and time.time() - last_change >= self.quiet_s:
                return
            time.sleep(min(5, max(0.2, self.quiet_s / 4)))

    # ---------------------------------------------------------------- orchestrate
    def execute(self, scenarios: list[dict]) -> Store:
        pf = preflight()
        if not pf.ok:
            raise RealUnavailable(pf.reason)
        exe = claude_bin()
        self.log(f"Claude Code: {pf.version} · المصدر: {pf.auth}")
        self.log("تجهيز المستودع التجريبي وتثبيت Autoharness المثبّت ...")
        self.prepare(exe)
        results = []
        for i, sc in enumerate(scenarios, 1):
            self.log(f"[{i}/{len(scenarios)}] جلسة: {sc['id']} ...")
            res = self.run_session(exe, sc, i)
            results.append(res)
            self.log(f"    {'تمت' if res['ok'] else 'فشلت'} ({res['seconds']}s) — انتظار تأمّل Autoharness في الخلفية")
            self.wait_for_drain()
        pin = load_pin()
        info = {"mode": "real", "claude_version": pf.version, "auth_source": pf.auth.split(" (")[0],
                "autoharness_commit": pin["commit"], "autoharness_version": pin["plugin_version"],
                "plugin_pin_verified": bool(getattr(self, "pinned_ok", False)),
                "sessions": results, "finished_at_unix": int(time.time())}
        self.info_path.parent.mkdir(parents=True, exist_ok=True)
        self.info_path.write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return Store(self.project, label="real")


def load_scenarios(limit: int | None = None) -> list[dict]:
    data = json.loads((Path(__file__).with_name("scenarios.json")).read_text(encoding="utf-8"))
    sessions = data["sessions"]
    return sessions[:limit] if limit else sessions


def report_note(info_path: Path = REAL_INFO) -> str:
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    ok = sum(1 for s in info.get("sessions", []) if s.get("ok"))
    return (f"عدد الجلسات: {len(info.get('sessions', []))} (نجح {ok}) · Claude Code {info.get('claude_version', '?')} · "
            f"Autoharness {info.get('autoharness_version', '?')}.")
