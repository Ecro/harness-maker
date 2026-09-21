---
generated_by: harness-maker
harness_maker_version: 0.58.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/atomic_command.md.j2
provenance: official
description: Pre-completion stop sign — deterministic regression, structure and security
  checks.
content_hash: 4dc69df1e7759148b0283531ff9c133bf6055d5287236fbcfbe007e290673b1a
---
> **Before you begin — outline your plan.** First check whether an autoloop is
> active **for THIS session** (session-scoped — a loop in another session must
> not suppress your banner). Loop-mode is active iff `$HM_SESSION_ID` matches a
> `.claude/.hm-loop-*` marker's `claude_session_id:` content header, OR a legacy
> `<project-root>/.hm-loop-active` exists (degraded fallback). The project root is
> above `.worktrees/` if your cwd is inside a `.worktrees/<name>/` worktree (strip
> the `/.worktrees/<wt-name>/` suffix, or `git rev-parse --show-toplevel` then walk
> up out of `.worktrees/`).
> **If loop-mode is active for this session, skip this banner entirely and operate
> without it** — the autoloop runs silently and a per-iteration banner would flood
> the transcript. Otherwise, print the start banner below (in the configured output
> language), then begin.

<!-- @hm:banner:start -->
> 🎯 **Goal:** one line — what this command will accomplish for the user.
> 📋 **Plan:** a short numbered list of the top-level steps you intend to take —
> for a single stage, its `Step` / `Phase` / `Check` headings; for a fused
> workflow, **one line per stage** (the `## Stage:` entries), not every sub-step.
> Present them as **intended, conditional** steps — skip heuristics, early-exit /
> early-FAIL rules, and any stage's own `STOP — do not proceed` boundary override
> this plan; never treat the banner as a commitment to run past a STOP.

<!-- @hm:autopilot-picker -->
> **Autopilot session start.** This harness is configured for autonomy (`autonomy.level: ask`).
> **Arming works in any runtime**; only end-of-stage auto-advance needs Claude Code's `Skill`
> tool. If loop-mode is active for this session (see above), SKIP this. Otherwise, at the first eligible stage, ask the CLI
> whether autopilot is already active — **never decide this from whether the marker file
> exists.** Nothing collects a stale one, so file-existence reads as "already armed" and
> autopilot silently never turns on — the usual reason it looks dead.
>
> `uv run --with $HOME/harness-maker hm autopilot status --root . --session-id "$HM_SESSION_ID"`
>
> Branch on **both** fields of the JSON (it always exits 0):
> - `active: true` → armed already. Skip the picker; do not re-arm.
> - `reason: "foreign"` → **rare** (one file per session): the file at YOUR key holds someone
>   else's id. **You cannot tell an active peer from one abandoned mid-pipeline**, so do not
>   guess and never `--force` on your own initiative. State it — `idle_minutes` is the owner's
>   silence, `null` = unknown — then ask: *is another Claude session open in this project?*
>   Only on **no**, re-run the arm command with `--force`. On yes, stay gated.
> - `reason: "degraded-idless"` → no id of your own: **NORMAL state, not a failure** in Cursor/Codex (`$CLAUDE_ENV_FILE` is Claude-Code-only), a hook failure in Claude Code.
>   Arm either way — unset expands to `""` and arms the shared degraded marker.
> - `reason: "ask-pending"` → the normal path here (`level: ask`). Offer three options via
>   `AskUserQuestion` for the `research → spec → execute → review → verify → wrapup` pipeline:
>   **`auto_safe`** (stops at the plan interview), **`auto_full`** (answers it, and an
>   APPROVED review's `human_review_needed`), or **gated**. A CHANGES_REQUESTED review and
>   the wrapup land stop at every level. Arm with the PICKED level:
> - anything else → offer ONCE via `AskUserQuestion`: "Run the
>   `research → spec → execute → review → verify → wrapup` pipeline on autopilot this session
>   (stages auto-advance when no mandatory gate is pending), or stay gated?" On **yes**:
>   `uv run --with $HOME/harness-maker hm autopilot on --level <the level the user picked> --pipeline research,spec,execute,review,verify,wrapup --session-id "$HM_SESSION_ID"`
>   On **no**, proceed gated — do not re-prompt unless the user asks.
>
> **Persistence:** the marker lives at the **project root** (a stage inside
> `.worktrees/<slug>/` sees it), is **one file per session** (`.hm-autopilot-<id>`, so two
> can be armed), and expires after 18h. `session_scoped: false` = no id (Cursor, Codex,
> hook failure) → you share `.hm-autopilot-degraded`. Commit
> `autonomy.autopilot_persistent: true` to auto-arm every session; the default is `true`.
<!-- @hm:/autopilot-picker -->



> **Output language.** Respond to the user in **en**
> (en→English, ko→Korean, ja→Japanese, others→English fallback) on **every turn** —
> the live chat output and the start/end summary banners, not only the onboarding
> interview. Code, identifiers, file paths, and the persisted deliverable documents
> (PLAN / RESEARCH / REVIEW / SPEC) stay in **English**.
<!-- @hm:output_language -->


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
- `work-docs/REVIEW-{slug}.md` frontmatter — drives Check 1 (drift verdict).
- `work-docs/PLAN-{slug}.md` and `specs/SPEC-{slug}.md` (when present) — inform the `--force` rationale.
- Most recent Health snapshot at `.claude/observability/dashboard.md` (2-section schema: `Structural` / `Personalization`; pre-0.13.0 single-`Health:` scalar is intentionally unreadable here). ADR-0007 removed the former `External risks` section in 0.22.3.
- Most recent security findings at `.claude/observability/security/findings-*.jsonl`.

## The 5 Checks (run in order; STOP on first FAIL unless `--force`)

### Check 1 — Drift verdict (REVIEW present)

**Drift verdict existence** (ADR-006): Read `work-docs/REVIEW-{slug}.md` frontmatter.
- `drift_verdict` present AND `task_slug` matches current PLAN → **PASS**.
- `drift_verdict` absent OR `task_slug` mismatch → **FAIL**: `BLOCKED: check 1 (drift) — run /hm:review first`.

This check is mechanical on purpose. The LLM PLAN/SPEC coverage judgement that used to sit here
as "1b" is gone (PLAN-workflow-steps-vs-model-capability ADR-003). Per-scenario coverage is
enforced where the tests are written: `/hm:execute` Phase A authors one test per SPEC scenario
and Phase A.5's coverage lens blocks implementation on any `scenarios_missing` (A.5 is a
TUNE-class gate graded `**` — Side-preset evidence only, no ground-truth arm; see the
step-sensitivity registry); `/hm:wrapup` Step 3.5 writes the covering test ids back into the machine SPEC
(`pending_test`). Test-expressed PLAN exit criteria are re-run by Check 2 below; a script or
manual-checklist exit criterion has **no** automated re-check at this stage.
**`--no-tdd` path:** `/hm:execute --no-tdd` skips Phase A/A.5, and this stage does not
re-derive scenario coverage. Task-driven mode has no machine
SPEC to scan, so on that path an uncovered scenario reaches wrapup unflagged — the accepted
cost of `--no-tdd` without a SPEC contract.

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

**Ask the project's CI what the gates are — never guess them.** A guessed command that is
NARROWER than CI passes locally and fails on push, saying nothing about what it skipped.


```bash
!uv run --with $HOME/harness-maker hm verification_plan commands --root .
```


Run each printed command verbatim. **Exit 1 = degraded** (no CI, unreadable, nothing
recognised — stderr says which): only then fall back to the project's toolchain
(`pytest -q` / `ruff check .` / `ruff format --check .` / `mypy --strict`; `cargo test`;
`pnpm test`) and say the gates were guessed. `show` prints the full plan — blocking CI
commands NOT selected, plus what it could not classify — read it when a gate looks missing.
Parallel flags stay with `hm test_runners plan --root .`: `pytest` is serial by default,
`cargo`/`go`/`vitest`/`jest` are already parallel and a worker flag there nests.

If the harness has its own `.claude-verify.sh phase_<N>` script, prefer it over the generic toolchain commands.

FAIL when: any subprocess returns non-zero.

After every selected suite command passes, write the marker:


```bash
!uv run --with $HOME/harness-maker hm observability.verification_cache mark-pass --root . --mode relevant --checks lint,format,mypy,pytest
```


### Check 3 — Structural delta (formerly "Health delta")

Read the prior `structural` score from `.claude/observability/dashboard.md` — specifically the `score:` line under the **`## Structural`** section of the 2-section dashboard (0.22.3+ schema). Do NOT average with `Personalization`; it is an orthogonal signal (deliberately) owned by no check at all.

Recompute current structural score (or invoke `/hm:health` Step 1 if a fresh score is needed). Compare ONLY structural values.

**No-baseline PASS rule (ADR-004):** when `dashboard.md` is absent OR exists but does NOT begin with `---\ngenerated_by: harness-maker\n` (pre-0.13.0 single-`Health:` scalar schema) OR is missing the `## Structural` section / `score:` line, emit a **PASS** for this check with a `reason` string `"no-baseline: <cause>"` (e.g. `"no-baseline: dashboard.md missing"`, `"no-baseline: pre-0.13.0 schema"`). Report both `prior` (null) and `current` (value or null) in the text summary.

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

### Text (stdout, for humans)


```
=== /hm:verify ===

[1/5] Drift verdict (REVIEW present) ✅ PASS
[2/5] Regression smoke             ✅ PASS
[3/5] Structural delta             ✅ PASS  (structural 87 → 89, +2)
[4/5] Security high findings       ❌ FAIL
        1 unresolved high finding:
        - CVE-2026-12345 in dependency `httpx` (severity=high, no rationale).
        Resolve or record accepted-risk-with-rationale.

[5/5] (skipped — stopped at first FAIL)

RESULT: FAIL — 1 of 5 checks failed.
Override: --force --reason="<text>"
```


## Procedure


1. Read inputs (PLAN, SPEC, dashboard, security findings).
2. Run Check 1. If PASS, continue. If FAIL: emit the text summary + STOP (unless `--force`).
3. Repeat for Checks 2-5.
4. Emit the final RESULT line (text summary only — there is no JSONL ledger, see Outputs).
5. When `--force` is set with FAILing checks: emit the text summary with the override flag + reason, then return PASS exit code (let the workflow proceed). Wrapup will surface the override in the commit body footer.
6. **Stage terminal**: Emit the RESULT line and **STOP**. Do not proceed to `/hm:wrapup` or any other stage without an explicit user command — unless this stage was dispatched by `/hm:loop`, which owns the transition to the next stage. Exception: an auto-advance check below returning `proceed: true` supersedes this.

## Outputs

- Text summary on stdout (human-facing). No JSONL ledger from this stage: the former `verify-<date>.jsonl` record was hand-written prose nothing read (stage entry/exit is already in `stage-spans.jsonl` and `auto-advance.jsonl`); the CI-facing `verify` command in `cli.py` (`_write_verify_jsonl`) still appends its own machine record to that file family.
- Exit code: `0` for PASS or `--force` override; non-zero for FAIL without override.

## Quality Bar

- The gate is **non-negotiable**; bypassing requires `--force --reason=<text>`.
- A failed check produces actionable evidence (which scenario / which test / which finding) — not just a red line.
- `--force` is recorded in the RESULT line with the reason, and `/hm:wrapup` surfaces it in the commit body footer — auditable later.
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
