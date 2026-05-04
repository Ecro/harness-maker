# AI Readiness — harness-maker

**Composite:** 45 / 100

## Layer scores

| Layer | Score | What it measures |
|-------|------:|------------------|
| readiness | 43 | Deterministic structural signals (CLAUDE.md, hooks, tests, CI, …) |
| llm_judge | 50 | LLM-judged content quality vs rubrics |
| cache | 50 | Prompt-cache hit rate + failure-mode diagnosis |

## Actions

| Priority | Dimension | Summary | Suggestion |
|----------|-----------|---------|------------|
| P0 | guardrails | No hooks defined | Define PreToolUse/PostToolUse hooks (e.g., secret scan, telemetry) |
| P0 | guardrails | hooks.json missing | Add .claude/hooks/hooks.json with at least telemetry |
| P0 | memory_continuity | failures.md is empty or stub | Append real failure lessons after each incident |
| P0 | memory_continuity | memory/failures.md missing | Run /hm:make; document each post-mortem lesson in memory/failures.md |
| P0 | observability_setup | dashboard.md missing | Run /hm:ai-readiness to render the dashboard |
| P0 | observability_setup | no metrics.jsonl | Use Claude Code for ≥ 5 turns to accumulate telemetry |
| P0 | observability_setup | metrics.jsonl missing | Install the PostToolUse telemetry hook (run /hm:make) |
| P0 | observability_setup | .claude/observability/ missing | Run /hm:make to scaffold the observability directory |
| P0 | workflow_clarity | No /hm: commands found | Run /hm:make to install the standard /hm: commands |
| P0 | workflow_clarity | No fused workflows defined | Define fused workflows in harness.yaml (e.g., exec-rev, exec-rev-wrap) |
| P1 | context_quality | 274 lines vs 200 limit (Side) | Trim CLAUDE.md to ≤ 200 lines (split into skills or imports) |
| P1 | guardrails | Deny list does not cover dangerous patterns | Block rm -rf, curl\|sh, writes to /etc and ~/.ssh |
| P1 | guardrails | settings.json permissions.deny is empty or missing | Add settings.json `permissions.deny` blocking dangerous Bash patterns |
| P1 | memory_continuity | harness.yaml lacks memory configuration | Add `memory:` config to harness.yaml |
| P1 | memory_continuity | memory/wiki.md missing | Run /hm:make to install memory/wiki.md scaffolding |
| P1 | verification | verify-before-completion skill missing | Run /hm:make to install the verify-before-completion skill |
| P1 | workflow_clarity | harness.yaml missing workflow definitions | Add `workflows:` and `default_workflow:` to harness.yaml |

