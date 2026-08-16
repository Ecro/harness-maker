---
generated_by: harness-maker
harness_maker_version: 0.52.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/verify-before-completion/SKILL.md.j2
provenance: official
name: verify-before-completion
description: Pre-wrapup gate enforcing 5 checks before any /hm:wrapup or autoloop
  iteration close. Failure on any check blocks completion and surfaces the failing
  check name + remediation hint.
content_hash: 6540b967e2f157338e372b18804c8eeea094d0e6a7897a8d19d787d10d3062b0
---

# verify-before-completion

Mandatory gate before `/hm:wrapup` or autoloop iteration close. All 5
checks must pass; the first failure short-circuits and blocks.

ADR-0007 (0.22.3) reduced the gate from 6 to 5 checks by removing the
former Check 4 (anti-rot pending queue) when the `/hm:health`
external_risks layer was dropped. CVE coverage now lives in `/hm:verify`
Check 5 (security) via `secscan/dependency_cves.py`, not here.

Invoke before `/hm:wrapup` (M8 invariant), at the end of every `/hm:loop`
iteration, or on demand via `/hm:verify`. Skip only for trivial work units
(typo / docs-only / config-only — wrapup's pre-flight covers it) or when a
previous PASS in the same session is still valid (no new commits / test
changes since).

## The 5 Checks

### 1. PLAN/SPEC satisfaction + drift verdict — you verify (hard fail)

You are the judge for this check. Do NOT delegate to a subprocess.

**1a. Drift verdict** (ADR-006): read `work-docs/REVIEW-{slug}.md`
frontmatter. If `drift_verdict` is absent OR `task_slug` does not match the
current PLAN → `BLOCKED: check 1 (drift) — run /hm:review first` and stop.

**1b. PLAN/SPEC coverage**:

```bash
work_docs="work-docs/"
test -d "$work_docs" || { echo "BLOCKED: check 1 — work_docs dir missing"; exit 1; }
plan=$(ls "$work_docs"/PLAN-*.md 2>/dev/null | head -1)
test -n "$plan" || { echo "BLOCKED: check 1 — no PLAN-*.md found"; exit 1; }
echo "PLAN=$plan"
!git diff HEAD~1 HEAD 2>/dev/null || git diff
```

Read the PLAN (`$plan`) and `specs/SPEC-{slug}.md` when present,
and the diff. Every numbered PLAN item / SPEC In-Scope Scenario must have
matching code/test/doc changes in the diff, OR an explicit waiver in the PLAN's
`## ❓ Open Questions` resolution — a ticked checkbox alone does NOT pass. On any
miss, output `BLOCKED: check 1 (PLAN-fulfillment) — <item text> not found in
diff` and stop (do not proceed to check 2).

### 2. Regression / smoke gate

Use the deterministic verification-cache CLI; run the full suite only when the
cache is invalidated (ADR-007 — `relevant` mode ignores wrapup-only churn).

```bash
!uv run --with $HOME/harness-maker python -m harness_maker.observability.verification_cache check --root . --mode relevant || (
  uv run pytest -q &&
  uv run ruff check src/ tests/ &&
  uv run ruff format --check src/ tests/ &&
  uv run mypy --strict src/ &&
  uv run --with $HOME/harness-maker python -m harness_maker.observability.verification_cache mark-pass --root . --mode relevant --checks lint,format,mypy,pytest
)
```

Pick the toolchain that matches the project (Rust: `cargo test && cargo check`;
Node: `pnpm test && pnpm build`). If the project ships its own
`.claude-verify.sh`, prefer `bash .claude-verify.sh` over the generic commands.
FAIL on any non-zero exit.

### 3. Structural score within −5 of baseline

Read the prior `structural` score from the `score:` line under the
`## Structural` section of `.claude/observability/dashboard.md` (0.22.3+
2-section schema). Recompute the current structural score (or run `/hm:health`
Step 1 — it scores against preset `Side`). Compare ONLY
structural values — never read `## Personalization` for pass/fail.

**No-baseline PASS rule (ADR-004):** when `dashboard.md` is absent, lacks
`generated_by: harness-maker` frontmatter (pre-0.13.0 single-`Health:` schema),
or is missing the `## Structural` `score:` line → emit PASS with
`reason: "no-baseline: <cause>"`.

FAIL only when a parseable prior exists AND
`current_structural - prior_structural < -5`.

### 4. Zero unresolved high/P0 security findings

```bash
latest=$(ls -t .claude/observability/security/findings-*.jsonl 2>/dev/null | head -1)
if [ -n "$latest" ]; then
  # Count high/P0 findings NOT marked accepted-risk (one JSON object per line,
  # so a same-line exclusion is exact). grep -vc counts non-matching lines.
  unresolved=$(grep -E '"severity": ?"(high|P0)"' "$latest" | grep -vc 'accepted-risk-with-rationale' || true)
  [ "$unresolved" -eq 0 ] || exit 1
fi
exit 0
```

A finding marked `resolution: accepted-risk-with-rationale` (recorded in a PLAN
ADR or the wrapup commit body) does not count. The 7 gates use two severity
vocabularies — most emit `high`, but `hallucination` and `prod_name_guard` emit
`P0`; both must gate.

### 5. Worktree merge-safe (branch-agnostic)

```bash
git diff --check || exit 1                     # whitespace / leftover conflict markers
git ls-files --unmerged | grep -q . && exit 1  # unmerged paths
exit 0
```

## Failure Behavior

First failing check halts the gate.
Output: `BLOCKED: check <N> (<name>) — <reason>`.
When blocked, the calling command must abort. Remediation hints:
PLAN unclosed → list incomplete tasks; smoke fail → re-run failing test;
structural drop → show `/hm:health` Structural breakdown; security high/P0 →
list findings; merge conflict → show conflicting paths.

<!-- @hm:user:extensions -->
<!-- Project-specific verify checks beyond the 5 baseline. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
