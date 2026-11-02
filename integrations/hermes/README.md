# Hermes Agent (NousResearch) — NOT supported by Autoharness; closest real option below

**Honest status:** Autoharness cannot run inside Hermes Agent (it is Claude Code only; see the Codex
note). Hermes does not need it for the same job: Hermes ships its own skill mechanism, where the agent
creates and edits skills with its `skill_manage` tool. Autoharness's README even lists Hermes as a
*different* design ("timer + daemon") that inspired it. So there is no Autoharness feature to configure.

## What does work: let Hermes read the skills Autoharness wrote

Hermes stores its skills in `~/.hermes/skills/` (each skill a folder with a `SKILL.md`), and can scan extra
directories listed under `skills.external_dirs` in `~/.hermes/config.yaml` (docs:
hermes-agent.nousresearch.com/docs/user-guide/features/skills). Export a clean snapshot and point Hermes at it:

```bash
python -m autoharness_lab export ~/shared-skills        # SKILL.md folders only, no ledger/counters
cp config.yaml.example ~/.hermes/config.yaml            # or merge the `skills:` block into yours
hermes skills list                                      # the exported skills should now be listed
```

Caveat from the Hermes docs: external directories are **not** a write-protection boundary. If the folder is
writable, Hermes's agent may patch or delete skills there. Keep it read-only (`chmod -R a-w ~/shared-skills`)
if you want the snapshot untouched. Same-named skills in `~/.hermes/skills/` win over external ones.
