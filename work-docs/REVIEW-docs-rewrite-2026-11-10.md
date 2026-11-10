---
type: review
task_slug: docs-rewrite
created: 2026-11-10
spec: "[[SPEC-docs-rewrite]]"
plan: "[[PLAN-docs-rewrite]]"
rounds: 1
reviewers: [code-reviewer]
summary: "One code-reviewer round checked every HOW-IT-WORKS claim against the source: 3 major and 5 minor claim errors and 1 nit, plus stale lines outside the first scope and a weak test. All accepted and fixed."
---

# REVIEW — docs-rewrite

One code-reviewer round read both HOW-IT-WORKS locales against the stage templates, `check.py`,
`synthesize.py`, the hook templates, `spec_machine.py`, `models.py` and the Maker skill. It
confirmed the contract block, the agent and skill render tables, the four stage descriptions, the
`hm check` sections and exit codes, the worktree commands, the Claude hooks and the Korean/English
parity. The spec-validator was skipped (`validator: skip`, 1 AC). No `Do not change` path was
crossed.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F-1 | major | docs/HOW-IT-WORKS{,.ko}.md (§4 gates row, §13 toolchains row) | `hm check` never reads `toolchains`; without a CI file it derives ruff, mypy and pytest from pyproject.toml, plus `reviewers.mechanical_checks` (check.py:386-411). Fix: gates row reworded, toolchains row dropped | accepted | check.py `gate_commands` |
| F-2 | major | docs/HOW-IT-WORKS{,.ko}.md (§9 spec_gate row, §13 spec.strictness row) | `spec_gate` blocks writing a test file no SPEC references; it checks no approval (spec_gate.py:55-148). Fix: both rows say what it does | accepted | spec_gate.py |
| F-3 | minor | docs/HOW-IT-WORKS{,.ko}.md (§9) | The table mixed Claude and Codex hooks; Codex has no worktree_gate or PreCompact, runs flush_session at Stop and sessionstart_drift at SessionStart, and spec_gate on apply_patch. Fix: a host column and the Codex rows | accepted | codex/hooks.json.j2 |
| F-4 | minor | docs/HOW-IT-WORKS{,.ko}.md (§3.2 step 5) | A blocked quality score stops the stage only at `block`; at `warn` it warns. Fix: stated | accepted | spec.md.j2 Step 4.5 |
| F-5 | minor | docs/HOW-IT-WORKS{,.ko}.md (§5) | Advance runs only after a full-pipeline start or resume, and also stops on a non-zero last `hm check` and on queued asks. Fix: "Scope follows the ask" plus the full stop list, matching README | accepted | world-model SKILL.md.j2 Advance |
| F-6 | minor | docs/HOW-IT-WORKS{,.ko}.md (§11) | A single-voter finding can still be accepted by `code-verifier`. Fix: stated | accepted | execute.md.j2 second opinion |
| F-7 | nit | docs/HOW-IT-WORKS{,.ko}.md (§3.2) | The worktree applies only with `worktree.enabled`. Fix: stated | accepted | spec.md.j2 preflight |
| F-8 | minor | ARCHITECTURE.md:266, README.md (119, 145, 186, 456, 542, 745, 856-861, 883), README.ko.md:99, block-merge-spec.md:194 | Still presented `relevance.py`, the foreign-config import and autopilot as live. Fix: removed, or reworded to say they were deleted or retired; scope widened in the SPEC's O3 sense | accepted | SPEC O3 |
| F-9 | major | tests/unit/test_docs_rewrite.py | The test missed README, ARCHITECTURE and block-merge-spec; its heading regex was case-sensitive and narrow; it allowed duplicate stage sections; nothing checked locale parity; bare substring match. Fix: all living docs scanned line by line (a deleted name is allowed only on a line saying deleted or retired), case-insensitive regex over every retired piece, exactly one heading per stage, equal `##` section counts across locales, word-bounded module match | accepted | SPEC AC-001 |
