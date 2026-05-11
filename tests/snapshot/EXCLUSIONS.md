# Snapshot Exclusions

> Paths listed below are **excluded** from `tests/snapshot/regenerate.py` and
> `tests/unit/test_synthesize_snapshot.py` comparisons.
>
> Why: PLAN-llm-code-review-2026 ADR-005 abandons reviewer-output determinism
> at Phase C. Outputs whose body is allowed to vary cannot be hashed against
> a frozen `body_sha256` — they would flake.

## Format

One blob glob per line (matching `fnmatch.fnmatch` semantics against the
rendered file's path). Lines starting with `#` and blank lines are ignored.

```
# Example:
# .claude/agents/code-reviewer.md
# .claude/agents/security-reviewer.md
```

## Active exclusions

<!-- @hm:exclusion-list -->
<!-- Phase A5 lands the mechanism with an empty list; Phase C1 populates it -->
<!-- when reviewer prompts adopt agentic-depth framing (ADR-003).             -->
<!-- @hm:/exclusion-list -->
