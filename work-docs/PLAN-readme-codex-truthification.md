---
type: plan
task_slug: readme-codex-truthification
status: complete
created: 2026-05-22
tags: [harness-maker, plan, docs, readme, codex, multi-ide]
interview_rounds: 1
adrs: 1
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Truthify README/about docs about Codex install path (Claude Code is install manager today)."
---

## 🎯 Executive Summary

**TL;DR:** The README and several peer docs currently claim a working
`codex plugin marketplace add Ecro/harness-maker` install path. Empirical
test in this session (2026-05-22) showed Codex accepts the marketplace
registration but cannot find any plugin in it — we ship no Codex
`marketplace.json`, only `.codex-plugin/plugin.json` (a single-plugin
manifest). Codex CLI install is functionally **broken** today.

**What:** Rewrite all docs that claim standalone Codex install to reflect
the actual architecture — **Claude Code's plugin manager is the canonical
install path**; Codex and Cursor consume the *rendered artifacts* (hooks,
agents, skills, AGENTS.md) produced by `harness-maker make`. The
`uv run --with <claude-plugin-cache>` reference in `.codex/hooks.json`
makes this dependency visible already; docs need to catch up.

**Why:** Same regression class as `[wiki:gotcha] readme-one-prompt-bash-not-slash`
(2026-05-19) — README promised an install path the AI agent couldn't
actually deliver. That fix updated the *delivery mechanism* (Bash vs slash);
this one updates the *promise itself* (Codex parity vs Claude-Code-mediated).

**Key decisions:** see [ADR-001](#adr-001-codex-install-path-truthification).
- Tone: just state current reality, no future commitments.
- `.codex-plugin/plugin.json`: keep + clarify description.
- Release: single commit on main, no version bump.
- Regression defense: deferred (this PR is doc-only).

**Estimated impact:** ~10 file edits, mostly README + peer docs. No code,
no template, no test changes. Total ~1-2h.

## 📚 Prior Work

- **`[wiki:gotcha] readme-one-prompt-bash-not-slash` (2026-05-19)** —
  Direct precedent. README promised that AI agents could `/plugin install`
  for the user; in reality the assistant can't invoke built-in slash
  commands, so install commands were rewritten as `Bash: claude plugin
  marketplace add …`. The lesson recorded then: *"Per-IDE step budgets
  must be stated honestly in the README because non-Claude-Code IDEs
  (Cursor reload-window, Codex restart) can't reach the same headline."*
  This PLAN extends that principle from delivery mechanism to install path.
- **`[wiki:pattern] universal-cross-platform-install-prompt` (2026-05-17)** —
  The current Universal Bootstrap Prompt was reviewed for OS detection
  but not for IDE-install command validity. This PLAN re-validates the
  Codex branch.
- **`[wiki:pattern] oss-launch-readiness-three-layer` (2026-05-19)** —
  Layer 2 "Positioning surface" includes README accuracy. Truthification
  fits this layer's invariant ("README hero must reflect what the install
  actually does").
- **`[wiki:model-routing-multi-ide]` (2026-05-18, 0.15.0)** — Multi-IDE
  rendering shipped. The architecture decision then was Claude Code's
  `.claude/` as the *single source of truth*, with `.cursor/` and `.codex/`
  as sibling target-native renders. The README doc started overpromising
  per-IDE install parity around this time. This PLAN aligns docs back to
  that architecture.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|---|---|---|---|---|---|
| 1 | Future-Codex-marketplace signal tone | Scope | "현재 상태만 명시" vs "+ future intent" vs "+ GitHub issue link" | A — 현재 상태만 명시 | No future commitments; pure truthification | ADR-001 |
| 2 | `.codex-plugin/plugin.json` fate | Architecture | Keep + clarify vs keep as-is vs delete | A — 유지 + description 명확화 | Preserves 5-file version sync; manifest stub stays for future use | — |
| 3 | Release unit | Process | Single commit on main vs 0.23.5 patch release | A — 단일 commit on main | Doc-only; no version-bump needed for users not on the misleading branch | — |
| 4 | Regression defense | Risk | Add CI test of README install commands vs defer | B — 추가 안 함 | Doc-only scope; same-class bug repeat triggers structural defense | — |

## 📐 Architecture Decision Records

### ADR-001: Codex install path truthification
**Status:** Accepted (2026-05-22, via /hm:plan interview)
**Context:** README and peer docs claim `codex plugin marketplace add
Ecro/harness-maker` is a working install path. Empirical test 2026-05-22
showed Codex accepts the marketplace registration but `codex plugin add
harness-maker@harness-maker` fails with "plugin `harness-maker` was not
found in marketplace `harness-maker`" because the repo ships no Codex
`marketplace.json`. The `.codex/hooks.json` artifacts already reference
`~/.claude/plugins/cache/harness-maker-local/...` — the design has always
been Claude-Code-mediated; only the docs lied.
**Decision:** All docs are rewritten to state the current reality: Claude
Code is the install manager. Codex and Cursor consume the rendered
artifacts produced by `harness-maker make`. **No future-tense commitments**
about native Codex marketplace install. **No GitHub issue** filed
(intentional — preserves freedom to walk away from native Codex install
entirely if it never becomes a real demand).
**Consequences:**
- ✅ Docs match the architecture; users no longer hit the empty-marketplace error.
- ✅ Honest signaling: Codex-only users (no Claude subscription) learn the
  prerequisite upfront, not after install attempt.
- ⚠️ Reads less aggressive than the prior "three IDEs, three install
  paths" framing. Codex-only users may bounce.
- ⚠️ No regression guard against re-promising IDE parity in future README
  edits. (Q4 deferred; if same class of bug repeats, add CI install-cmd test.)
- **Re-open trigger:** if the "README overpromises IDE parity" failure
  class recurs a *third* time (precedent count: 2026-05-19
  `readme-one-prompt-bash-not-slash` + 2026-05-22 this PLAN = 2 so far),
  promote the deferred Q4 CI install-command test immediately as a P0
  follow-up. Two recurrences = pattern; three = structural defect.
**Rejected alternatives:**
- **Future-intent signal** ("native Codex marketplace planned") — Rejected
  because it commits without ETA and without confirmed demand. Users would
  ask "when?" and we have no answer.
- **GitHub issue + roadmap link** — Rejected for the same reason as above
  plus PR-burden risk (someone may submit a half-working marketplace PR
  that requires our review effort).
- **Patch release 0.23.5** — Rejected because doc-only changes don't need
  the 5-file version sync overhead. CHANGELOG `[Unreleased]` is enough.
- **Delete `.codex-plugin/plugin.json`** — Rejected because the version
  sync property + future-use option outweighs the "currently misleading"
  concern. We update its `description` field instead.
**Source:** Interview #1, #2, #3, #4 (whole-batch round)

## 🏗️ Technical Design

### Current State

- README hero (Universal Bootstrap Prompt) line 53-66 + 204-251 claim
  three parallel IDE install paths: `claude plugin marketplace add`,
  `git clone ~/.cursor/plugins/local/`, `codex plugin marketplace add`.
- `docs/BOOTSTRAP.md` line 50-53 has a Codex CLI install section with
  the same broken command.
- `tests/codex-compat/MANUAL_CHECKLIST.md` step 1 ("install") is marked
  **BLOCK threshold** — meaning a launch decision currently depends on
  a step that we can't pass.
- `.codex-plugin/plugin.json` exists with `version: 0.23.4` and a
  description that doesn't acknowledge the install constraint.

### Affected Components

| File | Section | Change kind |
|---|---|---|
| `README.md` | Universal Bootstrap Prompt; Bash-approval note (line 66); Manual install; comparison table | Rewrite |
| `README.ko.md` | Mirror of above | Rewrite (translate-aligned) |
| `docs/BOOTSTRAP.md` | Codex CLI section | Replace install command block |
| `tests/codex-compat/MANUAL_CHECKLIST.md` | Step 1 threshold + sub-steps | Re-scope or remove |
| `tests/cursor-compat/MANUAL_CHECKLIST.md` | Line 370 (Codex bootstrap mention) | Remove or re-scope |
| `.codex-plugin/plugin.json` | `description` field | Clarify install path |
| `.claude-plugin/plugin.json` | `description` (peer consistency) | Mild edit |
| `.cursor-plugin/plugin.json` | `description` (peer consistency) | Mild edit |
| `.claude-plugin/marketplace.json` | description text | Light edit |
| `CHANGELOG.md` | `[Unreleased]` section | Add docs entry |
| `.claude/memory/wiki.md` | inside `<!-- @hm:user:entries -->` block | Add wiki entry documenting fix |

### Out-of-scope (NOT touching)

- `docs/HOW-IT-WORKS.md`, `docs/ARCHITECTURE.md` — Codex mentions are
  architectural context, not install claims.
- `docs/release-checklist.md`, `docs/reference/preservation-matrix.md`,
  `docs/assets/showcase-diff.md` — passing mentions only.
- Code paths (`src/`), templates (`templates/`), tests (`tests/unit/`,
  `tests/integration/` outside compat manual checklists) — no code changes.
- 5-file version sync — release unit is "commit on main", not a tagged release.
- GitHub issue creation, social posts — no roadmap commitments.
- **`CHANGELOG.md` historical release entries (lines 613, 646 currently
  contain `codex plugin marketplace add Ecro/harness-maker` as part of
  prior release notes)** — DO NOT rewrite. Historical CHANGELOG entries
  are factual records of what the README said at the time of release;
  retroactively editing them corrupts the audit trail. The R2 final
  grep sweep will surface these matches — executor must skip them with
  this rationale, not edit them.

### Data Flow

No code, no data-flow changes.

### API Changes

None.

### Design Decisions

- **Doc strategy (ADR-001)** — Current reality only. No future tense.
- **Manifest description wording** — Keep the IDE list ("Claude Code · Cursor · Codex")
  because those ARE the three IDEs whose rendered artifacts work. Add a
  short clause stating Claude Code is the install manager.
- **Translation alignment** — `README.ko.md` is rewritten in the same
  PR as `README.md` to prevent en/ko drift. Translation done LLM-side
  in-session; user is invited to skim.

## 📝 Implementation Plan

### Phase 1 — `README.md` rewrite (BLOCK)
**Scope IN:** `README.md` — Universal Bootstrap Prompt branch logic, Manual
install table, Manual install per-IDE sections, comparison table.
**Scope OUT:** Everything else in the README (project pitch, features
list, etc.) unless a passing claim contradicts ADR-001.
**Exit criterion:** `grep -nE "codex plugin marketplace add Ecro/harness-maker"
README.md` returns no matches; new Codex section explicitly states the
Claude-Code-prerequisite.
**Risk:** medium (high user visibility; first-impression text).
**Rollback:** `git checkout HEAD -- README.md` (pre-commit) or
`git revert <hash>` (post-commit).

### Phase 2 — `README.ko.md` rewrite (mirror)
**Scope IN:** `README.ko.md` matching all Phase 1 edits.
**Scope OUT:** Other Korean docs (none currently in scope).
**Exit criterion:** Two concrete checks must both pass:
1. `grep -nE "codex plugin marketplace add" README.ko.md` returns 0.
2. Heading parity holds: `diff <(grep -E '^#' README.md) <(grep -E '^#' README.ko.md)` shows only translated-text differences (same number of lines, same heading depth). Structural alignment is the runnable signal; word-level translation accuracy is human-eyeballed in Step 6 verification.
**Risk:** low (mechanical mirror).
**Rollback:** same as Phase 1.

### Phase 3 — `docs/BOOTSTRAP.md` rewrite
**Scope IN:** `docs/BOOTSTRAP.md` — the explicit "Codex CLI" install section.
**Scope OUT:** Other sections of BOOTSTRAP unless they make the same false
claim.
**Exit criterion:** Codex CLI section no longer shows `codex plugin marketplace
add Ecro/harness-maker`; instead describes the Claude-Code-mediated path
+ what Codex users get (rendered artifacts).
**Risk:** low.
**Rollback:** `git checkout HEAD -- docs/BOOTSTRAP.md`.

### Phase 4 — `tests/codex-compat/MANUAL_CHECKLIST.md` + `tests/cursor-compat/MANUAL_CHECKLIST.md` re-scope
**Scope IN:**
- `tests/codex-compat/MANUAL_CHECKLIST.md` — step 1 install (currently BLOCK threshold), BLOCK/DEFER table at the top.
- `tests/cursor-compat/MANUAL_CHECKLIST.md` line 370 (its Codex-bootstrap mention).
**Scope OUT:** other steps (discovery / interview / AGENTS.md / `.codex/*`
render) which still validate post-`make` reality; cursor-compat steps
unrelated to Codex.
**Exit criterion:** Two concrete checks:
1. `tests/codex-compat/MANUAL_CHECKLIST.md` step 1 either (a) removed entirely with rationale, OR (b) re-scoped to verify `codex` binary present + `.codex/hooks.json` references a valid Claude-Code plugin cache. BLOCK/DEFER table updated to reflect the new step 1.
2. `grep -nE "codex plugin marketplace add Ecro/harness-maker" tests/codex-compat/MANUAL_CHECKLIST.md tests/cursor-compat/MANUAL_CHECKLIST.md` returns 0.
**Risk:** low (internal QA docs).
**Rollback:** same.

### Phase 5 — Manifest + marketplace.json description updates
**Scope IN:** `.codex-plugin/plugin.json` description field,
`.claude-plugin/plugin.json` + `.cursor-plugin/plugin.json` for peer
consistency, `.claude-plugin/marketplace.json` if its description text
makes the same false claim.
**Scope OUT:** Other JSON fields (name, version, license, keywords).
**Exit criterion:** All three plugin manifests + marketplace.json have
descriptions consistent with ADR-001 (Claude Code as install manager;
Codex/Cursor consume rendered artifacts).
**Risk:** low (descriptions are UI-strings; no parser cares about wording).
**Rollback:** same.

### Phase 6 — Memory wiki entry + CHANGELOG `[Unreleased]`
**Scope IN:**
- `.claude/memory/wiki.md` — append new entry **INSIDE** the
  `<!-- @hm:user:entries -->` … `<!-- @hm:/user:entries -->` block,
  documenting the truthification pattern (so the next README edit
  catches it).
- `CHANGELOG.md` — add `[Unreleased]` docs entry above `[0.23.4]`.
**Scope OUT:**
- `failures.md` (this isn't a code failure, it's a doc overreach;
  `wiki.md` is the right tier).
- Historical CHANGELOG entries containing the misleading command (see
  Out-of-scope note in Technical Design).
**Exit criterion:** Three concrete checks:
1. `wiki.md` has new entry inside the marker block (NOT at EOF). Verify via:
   `awk '/<!-- @hm:user:entries -->/,/<!-- @hm:\/user:entries -->/' .claude/memory/wiki.md | grep -q '\[wiki:.*codex-marketplace-readme-overpromise'`
   (matches the new slug between the two markers; guards the exact failure mode in `[wiki:gotcha] wrapup-marker-discipline-silent-loss`).
2. `CHANGELOG.md` has `[Unreleased]` section above `[0.23.4]` line. Verify:
   `grep -B1 '## \[0.23.4\]' CHANGELOG.md | head -1` contains `## [Unreleased]` (or the file structure shows `[Unreleased]` somewhere above `[0.23.4]`).
3. The `[Unreleased]` entry references this PLAN by filename.
**Risk:** medium (wiki marker discipline — known footgun).
**Rollback:** same.

### Phase 7 — Commit + push to main
**Scope IN:** Stage all Phase 1-6 changes in one focused commit.
**Scope OUT:** Memory frontmatter dirt (pre-existing from earlier sessions).
**Exit criterion:** `git log -1 --stat` shows one commit titled e.g.
"docs(readme): truthify Codex install path"; `git status` clean for
Phase 1-6 files; main pushed.
**Risk:** low (no version bump = no workflow gate).
**Rollback:** `git revert <hash>` + push.

## 🧪 Testing Strategy

- **Unit:** N/A — no code.
- **Integration:** Manual `codex plugin marketplace add /home/noel/harness-maker`
  + `codex plugin add harness-maker@harness-maker` to confirm the previously
  misleading command still fails identically (regression: if some future
  template change accidentally adds a Codex marketplace.json, the test
  would unexpectedly succeed and that's a signal we should re-evaluate
  ADR-001).
- **Manual (positive check):** Side-by-side read of README before/after
  to confirm:
  (a) hero one-prompt no longer offers Codex install instruction;
  (b) Codex users can find the Claude-Code-prereq instruction at the same
  reading depth (not buried in a footnote);
  (c) Korean version matches English structure;
  (d) **A Codex-only reader (no Claude subscription) can identify both
  the prerequisite AND the install path in the first reading pass** —
  if they have to search for it, the truthification rewrite is incomplete.
  This is human eyeballing but stating it explicitly ensures the
  "are users going to bounce?" Risk R3 mitigation actually got checked.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | en/ko translation drift after edit | medium | medium (Korean users see different content) | Rewrite both in same session; LLM does the translation; final diff review |
| R2 | Forgotten claim in a doc I didn't grep | low | low (next grep catches it; reversible) | Final sweep `grep -rnE "codex plugin marketplace add Ecro" --include="*.md"` before commit |
| R3 | Codex-only users feel project doesn't support them | medium | low (real OS users prioritize honest signaling) | Truthful tone; do NOT remove Codex from feature lists where rendered artifacts truly work |
| R4 | Same bug class recurs in 6 months | medium | medium ("README overpromises IDE parity" is now twice in 6 months) | Accepted risk (Q4 deferred); if 3rd recurrence, add CI install-cmd test then |
| R5 | Removing `tests/codex-compat/MANUAL_CHECKLIST.md` step 1 weakens launch readiness gate | low | low (we never could pass step 1 anyway; removing it is honesty) | Replace, don't simply delete — step 1 becomes "Codex binary present + `.codex/hooks.json` references valid Claude-Code cache" |

## ✅ Success Criteria

- [x] `grep -rnE "codex plugin marketplace add Ecro/harness-maker"
      README.md README.ko.md docs/ tests/codex-compat/` returns 0 matches.
- [x] README Universal Bootstrap Prompt either omits Codex install branch
      OR replaces it with the Claude-Code-prereq instruction.
- [x] `tests/codex-compat/MANUAL_CHECKLIST.md` step 1 either removed or
      re-scoped consistent with ADR-001; BLOCK/DEFER table updated.
- [x] `.codex-plugin/plugin.json` description text clarifies install path.
- [x] Peer manifests (`.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`)
      have peer-consistent descriptions.
- [x] `.claude/memory/wiki.md` new entry inside `<!-- @hm:user:entries -->`
      block documents the truthification pattern.
- [x] `CHANGELOG.md` `[Unreleased]` section bullet links this PLAN.
- [x] Single commit on main; no version bump; no tag push.

## 🔍 Plan Validation

**Round 1 outcome:** `NEEDS_REVISION` (3 P1, 2 P2, 1 P3).
**Resolution:** All 6 critiques applied directly in the PLAN body (no
new interview rounds required — all critiques refine plan body
mechanics, not user-locked decisions). Summary:

| # | Severity | Critique | Resolution |
|---|---|---|---|
| 1 | P1 | `tests/cursor-compat/MANUAL_CHECKLIST.md` line 370 missing from Affected Components | Added to Affected Components table + Phase 4 scope (now covers both cursor-compat and codex-compat manual checklists) |
| 2 | P1 | Phase 6 wiki marker exit criterion didn't guard against EOF-append (the `[wiki:gotcha] wrapup-marker-discipline-silent-loss` failure mode) | Replaced exit criterion with `awk` range match between the two markers + slug grep |
| 3 | P1 | CHANGELOG historical entries contain misleading command; R2 sweep would block commit without rationale | Added explicit Out-of-scope note: historical CHANGELOG entries are immutable factual records; executor skips them in R2 sweep |
| 4 | P2 | Phase 2 "structure matches" clause unverifiable LLM self-judgment | Replaced with `diff` of `grep -E '^#'` outputs (heading parity check is runnable) |
| 5 | P2 | ADR-001 didn't self-document re-open trigger | Added explicit "Re-open trigger" line to ADR Consequences |
| 6 | P3 | Testing Strategy missing positive verification of the new wording | Added explicit Codex-only-reader first-pass check to manual section |

Re-validate not invoked (validator threshold says re-validate only on
MAJOR_REVISION resolutions; NEEDS_REVISION → write PLAN and proceed).
Final `validator_outcome: NEEDS_REVISION_RESOLVED`.
