---
type: review-summary
task_slug: untested-trio-review-2026-05-19
status: complete
created: 2026-05-19
reviewer: Claude solo (ADR-002 amended)
plan: "[[PLAN-untested-trio-review-2026-05-19]]"
summary: "Cross-cutting view of 3 untested-in-practice features — shared anti-patterns + recommended fix-PLAN ordering."
---

# REVIEW SUMMARY — untested trio (second_brain + refdocs + sibling_repo)

This is Phase 4 of [[PLAN-untested-trio-review-2026-05-19]]. Per ADR-010 (scope tightened during validator resolution), this document contains **only** shared anti-patterns + fix-PLAN ordering + wikilinks. Per-feature finding tables live in their respective REVIEW docs (linked below) — do not duplicate here.

**Aggregate finding counts:**
- [[REVIEW-second-brain-2026-05-19]] — 17 findings · 1 critical · 8 major
- [[REVIEW-refdocs-2026-05-19]] — 19 findings · 1 critical (logged twice — same root cause across Boundary and Security) · 4 major
- [[REVIEW-sibling-repo-2026-05-19]] — 22 findings · 1 critical (logged twice — Boundary + Docs drift) · 5 major
- **Total: 58 findings · 3 distinct critical issues · 17 majors**

## Shared anti-patterns

### Pattern 1 — Validator gap on `..` parent traversal · spans 2/3 features
- [[REVIEW-refdocs-2026-05-19#B1]]: `RefFolder.path` accepts `../../../etc`; live-indexed system files
- [[REVIEW-sibling-repo-2026-05-19#B1]]: `HarnessConfig.sibling_repos` validator rejects absolute + tilde but accepts `..` traversal
- [[REVIEW-second-brain-2026-05-19]] — `SecondBrainFolder.path` validator BLOCKS `..` (cited "REVIEW-2026-05-17 security finding" in code comment at `models.py:296`). This is **the one feature that closed the gap**.

**Why it's a pattern, not three coincidences:** the project's `models.py` has a security history (REVIEW-2026-05-17) that closed the `..` gap for `SecondBrainFolder`, but the lesson did not propagate to the sibling validators (`RefFolder.path`, `sibling_repos`). When the next features land, the same gap will likely recur unless the validator is generalized.

**Anti-pattern lesson:** project-wide path-input validation should share a helper (`_validate_repo_relative_path(v) → v`) and be the default for any user-supplied filesystem path in `harness.yaml`. Opt-out (rather than opt-in) for the rare cases that genuinely need traversal.

### Pattern 2 — Loader convention divergence on `harness.yaml` · spans 2/3 features
- [[REVIEW-refdocs-2026-05-19#C1]] / [[REVIEW-refdocs-2026-05-19#I2]]: `refdocs_index._cli` uses an ad-hoc `text.startswith("---") + find + safe_load` parser
- [[REVIEW-second-brain-2026-05-19]] (B1 confirms this contract works): `second_brain._load_config` uses `harness_maker.io_utils.load_harness_yaml` — the canonical helper
- [[REVIEW-sibling-repo-2026-05-19]] (info, not a finding): `worktree._load_sibling_dirs:330` ALSO uses `load_harness_yaml` — correct.

**Pattern shape:** the canonical multi-doc loader exists (`io_utils.load_harness_yaml`) and is used by 2 of 3 consumers. The third (refdocs) reinvents the wheel. Future renderer changes to provenance frontmatter would diverge silently between the consumers. This is **the same defect class** that `PLAN-second-brain-write-failure` (ADR-005 cited in second_brain REVIEW B1) was created to prevent — fixture-vs-production drift.

### Pattern 3 — Personal/local paths baked into shipped defaults · spans 1/3 features (acute)
- [[REVIEW-second-brain-2026-05-19#B3]] / [[REVIEW-second-brain-2026-05-19#D2]]: `.claude/harness.yaml` ships `second_brain.vault_path = "/mnt/c/Users/euncheol.ro/Documents/obsidian-vault/second-brain"` (the maintainer's WSL path). On any other machine this fails.
- refdocs + sibling_repos default empty lists — no parallel issue.

**Pattern shape:** a single feature has the failure mode, but it's the same class as "any future feature that bakes a default path". Worth a project-wide policy: NO personal paths in any shipped `harness-yaml/*.yaml.j2` default. Interview drives all path fields.

### Pattern 4 — CLI fragmentation under `hm` typer entry · spans 3/3 features
- second_brain: `python -m harness_maker.second_brain`
- refdocs: `python -m harness_maker.refdocs_index`
- sibling/worktree: `python -m harness_maker.worktree` (sibling REVIEW C4 flagged the lack of `hm worktree`)

**Pattern shape:** the project ships an `hm` console script (`pyproject.toml [project.scripts]`), but none of the three reviewed features have a `hm <feature>` subcommand. Users must either know the `python -m harness_maker.<module>` invocation OR find it in a stage template. Low discoverability, high mental-model fragmentation.

**Anti-pattern lesson:** consolidate under `hm` typer subcommands. The `python -m` invocations can remain as the implementation but a unified discovery surface (`hm --help`) is the right user contract.

### Pattern 5 — Mock-blind boundary testing · spans 3/3 features (this is the load-bearing pattern the user flagged)
Every unit-test file for the three features uses ONLY `tmp_path`-relative paths. None of:
- `..` traversal (caught nothing for refdocs B1, sibling B1)
- Absolute paths outside the test dir (caught nothing for refdocs B1)
- Mismatched env state (caught nothing for second_brain B3 vault_path drift)
- Loader inconsistency across modules (caught nothing for refdocs C1/I2)
- Stale rendered files (caught nothing for sibling B2/I1 execute.md sentinel)
- Cross-tool worktree coexistence (caught nothing for sibling B3/D1 prefix-claim drift)

**Pattern shape:** the tests are *internally* sound (they pin the documented behavior) but *boundary-blind* (they don't probe what happens outside the documented happy path). The user's framing ("mock 위주라 신뢰 X — never live-used") was correct: 9 of the 11 critical/major findings in this trio (B1-class + B3-class + sentinel + integration) were **not detectable by any existing unit test**.

**Anti-pattern lesson:** future test PLANs for each feature should include an explicit "boundary suite" that probes the inputs the documented happy path doesn't take — `..`, absolute, missing, dirty, stale, concurrent, cross-tool. This is structurally different from "more tests of the same shape".

### Pattern 6 — Docs claim a safety property that the implementation does not enforce · spans 2/3 features
- [[REVIEW-sibling-repo-2026-05-19#B3]] / [[REVIEW-sibling-repo-2026-05-19#D1]]: CLAUDE.md says cleanup prefix-matched; `_list_worktrees` doesn't filter.
- [[REVIEW-second-brain-2026-05-19#I1]]: `wrapup.md.j2` tells LLM to use second_brain CLI but does not show schema; the implementation requires a non-trivial frontmatter shape. Stage template ≠ implementation contract.

**Pattern shape:** documentation evolves faster than implementation enforcement, and the gap is invisible until a user (or LLM) acts on the documented promise.

**Anti-pattern lesson:** assertions in CLAUDE.md / stage templates about safety/behavior properties should be backed by a test (or marked explicitly as aspirational). The `verify-before-completion` skill could grow a check that surfaces unbacked claims for periodic audit.

## Recommended fix-PLAN ordering

Each numbered entry below = one future `/hm:plan` task, in priority order. Use the linked finding sections as input scope.

### 1. **Validator-gap-on-traversal** · single PLAN covering ref_folders + sibling_repos · `Priority: P0 (critical)`
**Scope:** add `..` rejection to:
- `RefFolder.path` field_validator (`models.py:268-298`)
- `sibling_repos` field_validator pair (`models.py:598-611` + L740-L749) — also dedupe per [[REVIEW-sibling-repo-2026-05-19#C1]]
**Optional opt-in:** add `allow_outside_repo: bool = False` for the legitimate shared-architecture-across-siblings use case (mentioned in `RefFolder` docstring).
**Test additions:** [[REVIEW-refdocs-2026-05-19#test-gaps]] T4 + [[REVIEW-sibling-repo-2026-05-19#test-gaps]] T1 + T9 — one parametrized suite covering both classes.
**Risk:** low. Single helper, two callers.

### 2. **`cleanup_all` prefix safety** · `Priority: P0 (critical)`
**Scope:** [[REVIEW-sibling-repo-2026-05-19#B3]]. Either implement the prefix filter (`execute-*`, `plan-*`, `phase-*`, `autoloop-*`) OR rewrite CLAUDE.md `§Worktree cleanup` to describe the actual behavior. Code fix is preferable — the documented contract is the safer one.
**Test additions:** [[REVIEW-sibling-repo-2026-05-19#test-gaps]] T3.
**Risk:** medium (must verify no autoloop blocker recovery path depends on cleanup_all clearing unowned worktrees).

### 3. **Wrapup → second_brain integration UX** · `Priority: P1 (critical UX gap)`
**Scope:** [[REVIEW-second-brain-2026-05-19#I1]]. Two options:
- (a) auto-fill `created`/`updated` in `second_brain.write_note` when missing — wraps the requirement under a defaulting layer
- (b) update `wrapup.md.j2` with worked-example frontmatter blocks per note_type
**Recommended:** (a) — fixes the friction surface at the API level for all callers, not just wrapup.
**Test additions:** [[REVIEW-second-brain-2026-05-19#test-gaps]] T7 — wrapup template integration test that would fail today.
**Risk:** low. `write_note` is the single chokepoint; defaulting is additive.

### 4. **Loader convention propagation** · `Priority: P1`
**Scope:** [[REVIEW-refdocs-2026-05-19#C1]]. One-line change: `refdocs_index._cli` uses `load_harness_yaml`. Drop the ad-hoc parser at L226-L231.
**Test additions:** [[REVIEW-refdocs-2026-05-19#test-gaps]] T5.
**Risk:** very low.

### 5. **`Production.yaml.j2` vault_path default** · `Priority: P1`
**Scope:** [[REVIEW-second-brain-2026-05-19#B3]] / [[REVIEW-second-brain-2026-05-19#D2]]. Default `vault_path: ""` + interview-driven setup; OR `enabled: false` until `/hm:configure` is run.
**Test additions:** [[REVIEW-refdocs-2026-05-19#test-gaps]] T8 (renamed: `test_default_production_harness_yaml_has_no_personal_paths`).
**Risk:** low. Sets the right precedent for any future feature with paths.

### 6. **Execute.md sentinel + integration degrade path** · `Priority: P2`
**Scope:** [[REVIEW-sibling-repo-2026-05-19#B2]] + [[REVIEW-sibling-repo-2026-05-19#I1]]. Tighten the sentinel check (skip HTML comments) AND audit the degrade behavior (sibling worktrees created but not reported is a footgun).
**Risk:** medium. Touches the rendered execute.md contract; renderer + stage template both involved.

### 7. **Coverage-suite for boundary testing** · `Priority: P2`
**Scope:** all 24 `T*` test-gap entries across the three REVIEWs. Group into one or three test-only PLANs (recommend three — one per feature — to keep diffs reviewable). Each test directly maps to a finding in this review.
**Risk:** low. Test-only.

### 8. **CLI consolidation under `hm` typer subcommands** · `Priority: P3 (polish)`
**Scope:** Pattern 4 above. Register `hm second-brain`, `hm refdocs`, `hm worktree` typer subcommands forwarding to existing `_cli` entries. Keep the `python -m` invocations as the back-end.
**Risk:** low. Additive; existing stage templates continue working via `python -m`.

### 9. **`_capture_pending_in_worktree` --no-verify decision** · `Priority: P3 (governance)`
**Scope:** [[REVIEW-sibling-repo-2026-05-19#C5]]. Either document the exemption in CLAUDE.md (citing the data-loss-vs-hook tradeoff) OR refactor to try-without-no-verify-first-then-fall-back. Surface to user for direction.
**Risk:** low (decision-only; either path is implementable).

## Cross-references

- [[PLAN-untested-trio-review-2026-05-19]] — parent plan
- [[REVIEW-second-brain-2026-05-19]] — Phase 1 deliverable (17 findings)
- [[REVIEW-refdocs-2026-05-19]] — Phase 2 deliverable (19 findings)
- [[REVIEW-sibling-repo-2026-05-19]] — Phase 3 deliverable (22 findings)
- [[PLAN-multi-repo-mgmt-2026-05]] — sibling_repos origin plan (referenced in sibling REVIEW D2)
- [[PLAN-second-brain-write-failure]] — prior plan whose ADR-005 informed the loader convention pattern (Pattern 2)
