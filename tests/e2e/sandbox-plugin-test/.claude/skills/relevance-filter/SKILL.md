---
generated_by: harness-maker
harness_maker_version: 0.17.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/relevance-filter/SKILL.md.j2
provenance: official
name: relevance-filter
description: Score crawled anti-rot items against project context using LLM judgment
  + adaptive threshold (start 0.7, ±0.05 by accept/reject ratio). Use after research-crawler
  writes raw-<date>.jsonl, between crawl and structured question confirmation in /hm:health
  Step 2 (external risks layer).
content_hash: 3fd3ffb9ab1ac4ca9a6aff7dafb1488a3105c88cb12da9afe67f9314e8e2ba1e
---

# relevance-filter

> Score crawled items against project context using your own judgment, then
> apply an adaptive threshold to filter the proposal list.


## Communication Protocol

- Be direct. No flattery, no preamble, no "Great question!"
- Lead with concerns before agreement; when you agree, explain WHY with specific reasoning.
- Do not fold on pushback unless new evidence is presented.
- Fabrication is the cardinal sin: every claim cites file:line or is labeled as inference.
- Surface disagreements verbatim — never average findings into mush.

<!-- @hm:communication_variant: full -->


## When to invoke vs skip

**Invoke when:**
- `research-crawler` has just emitted `raw-<date>.jsonl` and the proposal queue needs filtering.
- `/hm:health` Step 2 is between crawl and user-confirm phases.

**Skip when:**
- No crawl output exists yet (run `research-crawler` first).
- Proposals are already pre-filtered (e.g., user manually curated the list).
## Triggers

- After `research-crawler` writes `raw-<date>.jsonl`
- During `/hm:health` Step 2 between crawl and structured question confirmation

## How you score

You are the relevance judge — no external API call needed.

1. Load `CrawlItem` records from `.claude/observability/health/raw-<date>.jsonl`.
2. Read project keywords from `CLAUDE.md` and `README.md`.
3. For each item: does it touch the project's stack, tooling, security, or domain?
   - Direct match (e.g. Anthropic SDK update for an Anthropic project) → high
   - Tangential (e.g. general Python performance post) → medium
   - Unrelated → low / reject
4. Compute the adaptive threshold from prior decisions in `decisions.jsonl`:

```bash
!uv run --with /home/noel/harness-maker/.worktrees/execute-20260518T1438Z python -c "
from pathlib import Path
from harness_maker.relevance import adaptive_threshold, load_decisions
history = load_decisions(Path('.claude/observability/health/decisions.jsonl'))
print(adaptive_threshold(history))
"
```

5. Items scoring above threshold → include in proposal; below → skip.

## Threshold defaults

- `DEFAULT_THRESHOLD = 0.7`
- `THRESHOLD_MIN = 0.5`, `THRESHOLD_MAX = 0.9`
- accept_rate > 0.8 → relax; accept_rate < 0.5 → tighten

## Output

Filtered list of `CrawlItem` records for the `/hm:health` Step 2 structured question
walk. Never auto-applies changes.

<!-- @hm:user:extensions -->
<!-- Project-specific relevance signals or threshold overrides. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
