---
generated_by: harness-maker
harness_maker_version: 0.2.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/context-linter/SKILL.md.j2
provenance: official
name: context-linter
description: Lint generated CLAUDE.md / agent / skill / workflow files for verbose-context
  bloat against per-preset line thresholds. Use before /hm:execute or /hm:wrapup to
  keep the agent context lean.
content_hash: 012827c4f0267b47cba5123ba3df775a79c2259ce96f6cd2ab2728552e0b3bfd
---

# context-linter

Self-lint skill bundled into the user's harness. Wraps `harness_maker.context_lint.lint`
to surface warnings when generated assets exceed the line budgets that protect model
attention quality.

## When to invoke

- Right before `/hm:execute` (catch bloat before it hits the iteration loop)
- Right before `/hm:wrapup` (final gate before commit)
- Manually on any single file: `lint(path, asset_type, preset)`

## Thresholds (lines, frontmatter excluded)

| Asset type   | Side preset | Production preset |
|--------------|------------:|------------------:|
| `CLAUDE.md`  |         200 |               500 |
| `agent`      |         100 |               200 |
| `skill`      |          50 |               150 |
| `workflow`   |         300 |               600 |
| `other`      |   (no limit) |       (no limit) |

Warnings include a suggested trim count and a hint to split long files into
referenced docs (link out from CLAUDE.md instead of inlining).

## Invocation

```python
from harness_maker.context_lint import lint
from harness_maker.models import Preset

warnings = lint(Path(".claude/agents/code-reviewer.md"), "agent", Preset.PRODUCTION)
for w in warnings:
    print("WARN:", w)
```

## Output

A flat list of warning strings. Empty list = file is within budget.
