---
type: plan
task_slug: hooks-merge-stale-path-dedup
status: complete
created: 2026-05-28
tags: [harness-maker, plan, python, render, hooks-merge, dedup]
interview_rounds: 1
adrs: 4
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Path-agnostic harness-hook identity so hooks.json merge stops duplicating across plugin-path changes"
---

# PLAN — hooks-merge-stale-path-dedup

## 🎯 Executive Summary

**TL;DR:** `hooks.json`'s merge already has a dedup normalizer (`_normalize_hm_managed_command`,
added 2026-05-22), but its regex matches **only** the `harness-maker-local` cache path. It misses
the GitHub marketplace cache (`…/cache/harness-maker/harness-maker/<ver>/…`) and the dev-repo path
(`--with /home/noel/harness-maker …`). So when a project's plugin resolution changes (version bump
OR marketplace switch), the un-matched forms keep full-command identities, aren't recognized as
"ours", and accumulate. Verified in `~/spoton`: switching local→GitHub produced **triplicated**
hooks (every harness hook present 3×), each firing per event, the stale copies running old code.

**What / Why:** Make the normalizer **path-agnostic** — key harness-hook identity on the
`python -m harness_maker.<invocation>` suffix (our module namespace = proof of ownership),
ignoring whatever precedes it. One identity per (event, matcher, module+args) → the merge keeps
exactly one entry (the template's current-path form) and **self-heals existing duplicates** on the
next render. This is a recurrence of the same dup bug the 05-22 fix targeted — closed permanently
by keying on the namespace instead of enumerating paths.

**Key Decisions:**
- Path-agnostic identity via `harness_maker.*` module suffix, not path enumeration (→ ADR-001)
- Scope = `hooks.json` only, all 3 schemas; `settings.json` legacy `.sh` is a separate task (→ ADR-002)
- Self-heal: broadened normalization collapses stale ON-DISK dups against the template set (→ ADR-003)
- Ship as 0.26.6 (→ ADR-004)

**Estimated impact:** ~2-line regex/normalizer change in `render.py` + regression tests. Fixes the
leak for every consumer on any version bump or marketplace switch; existing victims (spoton-class)
auto-clean on their next `/hm:make --update`.

## 📚 Prior Work

- **`[wiki:pattern] schema-aware-json-merge-discriminator` (2026-05-22)** — the merge this PLAN
  fixes: `_entry_identity` = `(matcher, _normalize_hm_managed_command(command), type)`;
  `_merge_hooks_json` = per-event union (template entries + existing entries whose identity ∉
  template set). The 05-22 work introduced `_normalize_hm_managed_command` specifically to dedup
  across cache-version bumps — but scoped its regex to `harness-maker-local`. This PLAN broadens it.
- **`cursor-mdc-orphan-sweep` (0.26.5, this session)** — same defect class ("fails to recognize
  ours when an identifier changes"), different mechanism (file-level orphan sweep vs intra-file
  hook merge). Same per-path/per-namespace fingerprint principle.
- **Empirical residue:** `/tmp/hooks.json.bak` is `~/spoton`'s real triplicated file — 27 blocks
  (PostToolUse 6 / PreCompact 6 / PreToolUse 9 / SessionStart 3 / Stop 3), correct = 9 (2/2/3/1/1).
  Used as Phase 2 real-data validation.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|-------|----------|----------|--------|------|-------|
| 1 | 정규화 범위 | Architecture | how broadly to recognize harness hooks | Path-agnostic — `harness_maker.*` module namespace | not path enumeration | ADR-001 |
| 2 | 수정 범위 | Scope | hooks.json only vs + settings.json legacy .sh | hooks.json dedup only | settings.json separate task | ADR-002 |
| 3 | 배포 | Phasing | ship method | 0.26.6 bump + release | self-heals existing victims | ADR-003/004 |

Validator NEEDS_REVISION resolution (folded in as plan revisions — defensible-default, no
user-facing trade-off): suffix-based prefix-agnostic regex (W1), tightened self-heal scope +
template-internal-uniqueness test (W2), Phase 2 path-pinned exit (W3), matcher-less arg-collision
test (W4), `<HM_CACHE>`→`<HM>` test grep (W5), Phase 3 bump-then-regen ordering (S2). See §🔍 Plan Validation.

## 📐 Architecture Decision Records

### ADR-001: Path-agnostic harness-hook identity via the `harness_maker.*` module namespace
**Status:** Accepted (2026-05-28, via /hm:plan interview)
**Context:** The dedup normalizer enumerated one path family (`harness-maker-local`), so any other
plugin-resolution path (GitHub cache, dev-repo, future) produced un-deduped duplicate hooks.
**Decision:** Identify a harness-owned hook by the `python -m harness_maker.<invocation>` suffix of
its command, regardless of any prefix (`uv run`, `--with <path>`, intermediate uv flags). Normalize
its identity to `<HM>:<invocation>` where `<invocation>` = module + trailing args
(e.g. `harness_maker.hooks.loop_gate --mode stop-hook`). Non-matching commands round-trip unchanged.
**Consequences:**
- ✅ Robust to every current AND future plugin-path form — closes the recurrence class.
- ✅ `harness_maker.*` is our namespace, so a match is definitively ours (no false ownership).
- ⚠️ Two intentionally-different `--with` paths for the *same* module+args collapse to one
  (pathological; a user pinning a harness hook to an old version is unsupported — see ADR-003).
**Rejected alternatives:**
- Enumerate github-cache + dev-repo path patterns in the regex — Rejected: breaks again on the next
  unforeseen path shape; that's exactly this bug.
**Source:** Interview #1 + validator W1

### ADR-002: Scope = `hooks.json` only (all 3 schemas)
**Status:** Accepted (2026-05-28, via /hm:plan interview)
**Context:** `~/spoton` also carried stale legacy `.sh` hooks in `settings.json` (a different,
shallow-merge code path the current harness no longer writes hooks into).
**Decision:** Fix only the `hooks.json` merge (nested Claude/Codex + flat Cursor schemas). The
`settings.json` legacy-hook accumulation is a separate root cause → separate task.
**Consequences:**
- ✅ Tight scope, one normalizer change.
- ⚠️ `settings.json` stale `.sh` hooks remain until their own task.
**Rejected alternatives:**
- Bundle settings.json cleanup — Rejected: different merge mechanism, scope creep.
**Source:** Interview #2

### ADR-003: Self-heal collapses on-disk duplicates; does NOT dedup template-internal duplicates
**Status:** Accepted (2026-05-28, via /hm:plan interview + validator W2)
**Context:** The merge emits `list(new_entries) + user_entries` (render.py:718); it drops existing
entries whose normalized identity ∈ the template set, but never dedups the template's own entries.
**Decision:** Rely on self-heal for stale ON-DISK harness duplicates (they normalize to a template
identity → dropped on next render). Guard the template-side invariant — that synthesize renders
exactly one identity per (event, matcher, module) — with an explicit test, since the normalizer
cannot fix a template that emits internal duplicates.
**Consequences:**
- ✅ Existing victims (spoton-class) auto-clean on next `/hm:make --update`; no manual migration.
- ⚠️ A template-side Jinja duplication bug would ship undetected by the normalizer — hence the
  separate template-uniqueness test.
**Rejected alternatives:**
- Also dedup template-internal entries in the merge — Rejected: masks template bugs; the template
  is the source of truth and must be correct, not laundered by the merge.
**Source:** Interview #3 + validator W2

### ADR-004: Ship as 0.26.6
**Status:** Accepted (2026-05-28, via /hm:plan interview)
**Context:** The fix benefits every consumer; current released version is 0.26.5.
**Decision:** Bump 0.26.5 → 0.26.6 (5-file sync + CHANGELOG), release via the `release.yml` tag-push
pipeline; existing duplicated installs self-heal on their next re-render under 0.26.6.
**Consequences:**
- ✅ Universal fix; spoton's manual hooks.json clean (done this session) becomes unnecessary going forward.
- ⚠️ Public version churn — mitigated by the Phase 2 real-residue validation before the irreversible tag push.
**Rejected alternatives:**
- Fix + tests, defer release — Rejected: leaves all other consumers exposed.
**Source:** Interview #3

## 🏗️ Technical Design

### Current State
`render.py`:
- `_HM_CACHE_CMD_RE = r"^uv run --with \S*harness-maker-local/harness-maker/[^/\s]+ python -m (?P<module>\S+)"`
  — matches ONLY the local-cache path; captures module (drops trailing args).
- `_normalize_hm_managed_command(cmd)` → `<HM_CACHE>:<module>` on match, else `cmd` unchanged.
- `_entry_identity(entry, schema)` → `(matcher_or_"", normalized_command, type_or_"")`.
- `_merge_hooks_json` → per-event: `list(new_entries) + [existing whose identity ∉ template set]`.

The narrow regex is the entire defect: github-cache and dev-repo command forms fail the match,
keep full-command identities, and accumulate as pseudo-"user" entries.

### Affected Components
- `src/harness_maker/render.py` — `_HM_CACHE_CMD_RE` (→ `_HM_MANAGED_CMD_RE`) + `_normalize_hm_managed_command`. `_entry_identity` / `_merge_hooks_json` unchanged (already call the normalizer).
- `tests/unit/test_render.py` — extend the merge/dedup test set.
- Version files (5) + `CHANGELOG.md`; 8 `tests/snapshot/*.expected.yaml` (version bump).

### Dependencies
None added.

### Design Decision (→ ADR-001, W1)
Replace the anchored, path-specific regex with a prefix-agnostic **suffix** match on our namespace:

```python
# Matches any command that invokes one of our modules, regardless of the
# `uv run --with <path>` (or any future) prefix. Our `harness_maker.*` namespace
# is proof of ownership; the volatile path is irrelevant to hook identity.
_HM_MANAGED_CMD_RE = re.compile(r"(?:^|\s)python -m (?P<invocation>harness_maker\.\S.*)$")

def _normalize_hm_managed_command(cmd: str) -> str:
    m = _HM_MANAGED_CMD_RE.search(cmd)
    if m is None:
        return cmd
    return f"<HM>:{m.group('invocation')}"
```

`<invocation>` captures module **and trailing args** (so `loop_gate --mode stop-hook` ≠
`loop_gate --mode subagent-stop`). Prefix-agnostic `search` tolerates intermediate `uv` flags
(W1). `<HM>:` prefix is internal-only — consumed solely by `_entry_identity` → `_merge_hooks_json`
set ops, never persisted to disk or manifest (so the rename from `<HM_CACHE>:` is cosmetic; W5
verifies no test asserts the literal).

### Data Flow (before → after, spoton marketplace switch)
```
existing on disk:  [github-0.26.5, local-0.26.4, dev-repo]  for each (event,matcher,module)
template (new):    [github-0.26.6]                          for each (event,matcher,module)

BEFORE: local-0.26.4 normalizes (matched) but github/dev-repo do NOT → 3 distinct identities,
        only the template's github id in the template set → the other 2 preserved → duplicates.
AFTER:  all 3 normalize to <HM>:<invocation> == the template's identity → all 3 ∈ template set →
        none preserved as "user" → merged = template's single github-0.26.6 entry. Self-healed.
```

### API Changes
None. Internal normalizer behavior broadened; `_entry_identity` / `_merge_hooks_json` signatures and contracts unchanged.

## 📝 Implementation Plan

### Phase 1 — Broaden the normalizer + regression tests
- **depends_on:** []
- **parallel_group:** serial-fix
- **merge_hazards:** none
- **Scope (in):** `src/harness_maker/render.py` (`_HM_CACHE_CMD_RE`→`_HM_MANAGED_CMD_RE`, `_normalize_hm_managed_command` + docstring); `tests/unit/test_render.py`.
- **Scope (out):** `_entry_identity`/`_merge_hooks_json` logic, settings.json, version files.
- **Pre-step (W5):** `grep -rn '<HM_CACHE>\|<HM>:' tests/` — update any test asserting the literal prefix in the same commit.
- **Regression cases (test_render.py):**
  - (a) **KEEP green** the existing 05-22 local-cache version-bump dedup test (no regression).
  - (b) github-cache version-bump (0.26.5→0.26.6) → single entry.
  - (c) marketplace-switch: existing = {local-0.26.4 + dev-repo} entries, template = github-0.26.6 → exactly 1 entry per (event,matcher,module) = the github one.
  - (d) full triplication self-heal: existing carries all 3 path forms → collapses to 1 each.
  - (e) user-authored non-harness `uv run` hook (e.g. `…/my-check.sh`) → preserved.
  - (f) **W1:** command with an intermediate uv flag (`uv run --with <path> --python 3.12 python -m harness_maker.telemetry`) still normalizes/dedups.
  - (g) **W4:** matcher-less collision — two `Stop` `loop_gate` entries with `--mode stop-hook` vs `--mode subagent-stop` stay distinct; same module+args across two paths collapse to one.
  - (h) Cursor flat-schema (`.cursor/hooks.json`) dedups identically.
  - (i) **W2:** assert the REAL rendered nested template (synthesize output, not a hand-built dict) has exactly one unique identity per (event,matcher,module) — guards the template-side invariant self-heal depends on.
- **Exit criterion:** `uv run pytest tests/unit/test_render.py -q` green AND full `uv run pytest tests/unit/` green AND `uv run mypy --strict src/` AND `uv run ruff check src/ tests/` + `ruff format --check`.
- **Risk:** medium (merge correctness governs whether user hooks survive).
- **Rollback point:** revert `render.py` to current HEAD.

### Phase 2 — Pre-release validation against the REAL triplicated residue
- **depends_on:** [1]
- **parallel_group:** serial-fix
- **merge_hazards:** none
- **Scope (in):** one-off script — load `/tmp/hooks.json.bak` (spoton's real 27-block file) as `existing`, render the nested `hooks.json` template fresh (0.26.6 github path), run `_merge_hooks_json`, assert the result.
- **Exit criterion (W3 — path-pinned, not count-only):**
  1. Total blocks 27 → **9**, per-event 2/2/3/1/1.
  2. **Every** surviving command's `--with` path == the exact 0.26.6 GitHub-cache form the release ships.
  3. **Zero** surviving commands contain `-local` OR `/home/noel/harness-maker` (dev-repo token).
- **Risk:** low (read-only; tmp fixture; no real-FS mutation).
- **Rollback point:** Phase 1 state.

### Phase 3 — Version bump 0.26.6 + snapshot regen
- **depends_on:** [2]
- **parallel_group:** serial-release
- **merge_hazards:** the 5 version files move together (`.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`) + `CHANGELOG.md`.
- **Scope (in):** **(S2 ordering)** (1) bump 0.26.5→0.26.6 in the 5 files + CHANGELOG, THEN (2) regenerate the 8 synthesize snapshots **from the main repo** (`uv run python tests/snapshot/regenerate.py`) so the embedded 0.26.6 version is captured (per `[fail:test] snapshot-regen-inside-worktree`).
- **Exit criterion:** `grep -l 0.26.5` among the 5 files = empty; all show 0.26.6; CHANGELOG has a 0.26.6 entry; snapshot regen produces only version-delta changes; full `tests/unit/` green from main (incl. regenerated snapshots).
- **Risk:** low.
- **Rollback point:** Phase 2 state.

### Phase 4 — Release (tag push → release.yml)
- **depends_on:** [3]
- **parallel_group:** serial-release
- **merge_hazards:** none.
- **Scope (in):** advisory boundary tests (`INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py`), then `git tag -a v0.26.6 -m "…"; git push origin main v0.26.6`. **No manual `gh release create`** (CLAUDE.md race).
- **Exit criterion:** `gh run list --workflow release.yml` shows the v0.26.6 run green (all jobs).
- **Risk:** medium — **irreversible** once published; forward-fix only via a new patch tag. Phase 2 is the guard that makes this acceptable.
- **Rollback point:** none (immutable); fix-forward with 0.26.7.

## 🧪 Testing Strategy

- **Unit (Phase 1):** cases (a)–(i) in `tests/unit/test_render.py` — covers both schemas, all 3 path
  forms, intermediate-flag robustness, matcher-less arg collision, user-hook preservation, and the
  template-internal-uniqueness guard.
- **Real-data (Phase 2):** the actual spoton triplicated `hooks.json` (`/tmp/hooks.json.bak`) → 27→9,
  path-pinned to 0.26.6 GitHub, zero stale tokens.
- **Release advisory (Phase 4):** boundary-parse suite.
- **Manual:** none required (the fix is internal; consumers self-heal on next render).

## ⚠️ Risks & Mitigation

| Risk | Sev | Mitigation |
|------|-----|------------|
| Over-merge collapses a genuine user hook | med | Match requires the `python -m harness_maker.*` namespace; user hooks running other tooling never match → preserved (test e). |
| Regex breaks on a future command shape (intermediate flags) | med | Prefix-agnostic `search` on the namespace suffix (W1); pinned by test (f). |
| Template-internal duplication ships undetected | low | ADR-003 + test (i) assert the rendered template has one identity per (event,matcher,module). |
| Self-heal removes a user-pinned old-version harness hook | low | Accepted (ADR-003) — harness hooks are ours; pinning is unsupported. |
| Wrong-version template passes Phase 2 on count alone | low | Phase 2 exit pins surviving path to the 0.26.6 GitHub form + asserts zero stale tokens (W3). |
| Snapshot drift from version bump | low | Regen from main, bump-then-regen order (S2). |

## ✅ Success Criteria

- [x] `_normalize_hm_managed_command` matches all harness-hook command forms via the `harness_maker.*` suffix (path-agnostic).
- [x] Regression cases (a)–(i) pass; full unit + `mypy --strict` + ruff green.
- [x] Phase 2: `/tmp/hooks.json.bak` (27 blocks) collapses to 9, all on the 0.26.6 GitHub path, zero `-local`/dev-repo tokens.
- [x] 5 version files + CHANGELOG at 0.26.6; snapshot regen from main produced no diff (version not in body-hashed content here).
- [x] `release.yml` v0.26.6 run green — triggered by this wrapup's tag push (Phase 4); monitored to completion below.

## 🔍 Plan Validation

**Validator outcome:** NEEDS_REVISION → **resolved** (no critical findings; diagnosis + fix confirmed
against source). All warnings/suggestions folded in as revisions:

| # | Finding | Sev | Resolution |
|---|---------|-----|------------|
| W1 | Anchored regex narrower than ADR-001; brittle to intermediate uv flags | warning | Switched to prefix-agnostic `search` on the `python -m harness_maker.*` suffix; test (f). |
| W2 | Self-heal wording conflates on-disk vs template-internal dedup | warning | Tightened ADR-003; added template-uniqueness test (i). |
| W3 | Phase 2 exit count-only could pass a wrong-version template | warning | Exit now pins survivors to 0.26.6 GitHub path + zero stale tokens. |
| W4 | Missing matcher-less arg-collision test | warning | Added test (g) (loop_gate `--mode` discriminator, matcher-less). |
| W5 | Prefix rename `<HM_CACHE>`→`<HM>` may break a test asserting the literal | warning | Phase 1 pre-step greps tests for the literal. |
| S1 | Existing 05-22 tests stay green | suggestion | Verified; explicit KEEP-green case (a). |
| S2 | Phase 3 bump-then-regen ordering | suggestion | Sequenced explicitly in Phase 3 scope/exit. |

**Clean (validator):** rollback-strategy, adr-completeness, scope-drift-hazards, spec-alignment.

## 🚦 Execution Status (2026-05-28, /hm:execute)

| Phase | Status | Notes |
|---|---|---|
| 1 — broaden normalizer + 7 regression tests | ✅ DONE | `_HM_CACHE_CMD_RE`→`_HM_MANAGED_CMD_RE` (prefix-agnostic `python -m harness_maker.*` suffix, module+args). test-reviewer PASS; RED→GREEN confirmed (6 tests RED pre-fix). W5 grep clean (no literal `<HM_CACHE>` in tests). |
| 2 — real-residue validation | ✅ DONE | `/tmp/validate_hooks_dedup.py` merged spoton's actual `/tmp/hooks.json.bak` (27 blocks) against the 0.26.6-github template → collapsed to **9** (2/2/3/1/1), zero `-local`/dev-repo tokens, all on 0.26.6 GitHub path. PASS. |
| 3 — 0.26.6 bump + snapshot regen | ✅ DONE | 5 files + CHANGELOG → 0.26.6; uv.lock re-pinned; version-sync tests pass; snapshot regen from main produced **no diff** (version not in body-hashed content here) — full `tests/unit/` green from main. |
| 4 — release (tag push → release.yml) | ⏳ PENDING (user) | Out of execute scope — push is user-initiated. After wrapup. |

**Phase D (all GREEN from main):** ruff ✓ · ruff format ✓ · `mypy --strict src/` ✓ · full `tests/unit/` ✓.

**Stage exit:** 9 files staged on `main`, NO commit (HEAD unchanged at `8539f61`). Worktree `execute-e29fe520bfd9-20260528T0634Z` finalized stage-only + cleaned; drift = the 9 intended files only.
