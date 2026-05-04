---
generated_by: harness-maker
harness_maker_version: 0.4.5
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/ai-readiness.md.j2
provenance: official
content_hash: 4f6b9e6f21c2b53f88b1d169e927093c1a0f9dac3fafd6f6698ccf1213da3390
---
# /hm:ai-readiness

3-layer AI readiness audit. You run this command in three steps.

## Step 1 — structural analysis (Layer 1 + Layer 3)

```bash
!uv run --with /home/noel/harness-maker python -m harness_maker.cli ai-readiness . \
  --skip-llm --json-output .claude/observability/.l1l3.tmp.json
```

## Step 2 — LLM evaluation (Layer 2, you evaluate inline)

Read each `.claude/rubrics/*.yaml`. If the directory is absent or empty, write `[]` to `.claude/observability/.l2.tmp.json` and skip to Step 3.

Each rubric file structure:
```yaml
dimension: <name>
target: <path or glob>    # relative to project root, e.g. CLAUDE.md or .claude/agents/*.md
rubrics:
  - id: <id>
    description: <check description>
    severity: P0 | P1 | P2
    action: <suggestion when fails>
```

For each rubric file:
1. Expand `target` as a glob under the project root (zero matches → skip)
2. For each matching file: read its content, evaluate each criterion
3. Produce one verdict per rubric item

Write your verdicts to `.claude/observability/.l2.tmp.json`:
```json
[
  {
    "file": "<absolute path>",
    "dimension": "<dimension>",
    "verdicts": [
      {
        "rubric_id": "<id>",
        "severity": "<P0|P1|P2>",
        "passed": true,
        "evidence": "<direct quote or line reference>",
        "suggestion": null
      }
    ]
  }
]
```

`suggestion` is `null` when `passed` is `true`; provide a concrete, file-specific fix when `passed` is `false`.

## Step 3 — finalize + write dashboard

```bash
!uv run --with /home/noel/harness-maker python -m harness_maker.cli ai-readiness-finalize \
  --scores-json .claude/observability/.l1l3.tmp.json \
  --verdicts-json .claude/observability/.l2.tmp.json
!rm -f .claude/observability/.l1l3.tmp.json .claude/observability/.l2.tmp.json
```

<!-- @hm:user:extensions -->
<!-- Project-specific ai-readiness extensions (custom panels, additional layers). Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
