---
generated_by: harness-maker
harness_maker_version: 0.7.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/agent-quality-rubric/SKILL.md.j2
provenance: official
name: agent-quality-rubric
description: Tier-rank an agent .md file Platinum/Gold/Silver/Bronze using static
  structural checks combined with the agent_prompt LLM rubric. Bronze tier auto-flags
  for anti-rot review. Calls harness_maker.agent_quality.score_agent.
content_hash: 979db9c4f67a9083cb32adf69a5969256db52964cb28ab4421e575d0151391ea
---

# agent-quality-rubric

Hybrid: static structural signals + Layer-2 LLM judgment against
`.claude/rubrics/agent_prompt.yaml`. Composite = `(static + llm) // 2`
when both run, static alone when the LLM is unreachable.


## When to invoke vs skip

**Invoke when:**
- `/hm:ai-readiness` is computing per-agent quality scores.
- A new agent template was added and needs a tier ranking.
- A regression check after a major agent prompt rewrite.

**Skip when:**
- The agent in question is already scored Platinum/Gold and unchanged since.
- The dashboard's last regenerated date is < 7 days ago and no agents changed.
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

## How to invoke

You are the LLM judge. Read the agent file and evaluate it against
`.claude/rubrics/agent_prompt.yaml`. Call the static scorer via subprocess,
then merge the two scores:

```bash
!uv run --with /home/noel/harness-maker/.worktrees/execute-20260508T1017Z python -c "
from pathlib import Path
from harness_maker.agent_quality import score_agent
result = score_agent(Path('.claude/agents/code-reviewer.md'), rubric_dir=Path('.claude/rubrics'), client=None)
print(result)
"
```

Then evaluate the same agent file against each rubric criterion in
`.claude/rubrics/agent_prompt.yaml` yourself. Compute:
- `llm_score` = severity-weighted pass rate (P0=3, P1=2, P2=1)
- `composite` = (static_score + llm_score) // 2
- `tier` = Platinum ≥90 / Gold ≥80 / Silver ≥70 / Bronze <70

## Static signals

- 40 pts — line count 100-500; 20 pts for 50-99 or 501-700
- 30 pts — valid YAML frontmatter (open + close)
- 30 pts — has bullets or fenced code blocks (structured prose)

<!-- @hm:user:extensions -->
<!-- Project-specific scoring overrides or rubric extensions. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
