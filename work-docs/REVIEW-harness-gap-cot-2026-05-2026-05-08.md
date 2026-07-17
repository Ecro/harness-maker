---
type: review
task_slug: harness-gap-cot-2026-05
status: in-progress
created: 2026-05-08
reviewers_invoked: [code-reviewer, security-reviewer, performance-reviewer, concurrency-reviewer]
consensus_method: cross-check
routing: conditional
target_commit: 52346c9
plan_ref: work-docs/plans/PLAN-harness-gap-cot-2026-05.md
---

# Review: harness-gap-cot-2026-05 (Reliability Stack 0.7.0, Phases 0-11)

> 12-phase autoloop output (53 files, +3462 lines) reviewed by 4 specialists in parallel.

## 🎯 Round 1 Summary

**Grade: F** (4 P0 / 6 P1 consensus-passed; ≥3 P0 → F per rubric)

- **Drift gate**: 5 findings (1 P0, 4 P1). 5 of 7 new modules are unreachable from runtime — exist as standalone Python only, never invoked by templates/hooks/security_scanner.
- **Code/Concurrency/Performance** triangulated the same architectural defect: **read-modify-write data-loss race** across 4 stores (`episodic`, `semantic`, `profile`, `tool_cascade`). All four use `mkstemp` + `read_text(existing)` + write-everything-back + `os.replace` — looks atomic, actually loses concurrent writes silently.
- **Security** added: prompt injection (3 sites), wrong-fd-mode, gate-not-wired, importlib side-effect risk.

## 🔍 Drift Findings (PLAN scope vs actual diff)

| ID | Sev | Phase | Issue |
|----|-----|-------|-------|
| **D1** | P0 | 8 | `prod_name_guard.py` exists, but `security_scanner.scan_all` does NOT call it. Docstring lies about "Gate 7". Corroborated by Security F4. |
| **D2** | P1 | 4 | `templates/skills/trajectory-monitor/SKILL.md` and `templates/agents/trajectory-monitor.md` (PLAN line 291) — **not created**. Drift monitor module exists but has no skill/agent surface. |
| **D3** | P1 | 5 | `templates/agents/consensus-arbiter.md.j2` was supposed to be modified for scope-aware consensus; `review_scope` frontmatter on reviewer agents was supposed to be added (PLAN line 298). Neither happened — only `conditional_router.py` was extended. The runtime consensus-arbiter prompt does NOT know about scope-aware consensus. |
| **D4** | P1 | 6 | PLAN said modify `templates/stages/review.md.j2` + `templates/agents/code-reviewer.md` for 2-pass review (PLAN line 305, ablation PASSED). Instead, a standalone module `src/harness_maker/two_pass_review.py` was created. The review-stage prompt is unchanged → 2-pass review is NOT actually invoked at review time. |
| **D5** | P1 | 9 | `templates/stages/spec.md.j2` and `templates/commands/hm/spec.md.j2` (PLAN line 327) — **not modified**. `spec_quality.py` exists but the spec-stage prompt does not invoke it → weak specs are NOT blocked at spec-driven mode. |

**Pattern: orphaned modules.** Outside their own unit tests, the following 6 modules have ZERO references in templates/hooks/runtime:

```
src/harness_maker/drift_monitor.py        — 0 integration sites
src/harness_maker/two_pass_review.py      — 0 integration sites
src/harness_maker/spec_quality.py         — 0 integration sites
src/harness_maker/tool_cascade.py         — 0 integration sites
src/harness_maker/test_dep_map.py         — 1 prose mention in execute.md.j2 (no call)
src/harness_maker/secscan/prod_name_guard.py — 0 integration sites (docstring lies)
```

Verified via:
```bash
$ grep -rn "from harness_maker.{module} import" --include="*.py" --include="*.j2" --include="*.md" \
  | grep -v "^tests/\|^src/harness_maker/{module}.py"
# → only the security_scanner docstring line for prod_name_guard
```

PLAN's intent was integration; implementation produced standalone modules that pass their own unit tests but are unreachable from the harness execution path. **The 12-phase autoloop satisfied "exit criterion: pytest passes" without satisfying the architectural goal.**

## ✅ Consensus Findings (consensus-passed, by severity)

### P0 — Blockers (4)

**CP1 — `episodic.py:47` read-modify-write loses concurrent writes**
- Reviewers: code [F1] + concurrency [C1] + performance [PF1] — **3/4 strong consensus**
- Evidence: `EpisodicStore.write()` uses `mkstemp` → `target.read_text()` → `f.write(existing + line)` → `os.replace`. Two concurrent hook fires both read N-line snapshot, both write N+1 lines, second `os.replace` clobbers first.
- Reasoning chain agrees across reviewers: TOCTOU between the read and the replace.
- **Fix**: Replace with direct `open(target, "a") + f.write(line + "\n")`. POSIX `O_APPEND` is atomic for single lines < 4KB.

**CP2 — `tool_cascade.py:91` read-modify-write loses concurrent failure logs**
- Reviewers: code [F2] + concurrency [C2] + performance [PF5] — **3/4 strong consensus**
- Same pattern as CP1. Under retry storm, multiple `_log_failure` calls clobber each other.
- **Fix**: Replace `mkstemp + read + replace` block (lines 84-98) with `open(self._log_path, "a") + f.write(json.dumps(entry) + "\n")` after `mkdir`.

**CP3 — `semantic.py:41` read-modify-write loses concurrent slug updates** *(architectural-pattern transitivity)*
- Reviewer: concurrency [C3] only — **1/4 single-source**, BUT same pattern as CP1+CP2 confirmed by 3 reviewers in adjacent modules. Promoted to **consensus-passed-by-pattern** under the architectural-transitivity rule (when a defect class is consensus-passed, every instance of the same pattern is consensus-passed).
- **Fix**: `fcntl.flock(LOCK_EX)` around `_read_index + _write_index`, OR rebuild index from JSONL append-only log on read.

**CP4 — `profile.py:35` read-modify-write loses concurrent profile updates** *(architectural-pattern transitivity)*
- Reviewer: concurrency [C4] only — same transitivity argument as CP3.
- **Fix**: Same as CP3 — flock around the read+write pair, or move to SQLite which handles concurrent writes natively.

### P1 — Must Fix (6)

**CP5 — `telemetry.py:142` non-atomic JSONL append (policy + size unbounded)**
- Reviewers: code [F4] + security [F5] + concurrency [C5] — **3/4 strong consensus**
- Two angles: (a) violates CLAUDE.md atomic_write policy; (b) POSIX `O_APPEND` only atomic up to PIPE_BUF (4096 B) — large entries can interleave.
- **Fix**: Either document the deliberate exception with an inline comment + bounded-size assertion, OR adopt the same `mkstemp + read + replace` pattern (which is also broken — see CP1; the right fix is `flock` + direct append).

**CP6 — `security_scanner.py:39` `_persist` non-atomic JSONL** *(architectural-pattern)*
- Reviewer: security [F2] only, but same pattern as CP5 → consensus-passed-by-pattern P1.
- **Fix**: Apply same fix as CP5.

**CP7 — `prod_name_guard` not wired into `security_scanner`** (D1 + Security F4)
- Reviewers: drift gate + security [F4] — **2/4 consensus**.
- Severity vote: drift=P0, security=P1 → middle = P1.
- security_scanner.py docstring lines 7-11 list 7 gates including `prod_name_guard`, but `scan_all()` body never imports or calls it.
- **Fix**: This requires a design decision (does scan_all receive a tool-call list?). Marked as **drift, requires manual integration** — not a one-line auto-fix.

**CP8 — `hallucination.py:53-55` `_is_guarded_import` is dead+broken** (Code F3)
- Single reviewer, but verified independently: function takes `ast.AST` and walks for `ExceptHandler`. Import nodes have no ExceptHandler children — always returns False. Function is never called (lines 73-78 do the actual guarded-import detection inline).
- Promoted to **consensus-passed** because the bug is verifiable by static reading (no reasoning ambiguity).
- **Fix**: Delete `_is_guarded_import` (lines 53-55).

**CP9 — `spec_quality.py:144` bare `except` swallows LLM errors → bypasses gate** (Code F7)
- Single reviewer, but the reasoning is concrete: in `DevMode.SPEC_DRIVEN`, network blip → silent fallback to heuristic → weak spec passes the gate that's supposed to block it.
- **Fix**: Add logger.warning before `pass` to surface the failure.

**CP10 — `two_pass_review.py:139-145` `merge_passes` returns invalidated findings** (Code F5)
- Single reviewer; the bug is in the contract: findings tagged `invalidated_by_context` are still returned in `merged`, requiring callers to filter by status. Defeats the design intent.
- Compounded by D4: nothing actually calls `merge_passes` from the runtime, so the user-visible impact is zero today — but if D4 is ever fixed (wire 2-pass into review.md.j2), the bug becomes immediately exploitable.
- **Fix**: Either return only `pass2_findings`, or rename status to make it explicit and update docstring.

### P2 — Should Fix (8)

| ID | Reviewer | File:line | Summary |
|----|----------|-----------|---------|
| CP11 | sec [F9] + conc [C6] | episodic.py:54 | `os.fdopen(mkstemp_fd, "a")` mode wrong — fd is at offset 0 (consensus 2/4) |
| CP12 | sec [F8] | two_pass_review.py:92 | Pass 2 prompt embeds raw PR title/desc — injection vector after redaction |
| CP13 | code [F8] | drift_monitor.py:42 | `SimpleHashEmbedding` is semantically meaningless; emits no warning when used as production fallback |
| CP14 | code [F9] | prod_name_guard.py:16 | Regex `\bprod\b` false-positives on `prod` as Python identifier |
| CP15 | code [F10] | conditional_router.py:56 | dedup key includes severity — defeats consensus detection when reviewers disagree on severity |
| CP16 | code [F11] | test_dep_map.py:83 | `break` in inner `for alias` loop, but `ast.walk` outer loop continues — same file appended twice |
| CP17 | code [F12] | cache_diagnostics.py:91 | `_classify_turn` checks `miss_min_threshold` before `miss_first` — first-turn small input misclassified |
| CP18 | conc [C7] | tool_cascade.py:36 | `_failure_counts`, `_switch_history` instance dicts have no lock — corrupt under shared use |

## ⚠️ Weak Consensus

None — all surface-matched pairs had aligned reasoning chains.

## 📝 Manual-Only Findings

Surface-unique findings preserved as-is (truncated; see raw reviewer outputs):

- **Sec F3 (P0)**: `spec_quality.py:126` raw spec text in LLM prompt — prompt injection. Single source. **Severity P0** stands; recorded for manual review.
- **Sec F6 (P1)**: `drift_monitor.py:126` SPEC/PLAN baseline passed raw to LLM judge without delimiters — prompt injection.
- **Sec F7 (P1)**: `hallucination.py:47` `importlib.util.find_spec()` may execute namespace package finders / .pth-registered hooks for attacker-controlled package names.
- **Code F6 (P1)**: `spec_quality.py:136` `import json` inside function body — should be module-level.
- **Perf PF2 (P1)**: `retrieval.py:43-47` re-reads full JSONL for each matching event. O(M*N) when one read would suffice.
- **Perf PF4 (P1)**: `hallucination.py:40` `_is_available` no `lru_cache` — `find_spec` repeats per file.
- **Perf PF6 (P2)**: `drift_monitor.py:47` naive Python cosine — would benefit from numpy at 1536-dim production embeddings.
- **Perf PF7 (P2)**: `drift_monitor.py:111` re-embeds baseline per call — should cache by hash.
- **Perf PF8 (P2)**: `test_dep_map.py:64` re-parses every test file's AST per source — should pre-build inverted import map.
- **Perf PF9 (P2)**: `prod_name_guard.py:69` sliding window passes full history — should bound at last `window+1` entries.
- **Conc C8 (P2)**: `cache_diagnostics.py:218` full-file read may see partial last line under concurrent writer (defense-in-depth).
- **Sec F1 (P0)** — **REJECTED on review**: `scan_prompt_injection_regex_only` deferred import does NOT have a swallowing except clause; ImportError would propagate. Reviewer reasoning was speculative.

## 🤝 Disagreements

- **CP1 severity**: code/concurrency=P0, performance=P1. Performance reviewer framed it as I/O cost; the others framed it as data loss. Data loss > cost → **P0** wins (majority + middle-of-scale rule both yield P0).

## Grade Computation

| | Count |
|---|---|
| consensus-passed P0 | 4 (CP1, CP2, CP3, CP4) |
| consensus-passed P1 | 6 (CP5, CP6, CP7, CP8, CP9, CP10) |
| consensus-passed P2 | 8 (CP11-CP18) |
| weak-consensus | 0 |
| manual-only | 12 |
| drift | 5 (D1=P0, D2-D5=P1) |

**Grade: F** (P0 ≥ 3 → F per rubric).

## Auto-Fix Decision

**Auto-fix is ENABLED in harness.yaml, but I am NOT proceeding into the auto-fix loop this round.**

Rationale:
1. **Most P0/P1 findings require architectural decisions, not one-line edits** — read-modify-write fix needs a choice between flock vs. append-only redesign; D1-D5 drift findings need new template files authored.
2. **Auto-fixing the orphaned-module pattern is out of scope** for the review stage's `Edit`-based auto-fix loop. It needs new template authoring (templates/skills/trajectory-monitor/SKILL.md, etc.).
3. **The PLAN itself has a integration gap** — the autoloop satisfied "pytest pass" but not "modules are reachable". Auto-fixing code without addressing the wiring would lock in the orphan pattern.

Status: **CHANGES_REQUESTED**.
human_review_needed: **true**.

## Recommended Next Steps (for user decision)

1. **Triage P0 races** — Choose between `fcntl.flock` (preserves current API, cross-platform caveat on Windows) or **append-only JSONL** redesign (simpler, requires re-thinking semantic.py + profile.py read paths). Recommendation: append-only for episodic + tool_cascade (pure log); flock for semantic + profile (need read-modify-write semantics).
2. **Wire the orphaned modules** — A new mini-PLAN is needed for D1-D5. Suggested phase order:
   - Phase 12a: wire `prod_name_guard` into `security_scanner.scan_all` (D1)
   - Phase 12b: render trajectory-monitor SKILL.md + agent template (D2)
   - Phase 12c: modify `consensus-arbiter.md.j2` + add `review_scope` frontmatter to reviewer templates (D3)
   - Phase 12d: modify `review.md.j2` to invoke 2-pass review at runtime (D4)
   - Phase 12e: modify `spec.md.j2` + `commands/hm/spec.md.j2` to invoke `evaluate_spec` (D5)
3. **Address P1 prompt injections** — wrap user-controlled text (spec body, baseline_text, PR metadata) in XML fences before LLM prompt interpolation. Single-shot pattern can be applied across spec_quality, drift_monitor, two_pass_review.
4. **CP8 + CP9** are clean one-line auto-fixes — could be applied immediately if user prefers.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining (P0/P1) | New |
|-----------|-------|---------------|-------------------|-----|
| 1 (init)  | F     | —             | 4 / 6             | —   |

Final grade: **F**
Iterations used: 1 / 3
Status: **CHANGES_REQUESTED**
human_review_needed: **true**
