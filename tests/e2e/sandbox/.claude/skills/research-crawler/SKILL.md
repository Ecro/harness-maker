---
generated_by: harness-maker
harness_maker_version: 0.6.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/research-crawler/SKILL.md.j2
provenance: official
content_hash: f33179104793a2c77bcecfa21b9fa25116f568255598220ab61ceaf4f6a50f6d
---
# research-crawler

> Crawl 4 sources for harness updates: Anthropic blog, GitHub releases (claude-code + reference repos), arxiv (cs.SE/cs.CL/cs.CR), and OSV.dev CVE feed.

## Triggers

- `/hm:refresh` invocation (manual or weekly schedule)
- Anti-rot freshness gauge crosses staleness threshold (`days since refresh`)

## Behavior

Invoke each crawler module from `harness_maker.crawler` with cached HTTP
clients. All four MUST run; partial failures degrade gracefully (the failing
source returns an empty list with a stderr warning, the rest continue).

```python
from harness_maker.crawler import anthropic_blog, github_releases, arxiv, osv_dev, write_raw

items = []
items += anthropic_blog.crawl()
items += github_releases.crawl()  # defaults to ["anthropics/claude-code"]
items += arxiv.crawl("cat:cs.SE OR cat:cs.CL OR cat:cs.CR")
items += osv_dev.crawl(packages=osv_dev.parse_uv_lock("uv.lock"))

write_raw(items, project_dir=".")
```

Output goes to `<project>/.claude/observability/refresh/raw-<YYYY-MM-DD>.jsonl`.
Downstream the `relevance-filter` skill scores each item.

## Output

A `raw-<date>.jsonl` snapshot of `CrawlItem` records. Never auto-applies
changes — only writes raw data; the `/hm:refresh` command is responsible for
the AskUserQuestion confirmation flow.

<!-- @hm:user:extensions -->
<!-- Project-specific crawler sources (additional RSS feeds, repos to track, etc.). Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
