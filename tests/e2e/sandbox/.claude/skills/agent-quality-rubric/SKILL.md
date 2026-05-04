---
generated_by: harness-maker
harness_maker_version: 0.3.5
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/agent-quality-rubric/SKILL.md.j2
provenance: official
name: agent-quality-rubric
description: Tier-rank an agent .md file Platinum/Gold/Silver/Bronze using static
  structural checks combined with the agent_prompt LLM rubric. Bronze tier auto-flags
  for anti-rot review. Calls harness_maker.agent_quality.score_agent.
content_hash: 5a863f9da9e424ebe5389194556fc3b917b9764bf5ad36f24ee1b86c14aeab1c
---

# agent-quality-rubric

Hybrid: static structural signals + Layer-2 LLM judgment against
`.claude/rubrics/agent_prompt.yaml`. Composite = `(static + llm) // 2`
when both run, static alone when the LLM is unreachable.

## When

- `/hm:ai-readiness` agent drill-down · after any `agents/*.md` edit
  · `/hm:refresh` Bronze flagging.

## Tier Thresholds

| Composite | Tier | Action |
|---|---|---|
| ≥ 90 | Platinum | None |
| ≥ 80 | Gold | None |
| ≥ 70 | Silver | Watch |
| < 70 | Bronze | Auto-register anti-rot patch candidate |

## Implementation

```python
from pathlib import Path
from harness_maker.agent_quality import score_agent
from harness_maker.llm_judge import AnthropicJudgeClient

result = score_agent(
    Path(".claude/agents/code-reviewer.md"),
    rubric_dir=Path(".claude/rubrics"),
    client=AnthropicJudgeClient(),
)
# {"static": 70, "llm": 85, "composite": 77, "tier": "Silver"}
```

`client=None` (or unreachable LLM) → static-only scoring with a logged
warning; the function never raises.

## Static signals

- 40 pts — line count 100-500; 20 pts for 50-99 or 501-700
- 30 pts — valid YAML frontmatter (open + close)
- 30 pts — has bullets or fenced code blocks (structured prose)

<!-- @hm:user:extensions -->
<!-- Project-specific scoring overrides or rubric extensions. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
