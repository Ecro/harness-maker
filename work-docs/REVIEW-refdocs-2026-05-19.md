---
type: review
task_slug: untested-trio-review-2026-05-19
feature: refdocs
status: complete
created: 2026-05-19
reviewer: Claude solo (ADR-002 amended)
plan: "[[PLAN-untested-trio-review-2026-05-19]]"
summary: "Deep review of harness_maker.refdocs_index + refdocs-search skill — lossy yaml index over user-registered doc folders."
---

# REVIEW — `refdocs` (harness-maker)

## Live-exercise preamble (paths + observations)

**Fixture used:**
- ref_folder: `docs/` (in-repo, relative path) — registered in Phase 0
- index output path: `.claude/observability/docs_index.yaml` (HARD-CODED — not under `.claude/observability/refdocs-fixture/` as the PLAN assumed)

**Successful index build:**
- `python -m harness_maker.refdocs_index build` → `docs_index.yaml: 13 entries, 0 warnings`
- All 13 entries had `kind: md`, with `title` extracted from frontmatter OR first H1, and H1/H2 headings list
- Non-ASCII (`HOW-IT-WORKS.ko.md`) indexed cleanly with Korean title + heading list (`목차`, `1. harness-maker 란?`, ...)

**Boundary exercises (live):**
1. **Absolute path** (`/tmp/refdocs-abs-test`) → indexed 1 entry, no warning (intentional — `RefFolder.path` docstring permits absolute)
2. **Parent traversal** (`../../../etc`) → indexed 3 entries from `/etc/X11/rgb.txt`, `/etc/java-11-openjdk/...`, `/etc/java-17-openjdk/...`. **No warning. No boundary check.** This is the biggest live finding.
3. **Symlink** (`/tmp/refdocs-symlink-host/linked → /tmp/refdocs-symlink-target/`) → 0 entries. `Path.rglob` does not follow symlinks by default. Good defense in depth.
4. **Dotfile** (`.secret.md`) → skipped by `_is_hidden`. Good.
5. **Duplicate ref_folder entries** (same `docs/` listed twice) → 26 entries (duplicate blocks in output). No deduplication.
6. **Loader inconsistency**: `_cli` (`refdocs_index.py:226-231`) parses harness.yaml via ad-hoc frontmatter-strip; `second_brain.py:247` uses `harness_maker.io_utils.load_harness_yaml`. Both succeed today, but the helper is the canonical path and refdocs bypasses it.

## Methodology

Solo deep read + 7-item self-critique gate per ADR-002 (amended). Live exercise: build over `docs/` fixture + 5 boundary cases (above). Read scope: `src/harness_maker/refdocs_index.py` (252 LOC) end-to-end; `RefFolder` in `models.py`; `tests/unit/test_refdocs_index.py` (170 LOC) fully; `.claude/skills/refdocs-search/SKILL.md` end-to-end; cross-checked loader convention against `second_brain.py`.

Finding count: **19 (1 critical, 4 major, 6 minor, 8 info/passes)**. Severity floor (≥ 3) met without escalation; consensus-arbiter not invoked.

## Correctness

### C1 — CLI uses ad-hoc multi-doc YAML parsing instead of `harness_maker.io_utils.load_harness_yaml` · `Severity: major`
**Where:** `refdocs_index.py:226-231`:
```python
text = yaml_path.read_text(encoding="utf-8")
if text.startswith("---\n"):
    end = text.find("\n---\n", 4)
    if end != -1:
        text = text[end + 5 :]
data = yaml.safe_load(text) or {}
```
vs `second_brain.py:247`:
```python
data = load_harness_yaml(yaml_path)
```
**Why it bites:** `load_harness_yaml` is the project's canonical multi-doc reader (per CLAUDE.md §2 "Provenance YAML frontmatter / multi-document stream / Reverse mapper"). The ad-hoc parser:
- Strips ONE `---\n...---\n` block; if a future renderer adds a second doc, results diverge.
- Does not validate provenance fields (`content_hash`, `generated_by`).
- Re-implements logic that is being centralized for a reason.
**Suggested fix:** `data = load_harness_yaml(yaml_path)` — one-liner. Drop lines 226-231.

### C2 — Brace-glob expansion is single-level only · `Severity: minor`
**Where:** `_walk:152-158`. Supports `**/*.{md,txt,pdf}` but not nested braces (`{a,{b,c}}`) or alternation outside the extension position. Documented in code comment ("extension-style alternation"). Acceptable for current use; document the limitation in `RefFolder.glob` docstring (currently only "default" is shown).

### C3 — Duplicate `ref_folders` entries are not deduplicated · `Severity: minor`
**Where:** `build:69-72` iterates the list as-given. Duplicate-path entries (same `path`, same `glob`) produce duplicate blocks in the output. The skill consumer (refdocs-search) reads each block independently; same file appears twice in triage list.
**Suggested fix:** in `build`, drop duplicates by `(path, glob)` tuple before walking, emit one warning per dropped duplicate.

### C4 — Title-extraction read cap at 256 KB · `Severity: info` (working as documented)
**Where:** `refdocs_index.py:40` `_MD_READ_BYTES_CAP = 256 * 1024`, applied at `:176`. Big MDs (e.g., aggregated changelogs) get truncated for title/heading extraction. Acceptable — actual content is read fresh at query time by the skill consumer.

### C5 — Behaviorally-identical builds produce timestamp diff · `Severity: minor`
**Where:** `build:64` always uses `datetime.now(UTC)` for `generated_at`. Running the indexer twice in a row produces a diff (different timestamp) even if no underlying files changed. Atomic-write replaces every time. Cost: git diff churn if the file is committed; the file isn't committed currently (gitignored under `.claude/`), so cost is low.

### C6 — Pdf entries write `filename_only: true` but skill's PDF Read path uses `pages=...` — needs the filename, no contradiction · `Severity: info` (passes)
Confirmed: skill SKILL.md docs the pdf use case via multimodal Read with `pages` parameter. `_entry_for:162-163` emits the minimal entry. Consistent.

## Boundary & mock-reality gap

### B1 — `../` parent-traversal in `ref_folders` walks ANY filesystem location · `Severity: critical`
**Live reproduction:** `ref_folders: [{path: "../../../etc", glob: "**/*.txt"}]` indexed files from `/etc/X11/rgb.txt`, `/etc/java-*-openjdk/security/policy/README.txt`. Generated `docs_index.yaml` lists those paths verbatim. **No warning, no boundary check.**

This is **structurally different** from `second_brain` which:
- Rejects `..` segments at config-time in `SecondBrainFolder.path` validator (`models.py:296`)
- Resolves writes through a vault-relative root with `.is_relative_to(root)` check

`RefFolder.path` is intentionally free-text (per `models.py:268-275` docstring: "stored as free-text str ... relative paths like `../shared-architecture` survive git commits"). The use case is legitimate: a multi-repo project sharing docs.

**But:** in the harness-maker UX model where `.claude/harness.yaml` is authored by an LLM agent (interview → synthesize → render), or edited by an attacker with write access to the workspace, a malicious or buggy `ref_folder` entry leaks filesystem structure into `docs_index.yaml`. The LLM reading the index for triage may then quote those paths back to the user, or feed them to subsequent stage prompts.

**Why this is the biggest finding in this REVIEW:** the user said "mock 위주라 신뢰 X" — the unit tests do not exercise `../` traversal because the test convention is to use temp-dir-relative paths that don't escape. The mock world never sees this.

**Suggested fix:**
- Reject `..` segments AND absolute paths outside `harness_root` in `RefFolder.path` validator
- OR emit a `LOUD warning` in `_build_block` when `abs_root` is not under `harness_root` AND not under `Path.home()` AND not under `/tmp`
- OR add an explicit `allow_outside_repo: bool = False` opt-in flag on `RefFolder`
The legitimate "shared-architecture across sibling repos" use case is preserved via the opt-in.

### B2 — Absolute paths allowed without policy gate · `Severity: minor`
**Confirmed live.** Permissible per docstring, but no warning when the absolute path resolves outside `harness_root` AND outside `Path.home()`. Same fix class as B1.

### B3 — Symlinks NOT followed by `Path.rglob` · `Severity: info` (passes)
Tested live. Good defense in depth — but worth documenting in code comment + adding a test (T1 below).

### B4 — DOCX double-warn protected · `Severity: info` (passes)
`tests/unit/test_refdocs_index.py:114-124` covers the seen-set dedup. Solid.

### B5 — Hidden dirs skipped · `Severity: info` (passes)
`_is_hidden:135-143` covers `.git`, `.venv`, etc. Tested. Solid.

### B6 — PLAN expected `.claude/observability/refdocs-fixture/` but code writes to `.claude/observability/docs_index.yaml` (hard-coded path) · `Severity: minor` (PLAN gap, not refdocs gap)
**Where:** `refdocs_index.py:81` `harness_root / ".claude" / "observability" / "docs_index.yaml"`. The PLAN's Phase 2 rollback assumed a feature-isolated fixture directory; the real code uses the shared observability dir (alongside metrics, dashboard, health). Phase 5 rollback in this REVIEW's parent PLAN must be amended (see [[PLAN-untested-trio-review-2026-05-19]] Amendments).

### B7 — Non-ASCII titles work · `Severity: info` (passes)
`HOW-IT-WORKS.ko.md` indexed with Korean title + headings. Yaml dump uses `allow_unicode=True` (`:79`). Solid.

## Security & permission posture

### S1 — Filesystem disclosure via configured ref_folders (overlap with B1) · `Severity: critical`
Documented in B1. Listed here under Security too because the disclosure surface is the most security-relevant axis.

### S2 — No shell injection vector · `Severity: info` (passes)
Build pipeline is pure Python file I/O + `yaml.safe_dump`. CLI takes one optional positional arg. No `subprocess`. The downstream skill instructs the LLM to use `rg -F` (fixed-string mode) which is the right choice — but that's the LLM's responsibility, not refdocs_index's.

### S3 — Symlink not followed · `Severity: info` (passes, defense-in-depth)
See B3.

### S4 — Index output overwrites with no provenance · `Severity: minor`
**Where:** `atomic_write` at `:82` writes only `payload` (no `generated_by`, no `content_hash`). The file landing in `.claude/observability/` has no marker that distinguishes "harness-maker generated this" from "user wrote this manually". CLAUDE.md §"Brownfield-safe" expects provenance on every generated file ("All generated files include frontmatter: generated_by + content_hash + source_template + harness_maker_version").
**Suggested fix:** prepend a provenance frontmatter block to `docs_index.yaml`, mirroring the renderer convention. Could break existing skill SKILL.md consumers — verify the skill handles multi-doc-stream (it reads YAML; should be fine via `safe_load_all`).

## Integration boundary

### I1 — Skill SKILL.md tells LLM to use `rg -n -C 2 -F` with the ref_folder path — works for relative paths but ambiguous for absolute · `Severity: minor`
**Where:** `.claude/skills/refdocs-search/SKILL.md` body, "Search candidate content by `kind`" table.
**Why it's ambiguous:** the index stores `path: ../../../etc` and `relpath: X11/rgb.txt`. The skill says "rg -n -C 2 -F '<term>' <ref_folder>/<relpath>". If the LLM concatenates `../../../etc/X11/rgb.txt`, that works from harness_root cwd. If the LLM cwd-resolves first, also works. But: the path interpretation is implicit — relative to what?
**Suggested fix:** store `abs_root: <resolved-path>` in each block (alongside `path: <as-written>`); skill uses `abs_root` for `rg` invocation.

### I2 — Refdocs vs Second Brain loader convention divergence (overlap with C1) · `Severity: major`
Same root cause as C1. Logged separately here because the integration-boundary view (multiple modules reading the same file via different parsers) is worth surfacing for the cross-cutting Phase 4 summary.

### I3 — `docs_index.yaml` is one of many files in `.claude/observability/` · `Severity: info` (no conflict, but proximity worth noting)
Co-located with `metrics-*.jsonl`, `dashboard.md`, `orphans-*.jsonl`, etc. No filename collision. /hm:health and other stages read those neighbors; refdocs only touches `docs_index.yaml`. Clean separation.

### I4 — Stale-index detection is documented in the skill but not automated · `Severity: minor`
**Where:** SKILL.md says "Glance at `generated_at`. If user mentions adding docs since, suggest a rebuild". This puts the staleness check on the LLM. No `--check-stale` flag in the build CLI. No hook that rebuilds when ref_folder content changes.
**Suggested fix:** out-of-scope here, but worth a follow-up: post-render hook OR `/hm:health` check could compute mtimes vs `generated_at`.

## UX & observability

### U1 — Single happy-path CLI surface (`build` only) is clear · `Severity: info` (passes)
The CLI is intentionally minimal. No flags to remember. Matches the "loose tools" philosophy.

### U2 — No `--dry-run`, no `--folder <path>` selective build · `Severity: minor`
Always rebuilds all `ref_folders`. For a future user with 10+ folders, full rebuild on every change is fine for now (size budget). Worth a `--folder` flag eventually.

### U3 — Warnings are printed on the final line but not separated from result · `Severity: info`
Output `docs_index.yaml: 13 entries, 0 warnings` then `warn: ...` per warning. Clear at human-read; an LLM parsing programmatically would need to know the format.

## Docs drift

### D1 — Skill SKILL.md is well-aligned with code · `Severity: info` (passes)
Lossy-index + original-file two-tier search documented matches `_entry_for` (title + headings only). PDF Read with `pages=` matches `filename_only: true` (skill consumer fetches content separately). DOCX unsupported note matches `_WARN_EXTS`.

### D2 — README does not mention refdocs feature · `Severity: minor`
Discoverability low. A new user setting up `harness.yaml` likely sees `ref_folders: ` empty and doesn't know what it does without reading source or the skill SKILL.md (which only loads when the skill is invoked).

### D3 — `commands/hm/configure.md.j2` (referenced in second_brain REVIEW) likely also gates refdocs registration · `Severity: info` (out of scope for direct verification here)
Not exercised live. Worth verifying as part of cross-cutting Phase 4.

## Test gaps

| # | Gap | Why missing matters | Suggested test |
|---|-----|---------------------|----------------|
| T1 | Symlink follow behavior (related: B3) | Defense-in-depth, regression guard | `test_build_does_not_follow_symlinks` (asserts entries=0 for symlinked dir) |
| T2 | Duplicate ref_folder entries (related: C3) | Visible UX issue in index output | `test_build_deduplicates_or_warns_on_duplicate_paths` |
| T3 | Absolute path indexing | Already works but no test pins the behavior | `test_build_accepts_absolute_path` |
| T4 | `..` parent-traversal (related: B1/S1) | Critical security/posture | `test_build_warns_or_rejects_parent_traversal_outside_repo` |
| T5 | CLI loader uses `load_harness_yaml` (related: C1) | Pins the canonical loader convention | `test_cli_uses_load_harness_yaml_helper` (mock the helper, assert called) |
| T6 | `OSError` from unreadable file caught at `_extract_md_metadata:177-178` | Defensive code that is not tested | `test_extract_md_metadata_returns_none_on_unreadable_file` (chmod 0 then read) |
| T7 | Title cap > 256 KB (related: C4) | Pin that titles past the cap don't extract | `test_extract_md_metadata_caps_at_256k_for_title_lookup` |
| T8 | Provenance frontmatter on output (related: S4) | Currently no provenance — codify whatever decision is made in fix-PLAN | `test_build_output_has_provenance_frontmatter` (after fix) |

## Devils-advocate self-critique

Per ADR-002 amended, 7-item checklist gate:

1. ✅ **Live exercise produced an observation contradicting unit-test assumption** — `../` traversal was indexed without warning. The unit tests (`tests/unit/test_refdocs_index.py`) never test paths outside `tmp_path`, so the mock world cannot see the boundary. This is the load-bearing finding (B1/S1).
2. ✅ **All 6 dimensions traversed** — every section has at least 2 findings or explicit `passes`.
3. ✅ **Severity defensible** — B1/S1 critical because of the disclosure surface + mock-blind nature; C1/I2 major because of the inconsistency-with-second_brain-loader pattern (CLAUDE.md §2 expectations); minors are quality-of-life.
4. ✅ **No-finding sections have rationale** — `info`-level entries with `(passes)` annotation document what was checked.
5. ✅ **All files in PLAN read scope covered** — `refdocs_index.py` 252 LOC end-to-end, `RefFolder` in models.py, `tests/unit/test_refdocs_index.py` 170 LOC fully, `SKILL.md` body, cross-checked against `second_brain.py` for loader convention.
6. ✅ **Tests read, not just source** — see #5. Test conventions inspected for boundary coverage (T1-T8 all derived from gap analysis).
7. ✅ **Error paths exercised** — missing folder, DOCX, dotfile, symlink, duplicate entries, absolute path, `..` traversal all hit live.

**Self-critique adjustment:** initial draft had C1 as `minor` (just a code-smell). On re-read I escalated to `major` because the divergence from `load_harness_yaml` is exactly the kind of fixture-vs-production drift that the PLAN-second-brain-write-failure (PLAN ADR-005 referenced in REVIEW-second-brain B1) was created to prevent. Two modules reading the same file via different parsers is a regression-class waiting to happen.

## Cross-references

- [[PLAN-untested-trio-review-2026-05-19]] — parent plan (this REVIEW = Phase 2 deliverable)
- [[REVIEW-second-brain-2026-05-19]] — Phase 1 REVIEW; **shared pattern**: both features have loader-vs-config gaps (second_brain: vault_path personal-baked in default config; refdocs: ad-hoc loader)
- [[REVIEW-sibling-repo-2026-05-19]] — Phase 3 REVIEW
- [[REVIEW-untested-trio-summary-2026-05-19]] — Phase 4 cross-cutting summary (B1/S1 + C1/I2 should anchor "shared anti-patterns")
