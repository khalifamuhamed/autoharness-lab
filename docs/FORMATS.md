# On-disk formats this demo reads (from Autoharness's README and source, commit 92015c0)

This demo only *reads* these files; it never imports Autoharness code. If upstream changes a format, the
report may need updating, which is one more reason the commit is pinned.

```
<project>/.claude/skills/<name>/SKILL.md          frontmatter: name, description (a "Use when ..." trigger), category
<project>/.claude/skills/<name>/.ledger.jsonl     append-only, one JSON per line: {"action","reason","evidence"}
                                                  + "absorbed_into" (merge) / "path" (remove_file)
<project>/.claude/skills/<name>/.sidecar.json     {"created_by":"agent","use","view","patch","anchor","verification"}
<project>/.claude/skills/<name>/references/evidence-<sha256>.md   redacted transcript slice per ledger entry
<project>/.claude/skills/.archive/<name>/         retired skill (merged or pruned); move back to revive
<project>/.claude/autoharness/requests            request counter (denominator of the usage rate)
<project>/.claude/autoharness/runs/<run-id>.json  {"run_id","verdicts":[{"action","name","ok","findings","notes"}]}
<project>/.claude/autoharness/last_run.json       one-line summary shown at the next session start
<project>/.claude/autoharness/intents/            queued proposals waiting for the promoter
<project>/.claude/autoharness/snapshots/          tarballs the curator takes before a merge (keeps 5)
~/.claude/skills, ~/.claude/autoharness           the global layer (or AUTOHARNESS_GLOBAL_ROOT); off with AUTOHARNESS_DISABLE_GLOBAL=1
```

## How events are classified in the report

Same rule as upstream's own `lib/metrics.py`:

| Ledger / location | Meaning | Report label |
|---|---|---|
| `create` | learned a new skill | أُنشئت (created) |
| `patch` / `update` | changed an existing skill | حُدِّثت (updated) |
| `remove_file` | dropped a support file | حُذف ملف مساند |
| `delete` + `absorbed_into` | folded into an umbrella skill | دُمجت (merged) |
| `delete`, no `absorbed_into` | deliberate retirement | قُلِّمت (pruned, with reason) |
| archived, no `delete` line | lifecycle pass (never used/viewed, or over capacity) | قُلِّمت آليًا (pruned, inferred) |
| `runs/*.json` verdict with `ok:false` | proposal rejected by the promoter | مقترحات رُفضت |

The ledger has no timestamps; skills are ordered by their creation anchor (request count at creation).

## Typical sizes (from upstream's constants and our sample store)

- `SKILL.md` body ≤ 25 non-blank lines (`AUTOHARNESS_SKILL_BODY_MAX_LINES`), description ≤ 1024 chars, body ≤ 100 KB hard cap.
- Evidence slice: one file per ledger entry, bounded by the capture window cap (200 KB), usually far less.
- A skill folder is therefore typically a few KB (the sample store: ~1 KB per skill); the curator keeps up to 5
  snapshot tarballs of the skill tree (`AUTOHARNESS_SNAPSHOT_KEEP`).

## Conformance (checked once, outside this repo)

Against an upstream checkout at the pinned commit `92015c0`, with `AUTOHARNESS_DISABLE_GLOBAL=1`: the live skills of
the generated SAMPLE store pass upstream's own `validate.description_findings` (60-char index budget) and
`validate.structure`, and upstream's `metrics.collect` reports deaths `absorbed=1, pruned=1, lifecycle=1`, the same
split this report derives. This was done by importing the upstream checkout in a throw-away shell; the repo itself
never imports or contains upstream code. The sample is still example data, not a real run.
