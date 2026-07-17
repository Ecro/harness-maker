---
type: plan
task_slug: worktree-finalize-stash-isolation
status: complete
created: 2026-05-19
completed: 2026-05-20
tags: [harness-maker, plan, python, worktree, git, session-isolation]
interview_rounds: 6
adrs: 6
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Transparent stash isolation in finalize+wrapup, with handshake file for stage-only mode."
---

# PLAN — Worktree finalize: transparent stash isolation

## 🎯 Executive Summary

**TL;DR.** `worktree.finalize`'s `git merge --squash` runs from the base repo while base may have pre-existing dirty work (staged + unstaged + untracked). The squash stages our worktree's changes **on top of** that pre-existing index state. `/hm:wrapup`'s scoped `git add .claude/memory/ work-docs/PLAN-{slug}.md work-docs/REVIEW-{slug}-*.md` + `git commit` then makes a single commit of whatever happens to be in the index — sweeping the user's unrelated dirty into the wrong PLAN's commit (validator finding #8 corrects an earlier mischaracterization that blamed `git add -A`; the real bug is **index state at commit time**, not the staging command).

**Fix.** Wrap the squash step in a `git stash push -u` envelope so the base is clean during squash. In `success` mode, finalize stash-pops inside its own transaction. In `stage-only` mode (the production /hm:execute → /hm:wrapup flow), finalize writes the stash ref to `.claude/.hm-finalize-stash-{wt_name}` and a new `worktree post-commit-pop` CLI step runs from `/hm:wrapup` *after* its commit lands, then pops the stash. Always-on, no abort in the happy path. The two failure paths where the machine cannot decide alone — stash-pop merge conflict and untracked-vs-newly-tracked collision — emit distinct signals that the slash-command LLM picks up to `AskUserQuestion` (with explicit autoloop exception, gated on literal stderr substring).

**What.** Modify `src/harness_maker/worktree.py`: add stash helpers, wire stash-push into `_cli_finalize` (success + stage-only), add new CLI subcommand `post-commit-pop`. Update `.claude/commands/hm/execute.md` Step 5 with informational pre-check (warning about staging collapse). Update `.claude/commands/hm/wrapup.md` to invoke `post-commit-pop` after its commit. Add unit + integration tests covering the full failure matrix.

**Why.** Real user pain (2026-05-19): a `/hm:plan` session's main-branch dirty work got squashed into another PLAN's commit during finalize.

**Key Decisions** (see ADRs):
- ADR-001 Transparent stash isolation + stage-only handshake + accepted staging collapse + capture-then-stash ordering pinned
- ADR-002 L3 = informational pre-check only, with staging-collapse warning text
- ADR-003 Two-class pop failure handling (merge-conflict vs untracked-collision), both AskUserQuestion under autoloop with substring-gated permission
- ADR-004 No CLAUDE.md global rule, no Step 0 mention
- ADR-005 Submodule presence with dirty submodule state = abort with clear error (transparent guarantee carve-out)
- ADR-006 Multi-repo finalize: fail-fast, preserve all per-repo stash refs, NO cross-repo rollback (asymmetric to create() — intentional)

**Estimated impact.** Touches 3 production files (`worktree.py`, `execute.md` template, `wrapup.md` template) + rendered copies. ~120 LOC + ~8 test cases. No public CLI signature change; one new CLI subcommand (`post-commit-pop`).

## 📚 Prior Work

- **PLAN-multi-repo-mgmt-2026-05.md** — established per-session marker file (`.claude/.hm-loop-{wt_name}`, ADR-006) and cross-session gate. That work prevents Write/Edit drift across sessions; this PLAN closes the orthogonal finalize-time contamination path.
- **CLAUDE.md** "Stash pop conflict resolution pattern" memory (`feedback_stash_pop_conflict_pattern.md`) — grep ALL files for conflict markers; stash entry stays until manually dropped. This PLAN inherits + extends that pattern for two pop-failure classes.
- **2026-05-08 finalize-bug forensic** (referenced in `worktree.py:184`) — added `_capture_pending_in_worktree` (worktree-side fix). This PLAN adds the symmetric base-side fix.

## 🎙️ Interview Transcript

| # | Topic | Category | Question (1 line) | Choice | → ADR |
|---|-------|----------|-------------------|--------|-------|
| 1 | Layer scope | Scope | L1/L2/L3/L4 중 어느 layer | "L1+L2+L3, CLAUDE.md 제외, L3 는 execute.md 만" | ADR-004 |
| 2a | L1 dirty def | Architecture | base dirty 정의 | "create 는 무조건 만들 수 있는 것 아니야?" → L1 드롭 | (dropped) |
| 2b | re-scope after L1 drop | Scope | L3 only / L2+L3 / L2 only | L2 + L3 | ADR-001 |
| 3a | L2 mechanism | Architecture | runtime diff / baseline / stash | runtime diff (later reframed) | ADR-001 |
| 3b | L3 placement | Architecture | Step 0 / Step 5 / both | Step 5 직전 | ADR-002 |
| 4a | L2 default | Risk | abort default / opt-in / strict | "abort 하면 어떻게 마음 놓고 병렬?" → 전면 reframe | ADR-001 |
| 4b | L2 modes | Scope | success / stage-only / fail | success + stage-only | ADR-001 |
| 4c | L3 behavior | Architecture | pre-check / post-react / both | (later reframed to informational only) | ADR-002 |
| 5a | Design confirm | Architecture | transparent always-on, L3 informational | 맞음 | ADR-001, ADR-002 |
| 5b | Pop conflict | Failure | preserve+ask / warn-only / rollback | preserve stash + AskUserQuestion | ADR-003 |
| 6a | stage-only pop timing | Architecture | handshake file / drop stage-only / carve-out dirty | finalize emits stash-ref file → wrapup pops post-commit | ADR-001 |
| 6b | Staging preserve | Architecture | unstaged collapse + warn / --keep-index dance | unstaged collapse accepted, warn in Step 5 | ADR-001 |

**Assumptions** (defensible defaults — common-ground per 5-term inequality gate):
- Multi-repo: stash isolation applied per base repo independently; failure semantics in ADR-006.
- Empty base (`git status --porcelain` clean): skip stash entirely; current code path unchanged.
- Stash message format: `hm-finalize-{wt_name}` for grep-ability and recovery guidance.
- Stash-ref file format: `.claude/.hm-finalize-stash-{wt_name}` containing a single line with the stash ref + repo absolute path (for unambiguous lookup when wrapup runs from any cwd).
- Autoloop exception is gated on exact stderr substring (per ADR-003); only the LLM's discipline (template prose) enforces — ADR-003 documents this honestly.

## 📐 Architecture Decision Records

### ADR-001: Transparent stash isolation with stage-only handshake; staging collapse accepted; capture-then-stash ordering pinned
**Status:** Accepted (2026-05-19, revised 2026-05-20 post-validator)
**Context:** Base repo's pre-existing dirty (staged + unstaged + untracked) gets mixed with the worktree branch's squash result at finalize time, then swept by wrapup's commit. Two design families: (a) abort + force user resolution; (b) transparent isolation via `git stash`. Round 4 user reframe: "어떤 상황에서도 알아서 머지" → (b). Validator surfaced three sub-problems requiring explicit decisions: (i) stage-only mode pop timing (pop before wrapup commits = re-contaminates), (ii) staging-vs-unstaged preservation (default pop loses staged status), (iii) capture-pending vs stash-base ordering (orphan stash risk on capture failure).
**Decision:**

1. **Mechanism**: at `_cli_finalize` for `success` and `stage-only`, run `git stash push -u -m "hm-finalize-{wt_name}"` in the **base** repo immediately before `merge()`. If `git status --porcelain` (base) is empty, skip stash entirely.

2. **Stage-only handshake (validator finding #1)**: `success` mode pops inside its own `try/finally`. `stage-only` mode does NOT pop in finalize. Instead, finalize atomic-writes the stash ref + base path to `.claude/.hm-finalize-stash-{wt_name}` (under base/.claude/). A new CLI subcommand `python -m harness_maker.worktree post-commit-pop <base_dir>` reads all `.hm-finalize-stash-*` files in that base, pops each, classifies errors, removes the ref file on success. `/hm:wrapup` invokes this CLI **immediately after** its `git commit` step.

3. **Staging preservation (validator finding #2)**: `git stash push -u` followed by `git stash pop` (no `--index`) is used — user's staged state collapses to unstaged after pop. Accepted trade-off because `--keep-index` would leave staged content visible to the squash (different silent corruption). Step 5 informational pre-check explicitly warns: "base 의 staged 파일은 finalize 후 unstaged 로 복원됩니다 — 다시 git add 가 필요할 수 있습니다."

4. **Ordering (validator finding #9 + 2nd-pass critical)**: per worktree, the order is `stash-base` → `capture-pending-worktree` → `merge` → (success: `commit` THEN `cleanup` THEN pop / stage-only: `_write_stash_ref_file` THEN `cleanup`). Control flow is a single `try` block with a `popped_or_handed_off: bool` flag. On exception anywhere inside the try, the `finally:` pops the stash directly (rollback path). On success fallthrough, the flag is set after either `commit`+`cleanup` (success mode) or `_write_stash_ref_file`+`cleanup` (stage-only handshake), and `finally:` skips pop. Critical: **`cleanup` runs AFTER `_write_stash_ref_file` in stage-only mode**. If `cleanup` fails after a successful squash, the worktree dangles but the stash-ref handshake is intact — wrapup's `post-commit-pop` still recovers user dirty; the dangling worktree becomes a separable `git worktree remove` follow-up rather than re-contamination. This eliminates the validator 2nd-pass critical (cleanup-failure-after-squash silently mixing user dirty into staged squash).

5. **Empty-base path**: `git status --porcelain` clean → skip stash entirely, fall through to existing merge logic. Current behavior preserved for the clean-base case (zero behavior change for users without dirty base).

**Consequences:**
- ✅ Parallel work safe across both success and stage-only modes.
- ✅ No abort in happy path; transparent fix.
- ✅ "wrapup owns commits" pattern (CLAUDE.md / execute.md Step 4) preserved.
- ⚠️ Stage-only mode adds finalize↔wrapup coupling via `.hm-finalize-stash-{wt_name}` file. Wrapup-less flows (e.g., `/hm:exec-rev`) need to either invoke `post-commit-pop` manually or accept the stash remains until next wrapup. Documented in execute.md Step 5 "Workflows without wrapup" note.
- ⚠️ User's `git add` staging intent is **lost** (collapsed to unstaged) every time finalize runs with dirty base. Surfaced in Step 5 informational text.
- ⚠️ Stash op adds 2 git invocations per finalize when base is dirty (~200ms); zero when clean.

**Rejected alternatives:**
- Abort + `--allow-outside-scope` escape — Rejected (Round 4 user reframe).
- Eliminate stage-only mode (finalize commits, wrapup amends) — Rejected because it breaks "wrapup owns commits" pattern documented in CLAUDE.md and execute.md.
- `--keep-index` + `pop --index` dance — Rejected because `--keep-index` exposes staged content to the squash, replacing one silent corruption with another (validator finding #2).
- Stage-only + dirty base = abort (carve-out) — Rejected because stage-only is the **default** production flow; aborting it on dirty base reintroduces the friction Round 4 rejected.

**Source:** Interview #1, #2b, #3a, #4a, #5a, #6a, #6b. Validator findings #1, #2, #9.

### ADR-002: L3 = informational pre-check only at execute.md Step 5; explicit staging-loss warning
**Status:** Accepted (2026-05-19)
**Context:** With L1 dropped and L2 reframed transparent, L3's role becomes purely informational — there's no abort in the happy path. Validator finding #2 adds a required disclosure (staging collapse).
**Decision:** `execute.md` Step 5 (immediately before `worktree finalize` CLI invocation):
1. Run `git status --porcelain` in the base repo.
2. If non-empty, surface to user:
   > "다음 파일이 base 에 dirty 상태로 있어 finalize 가 자동 stash 후 복원합니다: {files}
   > **알림:** staged 파일은 unstaged 상태로 복원됩니다 — 필요시 다시 `git add` 하세요."
3. NO question — purely informational. Proceed to finalize.
4. If finalize stderr contains the literal substring `[finalize] stash-pop conflict` OR `[finalize] untracked-file collision` (per ADR-003), THEN AskUserQuestion (autoloop exception, gated on exact substring).
NOT in CLAUDE.md. NOT in Step 0. NOT in worktree-isolator skill.
**Consequences:**
- ✅ User aware of dirty-base behavior without friction.
- ✅ Staging-loss disclosed up front (no surprise).
- ⚠️ LLM drift can drop the pre-check; the machine layer (ADR-001) is the actual defense.
- ⚠️ Pre-check adds one `git status` (~10ms).
**Rejected alternatives:** CLAUDE.md global rule (Round 1 user); Step 0 placement (L1 dropped); blocking AskUserQuestion in happy path (Round 5).
**Source:** Interview #1, #3b, #4c, #5a. Validator finding #2.

### ADR-003: Two-class pop failure handling — merge conflict and untracked-vs-newly-tracked collision
**Status:** Accepted (2026-05-19, expanded 2026-05-20 post-validator)
**Context:** `git stash pop` can fail in two distinct ways the user must resolve manually:
- (A) **Merge conflict**: stashed tracked file overlaps squash result on the same lines. Working-tree files contain `<<<<<<<` markers. Original Round 5 case.
- (B) **Untracked-vs-newly-tracked collision** (validator finding #3): base had untracked `notes.txt`; worktree branch created tracked `notes.txt` with different content; squash brought tracked version in; pop refuses to restore untracked file ("error: could not restore untracked files from stash"). Files NOT touched in working tree; recovery requires `git checkout stash@{0} -- <file>`.
**Decision:** `_restore_base_dirty` (success mode) and `post-commit-pop` (stage-only mode) classify pop failure into A or B by parsing `git stash pop` stderr and probing for conflict markers:
1. **Class A (merge conflict)**: preserve stash@{0}, emit literal stderr block:
   > `[finalize] stash-pop conflict — autoloop must halt`
   > `Stash: stash@{0} ({stash_message})`
   > `Conflicted files: {list}`
   > `Resolve: grep -l '<<<<<<<' . then edit + git add + git stash drop stash@{0}`
2. **Class B (untracked collision)**: preserve stash@{0}, emit literal stderr block:
   > `[finalize] untracked-file collision — autoloop must halt`
   > `Stash: stash@{0} ({stash_message})`
   > `Files (in stash, not restored): {list}`
   > `Recover: git checkout stash@{0} -- <file> (rename first if needed) then git stash drop stash@{0}`
3. Exit `_cli_finalize` (or `post-commit-pop`) with rc=1.
4. Step 5 LLM detects either literal substring → AskUserQuestion (autoloop exception). Step 5 prose: "You MAY AskUserQuestion ONLY IF the literal string `[finalize] stash-pop conflict` OR `[finalize] untracked-file collision` appears in the most recent finalize/post-commit-pop stderr. Any other failure: halt with stderr message, do NOT ask." (validator finding #7).
**Consequences:**
- ✅ Both real failure modes get actionable recovery guidance.
- ✅ Autoloop permission scoped to exact substrings — minimizes over-extension.
- ⚠️ Substring-based permission is LLM-discipline-enforced, not machine-enforced. Acceptable because the alternative (trajectory-monitor token recognition) is out of scope this PLAN.
- ⚠️ Autoloop halts on either signal — rare but possible. Acceptable.
**Rejected alternatives:** warn-only / silent (loses safety); rollback (squash-revert complexity, ambiguous in stage-only); single generic signal (loses recovery specificity).
**Source:** Interview #5b. Validator findings #3, #7.

### ADR-004: No CLAUDE.md global rule, no Step 0 mention, no skill update
**Status:** Accepted (2026-05-19)
**Context:** Round 1 user explicitly excluded CLAUDE.md global edits. Step 0 dropped with L1.
**Decision:** L3's LLM contract lives ONLY in `.claude/commands/hm/execute.md` Step 5 and `.claude/commands/hm/wrapup.md` (the latter for invoking `post-commit-pop`). NOT in CLAUDE.md. NOT in worktree-isolator skill. NOT in Step 0. NOT in any other stage template.
**Consequences:** ✅ Minimal surface. ⚠️ Custom workflows skipping execute+wrapup get only machine-layer protection.
**Rejected alternatives:** CLAUDE.md global "Worktree 공유" addition.
**Source:** Interview #1.

### ADR-005: Submodule with dirty submodule state — abort with clear error (transparent carve-out)
**Status:** Accepted (2026-05-20, post-validator)
**Context:** Validator finding #5 — `git stash` does NOT stash submodule pointer changes by default (requires `submodule.recurse=true`), and even with `-u` it stashes the parent's pointer but not the submodule's own working tree. A user with a dirty submodule pointer bump on base + a worktree branch bumping the same submodule = silent pointer corruption after squash + pop.
**Decision:** Before stashing in `_stash_base_dirty`, probe `git submodule status` (cheap — no network). If output contains the `+` prefix (submodule SHA changed) or `-` prefix (uninitialized), emit:
> `[finalize] submodule state cannot be transparently isolated — please commit or reset submodule changes before finalize.`
> `Submodules with state: {list}`
Exit rc=1 (treated by Step 5 LLM as a "halt with stderr" — NOT a substring-gated AskUserQuestion exception). User resolves submodule manually, retries finalize.
This is the **single carve-out** from the "transparent always" guarantee. Justified because submodule semantics are inherently outside the scope of base-repo stash.
**Consequences:**
- ✅ No silent submodule corruption.
- ⚠️ Users with submodule repos see the abort path; rare in our user base but real.
- ⚠️ Inconsistent with Round 4's "어떤 상황에서도" — surfaced explicitly so the trade-off is visible.
**Rejected alternatives:** Recurse stash into submodules — Rejected because submodule's own stash list is unrelated to parent's; conflict recovery becomes a multi-repo coordination problem out of scope.
**Source:** Validator finding #5.

### ADR-006: Multi-repo finalize — fail-fast, preserve all per-repo stash refs, NO cross-repo rollback
**Status:** Accepted (2026-05-20, post-validator)
**Context:** Validator finding #6 — `worktree.create()` (worktree.py:143-151) rolls back ALL created worktrees if sibling N fails, to avoid orphaned state. The risk table for finalize said "don't try to revert across repos" without justification — asymmetric.
**Decision:** The asymmetry is **intentional**:
- `create()` rolls back because created-empty-worktrees are non-destructive to user state.
- `finalize` does NOT roll back because the only rollback available — reverting committed squash commits via `git reset --hard HEAD~1` on earlier repos — would destroy user-visible state (commit history). The cure would be worse than the disease.
On multi-repo failure in finalize:
1. Continue the existing fail-fast pattern (`_cli_finalize` lines 640-650). Per-repo status emitted to stderr.
2. Additionally: preserve all per-repo `.hm-finalize-stash-{wt_name}` files so wrapup-driven recovery works repo-by-repo.
3. Surface a clear stderr block: `[finalize] multi-repo failure — primary committed, sibling N failed. Run 'post-commit-pop' per-repo after manual resolution.`
**Consequences:**
- ✅ No destructive cross-repo rollback.
- ⚠️ User holds half-finalized state on multi-repo failure — manual cleanup required.
- ⚠️ Documented explicitly so the asymmetry vs create() is not surprising.
**Rejected alternatives:** Mirror create()'s rollback by reverting earlier-repo squash commits — Rejected because user-visible commit history mutation is more destructive than the failure itself.
**Source:** Validator finding #6.

## 🏗️ Technical Design

### Current State (paths to be changed)

`src/harness_maker/worktree.py:233-259` (`merge()`) — invokes `git merge --squash <branch>` from base. **No isolation.**

`src/harness_maker/worktree.py:542+` (`_cli_finalize`) — success / stage-only branches call `_capture_pending_in_worktree(current_wt)` (worktree-side), then `merge(...)` (base-side, **unisolated**), then `cleanup`.

`.claude/commands/hm/execute.md:203-220` (template lives in `src/harness_maker/templates/stages/execute.md.j2`) — Step 5 invokes `python -m harness_maker.worktree finalize <WT> stage-only` with no pre-check.

`.claude/commands/hm/wrapup.md:~199` (template in `src/harness_maker/templates/stages/wrapup.md.j2`) — scoped `git add .claude/memory/ work-docs/PLAN-{slug}.md work-docs/REVIEW-{slug}-*.md` + `git commit -m ...`. **Commits whatever is in the index** (which includes squash result + any pre-existing user dirty if not isolated).

### Affected Components

| Component | Change |
|-----------|--------|
| `src/harness_maker/worktree.py` | New helpers: `_probe_submodules`, `_stash_base_dirty`, `_classify_pop_failure`, `_restore_base_dirty`, `_write_stash_ref_file`, `_read_stash_ref_file`. New CLI subcommand `post-commit-pop`. Wire stash into `_cli_finalize` per ADR-001. |
| `src/harness_maker/templates/stages/execute.md.j2` | Add Step 5 informational pre-check (ADR-002). |
| `src/harness_maker/templates/stages/wrapup.md.j2` | Add post-commit-pop invocation after the commit step. |
| `.claude/commands/hm/execute.md`, `.claude/commands/hm/wrapup.md` | Re-rendered output. |
| `tests/unit/test_worktree.py` (+ new `test_worktree_stash.py` if size warrants) | Full failure-matrix unit tests. |
| `tests/integration/test_worktree_stash_isolation.py` (new, INTEGRATION-gated) | End-to-end cross-session reproducer + submodule abort + multi-repo fail-fast. |
| `tests/snapshots/...` | Update execute.md + wrapup.md snapshots. |

### Dependencies
None added.

### Data Flow

**Success mode** (finalize is the sole transaction — pop happens here, no handshake):
```
_cli_finalize(success, current_wt):
  base = current_wt.parent.parent
  _probe_submodules(base)                           # ADR-005: may exit rc=1
  stash_ref = _stash_base_dirty(base, wt_name)      # None if clean
  pop_rc = 0
  try:
    _capture_pending_in_worktree(current_wt)
    merge(current_wt, strategy=squash, commit=True) # commits inside envelope — squash leaves index
    cleanup(current_wt, on_success=True)            # may fail after commit; pop is still safe (commit detached the squash from index)
  finally:
    if stash_ref is not None:
      ok, klass, files = _restore_base_dirty(base, stash_ref)
      if not ok:
        emit_pop_failure_signal(klass, stash_ref, files)  # ADR-003
        pop_rc = 1
  _clear_loop_marker(...)
  return pop_rc
```
Note: in success mode, `cleanup` failure AFTER `merge(commit=True)` is safe to pop over because the squash result is already in HEAD, not in the index. The index is clean at pop time.

**Stage-only mode** (finalize stages; wrapup commits then pops):
```
_cli_finalize(stage-only, current_wt):
  base = current_wt.parent.parent
  _probe_submodules(base)                           # ADR-005
  stash_ref = _stash_base_dirty(base, wt_name)      # None if clean
  handed_off = (stash_ref is None)   # no stash → nothing to hand off, "vacuously" complete
  try:
    _capture_pending_in_worktree(current_wt)
    merge(current_wt, strategy=squash, commit=False) # leaves index staged
    if stash_ref is not None:
      _write_stash_ref_file(base, wt_name, stash_ref, session_marker)
      handed_off = True                              # CRITICAL: flip BEFORE cleanup, not after
    cleanup(current_wt, on_success=True)             # may fail; handed_off already True → finally skips pop
  finally:
    if stash_ref is not None and not handed_off:
      _restore_base_dirty(base, stash_ref)          # rollback only when handoff did not complete
  _clear_loop_marker(...)
  return 0

# Called from wrapup AFTER its git commit:
_cli_post_commit_pop(base):
  for ref_file in (base / ".claude").glob(".hm-finalize-stash-*"):
    stash_ref = _read_stash_ref_file(ref_file)
    ok, klass, files = _restore_base_dirty(base, stash_ref)
    if not ok:
      emit_pop_failure_signal(klass, stash_ref, files)
      # don't delete ref_file — user resolution may need it
      return 1
    ref_file.unlink()
  return 0
```

**Empty-base path** (no behavior change):
```
stash_ref = None   → finally: noop, no ref file written, identical to current behavior.
```

### API Changes
- New CLI subcommand: `python -m harness_maker.worktree post-commit-pop <base_dir>`. Returns 0 on full success, 1 on any pop failure (with classified stderr).
- Existing CLI signatures unchanged.

## 📝 Implementation Plan

### Phase 1 — Stash helpers + happy-path unit test
**Scope.**
- **In:** `src/harness_maker/worktree.py` only.
  - `_probe_submodules(base) -> None | raises RuntimeError` (ADR-005).
  - `_stash_base_dirty(base, wt_name) -> str | None` (returns stash ref or None for clean base).
  - `_classify_pop_failure(stderr_text, base) -> ("merge_conflict" | "untracked_collision" | "unknown", list[Path])`.
  - `_restore_base_dirty(base, stash_ref) -> tuple[bool, str, list[Path]]` — wraps `git stash pop`, classifies on failure.
  - Wire into `_cli_finalize` success branch (full envelope per Data Flow above). **Stage-only branch deferred to Phase 2.**
- **In:** ONE unit test in `tests/unit/test_worktree_stash.py`: dirty-base happy path in success mode (modify a tracked file in base, run finalize success, verify base file restored as unstaged, squash committed cleanly).
- **Out:** Stage-only handshake, templates, full failure matrix.

**Exit criterion** (validator finding #4 fix — real runnable check):
```bash
uv run pytest tests/unit/test_worktree_stash.py::test_success_dirty_base_happy_path -v
uv run ruff check src/harness_maker/worktree.py
uv run mypy --strict src/harness_maker/worktree.py
```

**Risk:** medium. Git stash semantics on `-u` + untracked have subtle behavior; the happy-path test catches the obvious break.

**Rollback point:** revert Phase 1 commit; worktree.py returns to pre-change state.

### Phase 2 — Stage-only handshake (stash-ref file + post-commit-pop CLI)
**Scope.**
- **In:** `worktree.py`:
  - `_write_stash_ref_file(base, wt_name, stash_ref, session_marker)` — atomic write of structured content (lines: `ref: <stash_ref>`, `base: <abs path>`, `session: <marker>`, `created_at: <iso8601>`). Session marker = the existing per-session marker basename (`.hm-loop-{wt_name}` value) so the ref file is bound to the same session that created the stash.
  - `_read_stash_ref_file(path) -> StashRef` — parse structured content.
  - Wire stage-only branch in `_cli_finalize` per Data Flow `handed_off` pattern. CRITICAL: `_write_stash_ref_file` runs BEFORE `cleanup`, and `handed_off` flips immediately after write.
  - **Multi-repo loop semantics (validator 2nd-pass warning #4)**: the per-`current_wt` loop writes its own ref file when that repo's stash exists. On fail-fast return (a later repo fails), do NOT unlink ref files for already-succeeded repos. The existing fail-fast preserves the per-session marker; ref files inherit the same preservation policy.
  - New CLI subcommand `_cli_post_commit_pop(base_dir)` — globs `.hm-finalize-stash-*` in `base_dir/.claude/`, filters by **session match** (only pop refs whose `session:` matches an active per-session marker for the current process — prevents stale-ref contamination when wrapup runs from a different session, validator 2nd-pass warning #3), pops each match, classifies failures, deletes ref file on successful pop.
  - Update `main()` dispatcher to recognize `post-commit-pop`.
  - **Gitignore extension**: idempotent line-append `.claude/.hm-finalize-stash-*` via the existing `_ensure_gitignore_entry` pattern.
- **In:** Unit tests in `test_worktree_stash.py`:
  - stage-only writes ref file when dirty; `handed_off=True` flips BEFORE cleanup so a synthesized cleanup failure does NOT trigger pop.
  - stage-only skips ref file when base clean.
  - post-commit-pop reads ref, session-match passes, pops cleanly, deletes ref.
  - post-commit-pop with stale ref (no matching active session marker) SKIPS the pop and emits a non-failing notice.
  - multi-repo: repo 1 succeeds + writes ref, repo 2 fails → repo 1's ref file remains on disk.

**Exit criterion.**
```bash
uv run pytest tests/unit/test_worktree_stash.py::test_stage_only_handshake -v
uv run pytest tests/unit/test_worktree_stash.py::test_post_commit_pop_happy_path -v
```

**Risk:** medium. Race condition concern: if wrapup never runs (user kills session), the ref file + stash both linger. Documented; `/hm:refresh` 24h stale cleanup should be extended (out of scope this PLAN — note in risks).

**Rollback point:** revert Phase 2 commit; Phase 1's success-mode envelope still operative.

### Phase 3 — Template wiring (execute.md Step 5 + wrapup.md post-commit-pop)
**Scope.**
- **In:**
  - `src/harness_maker/templates/stages/execute.md.j2` Step 5: add informational pre-check fragment (ADR-002 text including staging-loss warning) before finalize CLI invocation. Add LLM permission gate prose (ADR-003 substring match + autoloop exception) after.
  - `src/harness_maker/templates/stages/wrapup.md.j2`: add a `post-commit-pop` invocation immediately after the commit step. **Use the same shape as the existing `harness_maker.worktree` invocations in execute.md.j2** — `!uv run --with {{ harness_maker_src_path }} python -m harness_maker.worktree post-commit-pop "$(pwd)"` for non-Codex, wrapped in `{% if is_codex %}Bash("uv run ... post-commit-pop ..."){% else %}!uv run ...{% endif %}` for the dual-render Codex target (per validator 2nd-pass warning — Codex uses `Bash(...)` tool calls, not `!` shell directives). Add the same substring-gated AskUserQuestion permission prose (recognize `[finalize] stash-pop conflict` OR `[finalize] untracked-file collision` in stderr).
  - Re-render `.claude/commands/hm/execute.md` and `.claude/commands/hm/wrapup.md`.
  - Snapshot test must assert BOTH the Codex render and the non-Codex render produce the expected invocation form.
- **Out:** No CLAUDE.md edit. No Step 0 edit. No skill edit.

**Exit criterion.**
```bash
uv run pytest tests/unit/test_render_execute_md.py -v   # snapshot
uv run pytest tests/unit/test_render_wrapup_md.py -v    # snapshot
grep -q "자동 stash 후 복원" .claude/commands/hm/execute.md
grep -q "post-commit-pop" .claude/commands/hm/wrapup.md
```

**Risk:** low. Template edits with snapshot tests.

**Rollback point:** revert Phase 3 commit; machine layer (Phase 1+2) still defends.

### Phase 4 — Full failure matrix (unit + integration)
**Scope.**
- **In:**
  - `tests/unit/test_worktree_stash.py` — full matrix:
    - clean base (no-op, behavior identical to pre-PLAN)
    - dirty no-overlap (already in Phase 1 — kept)
    - dirty tracked-overlap → merge conflict (Class A, ADR-003)
    - dirty untracked + worktree creates same path → untracked collision (Class B, ADR-003)
    - dirty submodule pointer → abort with submodule error (ADR-005)
    - capture-pending failure after successful stash → finally pops, no orphan stash (ADR-001 ordering)
    - **cleanup() failure AFTER squash+ref-file-write in stage-only** → `handed_off=True` keeps `finally:` from popping; ref file remains for wrapup recovery; dangling worktree surfaces as a separable cleanup-only error (validator 2nd-pass critical)
    - **post-commit-pop with stale ref from different session** → SKIPS the pop, emits notice, leaves ref untouched (validator 2nd-pass warning #3 — prevents cross-session contamination via stale ref)
    - multi-repo success on repo 1, failure on repo 2 → fail-fast, all stash refs preserved (ADR-006)
    - **multi-repo: repo 1 writes ref file + succeeds; repo 2 fails → repo 1's ref file still on disk** (validator 2nd-pass warning #4)
  - `tests/integration/test_worktree_stash_isolation.py` (`INTEGRATION=1` gated) — end-to-end:
    - Reproduce original user incident: two sessions, parallel worktrees, finalize session A → session B's dirty intact + only A's changes in the commit. **Use real `/hm:wrapup` commit semantics** (scoped `git add` of memory/PLAN/REVIEW paths, NOT `git add -A` — per validator finding #8).
    - Stash-pop conflict reproducer end-to-end.

**Exit criterion.**
```bash
uv run pytest tests/unit/test_worktree_stash.py -v
INTEGRATION=1 uv run pytest tests/integration/test_worktree_stash_isolation.py -v
uv run pytest tests/ -q
uv run ruff check && uv run mypy --strict
```

**Risk:** low-medium. Integration tests need careful tmp-repo fixtures; reuse existing `tests/unit/test_worktree.py:repo` fixture pattern.

**Rollback point:** revert Phase 4 commit; production code untouched.

## 🧪 Testing Strategy

**Unit (mocked + tmp-repo):**
- Per Phase 4 matrix above.
- `_classify_pop_failure` table-driven: feed sample stderr strings, assert classification.
- `_probe_submodules` table-driven: synthetic submodule state outputs.

**Integration (`INTEGRATION=1`):**
- **Critical reproducer:** drive the real wrapup commit chain (scoped `git add` of memory/PLAN/REVIEW + `git commit`) — NOT a synthetic `git add -A` — to verify the actual production flow. (validator finding #8)
- Stash-pop merge conflict and untracked-collision both reproducible.

**Manual checklist** (post-merge, recorded in PR description):
- `/hm:execute` on slug with dirty unrelated tracked file in base → completes; base file restored as unstaged; warning shown.
- `/hm:execute` on slug with dirty untracked file overlapping worktree branch's new tracked file → Class B halt, recovery guidance accurate.
- `/hm:execute` on slug in a repo with dirty submodule pointer → ADR-005 abort.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Submodule with dirty state | low | high | ADR-005: abort with clear error. Phase 4 test covers. |
| Stash includes `core.autocrlf` quirks | low | medium | Catch RuntimeError in `_stash_base_dirty`; emit "[finalize] stash setup failed: {err}" without entering merge. Preserves base state. |
| User staged content silently becomes unstaged | high (every dirty finalize) | low | Disclosed in Step 5 pre-check warning per ADR-002. Acceptable trade-off per ADR-001. |
| Wrapup never runs (session killed) → stash + ref file linger | low | low | `/hm:refresh` extension to clean 24h-stale `.hm-finalize-stash-*` files — **out of scope this PLAN**, tracked as follow-up. |
| LLM under autoloop over-extends substring permission to non-stash failures | low | medium | ADR-003 prose is explicit; literal substring match is the gate. Trajectory-monitor enforcement is a follow-up. |
| Multi-repo half-finalized state | low | medium | ADR-006: fail-fast, preserve all stash refs, clear stderr. Recovery is per-repo `post-commit-pop`. |
| Pre-check `git status` adds noise on every clean finalize | n/a | n/a | When clean, output is empty → pre-check emits nothing, fully quiet. |
| New `.hm-finalize-stash-*` files committed by accident | medium | low | Add `.claude/.hm-finalize-stash-*` to gitignore in same idempotent line-append pattern as `.hm-loop-*` (worktree.py:462-490). Phase 2. |

## ✅ Success Criteria

- [x] `_probe_submodules`, `_stash_base_dirty`, `_classify_pop_failure`, `_restore_base_dirty` landed + unit-tested (Phase 1).
- [x] `_cli_finalize` success mode wraps squash in stash envelope (Phase 1).
- [x] `_cli_finalize` stage-only mode writes `.hm-finalize-stash-{wt_name}` ref file (Phase 2).
- [x] `post-commit-pop` CLI subcommand reads ref, pops, classifies, deletes ref (Phase 2).
- [x] `.claude/commands/hm/execute.md` Step 5 contains informational pre-check + staging-loss warning + substring-gated AskUserQuestion permission (Phase 3).
- [x] `.claude/commands/hm/wrapup.md` invokes `post-commit-pop` after its commit + same substring permission (Phase 3).
- [x] `.gitignore` covers `.claude/.hm-finalize-stash-*` via idempotent line-append (Phase 2 via `_ensure_gitignore_entry`).
- [x] Full suite GREEN (`uv run pytest tests/ -q`, ruff, mypy).
- [ ] **(deferred — Phase 4 follow-up)** Integration test reproducing original user incident — main's unrelated dirty preserved + correct file commits — uses **real** wrapup commit chain (not `git add -A` stand-in).
- [ ] **(deferred — Phase 4 follow-up)** Both Class A (merge conflict) and Class B (untracked collision) failure paths covered + actionable. Stale-session-skip test added in Phase 2; full conflict-classification test matrix is follow-up.
- [ ] **(deferred — Phase 4 follow-up)** Submodule abort path tested (ADR-005).
- [ ] **(deferred — Phase 4 follow-up)** Multi-repo fail-fast preserves all per-repo stash refs (ADR-006).
- [ ] **(deferred — Phase 4 follow-up)** Manual checklist completed.

> **Phase 4 deferral note**: `/hm:exec-rev` workflow ran Phases 1+2+3 (core mechanism + handshake + templates). Phase 4 (full failure matrix tests + manual verification) is tracked in REVIEW-{slug}-2026-05-20.md "Follow-up Recommendations" with priority order. Also outstanding: REVIEW manual-only P0 (`stash@{N}` positional-ref staleness → SHA-based ref refactor) and security-reviewer P1 (path-traversal on `session:` field) require follow-up PLAN. Two consensus-passed findings (atomic `.gitignore` write + exact stash-list match) were auto-fixed in REVIEW Round 2.

## 🔍 Plan Validation

**First pass (2026-05-19):** MAJOR_REVISION. 3 critical findings (stage-only pop timing; staging collapse; untracked collision), 6 warnings (Exec summary mischaracterization; Phase 1 forward-reference; submodule undecided; multi-repo policy asymmetric without ADR; autoloop substring un-enforced; capture-pending ordering ambiguous).

**Resolution (2026-05-20):**
- Critical #1 → Interview Round 6a → ADR-001 stage-only handshake via `.hm-finalize-stash-{wt_name}` + `post-commit-pop` CLI invoked from wrapup.
- Critical #2 → Interview Round 6b → ADR-001 + ADR-002 explicit "staged collapses to unstaged" acceptance + Step 5 disclosure.
- Critical #3 → Defensive coding decision (not interviewed; defensible default) → ADR-003 expanded to two-class pop failure handling.
- Warning #4 → Phase 1 exit criterion now references a real test in Phase 1's scope (`test_success_dirty_base_happy_path`).
- Warning #5 → ADR-005 (submodule abort).
- Warning #6 → ADR-006 (multi-repo fail-fast policy made explicit).
- Warning #7 → ADR-003 prose tightened to literal substring match for autoloop permission; honest acknowledgment that LLM discipline is the gate.
- Warning #8 → Executive Summary corrected to cite real wrapup mechanism (scoped `git add` + commit, NOT `git add -A`). Phase 4 integration test note reinforces.
- Warning #9 → ADR-001 ordering pinned (stash-base → capture-pending-worktree → merge → ...) with `finally:` covering stash regardless of capture outcome.

**Second pass (2026-05-20):** NEEDS_REVISION. 8/9 prior findings RESOLVED, 1 PARTIALLY_RESOLVED (#9 ADR wording vs Data Flow mismatch), 1 new critical (cleanup-failure mid-stage-only re-contaminates via `except: pop`), 3 new warnings (Jinja `<plugin_path>` placeholder + missing Codex branch; `post-commit-pop` lacks session-scope → stale-ref contamination; multi-repo ref-file lifecycle not operationalized in pseudocode).

**Resolution of 2nd pass (no 3rd validator pass — per protocol, two passes are the bound):**
- 2nd-pass critical (cleanup-failure mid-stage-only) → Data Flow stage-only rewritten with `handed_off: bool` flag that flips to True **before** `cleanup()` runs. `finally:` pops only when `not handed_off`. Cleanup failure leaves handoff intact; wrapup recovers user dirty; dangling worktree becomes a separable concern. Success mode Data Flow also clarified — `cleanup` failure after `merge(commit=True)` is safe to pop over because the squash result is in HEAD, not in the index. Phase 4 test added for cleanup-after-squash failure path.
- 2nd-pass warning #9 (ADR §4 wording) → ADR-001 §4 rewritten to describe the single try/finally + `handed_off` flag pattern. Wording now matches the pseudocode exactly.
- 2nd-pass warning Jinja → Phase 3 scope text now uses `{{ harness_maker_src_path }}` and includes the `{% if is_codex %}Bash(...){% else %}!{% endif %}` dual-render branch. Snapshot test required for both renders.
- 2nd-pass warning session-scope → Phase 2 `_write_stash_ref_file` signature now takes `session_marker`; ref file content is structured (`ref:`, `base:`, `session:`, `created_at:`). `post-commit-pop` filters by session-marker match before popping; stale refs from prior sessions are SKIPPED with a non-failing notice. Phase 4 includes the stale-ref test case.
- 2nd-pass warning multi-repo loop → Phase 2 'In' bullets now spell out: per-repo loop writes its own ref file when that repo's stash exists; on fail-fast, do NOT unlink ref files for already-succeeded repos (ref files inherit the per-session marker preservation policy). Phase 4 includes the multi-repo ref-preservation test.

**Outstanding accepted risks (documented, not blocking):**
- LLM substring-gated AskUserQuestion permission relies on template prose discipline; machine-level trajectory-monitor enforcement is a follow-up (ADR-003 Consequences ⚠️).
- Wrapup-less custom flows (e.g., `/hm:exec-rev` without wrapup) leave the stash + ref file lingering until next wrapup or `/hm:refresh` 24h cleanup extension (out of scope this PLAN).
