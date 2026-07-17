---
type: review
task_slug: second-brain-promotion
status: APPROVED
created: 2026-05-28
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: second-brain-promotion
  computed_at: 2026-05-28
---

## 🎯 Round 1 Summary

**Grade (Round 1): B** — one P1 (consensus across both reviewers on the same code
region, converging fix) + several P2/P3. Auto-fix applied in Round 2 → **Grade A**.

The diff (5 version files, `second_brain.py` +90, `wrapup.md.j2` +59, 2 test files,
8 regenerated snapshot fixtures, CLAUDE.md/CHANGELOG, tracked `.claude` version
bumps) is in scope and well-tested. Both reviewers independently flagged the
`note_type` handling at `second_brain.py:280` and converged on the same remedy.

## 🔍 Drift Findings

`drift_verdict: clean`. Every changed file maps to a PLAN phase scope:
Phase 1 (`second_brain.py`, `test_second_brain.py`), Phase 2 (`wrapup.md.j2`),
Phase 3 (5 version files + `uv.lock`), Phase 4 (`test_second_brain_e2e.py`,
regenerated `.claude/` + snapshot fixtures), Phase 5 (CLAUDE.md, CHANGELOG).
No scope drift, no incomplete phase.

## ✅ Consensus Findings

### [strong-actionable] `promote_note` mishandled `note_type` — `second_brain.py:280`

Both reviewers flagged the same code region with converging fixes:

- **code-reviewer (P1):** folder selection `next((f for f in cfg.folders if f.write), None)`
  picks the *first writable folder* ignoring `note_types`. For a per-type
  multi-folder Obsidian layout, promoting a type not allowed in the first
  writable folder is rejected by `_ensure_type_allowed`, and Step 5.6's
  graceful-degrade **silently** swallows it as "not promoted" — the exact
  empty-vault failure mode this PLAN exists to fix.
- **security-reviewer (P2):** `note_type` is interpolated raw into the write
  path. Not an exploitable escape (the downstream `_resolve_authorized`
  `resolve()` + `is_relative_to` allowlist contains traversal, and
  `_ensure_type_allowed` rejects non-enum types before `atomic_write`), but the
  defense is implicit/fragile. Recommended validating `note_type` against the
  enum at the source.

OBSERVE (both): `relpath = f"{folder.path}/{note_type}-{_slugify(source_slug)}.md"`
with `note_type` raw + folder chosen without consulting `note_types`.
CONCLUDE: functionality (wrong folder) + hardening (raw interpolation) — one fix
resolves both.

**Resolution (Round 2):** validate `note_type` against `SecondBrainNoteType` at
the top of `promote_note` (raise a clear `unknown note type` on miss), select the
first writable folder **that accepts the type**, and build the path from the
validated `nt.value` (no raw caller string in the path). Also added
`choices=[t.value …]` to the CLI `--type` arg (boundary defense). Resolves the
code-reviewer P1, the security-reviewer P2, and the P3 misleading-error nit.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| # | Sev | Reviewer | Finding | Resolution (Round 2) |
|---|-----|----------|---------|----------------------|
| M1 | P1 | security | No negative test for malicious `note_type`/`source_slug` (new security-relevant behavior shipped untested). | Added `test_promote_note_rejects_unknown_type` (traversal payload → `unknown note type`, no file escapes) + `test_promote_note_source_slug_traversal_is_neutralized`. |
| M2 | P2 | code | `extra_frontmatter` could inject `created`/`project`, defeating the "core keys win" comment. | Added `_PROMOTE_RESERVED_KEYS` strip; added `test_promote_note_extra_frontmatter_cannot_override_reserved`. |
| M3 | P2 | code | Empty `links` → "weak graph connectivity" warning on every promote. | Default `[[<project_id>]]` backlink when no links; added `test_promote_note_defaults_project_backlink_no_weak_graph_warning`. |
| M4 | P2 | code | Slug collision (60-char cap / non-alnum collapse) silently overwrites distinct sources. | Documented as accepted in `_slugify` docstring (caller contract: stable + unique-after-kebab; Step 5.6 already requires a stable id). |
| M5 | P3 | code | Unknown `note_type` produced a misleading "not allowed in folder" message. | Fixed for free by the enum validation (now `unknown note type`). |
| M6 | P3 | security | `--frontmatter-json` injection — bounded by `yaml.safe_dump` + core-key-wins. | Cleared (no action); reserved-key strip (M2) further hardens it. |

Also added `test_promote_note_selects_writable_folder_by_note_type` (two-folder
config) to lock the P1 fix.

## 🤝 Disagreements

The P1/P2 severity split on the shared finding reflects the two lenses
(functionality vs security), not a true disagreement — both pointed at
`second_brain.py:280` and the same fix satisfies both. Resolved to a single
strong-actionable item.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 1 P1 + 4 P2 + 2 P3 | — |
| 2         | A     | 5 (+3 tests)  | 0 (M4 accepted-risk, documented) | 0 |

Final grade: **A**
Iterations used: 2 / 3
Status: APPROVED
human_review_needed: false
