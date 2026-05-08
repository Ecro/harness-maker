---
generated_by: harness-maker
harness_maker_version: 0.6.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: stages/verify.md.j2
provenance: official
content_hash: 0d8b5fcd83e26d95888276bfd226a4c705d626d52471c770b3f66bdc041fbe02
---
# Stage: verify

> Atomic stage. Pre-completion verification gate — 6-check stop sign before `wrapup`. Failures block by default; `--force` overrides explicitly.


## Communication Protocol

- Be direct. PASS / FAIL — no soft language.
- A failed check produces actionable evidence: which check, what failed, what to run to reproduce. Never just "regression detected".
- `--force` is logged with reason; never silent.
- Stop at the first FAIL — do not run remaining checks. The user fixes that one and re-runs.

## Purpose

Block silent regressions and partial completions. Run a rigid 6-check rubric that any work unit MUST pass before being declared done. This is the machine-checkable stop sign before `/hm:wrapup`.

## When to Run

- Just before `wrapup` (paired stages — verify then wrapup).
- At the end of every autoloop iteration (M8 invariant).
- On demand via `/hm:verify` whenever doubt arises.

## Usage

```
/hm:verify [--force] [--reason=<text>]
```

- `--force` — proceed even when one or more checks FAIL. **Logged with the override reason.** Use only when the user has consciously chosen to bypass (emergency hotfix, intentional debt). Without `--reason=<text>`, `--force` requires confirmation via AskUserQuestion in `en`.
- `--reason=<text>` — free-form override rationale. Required for `--force` in non-interactive contexts (autoloop).

## Inputs

- Current working tree state (staged + unstaged).
- `work-docs/PLAN-{slug}.md` and `specs/SPEC-{slug}.md` (when present) — drive Check 1.
- Most recent Health snapshot at `.claude/observability/dashboard.md`.
- Most recent security findings at `.claude/observability/security/findings-*.jsonl`.
- Anti-rot pending queue at `.claude/observability/refresh/pending.jsonl`.

## The 6 Checks (run in order; STOP on first FAIL unless `--force`)

### Check 1 — PLAN/SPEC satisfaction

Every SPEC In-Scope Scenario in `specs/SPEC-{slug}.md` (when SPEC exists) is covered by a passing test in the work unit's diff, OR has an explicit waiver recorded in the PLAN's `## ❓ Open Questions` resolution.

```bash
# When SPEC exists:
- For each S1, S2, ... in SPEC: confirm a test function `test_s<N>_*` exists and passes.
- For each PLAN phase exit-criterion: confirm the criterion command runs GREEN.
```

FAIL when: any scenario lacks coverage AND lacks waiver.

### Check 2 — Regression smoke

Run the project's full check suite. Pick the toolchain that matches the project:

```bash
# Python:
!uv run pytest -q
!uv run ruff check src/ tests/
!uv run mypy --strict src/
# Rust: cargo test && cargo check
# Node: pnpm test && pnpm build
```

If the harness has its own `.claude-verify.sh phase_<N>` script, prefer it over the generic toolchain commands.

FAIL when: any subprocess returns non-zero.

### Check 3 — Health delta

Read the prior Health score from `.claude/observability/dashboard.md` (the snapshot recorded at the start of this work unit, or the last `/hm:ai-readiness` run).

Recompute current Health (or invoke `/hm:ai-readiness` if a fresh score is needed).

FAIL when: `current - prior < -5` (Health dropped more than 5 points). Mid-work-unit dips are normal; a 5+ point drop signals quality regression.

### Check 4 — Anti-rot pending queue

Read `.claude/observability/refresh/pending.jsonl` (when present).

FAIL when: any pending item has `relevance_score >= 0.8` AND `category in {security, breaking-change}`. These are blocking items — `wrapup`-ing while ignoring them silently absorbs the rot.

PASS when: queue is empty, or remaining items are below the blocking threshold.

### Check 5 — Security high findings

Read the most recent `.claude/observability/security/findings-*.jsonl`.

FAIL when: any finding has `severity == "high"` AND `resolution != "accepted-risk-with-rationale"`. Resolutions must be deliberate (recorded in PLAN ADR or wrapup commit body).

PASS when: zero unresolved high findings.

### Check 6 — Worktree merge cleanliness

When worktree isolation was engaged (`.worktrees/execute-*` exists or did exist), confirm the merge happened cleanly:

```bash
!git status
!git diff --check  # detects whitespace conflicts
```

FAIL when: there are unmerged paths, conflict markers, or unresolved merge state.

PASS when: working tree is clean OR has only the staged changes from `/hm:execute` Step 5 `stage-only`.

## Output

Write **both** formats:

### Text (stdout, for humans)

```
=== /hm:verify ===

[1/6] PLAN/SPEC satisfaction       ✅ PASS
[2/6] Regression smoke             ✅ PASS
[3/6] Health delta                 ✅ PASS  (87 → 89, +2)
[4/6] Anti-rot pending queue       ❌ FAIL
        2 items at relevance≥0.8 + category=security:
        - CVE-2026-12345 in dependency `httpx` (pending since 2026-05-01)
        - Anthropic blog "tool-use schema v3" (pending since 2026-05-03)
        Run /hm:refresh to triage these before wrapup.

[5/6] (skipped — stopped at first FAIL)
[6/6] (skipped — stopped at first FAIL)

RESULT: FAIL — 1 of 6 checks failed.
Override: --force --reason="<text>"  (logs to verify-<date>.jsonl with the reason)
```

### JSON (`.claude/observability/verify-<YYYY-MM-DD>.jsonl`, append one record)

```json
{
  "timestamp": "2026-05-08T14:23:01Z",
  "stage": "verify",
  "result": "FAIL",
  "checks": [
    {"id": 1, "name": "plan_spec_satisfaction", "result": "PASS"},
    {"id": 2, "name": "regression_smoke", "result": "PASS"},
    {"id": 3, "name": "health_delta", "result": "PASS", "delta": 2, "prior": 87, "current": 89},
    {"id": 4, "name": "antirot_pending", "result": "FAIL", "blocking_items": 2, "items": [...]},
    {"id": 5, "name": "security_high", "result": "SKIPPED"},
    {"id": 6, "name": "worktree_merge", "result": "SKIPPED"}
  ],
  "force_override": false,
  "override_reason": null
}
```

When `--force` is set, append the same record with `"force_override": true, "override_reason": "<text>"`.

## Procedure

1. Read inputs (PLAN, SPEC, dashboard, security findings, pending queue).
2. Run Check 1. If PASS, continue. If FAIL: emit text + JSON record + STOP (unless `--force`).
3. Repeat for Checks 2-6.
4. Emit final RESULT line + JSON record.
5. When `--force` is set with FAILing checks: emit text + JSON record with override flag + reason, then return PASS exit code (let the workflow proceed). Wrapup will surface the override in the commit body footer.

## Outputs

- Text summary on stdout (human-facing).
- One JSON record appended to `.claude/observability/verify-<YYYY-MM-DD>.jsonl`.
- Exit code: `0` for PASS or `--force` override; non-zero for FAIL without override.

## Quality Bar

- The gate is **non-negotiable**; bypassing requires `--force --reason=<text>`.
- A failed check produces actionable evidence (which scenario / which test / which finding) — not just a red line.
- The JSON record is parseable by the autoloop driver to make stop/continue decisions without re-parsing stdout.
- `--force` is recorded in the JSONL with the reason — auditable later.
- No check produces false PASS by missing inputs (e.g., a missing `findings-*.jsonl` is a soft skip, not a silent PASS).

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific verify checklist items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the verify stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
