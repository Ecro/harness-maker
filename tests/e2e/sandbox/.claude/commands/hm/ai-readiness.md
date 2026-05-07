---
generated_by: harness-maker
harness_maker_version: 0.5.4
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/ai-readiness.md.j2
provenance: official
content_hash: 50723b24320945863213ad4c16d6dc155dbdf0102f0f65c6b0e10d3d2bc5b077
---
# /hm:ai-readiness

3-layer AI readiness audit + guided improvement.

## Step 1 — structural analysis (Layer 1 + Layer 3)

```bash
!uv run --with /home/noel/harness-maker python -m harness_maker.cli ai-readiness . \
  --skip-llm --json-output .claude/observability/.l1l3.tmp.json
```

## Step 2 — LLM evaluation (Layer 2, you evaluate inline)

Read each `.claude/rubrics/*.yaml`. If the directory is absent or empty, write `[]` to
`.claude/observability/.l2.tmp.json` then proceed to Step 3.

Rubric file structure:
```yaml
dimension: <name>
target: <path or glob>    # relative to project root
rubrics:
  - id: <id>
    description: <check>
    severity: P0 | P1 | P2
    action: <suggestion when fails>
```

For each rubric file:
1. Expand `target` glob under project root (zero matches → skip)
2. For each matching file: read content, evaluate each criterion
3. Produce one verdict per rubric item

Write verdicts to `.claude/observability/.l2.tmp.json`:
```json
[
  {
    "file": "<absolute path>",
    "dimension": "<dimension>",
    "verdicts": [
      {"rubric_id": "<id>", "severity": "<P0|P1|P2>", "passed": true,
       "evidence": "<direct quote or line reference>", "suggestion": null}
    ]
  }
]
```
`suggestion` is `null` when `passed=true`; provide a concrete, file-specific fix when `passed=false`.

## Step 3 — finalize + write dashboard

```bash
!uv run --with /home/noel/harness-maker python -m harness_maker.cli ai-readiness-finalize \
  --scores-json .claude/observability/.l1l3.tmp.json \
  --verdicts-json .claude/observability/.l2.tmp.json
!rm -f .claude/observability/.l1l3.tmp.json .claude/observability/.l2.tmp.json
```

## Step 4 — triage + guided improvement

Classify every action from Step 3 into two buckets:

**🤖 AI-fixable** — config, docs, file structure (you can apply these now):
signals: `claude_md_*`, `readme_present`, `agent_frontmatter_*`, `agents_within_limit`,
`side_governance_skipped`, `permissions_*`, `deny_*`, `hooks_*`, `fused_workflow_*`,
`commands_*`, `harness_*`, `memory_*`, `observability_*`, `dashboard_md_*`,
`wiki_md_present`, `failures_md_present`, `adr_present`, `contributing_present`,
any rubric verdict that only requires writing or editing a documentation/config file.

**👤 Human-required** — code, CI, actual usage, security review (you explain what to do):
signals: `stack_detected`, `tests_present`, `ci_workflow_*`, `metrics_*`,
`no_high_security_findings`, `failures_md_has_content` (needs lived experience).

Present a triage table to the user:
| # | Priority | Dimension | Issue | Who |
|---|----------|-----------|-------|-----|
| 1 | P0 | governance | docs/adr/ missing | 🤖 |
| 2 | P0 | observability | metrics.jsonl absent | 👤 |
...

Then use AskUserQuestion:
> "Found N fixable items and M human-required items. Shall I work through the fixable ones now?"

**If yes** — go through each 🤖-fixable group:
1. Group related items (e.g. several deny-rule gaps → one settings.json edit).
2. If the fix needs project context not available in CLAUDE.md (e.g. the purpose
   of this project, team size, primary workflow), ask ONE focused AskUserQuestion.
3. Apply the fix directly. Show what changed.
4. Continue to the next group without re-asking.

After all fixes, re-run structural analysis to confirm score improvement:
```bash
!uv run --with /home/noel/harness-maker python -m harness_maker.cli ai-readiness . --skip-llm
```

**For 👤-required items** — briefly state: what action is needed, why you can't do it,
and what the expected score gain is once done.

<!-- @hm:user:extensions -->
<!-- Project-specific ai-readiness extensions (custom panels, additional layers). Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
