---
generated_by: harness-maker
harness_maker_version: 0.52.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: stages/verify.md.j2
provenance: official
content_hash: 42234749fd74db27207b49a2a8ca65235db3b1150c3211864462994405a9d069
---
# Stage: verify

> Atomic stage. Pre-completion verification gate — 5-check stop sign before `wrapup`. Failures block by default; `--force` overrides explicitly.

## Communication Protocol

- Be direct. PASS / FAIL — no soft language.
- A failed check produces actionable evidence: which check, what failed, what to run to reproduce. Never just "regression detected".
- `--force` is logged with reason; never silent.
- Stop at the first FAIL — do not run remaining checks. The user fixes that one and re-runs.

## Purpose

Block silent regressions and partial completions. Run a rigid 5-check rubric that any work unit MUST pass before being declared done. This is the machine-checkable stop sign before `/hm:wrapup`.

## When to Run

- Just before `wrapup` (paired stages — verify then wrapup).
- At the end of every autoloop iteration (M8 invariant).
- On demand via `/hm:verify` whenever doubt arises.

## Usage

```
/hm:verify [--force] [--reason=<text>]
```

- `--force` — proceed even when one or more checks FAIL. **Logged with the override reason.** Use only when the user has consciously chosen to bypass (emergency hotfix, intentional debt). Without `--reason=<text>`, `--force` requires confirmation via `AskQuestion` (Cursor) or `AskUserQuestion` (Claude Code) in `en`.
- `--reason=<text>` — free-form override rationale. Required for `--force` in non-interactive contexts (autoloop).

## Inputs

- Current working tree state (staged + unstaged).
- `work-docs/PLAN-{slug}.md` and `specs/SPEC-{slug}.md` (when present) — drive Check 1.
- Most recent Health snapshot at `.claude/observability/dashboard.md` (2-section schema: `Structural` / `Personalization`; pre-0.13.0 single-`Health:` scalar is intentionally unreadable here). ADR-0007 removed the former `External risks` section in 0.22.3.
- Most recent security findings at `.claude/observability/security/findings-*.jsonl`.

## The 5 Checks (run in order; STOP on first FAIL unless `--force`)

### Check 1 — PLAN/SPEC satisfaction + drift verdict

**1a. Drift verdict existence** (ADR-006): Read `work-docs/REVIEW-{slug}.md` frontmatter.
- `drift_verdict` present AND `task_slug` matches current PLAN → proceed to 1b.
- `drift_verdict` absent OR `task_slug` mismatch → **FAIL**: `BLOCKED: check 1 (drift) — run /hm:review first`.

**1b. PLAN/SPEC coverage**: Every SPEC In-Scope Scenario in `specs/SPEC-{slug}.md` (when SPEC exists) is covered by a passing test in the work unit's diff, OR has an explicit waiver recorded in the PLAN's `## ❓ Open Questions` resolution.

```bash
# When SPEC exists:
- For each S1, S2, ... in SPEC: confirm a test function `test_s<N>_*` exists and passes.
- For each PLAN phase exit-criterion: confirm the criterion command runs GREEN.
```

FAIL when: any scenario lacks coverage AND lacks waiver.

### Check 2 — Regression smoke

**Check-suite skip** (ADR-007 + PLAN-workflow-overhead-post024): use the
deterministic verification-cache CLI, not prose reasoning, before running
the suite. The default `relevant` mode ignores wrapup-only memory/work-docs
churn but invalidates on source, tests, lockfiles, tool config, CI, and
verification script changes.


```bash
!uv run --with $HOME/harness-maker hm observability.verification_cache check --root . --mode relevant
```


If this exits `0`, print `PASS (cached)` and skip to Check 3. If it exits
`1`, run the suite below. Do not write a passing marker until every suite
command has passed.

Run the project's full check suite. Pick the toolchain that matches the project:

> **Ask for the runner's own recipe first — do not guess the parallel flag.** `hm test_runners
> plan --root .` names this project's runner, a worker count already capped for the machine
> (about half its cores, never all of them), and whether the runner is ALREADY parallel — for
> `cargo`, `go`, `vitest`, `jest` and `flutter` it is, and adding a worker flag there caps or
> nests instead of accelerating. `pytest` is the one common runner that is serial by default.
> Run the FULL suite here regardless: this is the stage that owns the whole-suite pass, and a
> suite only ever run in parallel hides order-dependent failures, so keep the flag on the
> command line and out of the project's persistent config.


```bash
# Python:
!uv run pytest -q
!uv run ruff check src/ tests/
!uv run ruff format --check src/ tests/
!uv run mypy --strict src/
# Rust: cargo test && cargo check
# Node: pnpm test && pnpm build
```


If the harness has its own `.claude-verify.sh phase_<N>` script, prefer it over the generic toolchain commands.

FAIL when: any subprocess returns non-zero.

After every selected suite command passes, write the marker:


```bash
!uv run --with $HOME/harness-maker hm observability.verification_cache mark-pass --root . --mode relevant --checks lint,format,mypy,pytest
```


### Check 3 — Structural delta (formerly "Health delta")

Read the prior `structural` score from `.claude/observability/dashboard.md` — specifically the `score:` line under the **`## Structural`** section of the 2-section dashboard (0.22.3+ schema). Do NOT average with `Personalization`; it is an orthogonal signal (deliberately) owned by no check at all.

Recompute current structural score (or invoke `/hm:health` Step 1 if a fresh score is needed). Compare ONLY structural values.

**No-baseline PASS rule (ADR-004):** when `dashboard.md` is absent OR exists but does NOT begin with `---\ngenerated_by: harness-maker\n` (pre-0.13.0 single-`Health:` scalar schema) OR is missing the `## Structural` section / `score:` line, emit a **PASS** for this check with a `reason` string `"no-baseline: <cause>"` (e.g. `"no-baseline: dashboard.md missing"`, `"no-baseline: pre-0.13.0 schema"`). Record both `prior: null` and `current: <value-or-null>` in the JSONL.

FAIL when: a parseable prior baseline exists AND `current_structural - prior_structural < -5` (structural score dropped more than 5 points). Mid-work-unit dips are normal; a 5+ point drop signals quality regression.

> **Personalization is NOT a gating field.** The `## Personalization` section (composite / tier / action_items) is informational only — verify must never read it for pass/fail. ADR-002 (amended by ADR-007).

### Check 4 — Security high findings

Read the most recent `.claude/observability/security/findings-*.jsonl`.

FAIL when: any finding has `severity == "high"` AND `resolution != "accepted-risk-with-rationale"`. Resolutions must be deliberate (recorded in PLAN ADR or wrapup commit body).

PASS when: zero unresolved high findings.

### Check 5 — Worktree merge cleanliness

When worktree isolation was engaged (`.worktrees/execute-*` exists or did exist), confirm the merge happened cleanly:

```bash
!git status
!git diff --check  # detects whitespace conflicts
```

FAIL when: there are unmerged paths, conflict markers, or unresolved merge state.

PASS when: working tree is clean OR has only the staged changes from `/hm:execute` Step 5 `stage-only`.

## Advisory probes (non-blocking)

These do **NOT** gate completion. They surface latent footguns and continue
with `exit 0` regardless of outcome. They sit OUTSIDE the 5-check contract
of `verify-before-completion` — adding new gating checks means changing
that SKILL; adding new advisory probes means appending here.

### A1. `work_docs/` (underscore) footgun probe

```bash
if [ -d "work_docs" ]; then
  echo "WARN: work_docs/ (underscore) directory found." >&2
  echo "      The harness-maker directory is work-docs/ (hyphen);" >&2
  echo "      work_docs is only the YAML key in harness.yaml." >&2
  echo "      Migration: git mv work_docs/* work-docs/ && rmdir work_docs" >&2
fi
exit 0
```

## Emit Gate 0 receipt (ADR-001, ADR-005)

You have completed the stage. Emit a receipt so the autoloop driver's Gate 0 can detect missing stages at the next convergence check. Pick `<verdict>`:

- **`pass`** — verify produced a green "=== /hm:verify ===" report (all gating checks passed).
- **`fail`** — any gating check failed; the report's status is non-OK.
- **`skipped`** — **DO NOT emit this value from a stage prompt.** Reserved for the autoloop driver's auto-retry escape hatch (ADR-005 of PLAN-loop-mid-stop-and-review-skip).

The shell guard below makes the receipt a no-op when `.current-iter` is absent — that file is written only by the autoloop driver at iter start. Standalone runs (no autoloop), no-isolation runs, and post-`/compact` restoration before iter 1 all skip the write naturally. This is by design — Gate 0 only reads receipts written under `iter-N` for N≥1. A `/hm:loop` iteration that includes `verify` in `--per-iter-stages` requires this receipt; without it Gate 0 would loop forever.


```bash
!if [ -f "./.claude/.hm-iter-receipts/.current-iter" ]; then \
   ITER=$(cat "./.claude/.hm-iter-receipts/.current-iter" 2>/dev/null); \
   if [ -n "$ITER" ]; then \
     uv run --with $HOME/harness-maker hm iter_receipts write \
       --iter "$ITER" --stage verify --verdict <verdict> --root "."; \
   fi; \
 fi
```


## Output

Write **both** formats:

### Text (stdout, for humans)


```
=== /hm:verify ===

[1/5] PLAN/SPEC satisfaction       ✅ PASS
[2/5] Regression smoke             ✅ PASS
[3/5] Structural delta             ✅ PASS  (structural 87 → 89, +2)
[4/5] Security high findings       ❌ FAIL
        1 unresolved high finding:
        - CVE-2026-12345 in dependency `httpx` (severity=high, no rationale).
        Resolve or record accepted-risk-with-rationale.

[5/5] (skipped — stopped at first FAIL)

RESULT: FAIL — 1 of 5 checks failed.
Override: --force --reason="<text>"  (logs to verify-<date>.jsonl with the reason)
```


### JSON (`.claude/observability/verify-<YYYY-MM-DD>.jsonl`, append one record)


```json
{
  "timestamp": "2026-05-17T14:23:01Z",
  "stage": "verify",
  "result": "FAIL",
  "checks": [
    {"id": 1, "name": "plan_spec_satisfaction", "result": "PASS"},
    {"id": 2, "name": "regression_smoke", "result": "PASS"},
    {"id": 3, "name": "structural_delta", "result": "PASS", "delta": 2, "prior": 87, "current": 89, "reason": null},
    {"id": 4, "name": "security_high", "result": "FAIL", "blocking_items": 1, "items": ["CVE-2026-12345"], "reason": null},
    {"id": 5, "name": "worktree_merge", "result": "SKIPPED"}
  ],
  "force_override": false,
  "override_reason": null
}
```


For no-baseline PASS, the corresponding check record carries `"result": "PASS"` and a populated `"reason"` string (e.g. `"no-baseline: dashboard.md missing"` / `"no-baseline: pre-0.13.0 schema"`); `prior` / `current` may be `null`. Verify never emits `result: "PASS"` for Check 3 silently — a populated `reason` is mandatory whenever the baseline was missing or unparseable.

> **Personalization field is informational only.** The JSONL record never contains a `personalization` check entry. Verify reads structural only; the `## Personalization` section of dashboard.md is for `/hm:health` reporting and is ignored by this stage. ADR-002 (amended by ADR-007).

When `--force` is set, append the same record with `"force_override": true, "override_reason": "<text>"`.

## Procedure


1. Read inputs (PLAN, SPEC, dashboard, security findings).
2. Run Check 1. If PASS, continue. If FAIL: emit text + JSON record + STOP (unless `--force`).
3. Repeat for Checks 2-5.
4. Emit final RESULT line + JSON record.
5. When `--force` is set with FAILing checks: emit text + JSON record with override flag + reason, then return PASS exit code (let the workflow proceed). Wrapup will surface the override in the commit body footer.
6. **Stage terminal**: Emit the RESULT line and **STOP**. Do not proceed to `/hm:wrapup` or any other stage without an explicit user command — unless this stage was dispatched by `/hm:loop`, which owns the transition to the next stage. Exception: an auto-advance check below returning `proceed: true` supersedes this.

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


<!-- @hm:autopilot-advance -->
## Auto-advance check (autopilot — Claude Code only)

Before the STOP banner below, check whether this session runs under **autopilot** (live
auto-advance, ADR-005) — **Claude-Code-only**: it needs the `.hm-autopilot` marker (armed
by the picker) and the `Skill` tool. **This section is a NO-OP** — fall straight through
to the STOP banner, running nothing below — **if any of: no `Skill` tool (Cursor/Codex),
no active marker, or loop-mode is on for THIS session (a `.claude/.hm-loop-*` marker
matches `$HM_SESSION_ID`, or a legacy `.hm-loop-active` exists).**

**Step 1 — mandatory gate FIRST (absent-case = STOP).** Evaluate THIS stage's gate
*before* anything else: If any verification check FAILED, STOP.
If the gate is pending/unresolved → record it on the ledger, then **STOP** (print the
banner). Do NOT run the boundary check — a stage that stops at its gate must not record an
advance:

!uv run --with $HOME/harness-maker hm autopilot_caps gate-blocked --root . --stage verify --session-id "$HM_SESSION_ID"

**Step 2 — boundary check (ONLY when the gate is clear).** Run the deterministic check
(it enforces the Phase-5 runaway caps + kill switch, and on proceed records the advance it
authorizes — so it must run only after Step 1 clears):

If this stage has a slug, **append** it to the command below in single quotes — e.g.
` --slug 'my-task'`. Never a shell expression or a bracketed placeholder. Omit it
otherwise; the marker keeps the earlier stage's slug.


!uv run --with $HOME/harness-maker hm autopilot_caps boundary --root . --current verify --session-id "$HM_SESSION_ID" --step-cap 20 --time-cap-min 300

Read the JSON:
- `proceed: false` → **STOP** (print the banner) — **except `bad_slug`**. `step_cap`/
  `time_cap` = a runaway cap fired (`halted_cap` logged, marker cleared); `kill_switch` =
  autopilot off/expired; `merge_gate` = the next stage is human-gated (e.g. wrapup's
  merge/land — the marker was cleared, so invoke `/hm:wrapup` manually); `unknown_stage` =
  `--current` not in the pipeline; `pipeline_complete: true` = the pipeline finished and
  the marker was cleared.
  **`bad_slug` is yours to undo**: the `--slug` you passed is invalid; nothing was
  authorized. Do NOT print the banner — re-run with a corrected slug, or no flag.
- `proceed: true` → **auto-advance**: invoke `Skill(hm:<next_stage from the JSON>)` with
  the JSON's `task_slug` as its argument (omit when `null`), instead of the STOP banner.
  **This supersedes this stage's earlier "Stage terminal … STOP"** — that governs the
  gated path, and `proceed: true` IS the authorization it asks for. `task_slug_source:
  "persisted"` means the slug came from an earlier stage — name it before invoking, so
  another task's slug cannot advance silently.

<!-- @hm:/autopilot-advance -->

## Stage summary — print before you STOP

Skip this banner entirely if loop-mode is active for THIS session (a
`.claude/.hm-loop-*` marker matches `$HM_SESSION_ID`, or a legacy
`.hm-loop-active` exists — the autoloop uses machine receipts, not prose).
Otherwise emit it as your final output, in the configured output language:
<!-- @hm:banner:end -->
> ✅ **Done:** Full check suite run — tests + lint + type
> 📁 **Artifacts:** the RESULT line (PASS / FAIL) above
> ➡️ **Next:** STOP — await the next user command


<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific verify checklist items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the verify stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
