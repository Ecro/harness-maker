---
generated_by: harness-maker
harness_maker_version: 0.3.2
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/relevance-filter/SKILL.md.j2
provenance: official
content_hash: d846b301f6964ce782b6bf5dc91e5a994a74ea902a0ccf1ff22d4b13c61dd5df
---
# relevance-filter

> Score crawled items against project context and apply an adaptive threshold.

## Triggers

- After `research-crawler` writes a `raw-<date>.jsonl`
- During `/hm:refresh` between crawl and AskUserQuestion confirmation

## Behavior

1. Load `CrawlItem` records from `.claude/observability/refresh/raw-<date>.jsonl`.
2. Extract project keywords from `CLAUDE.md` and `README.md` (token list).
3. Score each item with `harness_maker.relevance.score_item(item, keywords)`.
4. Compute the next threshold via `adaptive_threshold(history)` where
   `history` is the list of accept/reject booleans from prior `/hm:refresh`
   sessions (stored in `.claude/observability/refresh/decisions.jsonl`).
5. Filter items: `filter_items(items, threshold)`.

```python
from harness_maker.relevance import adaptive_threshold, filter_items, score_item

threshold = adaptive_threshold(history)
for item in items:
    item.score = score_item(item, project_keywords)
proposed = filter_items(items, threshold)
```

## Output

A list of `CrawlItem` records that passed the threshold, surfaced to the user
by `/hm:refresh` for explicit accept / reject / defer choice.
**Never auto-applies changes.**

## Threshold defaults (from `harness_maker.relevance`)

- `DEFAULT_THRESHOLD = 0.7`
- `THRESHOLD_MIN = 0.5`, `THRESHOLD_MAX = 0.9`
- `WINDOW = 20` recent decisions; `MIN_SAMPLES = 5` before adapting
- accept_rate > 0.8 → relax (lower threshold, more items pass)
- accept_rate < 0.5 → tighten (raise threshold, fewer items pass)

<!-- @hm:user:extensions -->
<!-- Project-specific relevance signals or threshold overrides. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
