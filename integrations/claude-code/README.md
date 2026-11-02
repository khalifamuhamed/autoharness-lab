# Claude Code (the primary, supported integration)

Autoharness is a **Claude Code plugin**. It is not a pip package: the PyPI project called `autoharness`
is unrelated, do not install it. Install it as a plugin, pinned to the exact commit this demo was built
against (`../../autoharness.pin.json`).

## Install (terminal)

```bash
# 1) register THIS repo's marketplace; it contains one entry that pins Autoharness's commit
claude plugin marketplace add ./autoharness-lab          # or: khalifamuhamed/autoharness-lab once pushed
# 2) install the pinned plugin (scope: user | project | local)
claude plugin install autoharness@autoharness-lab-pins --scope project
# 3) restart Claude Code (or /reload-plugins), then check
claude plugin list          # expect: autoharness@autoharness-lab-pins  Version: 0.5.3  enabled
```

The same inside Claude Code: `/plugin marketplace add ./autoharness-lab`, then `/plugin install autoharness@autoharness-lab-pins`.

Why not `/plugin marketplace add tigerless-labs/autoharness` (the upstream README's way)? That follows
upstream's moving `main` branch. The marketplace file here pins the commit instead
(`source: url`, `sha: 92015c0b…`), so you get exactly the audited version. We use the HTTPS `url`
source because the shorter `github` source cloned over SSH on our test box and failed without an SSH key.

## What was verified for real (Claude Code 2.1.316, no login needed for this part)

`claude plugin validate .` passes; `plugin marketplace add`, `plugin install autoharness@autoharness-lab-pins`
succeed; `plugin list` shows version 0.5.3; Claude's `installed_plugins.json` records
`gitCommitSha 92015c0b2583072d892b54ab83352ad3490c0a7f`; `plugin details` lists skill `learn`, agents
`reflector`/`curator`, hooks SessionStart/Stop/PreToolUse/SessionEnd, and the `stage_skill` MCP server.
Actual *learning* needs a logged-in model and was NOT run on that box.

## Project settings

`settings.project.json` is a template for a project's `.claude/settings.json` that declares the marketplace
and enables the plugin for everyone who clones the project (they are asked to trust the folder first).
It points at the GitHub URL this repo will have after you push it; before that, use the local path above.
Knobs are in `autoharness.env.example`. Requirement: `python3` on PATH must be **3.11 or newer**.

## Update / uninstall

Bump the `sha` in `.claude-plugin/marketplace.json` deliberately (and `autoharness.pin.json`), then
`claude plugin marketplace update autoharness-lab-pins && claude plugin update autoharness@autoharness-lab-pins`.
Uninstall: `claude plugin uninstall autoharness@autoharness-lab-pins`. Skills it wrote stay on disk until
you delete them (`python -m autoharness_lab delete <name>`).
