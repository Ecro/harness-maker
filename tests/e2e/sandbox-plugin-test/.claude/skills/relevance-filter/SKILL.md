---
generated_by: harness-maker
harness_maker_version: 0.4.8
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/relevance-filter/SKILL.md.j2
provenance: official
content_hash: 4020e7dfd7a241e031f5e50552ae169b8a585f9054f97f760328456caa5fabaf
---
# relevance-filter

> Score crawled items against project context using your own judgment, then
> apply an adaptive threshold to filter the proposal list.

## Triggers

- After `research-crawler` writes `raw-<date>.jsonl`
- During `/hm:refresh` between crawl and AskUserQuestion confirmation

## How you score

You are the relevance judge — no external API call needed.

1. Load `CrawlItem` records from `.claude/observability/refresh/raw-<date>.jsonl`.
2. Read project keywords from `CLAUDE.md` and `README.md`.
3. For each item: does it touch the project's stack, tooling, security, or domain?
   - Direct match (e.g. Anthropic SDK update for an Anthropic project) → high
   - Tangential (e.g. general Python performance post) → medium
   - Unrelated → low / reject
4. Compute the adaptive threshold from prior decisions in `decisions.jsonl`:

```bash
!uv run --with /home/noel/harness-maker python -c "
from pathlib import Path
from harness_maker.relevance import adaptive_threshold, load_decisions
history = load_decisions(Path('.claude/observability/refresh/decisions.jsonl'))
print(adaptive_threshold(history))
"
```

5. Items scoring above threshold → include in proposal; below → skip.

## Threshold defaults

- `DEFAULT_THRESHOLD = 0.7`
- `THRESHOLD_MIN = 0.5`, `THRESHOLD_MAX = 0.9`
- accept_rate > 0.8 → relax; accept_rate < 0.5 → tighten

## Output

Filtered list of `CrawlItem` records for the `/hm:refresh` AskUserQuestion
walk. Never auto-applies changes.

<!-- @hm:user:extensions -->
<!-- Project-specific relevance signals or threshold overrides. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
