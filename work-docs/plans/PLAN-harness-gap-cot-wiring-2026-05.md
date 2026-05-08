---
type: plan
task_slug: harness-gap-cot-wiring-2026-05
status: planning
created: 2026-05-08
parent_plan: PLAN-harness-gap-cot-2026-05
review_ref: REVIEW-harness-gap-cot-2026-05-2026-05-08.md
tags: [harness-maker, plan, wiring, race-fix, cursor-compat]
summary: "0.7.0 release-blocker fixes — wire orphaned modules + race fixes + Cursor postToolUse"
---

# PLAN: harness-gap-cot-wiring (0.7.0 release blockers)

## 🎯 Executive Summary

**TL;DR:** REVIEW-harness-gap-cot-2026-05-2026-05-08.md found 4 P0 + 6 P1 + 5 drift findings that block 0.7.0 push. This mini-PLAN closes them in 3 phases before any push.

**Why this exists:** the parent PLAN's 12-phase loop satisfied "pytest pass" but not "modules are reachable from runtime". Five of seven new reliability modules are orphaned (no template/hook calls them). Plus the same read-modify-write race pattern was implemented in 4 separate stores — caught independently by 3 reviewers. Plus Cursor target's `.cursor/hooks.json.j2` template never had a `postToolUse` block, so kairos's metrics.jsonl only ever recorded `stop` events (5 entries today, no per-call data).

**Scope:** narrow. No new features. Wire what already exists; fix what already broke; render what was forgotten.

**Decisions locked in (user-confirmed 2026-05-08):**
- Race fix split: append-only direct write for log-shaped stores (`episodic`, `tool_cascade`); `fcntl.flock` around read-modify-write for index-shaped stores (`semantic`, `profile`).
- Phase 12c (prod_name_guard wire): read tool history from `metrics.jsonl` (event=post_tool_use entries), pass last `window+1` entries to `scan_sequence`. No new tool-history schema.
- Phase 12f (2-pass review wire): the standalone `two_pass_review.py` module IS the runtime — `review.md.j2` invokes it via `python -m harness_maker.two_pass_review` rather than re-implementing it in prose. Keeps Python contract authoritative.
- Cursor postToolUse: render the block even though Cursor doesn't surface tokens. Tool-call counts + tool_name still useful for "what ran" timeline; dashboards can compute cost from session-level estimates instead.

**Estimated impact:** unblocks 0.7.0. Adds ~150 LoC across 4 phases. No new dependencies. Existing tests must still pass.

## 📚 Prior Work

- **PLAN-harness-gap-cot-2026-05** — parent. Phases 0-11 implemented but 5 orphaned + 4 races.
- **REVIEW-harness-gap-cot-2026-05-2026-05-08** — 4 reviewers' raw findings; auto-fix declined for architectural reasons.
- **kairos forensic 2026-05-08** (session memory) — established `.cursor/hooks.json` is read natively by Cursor IDE; this PLAN extends that file's render to include `postToolUse`.
- **CLAUDE.md "Atomic file write" + REVIEW M3 0.6.2** — the policy that the race fix must respect.

## 🏗️ Phase Plan

### Phase 12a — Race Fix (P0×4 + Cursor postToolUse)

**Scope (in):**
- `src/harness_maker/memory/episodic.py` — replace `mkstemp + read_text + replace` block (lines 47-62) with direct `open(target, "a")` JSONL append.
- `src/harness_maker/tool_cascade.py` — replace `_log_failure` body (lines 84-99) with same direct-append pattern.
- `src/harness_maker/memory/semantic.py` — wrap `_read_index + _write_index` in `_write` with `fcntl.flock(fd, LOCK_EX)` on a sentinel lock file (`<index>.lock`). Cross-platform: `fcntl` on POSIX, fall back to no-op + log warning on Windows (CLAUDE.md notes WSL2/NTFS Edit hazard but doesn't ban fcntl).
- `src/harness_maker/memory/profile.py` — same flock pattern around `set/_read/_write` block.
- `src/harness_maker/templates/cursor/hooks.json.j2` — add `postToolUse` block mirroring Claude Code PostToolUse → `harness_maker.telemetry`. Note in template comment that Cursor doesn't surface tokens (cost_usd will be null) but tool-call counts still useful.
- New tests: `tests/unit/test_memory/test_episodic.py` add `test_concurrent_append_no_loss` — spawn 2 processes writing 50 entries each, verify file has 100 lines after `wait`. Same for `tool_cascade.py`. For `semantic.py`/`profile.py` add `test_concurrent_set_no_lost_update` — 2 processes set different keys, verify both keys present.
- Snapshot regen for `tests/snapshot/*-cursor-*.expected.yaml` if affected.

**Scope (out):** D1-D5 wiring (Phase 12b/c), 2-pass review wiring (Phase 12d).

**Exit criterion:**
```
uv run pytest tests/unit/test_memory tests/unit/test_tool_cascade.py -v
```
all pass + 4 new concurrency tests pass + `git diff src/harness_maker/templates/cursor/hooks.json.j2` shows postToolUse block + manual: render kairos's `.cursor/hooks.json` and verify postToolUse line present.

**Risk:** medium. `fcntl.flock` portability — Windows path needs the no-op fallback. Snapshot regen could surprise.

**Rollback:** revert the 5 file edits + 1 template edit. No PLAN dependency on later phases for these.

### Phase 12b — D1: prod_name_guard wired into security_scanner

**Scope (in):**
- `src/harness_maker/security_scanner.py` — import `scan_sequence` from `prod_name_guard`. Inside `scan_all`, read `<target_dir>/.claude/observability/metrics.jsonl` (last 50 entries with `event=post_tool_use`), build `tool_calls: list[dict]` from `tool_name` + `tool_input` fields, pass to `scan_sequence(tool_calls, window=5)`. Append findings.
- `src/harness_maker/secscan/prod_name_guard.py` — verify `scan_sequence` accepts the schema we extract; adjust if not.
- `tests/unit/test_security_scanner.py` — add `test_prod_name_guard_wired` — drop a metrics.jsonl with Read(prod.db)→Write(prod.db) tool calls, verify `scan_all` returns a finding with `category="prod_name_guard"`.

**Scope (out):** trajectory-monitor agent (12c), 2-pass review (12d), spec-stage wiring (12e).

**Exit criterion:**
```
uv run pytest tests/unit/test_security_scanner.py -v
```
new test passes + `grep -n "prod_name_guard" src/harness_maker/security_scanner.py` shows real import + call (not just docstring).

**Risk:** low. `scan_sequence` already exists; only wiring + a small fixture.

**Rollback:** revert `security_scanner.py` changes; orphan state matches pre-12b.

### Phase 12c — D2/D3: trajectory-monitor surface + scope-aware consensus

**Scope (in):**
- `src/harness_maker/templates/skills/trajectory-monitor/SKILL.md.j2` (new) — Anthropic skill spec. Triggers when stage output is being summarized; calls `python -m harness_maker.drift_monitor` with current stage output + auto-resolved baseline.
- `src/harness_maker/templates/agents/trajectory-monitor.md.j2` (new) — sub-agent definition. Permissions: `Read`, `Bash(uv run:*)`, `Bash(git diff:*)`. No Write/Edit.
- `src/harness_maker/templates/agents/consensus-arbiter.md.j2` — modify procedure section to call `harness_maker.conditional_router.scope_aware_consensus` instead of strict cross-check; add scope-exempt-finding handling clause.
- All 5 reviewer agent templates (`code-reviewer.md.j2`, `security-reviewer.md.j2`, `performance-reviewer.md.j2`, `concurrency-reviewer.md.j2`, `ux-reviewer.md.j2`) — add `review_scope: [code|security|performance|concurrency|ux]` field to frontmatter.
- `src/harness_maker/drift_monitor.py` — add `__main__` block + `if __name__ == "__main__": main()` so `python -m harness_maker.drift_monitor` works (currently no CLI entry).
- Snapshot regen.

**Scope (out):** wire trajectory-monitor into a specific stage's prompt — that's a follow-up if user wants drift fired automatically. For now: skill exists, can be invoked on demand.

**Exit criterion:**
```
uv run pytest tests/unit/test_consensus.py tests/unit/test_drift_monitor.py -v
ls src/harness_maker/templates/skills/trajectory-monitor/SKILL.md.j2
ls src/harness_maker/templates/agents/trajectory-monitor.md.j2
grep -l "review_scope:" src/harness_maker/templates/agents/*-reviewer.md.j2 | wc -l  # → 5
```

**Risk:** medium — frontmatter changes must not break renderer's parser. Run `uv run pytest tests/snapshot -v` to confirm.

**Rollback:** delete 2 new template files; revert reviewer frontmatter; revert consensus-arbiter prompt.

### Phase 12d — D4/D5: review.md.j2 + spec.md.j2 wiring

**Scope (in):**
- `src/harness_maker/templates/stages/review.md.j2` — insert a "## Step 3.5 — 2-pass redaction" sub-step between current Step 2 (drift gate) and Step 3 (parallel reviewer invocation). Sub-step logic:
  1. Compute `pass1_context = redact_metadata(full_context)` via `python -m harness_maker.two_pass_review redact <stdin>`.
  2. Send Pass 1 prompt with redacted context to all reviewers.
  3. Send Pass 2 prompt with full context, asking reviewers to review their own Pass 1 findings.
  4. Merge with `merge_passes` filtering out `invalidated_by_context`.
- `src/harness_maker/two_pass_review.py` — fix `merge_passes` to only return `pass2_findings` (drop `invalidated_by_context` from the return list — addresses CP10 bug).
- Add `__main__` CLI for `python -m harness_maker.two_pass_review redact|build_pass1|build_pass2`.
- `src/harness_maker/templates/stages/spec.md.j2` — insert "## Step 3.5 — Spec quality gate" after spec authoring step. Calls `python -m harness_maker.spec_quality eval <spec_path>`. In `dev_mode == "spec-driven"` and score < threshold → BLOCK with explicit failure message + concrete improvement bullets. In task-driven → WARN only (PLAN ADR-006).
- `src/harness_maker/spec_quality.py` — add `__main__` CLI; fix bare `except` (CP9) to `except Exception as exc: logger.warning(...)`.
- Snapshot regen for review/spec stage outputs.

**Scope (out):** Cursor IDE-side spec gate (the rendered `.cursor/commands/hm-spec.md` already calls the same template — no separate work).

**Exit criterion:**
```
uv run pytest tests/unit/test_2pass_review.py tests/unit/test_spec_quality.py tests/snapshot -v
grep -n "two_pass_review\|2-pass" src/harness_maker/templates/stages/review.md.j2  # ≥1 hit
grep -n "spec_quality\|evaluate_spec" src/harness_maker/templates/stages/spec.md.j2  # ≥1 hit
```

**Risk:** medium. Modifying review/spec stage prompts ripples through every snapshot test.

**Rollback:** revert template + `two_pass_review.py` + `spec_quality.py` edits. Phases 12a/b/c stand alone.

## 🧪 Testing Strategy

| Phase | Unit | Integration | Manual |
|-------|------|-------------|--------|
| 12a | test_memory + test_tool_cascade + 4 new concurrency tests | — | render & verify `.cursor/hooks.json` shows postToolUse |
| 12b | test_security_scanner + 1 new wiring test | tests/integration/test_secscan_e2e if exists | — |
| 12c | test_consensus + test_drift_monitor + snapshot | — | render & inspect 2 new template files |
| 12d | test_2pass_review + test_spec_quality + snapshot | — | render & inspect review.md / spec.md |

All phases must pass `ruff check`, `ruff format --check`, `mypy --strict` before phase exit.

## ⚠️ Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| `fcntl.flock` Windows path | Medium | `import fcntl` inside try/except ImportError; fall back to no-op + warning |
| Snapshot avalanche on review.md.j2 / spec.md.j2 edits | High | Re-run `uv run pytest tests/snapshot -v --snapshot-update` once after Phase 12d, manual diff review |
| Cursor `postToolUse` may not be supported by older Cursor (<2.4) | Low | Template comment notes "Cursor 2.4+"; older Cursor will silently skip unknown event |
| 2-pass adds 2× LLM cost per review | Medium | ADR for default-on-or-opt-in; lock to opt-in for Side preset, on for Production |
| flock contention on hot semantic write | Low | Lock is held briefly (microseconds); contention only matters at >1000 writes/sec |

## ✅ Success Criteria

- [ ] Phase 12a: `test_concurrent_append_no_loss` x2 + `test_concurrent_set_no_lost_update` x2 pass
- [ ] Phase 12a: `.cursor/hooks.json` rendered output shows `postToolUse` block
- [ ] Phase 12b: `scan_all` on a target with prod-sequence metrics returns ≥1 finding with `category="prod_name_guard"`
- [ ] Phase 12c: 2 new template files exist + 5 reviewer templates have `review_scope` frontmatter + `python -m harness_maker.drift_monitor` runs
- [ ] Phase 12d: review.md.j2 invokes 2-pass; spec.md.j2 invokes evaluate_spec; bare `except` in spec_quality is logged
- [ ] Full `uv run pytest -q` passes
- [ ] `ruff check` + `ruff format --check` + `mypy --strict` clean
- [ ] No P0 finding in re-run of `/hm:review` on the wiring commit

## Out of Scope (explicit Non-Goals)

- New reliability features beyond what 0.7.0 PLAN already proposed.
- Deeper consensus rule (e.g., domain-expert weighting). 0.7.0's scope-aware fix is the ceiling.
- Migration tool for old `metrics.jsonl` schema — the existing format is forward-compat already.
- ux-reviewer changes — wasn't part of the original 12-phase scope; leave alone.
- Manual fixes for the P2 findings (CP11-CP18) and the manual-only 12 — those go to a 0.7.1 cleanup PLAN.

## 🔍 Plan Validation

Self-review (no plan-validator invoked — this is a fixed-scope addendum, not a discovery PLAN):
- All 5 drift findings (D1-D5) mapped to a phase ✓
- All 4 P0 races (CP1-CP4) mapped to Phase 12a ✓
- Cursor postToolUse mapped to Phase 12a ✓
- CP9 (spec_quality bare except) folded into Phase 12d ✓
- CP10 (merge_passes invalidated bug) folded into Phase 12d ✓
- CP8 (hallucination dead `_is_guarded_import`) — not in scope; trivial 3-line delete, do as part of the wrapup commit
- Race-fix strategy locked: append-only for logs, flock for indices ✓
- No new dependencies ✓
