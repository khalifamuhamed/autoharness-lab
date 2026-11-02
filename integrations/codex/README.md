# Codex (OpenAI) — NOT supported by Autoharness; closest real option below

**Honest status:** Autoharness cannot run inside Codex. Its learning loop is wired to Claude Code's plugin
system (hooks `SessionStart/Stop/PreToolUse/SessionEnd`, plugin agents `reflector`/`curator`, an MCP tool
registered by the plugin manifest). Its own README says: "Today it runs on Claude Code." There is no
Codex mode, so nothing here learns, merges or prunes skills inside Codex.

## What does work: share the skills Autoharness wrote under Claude Code

Autoharness stores skills as plain `SKILL.md` folders, and Codex reads the same shape: a directory with
a `SKILL.md` carrying `name` and `description`. Codex looks for repository skills in `.agents/skills`
(from the working directory up to the repo root) and personal skills in `$HOME/.agents/skills`, and it
reads `AGENTS.md` for always-on project guidance (OpenAI Codex docs: developers.openai.com/codex/skills,
/codex/guides/agents-md).

```bash
# one-way snapshot: active Autoharness skills -> a project's .agents/skills (no ledger, no counters)
python -m autoharness_lab export /path/to/your-project/.agents/skills
```

Then copy `AGENTS.md.example` into your project as `AGENTS.md` (or merge it). Re-run `export` whenever you
want a fresh snapshot. Treat the exported copy as read-only: edits made there do not flow back, and a
re-export overwrites them. Skills stay governed (created, updated, pruned) in Claude Code only.
