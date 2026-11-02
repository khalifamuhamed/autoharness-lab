"""Read-only view of the plain files Autoharness leaves on disk.

Formats are taken from Autoharness's README and source (see docs/FORMATS.md):
  <root>/skills/<name>/SKILL.md            the skill (frontmatter: name, description, category)
  <root>/skills/<name>/.ledger.jsonl       append-only: {"action","reason","evidence"[, "absorbed_into","path"]}
  <root>/skills/<name>/.sidecar.json       {"created_by":"agent","use","view","patch","anchor",...}
  <root>/skills/<name>/references/evidence-<sha256>.md   redacted transcript slice behind a ledger entry
  <root>/skills/.archive/<name>/           retired skills (merged or pruned); moving back revives them
  <root>/autoharness/runs/<run-id>.json    {"run_id","verdicts":[{"action","name","ok","findings","notes"}]}
  <root>/autoharness/last_run.json, requests, intents/, snapshots/

<root> is `<project>/.claude` (project layer) or `~/.claude` (global layer, or AUTOHARNESS_GLOBAL_ROOT).
This module never writes anything.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")  # same rule Autoharness enforces for skill names


def check_name(name: str) -> str:
    if not isinstance(name, str) or ".." in name or not SAFE_NAME.match(name):
        raise ValueError(f"unsafe skill name: {name!r}")
    return name


def dir_size(path: Path) -> tuple[int, int]:
    """(total bytes, file count) of a directory tree; 0,0 if missing. Symlinks are not followed."""
    total = files = 0
    if not path.exists():
        return 0, 0
    for p in path.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
                files += 1
        except OSError:
            continue
    return total, files


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Tiny flat-`key: value` reader (enough for SKILL.md as Autoharness writes it)."""
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    meta: dict[str, str] = {}
    for line in text[4:end].split("\n"):
        if ":" in line and not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            meta[k.strip()] = v
    body = text[end + 4:].lstrip("\n")
    return meta, body


def read_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").split("\n"):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue  # a torn last line is skipped, exactly as Autoharness does
        if isinstance(obj, dict):
            out.append(obj)
    return out


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


@dataclass
class Skill:
    name: str
    layer: str
    archived: bool
    path: Path
    description: str = ""
    category: str = "general"
    body: str = ""
    ledger: list[dict] = field(default_factory=list)
    sidecar: dict = field(default_factory=dict)
    size_bytes: int = 0
    file_count: int = 0

    @property
    def managed(self) -> bool:
        """Autoharness only touches skills whose sidecar says created_by == agent."""
        return self.sidecar.get("created_by") == "agent"

    def evidence_path(self, ref: str) -> Path | None:
        if not isinstance(ref, str) or not ref.startswith("references/evidence-") or ".." in ref:
            return None
        p = self.path / ref
        return p if p.is_file() else None


@dataclass
class Layer:
    name: str          # "project" | "global"
    root: Path         # the `.claude`-like directory

    @property
    def skills_dir(self) -> Path:
        return self.root / "skills"

    @property
    def archive_dir(self) -> Path:
        return self.skills_dir / ".archive"

    @property
    def state_dir(self) -> Path:
        return self.root / "autoharness"


class Store:
    def __init__(self, project_dir: Path, global_root: Path | None = None, label: str = ""):
        self.project_dir = Path(project_dir)
        self.layers: list[Layer] = [Layer("project", self.project_dir / ".claude")]
        if global_root is not None:
            self.layers.append(Layer("global", Path(global_root)))
        self.label = label

    def layer(self, name: str) -> Layer:
        for lyr in self.layers:
            if lyr.name == name:
                return lyr
        raise KeyError(name)

    # ---- skills -------------------------------------------------------------------------
    def _load(self, lyr: Layer, d: Path, archived: bool) -> Skill:
        meta, body = parse_frontmatter((d / "SKILL.md").read_text(encoding="utf-8", errors="replace"))
        size, files = dir_size(d)
        return Skill(
            name=d.name, layer=lyr.name, archived=archived, path=d,
            description=meta.get("description", ""), category=meta.get("category") or "general",
            body=body, ledger=read_jsonl(d / ".ledger.jsonl"),
            sidecar=read_json(d / ".sidecar.json", {}) or {}, size_bytes=size, file_count=files,
        )

    def skills(self, *, archived: bool | None = None, managed_only: bool = True) -> list[Skill]:
        out: list[Skill] = []
        for lyr in self.layers:
            places = []
            if archived in (None, False):
                places.append((lyr.skills_dir, False))
            if archived in (None, True):
                places.append((lyr.archive_dir, True))
            for base, is_arch in places:
                if not base.is_dir() or base.is_symlink():
                    continue
                for d in sorted(base.iterdir()):
                    if d.name.startswith(".") or d.is_symlink() or not (d / "SKILL.md").is_file():
                        continue
                    try:
                        sk = self._load(lyr, d, is_arch)
                    except (OSError, ValueError):
                        continue
                    if managed_only and not sk.managed:
                        continue
                    out.append(sk)
        return out

    def find(self, name: str, *, archived: bool | None = None) -> Skill | None:
        check_name(name)
        for sk in self.skills(archived=archived, managed_only=False):
            if sk.name == name:
                return sk
        return None

    # ---- run accounts -------------------------------------------------------------------
    def runs(self) -> list[dict]:
        out = []
        for lyr in self.layers:
            rdir = lyr.state_dir / "runs"
            if rdir.is_dir():
                for p in sorted(rdir.glob("*.json")):
                    rec = read_json(p)
                    if isinstance(rec, dict):
                        rec["_layer"] = lyr.name
                        out.append(rec)
        return out

    def request_count(self, layer: str = "project") -> int:
        p = self.layer(layer).state_dir / "requests"
        try:
            return int(p.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return 0

    # ---- sizes --------------------------------------------------------------------------
    def sizes(self) -> list[dict]:
        rows = []
        for lyr in self.layers:
            live = arch = 0
            live_b = arch_b = 0
            if lyr.skills_dir.is_dir():
                for d in lyr.skills_dir.iterdir():
                    if d.name == ".archive" or not d.is_dir():
                        continue
                    live += 1
                    live_b += dir_size(d)[0]
            if lyr.archive_dir.is_dir():
                for d in lyr.archive_dir.iterdir():
                    if d.is_dir():
                        arch += 1
                        arch_b += dir_size(d)[0]
            state_b, state_f = dir_size(lyr.state_dir)
            rows.append({
                "layer": lyr.name, "skills": live, "skills_bytes": live_b,
                "archived": arch, "archived_bytes": arch_b,
                "state_bytes": state_b, "state_files": state_f,
            })
        return rows


# ---- timeline: what happened, derived from Autoharness's own accounts ---------------------
@dataclass
class Event:
    kind: str                # created | updated | merged | pruned | pruned_auto | file_removed
    skill: str
    reason: str = ""
    evidence: str = ""
    absorbed_into: str = ""
    detail: str = ""         # e.g. subfile path
    derived: bool = False    # True when no ledger line exists and the report inferred it


def build_events(store: Store) -> list[Event]:
    """Classify per Autoharness's own metrics rules (lib/metrics.py `_deaths`):
    ledger `create` -> created; `patch`/`update` -> updated; `remove_file` -> file removed;
    `delete` with `absorbed_into` -> merged (folded into an umbrella); `delete` without it -> pruned
    (deliberate retirement). An archived skill with no `delete` line was archived by the lifecycle
    pass (usage rate / capacity), which leaves no ledger line -> `pruned_auto` (derived)."""
    events: list[Event] = []
    ordered = sorted(store.skills(managed_only=True), key=lambda k: (int(k.sidecar.get("anchor", 0) or 0), k.name))
    for sk in ordered:
        saw_delete = False
        for e in sk.ledger:
            action = e.get("action")
            ev = str(e.get("evidence") or "")
            reason = str(e.get("reason") or "")
            if action == "create":
                events.append(Event("created", sk.name, reason, ev))
            elif action in ("patch", "update"):
                events.append(Event("updated", sk.name, reason, ev))
            elif action == "remove_file":
                events.append(Event("file_removed", sk.name, reason, ev, detail=str(e.get("path") or "")))
            elif action == "delete":
                saw_delete = True
                into = str(e.get("absorbed_into") or "")
                events.append(Event("merged" if into else "pruned", sk.name, reason, ev, absorbed_into=into))
        if sk.archived and not saw_delete:
            events.append(Event("pruned_auto", sk.name, derived=True))
    return events


def rejected_proposals(store: Store) -> list[dict]:
    rows = []
    for rec in store.runs():
        for v in rec.get("verdicts", []):
            if isinstance(v, dict) and not v.get("ok", True):
                rows.append({"run": str(rec.get("run_id", "")), "action": v.get("action"),
                             "name": v.get("name"), "findings": v.get("findings", [])})
    return rows
