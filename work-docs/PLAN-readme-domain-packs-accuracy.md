---
type: plan
task_slug: readme-domain-packs-accuracy
status: complete
created: 2026-05-19
tags: [harness-maker, plan, docs, readme, accuracy]
interview_rounds: 0
adrs: 0
validator_outcome: SKIPPED_LOW_RISK
summary: "Correct README's Domain Packs claims to match shipped implementation (python-only sample, standards-only graft)."
---

## 🎯 Executive Summary

**TL;DR.** README (lines 143, 358) advertises `--add-domain python|node|rust` as
grafting "standards, agents, and skills". Reality: only `python` ships with a
real standards file; `node` / `rust` get the same blank user-stub treatment as
any custom name; no `agents` or `skills` grafting mechanism exists. Fix the two
lines.

**What.** Two surgical edits to `README.md` (≤10 lines net diff). No code change.

**Why.** User audit flagged README ≠ reality. Misleading marketing for a 0.17.x
docs / accuracy patch. Cheapest path to close the gap (interview Step 0 skip
heuristic: single file, no architecture/contract change, fully reversible).

**Key decisions.** None promoted to ADR — see "Interview Transcript" skip note.

**Estimated impact.** README only. CHANGELOG entry. Affects no installed
harnesses, no tests, no version bump required (docs-only is conventional
patch-version material, but this can ride the next release).

## 🎙️ Interview Transcript

**Interview skipped (Step 0 — all 4 criteria hold):**
- Scope: single file (`README.md`).
- Architecture: no component / module change.
- Contracts: no API / file-format change.
- Risk: reversible <1h, no installed-harness impact, no behavior change.

User chose "README 정직화 (최소 작업)" from the up-front direction picker
(Claude session, 2026-05-19). The remaining decision — *what* the corrected
text should say — is captured directly in `## 🏗️ Technical Design` below.

## 🏗️ Technical Design

### Current state (verified 2026-05-19)

- `src/harness_maker/cli.py:37` — `_SHIPPED_DOMAIN_SAMPLES = frozenset({"python"})`.
  `--add-domain python` skips stub creation (line 357 branch) and only appends
  `python` to `harness.yaml.project.domains`.
- `src/harness_maker/templates/agents/_standards/` ships exactly **two** files:
  `python.md.j2` (real rules) + `_template.md.j2` (blank skeleton). No
  `node.md.j2`, no `rust.md.j2`.
- 5 reviewer body templates inline domain standards via
  `{% for d in config.project.domains %}{% include "agents/_standards/" + d + ".md.j2" ignore missing %}`.
  `ignore missing` is what makes unknown names silently render nothing — this
  is what lets `--add-domain node` "appear to work" while contributing zero
  actual content until the user fills the stub.
- **Zero** templates dispatch agents or skills by domain. The README's "agents,
  and skills" promise has no implementation hook.

### Affected files

- `README.md` (only).

### Corrected wording

**Line 143** (currently inside "Layered on top of the base render"):

```markdown
- **Domain packs** — `--add-domain python` inlines a stack-specific standards block
  into the 5 reviewer agents (code, security, performance, concurrency, ux).
  `python` ships as the only sample today; `--add-domain <other>` scaffolds a
  blank user-side stub at `.claude/agents/_standards/<name>.md` for teams to fill
  in without forking harness-maker.
```

**Line 358** (currently inside "🎯 Personalization — *fits your project*"):

```markdown
- **Domain packs.** `--add-domain python` inlines stack-specific standards into
  the 5 reviewer agents. Today `python` is the only pre-filled sample; other
  domain names scaffold blank user-side stubs that teams fill in without forking
  harness-maker.
```

Both rewrites:
- Drop the "or `node`, `rust`" parenthetical (false: those names don't ship).
- Drop "agents, and skills" (false: no such mechanism).
- Keep the truthful pieces: reviewer-inlining, custom-domain stubs, no-fork
  workflow.
- Keep line 359's `--add-domain` flag mention as-is (the flag exists).

### Out of scope (deliberate)

- Building actual `node` / `rust` standards packs.
- Adding any per-domain agent or skill dispatch mechanism.
- Touching `_SHIPPED_DOMAIN_SAMPLES` or `cli.py`.
- Changing `--add-domain` CLI behavior.
- CHANGELOG entry style or version bump — handled at next release-prep, not in this PLAN.

## 📝 Implementation Plan

### Phase 1 — Edit README

- **Scope (in):** `README.md` lines 143 (Section "How it fits your project") and 358 ("🎯 Personalization") rewritten per "Corrected wording" above.
- **Scope (out):** every other file in the repo.
- **Exit criterion:**
  - `grep -n "or \`node\`, \`rust\`" README.md` → no output.
  - `grep -n "agents, and skills" README.md` → no output.
  - `grep -n "Domain packs" README.md` → 2 matches (lines 143-ish, 358-ish, exact line numbers may shift).
  - `grep -n "agents/_standards" README.md` → ≥1 match (new wording references the path).
- **Risk:** low.
- **Rollback:** `git checkout README.md` (single-file revert).

## 🧪 Testing Strategy

- **Manual:** Diff inspection — confirm the two bullets read truthfully and adjacent prose still flows.
- **Mechanical:** the four `grep` commands above (run after edit, before commit).
- **No unit/integration tests** — README is not under test, and adding one for two prose lines would over-fit.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Future contributor sees the "stub" wording and tries to add `node`/`rust` packs without realising the README was just deflating expectations. | low | low | Phase 1 wording explicitly says "today" and "only sample" — invites future expansion, doesn't claim it's done. |
| User who liked the original framing assumes we're scaling back the product. | very low | low | We're not — only correcting documentation. If the user later chooses the "Full domain pack infra" branch (option 3 from the upfront picker), the wording can be re-expanded then. |
| Markdown lint / line-length rule trips on the rewritten bullet. | low | trivial | Wrap at the same width as adjacent bullets in each section. |

## ✅ Success Criteria

- [x] Line 143-equivalent bullet replaced with the corrected wording.
- [x] Line 358-equivalent bullet replaced with the corrected wording.
- [x] All 4 `grep` checks from Phase 1 exit criterion pass.
- [x] Manual read-through: surrounding paragraphs in "How it fits your project" and "🎯 Personalization" still flow naturally.
- [x] No other file modified.

## 🔍 Plan Validation

Validator skipped — interview-skip path. Outcome recorded as
`SKIPPED_LOW_RISK` in frontmatter. Rationale: a two-line README correction
does not benefit from `plan-validator` critique; the cost of running the
agent exceeds the risk it would catch. If future-you disagrees, re-run
`/hm:plan` and override the Step 0 skip explicitly.
