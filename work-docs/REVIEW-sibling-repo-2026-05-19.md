---
type: review
task_slug: untested-trio-review-2026-05-19
feature: sibling_repo
status: complete
created: 2026-05-19
reviewer: Claude solo (ADR-002 amended)
plan: "[[PLAN-untested-trio-review-2026-05-19]]"
summary: "Deep review of sibling_repos surface across models, interview, synthesize, worktree, cli — multi-repo worktree creation and lifecycle."
---

# REVIEW — `sibling_repo` (harness-maker)

## Live-exercise preamble (paths + observations)

**Fixture:** `../claude-code-discord` (sibling repo, has untracked files — override accepted in PLAN Amendment A3)

**Multi-repo worktree creation:**
```
$ uv run python -m harness_maker.worktree create execute /home/noel/harness-maker
/home/noel/harness-maker/.worktrees/execute-20260519T1322Z
/home/noel/claude-code-discord/.worktrees/execute-20260519T1322Z-claude-code-discord
```
Both worktrees created. Untracked files in sibling did NOT block (override A3 validated empirically).

**Marker file:** `.claude/.hm-loop-execute-20260519T1322Z` contains both worktree paths, one per line. Atomic-written.

**execute.md sentinel:** `<!-- # SIBLING_WORKTREE_PATHS -->` present in `.claude/commands/hm/execute.md:67`. The `_execute_md_has_sentinel` check (substring `"SIBLING_WORKTREE_PATHS"` anywhere in file) returns True — but the substring lives inside a commented-out comment marker, not in the executable instruction body. This passed regardless.

**Finalize stage-only:**
```
$ uv run python -m harness_maker.worktree finalize <WT> stage-only
```
Cleanly merged both primary + sibling worktrees, no commit (per PLAN ADR + execute-stage Step 5 convention). `git status --porcelain` post-finalize → empty (no leftover stage). `git log` shows no new commit. Marker file removed.

**Cleanup of stragglers:** `.worktrees/` had a mystery `execute-20260519T1318Z` from an earlier abandoned session — same-named sibling worktree present in `../claude-code-discord/.worktrees/`. `finalize ... fail` cleaned them. Demonstrates: an interrupted/aborted session leaves orphans on BOTH primary and sibling sides. No background sweeper.

**Boundary live exercises:**
1. Absolute path: `HarnessConfig(sibling_repos=['/abs/path'])` → `ValidationError: sibling_repos must contain relative paths`. ✅
2. Tilde prefix: `HarnessConfig(sibling_repos=['~/path'])` → same rejection. ✅
3. **Parent traversal:** `HarnessConfig(sibling_repos=['../../../etc', '../../../../tmp/foo'])` → **accepted, no error.** Validator only checks for absolute/tilde, NOT `..` traversal.

## Methodology

Solo deep read + 7-item self-critique gate per ADR-002 (amended). Live exercise: multi-repo create + finalize stage-only + fail-mode cleanup + boundary validation. Read scope: `src/harness_maker/worktree.py` (676 LOC) end-to-end; `sibling_repos` Field × 2 in `models.py` (L580 / L734) + duplicated validators (L598-L611 / L740-L749); `interview.py` `_ask_sibling_repos` (L447-L467) + `answers_from_harness_yaml` (L737); `synthesize.py` (L643); `cli.py` `sibling_repos_override` (L166-L169, L282, L688-L691); `tests/unit/test_interview_sibling.py` (110 LOC) fully; `tests/unit/test_worktree_multi.py` first 80 LOC + grep-located key finalize tests. Cross-referenced `PLAN-multi-repo-mgmt-2026-05.md` (sibling_repos origin plan, Grade A through Phase 2).

Finding count: **22 (1 critical, 5 major, 7 minor, 9 info/passes)**. Severity floor (≥ 3) met without escalation; consensus-arbiter not invoked.

## Correctness

### C1 — `_reject_absolute_sibling_paths` validator is duplicated verbatim on `HarnessConfig` (L598-L611) and `InterviewAnswers` (L740-L749) · `Severity: major`
**Where:** `models.py:598-611` and `models.py:740-749` — identical implementations, identical docstrings.
**Why it bites:** any future change (e.g., adding `..` rejection — see B1) must be made in two places. The two classes have parallel `sibling_repos` fields by design (different lifecycle stages — interview answers vs synthesized harness config), but the *validation rule* is the same. Drift risk grows with codebase age.
**Suggested fix:** extract `_validate_sibling_repos_relative(v: object) -> object` as a module-level function; both classes reference it via `field_validator("sibling_repos", mode="before")(_validate_sibling_repos_relative)`.

### C2 — Multi-repo `create()` pre-flights branch-name availability across ALL repos (atomic) · `Severity: info` (passes)
**Where:** `worktree.py:95-106` `_find_free_name` checks `_branch_exists` on every sibling for both `{name}` and `{name}-{slug}` before any worktree is created. Plus on `create()` rollback (L143-L150), already-created sibling worktrees are removed if a later create fails. Solid transactional shape.

### C3 — `_find_free_name` retry budget is 100 attempts · `Severity: info` (passes, design)
**Where:** `worktree.py:99-106`. Hits if 100 same-timestamp branches exist (impossible under normal flow). Sound bound.

### C4 — CLI `worktree` subcommand discoverability: `uv run hm worktree --help` returns "no such command" · `Severity: minor`
**Where:** `pyproject.toml` defines `[project.scripts] harness-maker = "harness_maker.cli:main"`. The `worktree` operations live in `harness_maker.worktree.__main__`-style entry, not in the typer `cli.app` registry. A user typing `hm worktree --help` or `harness-maker worktree --help` is told the command doesn't exist; they must know to use `python -m harness_maker.worktree`.
**Suggested fix:** register a `worktree` typer command in `cli.py` that forwards to `harness_maker.worktree._cli_create` / `_cli_finalize`.

### C5 — `_capture_pending_in_worktree` uses `git commit --no-verify` · `Severity: major`
**Where:** `worktree.py:215-218`. The `--no-verify` flag bypasses pre-commit hooks.
**CLAUDE.md (global) says:** "Never skip hooks (--no-verify, --no-gpg-sign, etc) unless the user explicitly requests it". This is exactly the case the global rule prohibits.
**Counter-argument (already in docstring at L196-L201):** the WIP commit is a safety capture for uncommitted work that would otherwise be silently deleted by `cleanup --force`. If a pre-commit hook rejects the WIP commit, the worktree is left half-finalized and data loss may occur.
**Verdict:** the technical justification is real, but the global rule is also real. **Surface to user for decision**, do not silently keep `--no-verify`.
**Suggested resolution:** either (a) document explicitly in CLAUDE.md project section that `worktree._capture_pending_in_worktree` is exempt with cited rationale, OR (b) try `git commit` without `--no-verify` first, fall back to `--no-verify` + WARN if hook rejects.

### C6 — `_capture_pending_in_worktree` rollback on commit failure uses `git reset HEAD` · `Severity: info` (passes)
**Where:** `worktree.py:222-228`. On commit failure, unstages so the worktree is restorable for retry. Good defense.

### C7 — `_detect_existing_worktree` walks path right-to-left to find innermost worktree · `Severity: info` (passes, ADR-006 cited)
**Where:** `worktree.py:493-522`. Comment cites ADR-006 (marker-based detection removed). Path-only is correct for parallel sessions.

## Boundary & mock-reality gap

### B1 — `..` traversal in `sibling_repos` NOT rejected at validation · `Severity: critical`
**Live reproduction:** `HarnessConfig(sibling_repos=['../../../etc'])` accepted without error. `InterviewAnswers` validator (same pair) also accepts. Tests at `test_interview_sibling.py:41-51` only cover absolute path rejection, not `..` traversal.

**What happens at runtime?** `_load_sibling_dirs:336` resolves `(base / rel).resolve()` for each. If the resolved path happens to be a git repo, `create()` adds a worktree there.  `git worktree add` against a non-git path fails loudly, so `/etc` would error. But a malicious or buggy `harness.yaml` could point at, say, `../../some-other-coworker-repo` and silently create a branch + worktree in someone else's repo without their consent.

**Why this is the biggest finding in this REVIEW:** the user said "mock 위주라 신뢰 X" — the unit tests at `test_worktree_multi.py` always pass tmp_path-relative siblings. The mock world never sees `..` traversal.

**Suggested fix (mirrors refdocs B1 in REVIEW-refdocs):**
- Reject `..` segments in `sibling_repos` validator
- AND emit a LOUD warning in `_load_sibling_dirs` when the resolved path is not a sibling at the *immediate parent* level (e.g., `../sibling-name` OK, `../../other-tree/foo` warned)
- Make the validator a shared helper (per C1 — fix both classes once)

### B2 — Stale `execute.md` sentinel check uses loose substring match · `Severity: major`
**Where:** `worktree.py:339-345` `_execute_md_has_sentinel` checks `"SIBLING_WORKTREE_PATHS" in md.read_text()`. The substring is present in a comment marker (`<!-- # SIBLING_WORKTREE_PATHS -->`) at `.claude/commands/hm/execute.md:67`, NOT in the executable body.
**Why it bites:** the check exists to detect "stale rendered execute.md that doesn't know about siblings" — but the comment-only presence trips the check as True even when the actual sibling-aware instruction body is absent. Future renderer changes that move the sentinel into the body without removing the comment would not be detected as stale-recovery either.
**Suggested fix:** check for a more specific marker that appears in the executable body (not in HTML comments), OR strip HTML comments before the substring check.

### B3 — CLAUDE.md says cleanup is "prefix-matched to self (phase-*, autoloop-*)" — but `_list_worktrees` (L262-L281) does NOT filter by prefix · `Severity: critical`
**Where:** `worktree.py:262-281`:
```python
def _list_worktrees(base_dir: Path) -> list[Path]:
    ...
    # Restrict to ones under base/.worktrees/ — leave external worktrees alone.
    if WORKTREE_DIR_NAME in p.parts and p.is_relative_to(base):
        paths.append(p)
    return paths
```
There is NO `name.startswith("phase-") or name.startswith("autoloop-")` filter. CLAUDE.md §"Cursor target 추가" says "cleanup 은 prefix 매치로 자기 것만 (phase-*, autoloop-*)" and the implementation does **not** do this.

**Live confirmation:** `cleanup_all` listed `execute-20260519T1318Z` and `execute-20260519T1322Z`, both with `execute-*` prefix — NOT `phase-*` or `autoloop-*`. So either (a) CLAUDE.md is wrong about the prefix being phase/autoloop (the actual prefix is `execute-*` / `plan-*` for stage-engaged worktrees), OR (b) the implementation is missing a filter.

**Why it bites:** if Cursor's `/worktree` command creates a worktree under `.worktrees/cursor-someslug/` AND registers it with git, `harness-maker.worktree.cleanup_all(force=True)` (called from `/hm:health` weekly cleanup OR autoloop blocker recovery) **would force-remove the Cursor worktree along with our own**. The "prefix match safety" advertised in CLAUDE.md does not exist in code.

**Suggested fix:** implement an explicit `_OWNED_PREFIXES = ("execute-", "plan-", "phase-", "autoloop-")` constant and filter `_list_worktrees` against it. OR rewrite CLAUDE.md to accurately describe what cleanup_all does (cleans all .worktrees/* registered with git, period).

### B4 — `cleanup_all` silently swallows individual cleanup errors · `Severity: minor`
**Where:** `worktree.py:284-300`. A single dirty/locked worktree raises `RuntimeError`, the loop `continue`s and moves on. The caller sees a return count smaller than expected but no per-worktree error.
**Justification (per docstring):** "a single dirty worktree shouldn't block the autoloop blocker recovery path" — reasonable in context. The cost is observability: the user does not know which worktrees survived.
**Suggested fix:** collect failures into a returned list `tuple[int, list[Path]]` (count, failed_paths); caller logs.

### B5 — Sibling worktree creation does NOT pre-check sibling repo state · `Severity: minor`
**Where:** `_load_sibling_dirs:327-336` reads paths from harness.yaml + resolves; `create()` calls `git worktree add` directly. No pre-check that the sibling is a git repo (would fail at git command), no check for sibling cleanliness (worktree add tolerates dirty source).
**Live observation:** my exercise added a worktree to `../claude-code-discord` which had 4 untracked files. `git worktree add` succeeded — untracked in source does not block. But if the sibling has merge-conflict markers or detached HEAD, behavior is unclear.

### B6 — `_capture_pending_in_worktree` known race with Cursor IDE concurrent writer (docstring L196-L201) · `Severity: minor`
**Where:** `worktree.py:182-230`. Docstring explicitly documents: "status-check + add + commit sequence is not atomic against a concurrent writer". Cleanup `--force` may delete a Cursor write between our status check and our add. The mitigation cited is "harness-maker and Cursor own different worktree prefixes, so the actual race surface is small" — but that mitigation contradicts B3 (the prefix safety doesn't exist).
**Suggested fix:** acknowledge in CLAUDE.md that this race exists; consider git index lock acquisition via flock if needed.

### B7 — Orphan worktree accumulation across aborted sessions · `Severity: minor`
**Live observation:** `execute-20260519T1318Z` was an orphan from earlier today; never auto-cleaned. CLAUDE.md notes "weekly cleanup hook" for stale worktrees via `/hm:health` — verified via grep that `/hm:health` step 2 references cleanup, but the actual cleanup happens only when the user runs `/hm:health`. Between runs, orphans accumulate.

## Security & permission posture

### S1 — Same `..` boundary issue as refdocs (overlap with B1) · `Severity: critical`
Logged in B1 above. Listed here under Security too.

### S2 — `cleanup_all force=True` removes worktrees indiscriminately (overlap with B3) · `Severity: critical`
The Cursor cross-tool concern (B3) is a Security/posture issue as well as a behavior bug. If a downstream tool relies on harness-maker NOT touching its `.worktrees/`, the assumed safety is illusory.

### S3 — Path resolution `(base / rel).resolve()` for sibling paths · `Severity: info` (no traversal-blocking, but `git worktree add` is the natural gate)
Resolve → if not a git repo → command fails. So filesystem traversal does not silently leak structure (unlike refdocs which builds an index). The blast radius is limited to the git command failing AND/OR creating an unwanted worktree in a sibling that IS a git repo.

### S4 — Marker file `.claude/.hm-loop-execute-<ts>` written with 0600 perms (chmod 600 implied by file mode `rw-------` in live `ls`) · `Severity: info` (passes)
Confirmed via live `ls -la .claude/.hm-loop-*`. Default umask honored. Not world-readable.

### S5 — `_ensure_gitignore_entry` (L462-L490) silently swallows OSError · `Severity: info`
**Why it's OK:** Best-effort write — if gitignore is read-only, the marker file is still written. The "marker file accidentally committed" risk is low because `.claude/` itself is already gitignored in this repo. Different consumer projects may not have `.claude/` gitignored; the entry-ensure protects them.

## Integration boundary

### I1 — Sentinel-check degrade path REPORTS only primary path but BOTH worktrees are actually created · `Severity: major`
**Where:** `worktree.py:386-394`:
```python
if sibling_dirs and not _execute_md_has_sentinel(base):
    print("[WARNING] execute.md is stale...", file=sys.stderr)
    print(str(wt_paths[0]))  # primary only
    return 0
```
Downstream consumer (the slash-command body) reads stdout, sees one path, treats as single-repo. **But sibling worktree was already created** (line 381 `create()` runs before sentinel check at 386). The sibling worktree is orphaned at the command level even though it's tracked in the marker file.
**Live confirmation:** B2 reproduction shows sentinel-check passing because of the substring-in-comment. Once the comment is removed or the check tightened, this degrade path will trip in real harness.yaml's with siblings + stale execute.md → user sees "single-repo" output but sibling worktrees exist + marker tracks them. Finalize would still process both via marker, but the slash-command body that consumed stdout would not know.

### I2 — Branch-name collision between same-basename siblings · `Severity: minor`
**Where:** `worktree.py:117` "Branch names: primary={name}, sibling={name}-{slug} where slug=sibling.name". If two siblings have the same `Path.name`, both get the same branch name. `_find_free_name` retries by adding suffix to `name` but not to `slug` — only the primary name moves on collision.
**Live unverified.** Worth a test (T2 below).

### I3 — `cli.py` `sibling_repos_override` parses `;`-separated string · `Severity: info` (passes)
**Where:** `cli.py:166-169` `--sibling-repos-override "../a;../b"`. `cli.py:688-691` `r.strip() for r in sibling_repos_override.split(";") if r.strip()`. Clean. Empty entries dropped.

### I4 — `interview.answers_from_harness_yaml` reads `sibling_repos` via `_list_of_strings` · `Severity: info` (passes)
**Where:** `interview.py:737`. Reverse-mapper round-trip. Tested at `test_interview_sibling.py:67-110`. Solid.

## UX & observability

### U1 — `python -m harness_maker.worktree` minimal CLI · `Severity: info` (passes)
Two subcommands (`create`, `finalize`). Usage printed on misuse. No `--help` at module level (calling with no args prints `usage: python -m harness_maker.worktree <create|finalize> [...]`).

### U2 — `interview._ask_sibling_repos` only warns on non-existent path · `Severity: minor`
**Where:** `interview.py:465-466`:
```python
if not Path(line).exists():
    print(f"  warn: path {line!r} not found on this machine (registering anyway).")
```
Registers anyway. Docstring justification: "the path may resolve on a different machine where the harness ships". OK for portability, but does NOT verify the path *is a git repo* even when it does exist. A user typo'ing a non-repo dir gets no early error.
**Suggested fix:** if path exists, also check `(Path(line) / '.git').exists() or Path(line, '.git').is_file()`; warn if not a git repo.

### U3 — No worktree-list / status command · `Severity: minor`
No `python -m harness_maker.worktree list` to inspect active markers + worktrees. Diagnostic would be useful for the orphan-cleanup case (B7).

### U4 — `_capture_pending_in_worktree` emits status to stderr · `Severity: info` (passes)
`[finalize] captured uncommitted work in <name> as WIP commit` — useful diagnostic, correctly directed to stderr.

## Docs drift

### D1 — CLAUDE.md cleanup-prefix safety claim does not match code (overlap with B3) · `Severity: critical`
Logged in B3. The Docs drift framing: someone reading CLAUDE.md will form an incorrect mental model of cross-tool safety.

### D2 — PLAN-multi-repo-mgmt-2026-05.md (origin plan) shows Phase 1+2 done Grade A; remaining Phase 3+ scope unverified · `Severity: info` (out of scope for live verification)
Mentioned in this REVIEW's parent PLAN's `Prior Work`. The origin plan should be cross-referenced from any future fix work on B1/B3/C1.

### D3 — `worktree-isolator` skill is documentation-only — explicitly noted in `execute.md:69` · `Severity: info` (passes)
The execute stage already names the deterministic CLI approach + cites the skill's probabilistic dispatch as the reason. Aligned with code.

## Test gaps

| # | Gap | Why missing matters | Suggested test |
|---|-----|---------------------|----------------|
| T1 | `..` traversal in `sibling_repos` (related: B1/S1) | Critical security/posture gap | `test_sibling_repos_rejects_parent_traversal` (HarnessConfig + InterviewAnswers both) |
| T2 | Branch-name collision between same-basename siblings (related: I2) | Defends `_find_free_name` against slug collisions | `test_create_handles_two_siblings_with_same_basename` |
| T3 | cleanup_all prefix filter (related: B3/D1) | Pin the Cursor cross-tool safety claim — CURRENTLY FAILING in spirit | `test_cleanup_all_only_removes_owned_prefixes` (after fix) |
| T4 | Sentinel-check on stale execute.md with siblings configured (related: B2/I1) | Pin the degrade path | `test_create_with_stale_execute_md_reports_primary_only_but_creates_siblings` |
| T5 | Sibling repo at non-existent path (related: B5/U2) | Validator only warns; worktree add would fail | `test_create_with_missing_sibling_returns_error` |
| T6 | `_capture_pending_in_worktree` --no-verify is intentional (related: C5) | Regression guard if the project policy reverses | `test_capture_pending_skips_pre_commit_hooks_intentionally` |
| T7 | Sibling repo with uncommitted (untracked AND modified) state | Worktree add tolerates untracked; behavior with modified-not-staged untested | `test_create_succeeds_with_dirty_sibling` |
| T8 | Orphan worktree detection (related: B7) | No tool helps the user find pre-cleanup state | `test_list_worktrees_reports_orphans_without_marker` |
| T9 | `_reject_absolute_sibling_paths` exists on both classes — drift guard (related: C1) | Pin the duplicated-validator pair | `test_both_models_reject_absolute_sibling_repos` (parametrize over HarnessConfig+InterviewAnswers) |

## Devils-advocate self-critique

Per ADR-002 amended, 7-item checklist gate:

1. ✅ **Live exercise produced an observation contradicting unit-test assumption** — multiple. (a) `..` traversal accepted at validation. (b) cleanup_all does NOT prefix-filter (CLAUDE.md drift). (c) execute.md sentinel substring matches inside HTML comment. Unit tests never see these because they always use tmp_path-relative paths and well-formed execute.md.
2. ✅ **All 6 dimensions traversed.**
3. ✅ **Severity defensible** — three critical findings (B1/B3, S1/S2 are overlaps): B1 is the validation gap; B3 is the docs-vs-impl drift in cleanup safety; both directly invalidate user assumptions. Major findings cite code lines + reproductions. Minors are quality-of-life or single-axis observations.
4. ✅ **No-finding sections have rationale** — every `info` entry annotated `(passes)` with the specific code path inspected.
5. ✅ **All files in PLAN read scope covered** — `worktree.py` 676 LOC end-to-end, both `sibling_repos` Field+validator locations in `models.py`, `interview.py` sibling functions, `synthesize.py` L643, `cli.py` overrides, both sibling test files (full read of interview test, key blocks of multi test).
6. ✅ **Tests read, not just source** — see #5. Cross-referenced `test_interview_sibling` for boundary coverage gaps.
7. ✅ **Error paths exercised** — absolute path rejection, tilde rejection, `..` traversal acceptance, finalize stage-only, finalize fail, orphan cleanup all hit live.

**Self-critique adjustment:** initial draft had B3 as `major`. On re-read, escalated to `critical` because the CLAUDE.md safety claim is *user-facing documentation* that a Cursor user (or anyone running `/hm:health` weekly cleanup) reads to understand cross-tool safety. The implementation gap means the documented promise is unverifiable from code alone. This is exactly the kind of "mock-and-docs-aligned-but-reality-different" gap the parent PLAN flagged.

## Cross-references

- [[PLAN-untested-trio-review-2026-05-19]] — parent plan (this REVIEW = Phase 3 deliverable)
- [[PLAN-multi-repo-mgmt-2026-05]] — origin plan (Phase 1+2 done Grade A); future fix-PLAN on sibling_repo should cross-reference for ADR continuity
- [[REVIEW-second-brain-2026-05-19]] — Phase 1 REVIEW; **shared pattern**: mock-blind `..` traversal coverage gap (second_brain blocks `..` in folder paths — sibling_repo does not)
- [[REVIEW-refdocs-2026-05-19]] — Phase 2 REVIEW; **shared pattern with this REVIEW**: `..` traversal in ref_folders AND sibling_repos both unrejected (B1 in both)
- [[REVIEW-untested-trio-summary-2026-05-19]] — Phase 4 cross-cutting summary (B1 anchors the shared "validator-gap-on-traversal" anti-pattern across all 3 features)
