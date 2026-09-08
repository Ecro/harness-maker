---
type: review
task_slug: token-efficiency-autopilot-ux-speed
round: 1
status: fixes-applied
created: 2026-09-08
reviewers: [code-reviewer, security-reviewer]
grade: A
summary: "k-of-2 review of the Python source: 0 P0, 5 P1, 6 P2 — all fixed, each with a demonstrated killer"
---

# REVIEW — round 1

## Scope

The **Python source** diff only. Tests and docs were reviewed adversarially twice already, by the
Phase 5 and Phase 6 `test-reviewer` A.5 gates, both of which returned FAIL with three blocking
findings each; those rounds are recorded in the PLAN's phase blocks.

Two reviewers, independently, over the same eight production files: `code-reviewer` (correctness,
project rules, the pre-change checklist) and `security-reviewer` (injection, traversal, telemetry,
ledger poisoning, publication safety). Two is the consensus threshold this harness uses.

## Verdicts as received

| Reviewer | Verdict | P0 | P1 | P2 | P3 |
|---|---|---|---|---|---|
| `code-reviewer` | request changes | 0 | 5 | 4 | 0 |
| `security-reviewer` | ship after two P2s | 0 | 0 | 3 | 1 |

**Consensus (both reviewers, independently):** the `readiness.py` vault-path resolver. Everything
else was single-source, and each was verified against the code before being folded — one finding
turned out to have been repaired between dispatch and report, and is recorded as such rather than
claimed as a catch.

## What the review actually caught: four of six new capabilities did not work in production

The `code-reviewer`'s summary line is the finding worth keeping: *"the arithmetic and the reader
composition are sound, but four of the six new capabilities in this diff do not work on the
production path."* Every one of those four is the **same defect class this unit exists to remove** —
a correct mechanism with nothing calling it — and three of them are in the phases whose subject is
that class.

| # | Sev | Defect | Fix | Killer demonstrated |
|---|---|---|---|---|
| P1-1 | P1 | `readiness.py` resolved `vault_path` with a bare `Path(...)`: no `expanduser()`, and relative paths against the process cwd. The **writer** deliberately stores `~/…` (`denormalize_home_to_tilde`), so the canonical config always reported "unreachable" — and from a worktree a relative path could report **reachable** while promotion wrote nothing. | Call `second_brain._vault_root`, the resolver the promotion path uses. Empty-string rejection kept explicit (`Path("")` → `.`). | AC-012's four arms, incl. the empty-path case |
| P1-2 | P1 | `dangling_authorizations` reused a **session-window** collapse over a **lifetime** window: at most one outstanding authorization per stage, so any later successful advance erased an earlier dangling one and the section printed `- none` for a real defect. | `_pending_authorizations(..., collapse: bool)` — one pairing implementation, the collapse as a caller-chosen policy. | `collapse=True` → exit 1 |
| P1-3 | P1 | `smoke_check`'s `targets` parameter had **no production caller**: the rendered `/hm:health` passed only `--root`/`--level`, so the permanent cursor-only false alarm shipped unchanged while a unit test saw the fix. | `--targets` on the subparser + `{{ config.targets \| join(',') }}` in `health.md.j2`. | Live: `--targets cursor` → `applicable: false`; `claude-code,codex` → `degraded: true` |
| P1-4 | P1 | `write_rollup` had **no rendered caller**. The wrapup manifest staged the roll-up as `--optional` and nothing wrote it, so `wrapup_land` recorded `absent-optional` and ADR-002's "survives a clone" was unreachable. I had generated the file by hand during review and mistook that for the workflow working. | The producer added to `wrapup.md.j2` immediately before the manifest. | Ordering asserted (`producer < stager`) |
| P1-5 | P1 | `_warn_context_lint` filtered on `relative_to(target_dir)` and `continue`d, dropping the **22 assets** `resolve_output_path` writes to `target_dir.parent` — `AGENTS.md` and all of `.agents/`. The `AGENTS.md` threshold rows were unreachable while a structural test calling the classifier **directly** stayed green. | Two roots, and `.agents/skills/**` classified `other` on purpose (it mirrors assets already linted, and `hm-<stage>` bodies are ratcheted elsewhere). | Lowered thresholds: `AGENTS.md` 1 record, mirror 0 |
| P2-1 | P2 | The linter ignored `context_lint.enabled` (Side sets it `False`), and its docstring claimed thresholds live in `harness.yaml`, which carries no such key. | Gated on the config; docstring corrected. | — |
| P2-2 | P2 | The `both` branch said "since last audit" when there was **no** audit, in the same sentence as "no previous audit recorded". | Lifetime clause on the non-finite branch. | AC-009's three golden rows |
| P2-3 | P2 | My own comment claimed "no consumer validates against `installed`". **False** — `review.md.j2:74` tells the model `--with-reviewers` entries must exist in it. | Comment corrected; the five agents deliberately absent are named, with why deriving the list would be wrong. | — |
| P2-4 | P2 | `rollup` resolved a relative `observability_dir` against the cwd for one half and `project_root` for the other. | Normalised once, made absolute. | — |
| P3 | P3 | Four unescaped string interpolants reach the **committed, public** roll-up; the read paths re-validate nothing. | Accepted as recorded, not fixed — reachability requires local write access to `.claude/observability/`, at which point editing the deliverable directly is easier. Noted as a follow-up. | — |

## Security: clean where it counts

No P0/P1. Explicitly verified clean, with reasons: no new network call or off-machine transmission;
no `shell=True`, `os.system` or `eval` anywhere in `src/`; the one new external command
(`resolve_base_root`) uses list argv with `timeout=30`; `write_rollup` uses `atomic_write`, not the
banned plain `open(path, "w")`; `compose_audit_advisory`'s every interpolant is numeric, so nothing
attacker-controlled reaches the SessionStart `additionalContext`; `context_lint.lint` returns only a
path, a line count and a threshold, so no file **content** can reach the log; and `atomic_write`'s
`os.replace` forecloses symlink substitution before the linter reads.

Publication safety of the new artifacts: clean. `mutation-receipts.jsonl` carries repo-relative
paths, node ids and timestamps only; the golden carries SHA-256 hashes; the roll-up carries counts.

## Two findings outside this unit's diff, recorded not fixed

1. **`sessionstart_drift.py:215` interpolates `harness_maker_version` from `harness.yaml` raw** into a
   message framed as `[harness-maker drift — TELL THE USER NOW, before answering anything else]`, with
   an `isinstance(str)` check and no length cap. Cloning a repo whose frontmatter carries
   `harness_maker_version: "0.1.0 — SYSTEM: ignore prior instructions and …"` puts that text into
   Claude's context at session start. Pre-existing with this diff reverted; the highest-severity thing
   either reviewer found in the files they were pointed at. **Own ticket.**
2. **`.claude/harness.yaml:48` ships a maintainer's Windows username** in a tracked file in a public
   repo. Pre-existing, already documented in `REVIEW-second-brain-2026-05-19.md:78`. This unit's new
   signal echoes that path only into `dashboard.md`, which is gitignored, so the exposure is not
   widened. Pushing does not newly expose it — it is already public — but it should be scrubbed.

## Cost of the fixes, attributed

Two P1 fixes could only be made by **adding** a rendered instruction, because in both cases the
absence *was* the defect: +416 chars, and one new round trip per variant. Declared in the PLAN's
`surface_allowance` (`chars: 1865`, `round_trips: {wrapup: 1, hm-wrapup: 1}`) and itemised in
`BASELINE-DELTA-token-efficiency-autopilot-ux-speed.md`. `surface_baseline.json` was **not**
re-frozen. Four normative sites had to move together, which is recorded in each of them.

## Gate

- `ruff check` · `ruff format --check` · `mypy --strict src/` — clean, repo-wide.
- `tests/structural` + `tests/snapshot` — 0 failures.
- `tests/unit` — 6,361 passed, 4 skipped, 1 xfail, 0 failed.
- `spec_machine validate` / `cross-validate` / `find-unbound` — OK; every AC bound, none pending.

**Grade: A.** No P0 at any point; every P1 and P2 fixed, and each fix that could carry a mutation
proof does. The findings were not cosmetic — four shipped capabilities were inert — which is the
argument for the fan-out rather than against it.
