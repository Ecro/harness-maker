---
type: research
task_slug: playbook-alignment
status: complete
created: 2026-09-16
tags: [harness-maker, research, python, jinja2, intent-layer, playbook, deliverables, world-state]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://claude.com/blog/the-ai-native-sdlc-playbook
  - https://waydev.co/anthropics-ai-native-sdlc-playbook-has-a-missing-layer-measurement/
  - https://www.genai-playbook.com/articles/ai-native-sdlc-playbook-en.html
  - https://menuagentic.com/blogs/ai-native-sdlc-artifact-chain/
related_docs:
  - "[[SPEC-intent-world-model-objective-layer]]"
  - "[[PLAN-intent-world-model-objective-layer]]"
  - "[[REVIEW-intent-world-model-objective-layer-2026-09-16]]"
  - "[[RESEARCH-cell-dev-future-and-intent-layer-fit]]"
  - "[[wiki:architecture] two-roots-versioned-state-vs-operational-events"
  - "[[wiki:gotcha] one-rendered-command-size-has-four-normative-sites"
  - "[[fail:design] git-identity-read-at-wrong-root-despite-spec-decision"
summary: "Make INTENT-<objective-id>.md the objective record itself (frontmatter = machine fields, body = Playbook sections); no second source"
---

# RESEARCH — playbook-alignment

## 🎯 Recommended Direction

**TL;DR:** Move the objective record from `.claude/world/objectives/<ID>.yaml` to
`work-docs/INTENT-<ID>.md`, where the YAML frontmatter *is* the machine record `world.py`
already validates and hashes, and the markdown body carries the Playbook's five sections
(Problem / Proposed outcome / Affected users and systems / Constraints / Open questions).
One file, one source of truth, human-authored first, machine-read second.

**Rationale.** Anthropic's Playbook (2026-08-21) makes `intent.md` the first committed artifact
of the chain `intent.md → spec.md → plan.md → diff → review`: the originator writes it after
brainstorming, the product owner corrects it, git history is the governance record. harness-maker
already has that chain shape (`RESEARCH → SPEC → PLAN → diff → REVIEW`) and already has the
machine half of an intent record (the objective YAML with approval hash, states, scope,
non_scope, hypothesis). What it lacks is the *human-readable* half and the *deliverable*
placement: today an objective is a hand-written YAML file under `.claude/world/`, with no
`create` verb, no prose, and no place in the `work-docs/` chain a reader follows. Making the
markdown deliverable the record (Approach B) closes both gaps without creating a mirror that
drifts (Approach A) and without pretending a YAML file is a Playbook artifact (Approach C).
The main impact is **user-facing workflow value**: an operator writes intent in the same
voice and folder as every other deliverable, and `/hm:plan` Step 0.5 / `/hm:review` Step 3.3
keep reading the same fields through `hm world`. Maintainer cost is one loader change plus a
frontmatter-preserving writer.

This is informational; `/hm:plan` locks it.

## 🔍 Refinement Decisions

Discovery lens: **User-workflow / product opportunity** (how an operator authors and reads
intent, which artifacts they already keep in `work-docs/`) and **Technical architecture**
(loader, writers, deliverable single-source, hash payload). `--deep` not set.

## 🛠️ Approaches Found

### Approach A — INTENT-<slug>.md as a *view* over the YAML record (two files)

| Field | Content |
|---|---|
| Approach | Keep `.claude/world/objectives/<ID>.yaml` as the record; add `work-docs/INTENT-<ID>.md` with Playbook prose and a frontmatter copy of the record fields; `hm world objective import <path>` derives the YAML from the markdown. |
| Assumption | Operators will author the markdown and never hand-edit the YAML. |
| Evidence | Playbook: intent is written by a human, reviewed by a human, committed ([claude.com](https://claude.com/blog/the-ai-native-sdlc-playbook)). Codebase: the SPEC's "record changes only through these verbs" contract and the approval hash live on the YAML (`world.py:161`, SPEC Constraints "Approval hash payload"). |
| Trade-off | A second source of truth for scope/hypothesis/non_scope — exactly the class the `consistency` lens flagged twice in the last review (`HASHED_FIELDS`, `validate_objective_record`). Every edit needs an import step or the two drift; the approval hash would bind to the YAML while the human reads the markdown. |
| Compatibility | Zero change to `world.py` readers, gate, templates. New verb + new deliverable prefix. |
| Risk | **medium** — drift is silent; the earlier review's disposition on duplicate sources was "a second source of truth is a defect, not a nit". |

### Approach B — INTENT-<ID>.md *is* the record (frontmatter = machine fields, body = prose) — recommended

| Field | Content |
|---|---|
| Approach | `world.py` loads objectives from `work-docs/INTENT-*.md` frontmatter (same `_validate_objective_raw` rules, `id` = the stem after `INTENT-`); writers (`approve/transition/activate/close/edit_objective`) rewrite **only** the frontmatter and leave the body byte-identical; the body carries the five Playbook sections. `.claude/world/objectives/` retires (no real files exist yet — dogfood has none; fixtures under `tests/fixtures/objective_scope_drift/` and `world_fixture.py` move). `INTENT` joins `DELIVERABLE_PREFIXES`; the gitignore negation, `_DELIVERABLE_RE`, `derive_deliverable_globs` and the structural test derive from it. PLAN frontmatter keeps `objective: <ID>` (the gate's `_plan_link` reads that key today) — adding a second key `intent:` would be a second link. |
| Assumption | The approval hash keeps covering `{hypothesis, non_scope, outcome_id, scope, target}` from frontmatter only; prose edits never invalidate an approval (the Playbook expects prose to be corrected freely). |
| Evidence | Playbook chain and per-initiative placement ([claude.com](https://claude.com/blog/the-ai-native-sdlc-playbook)); the artifact-chain critique that unlinked artifacts have "no check" between them ([menuagentic](https://menuagentic.com/blogs/ai-native-sdlc-artifact-chain/)) — here the link is the `objective:` key the gate already enforces. Codebase: `_DELIVERABLE_RE` already accepts any flat `work-docs/<PREFIX>-[^/]+.md`, so `INTENT-OBJ-7.md` (uppercase id) matches without changing the slug rule; `derive_deliverable_globs` filters to shapes that exist, so a project without intents gains no receipt rows. |
| Trade-off | One loader/writer change in `world.py` (a frontmatter-preserving dump), a SPEC revision to the "Storage root" and "Path ownership" rows, fixture moves, a migration note for anyone who created `objectives/*.yaml` between 0.57 and this change (none known). Four `parse_frontmatter` implementations already exist (`second_brain`, `reconcile`, `provenance`, `autopilot_caps._FRONTMATTER_RE`) — pick `second_brain.parse_frontmatter(text) -> (dict, body)`, do not add a fifth. |
| Compatibility | `hm world status/show/revisit` and the three template steps are unchanged in wording (they read through `hm world`). `DELIVERABLE_STATE_PATHS` loses the `objectives/` entry; `intent.yaml`, `assumptions.yaml`, `outcomes.yaml` stay under `.claude/`. The `objective_gate` reads the PLAN link, then `load_world` — unchanged. |
| Risk | **low–medium** — the writer must rewrite frontmatter without touching the body (a round-trip test on byte-identical body is the oracle); `yaml.safe_dump` reorders keys, so the frontmatter dump needs a stable key order or the diff noise defeats the "governance in git history" purpose. |

### Approach C — Keep YAML, add the Playbook prose fields to it

| Field | Content |
|---|---|
| Approach | Add optional `problem`, `affected`, `constraints`, `open_questions` (multi-line strings) to `_OBJECTIVE_OPTIONAL`; keep the file where it is. |
| Assumption | Operators are fine writing prose in YAML block scalars under `.claude/`. |
| Evidence | Cheapest in code (schema + validator only). Against: the Playbook's whole point is a markdown artifact "human-readable and machine-actionable" in the chain folder; `.claude/world/` is where no human browses, and the prior research found the layer is only used if the record is where the work is (`RESEARCH-cell-dev-future-and-intent-layer-fit`). |
| Trade-off | No deliverable in the chain; readers of `work-docs/` never see the intent; no `INTENT` prefix; the withdrawal criterion (10 wrapups unused → remove) becomes more likely to fire. |
| Compatibility | Full. |
| Risk | **low** technically, **high** for adoption. |

### Out of scope, noted for `plan`

- **Playbook Stage 6 (incident → new intent.md via control bands).** harness-maker has no
  incident/monitoring stage; `hm world outcome record` + `revisit_when` is the manual
  equivalent. Not part of this task.
- **`intent/` folder.** The Playbook suggests `intent/` (or a dedicated repo for multi-repo
  orgs). harness-maker's deliverable machinery is keyed to `work-docs/<PREFIX>-`; a second
  folder would need its own gitignore, sweep and manifest rows. Recommend `work-docs/INTENT-`
  and, if the user wants the Playbook name, a documented mapping rather than a second folder.

## ⚠️ Pitfalls

- **Two sources of truth drift silently.** The last review rejected exactly this pattern in
  the same module (`validate_objective_record` vs `validate_objective`; `HASHED_FIELDS` vs the
  inline list). Approach A recreates it at file level.
- **Frontmatter dumps reorder keys.** `yaml.safe_dump(sort_keys=False)` preserves insertion
  order but a record loaded, mutated and dumped can still move keys the human placed; git
  history is the Playbook's governance record, so noise there is a real cost. Decide key order
  once (the `_OBJECTIVE_REQUIRED` order, then optionals) and test it.
- **Body must be byte-preserved by every writer.** `approve`, `activate`, `close`, `drop`,
  `reopen` rewrite the record; if any of them re-emits the body through a parser the prose
  drifts (trailing newline, CRLF, code fences). One shared writer, one round-trip test.
- **Id charset vs deliverable stem.** Objective ids are `[A-Z0-9-]+`; deliverable stems are
  `[^/]+`. `INTENT-OBJ-7.md` works, but a lowercase `intent-obj-7.md` would not be an
  objective and would silently not load. The Step 3.3 charset check added in the last review
  (`[A-Z0-9-]+`) must stay aligned with whatever the stem rule becomes.
- **Deliverable prefix has three derived sites + the `spec_gate` hook.** Adding `INTENT` must
  land in `DELIVERABLE_PREFIXES` only; `.gitignore` negation and `derive_deliverable_globs`
  follow, and `tests/structural/test_deliverable_single_source.py` fails until the negation
  line is mirrored. (`[[wiki:architecture] workflow-loop-efficiency-stage-1]` recorded the
  case where two document types were invisible to `git status` for a whole phase.)
- **Two-roots rule.** INTENT files are *versioned* → current checkout root (same as PLAN);
  `approved_by` stays at the base root. The last task missed this once
  (`[fail:design] git-identity-read-at-wrong-root-despite-spec-decision`); carry the row into
  the writer, not just the SPEC table.
- **Measurement is the Playbook's own missing layer.** Waydev's critique: the playbook says
  what to commit but not how to correlate intent → outcome over time
  ([waydev](https://waydev.co/anthropics-ai-native-sdlc-playbook-has-a-missing-layer-measurement/)).
  harness-maker's `outcomes.yaml` + `gap`/`revisit` is that layer already; do not add an LLM
  gap detector (decided in the previous task, ADR-003 of the previous PLAN).
- **Rendered surface ratchet.** If Step 0.5 / Step 3.3 / 5.7 prose changes at all, four frozen
  numbers move (`[[wiki:gotcha] one-rendered-command-size-has-four-normative-sites]`). The
  recommended approach needs **no** template wording change; keep it that way.

## ❓ Open Questions

1. **Record location: A (mirror) or B (frontmatter is the record)?** Research recommends B;
   this is the binding architectural choice.
2. **Id and filename rule.** Keep `[A-Z0-9-]+` ids with `INTENT-<ID>.md`, or move to
   lowercase kebab ids to look like every other deliverable stem? (Changes the Step 3.3 check
   and `_OBJECTIVE_ID_RE`.)
3. **Authoring path.** Add `hm world objective new <ID> --title … --outcome …` that writes the
   frontmatter skeleton plus the five empty Playbook sections, or stay hand-authored with a
   template file (`templates/work-docs/INTENT.md.j2`) that `/hm:plan` Step 0.5 offers when no
   objective exists?
4. **PLAN link key.** Keep `objective: <ID>` (gate already reads it) or rename to
   `intent: INTENT-<ID>` for Playbook vocabulary? Renaming touches `_plan_link`, the plan
   template line 738, the gate baseline fixture and AC-012.
5. **Body sections: enforced or advisory?** Should `validate_objective` require the five `##`
   headings (machine-checked Playbook shape) or leave the body free (prose is the human's)?
6. **Bundle the review's P2 leftovers?** Three touch the same files and are small:
   wrapup 5.7 `supersedes` needs `--claim` (`5202e61acb247105`), `schema_version: "1.0"`
   validate/load mismatch (`0eadd6c9f6e3b3ef`), `load_world` keeping value rows that failed
   validation (`889c342883fae2a7`). Recommend bundling these three; leave `edit_objective`
   (no caller) and the TOCTOU notes for a later diet.
7. **Migration.** Is there any `.claude/world/objectives/*.yaml` in the wild? (None in this
   repo; the layer shipped hours ago.) If none, no converter — just retire the path.

## 📚 Sources

- Anthropic, *The AI-Native SDLC playbook* (2026-08-21) — intent.md placement, ownership, template sections, artifact chain, incident loop: https://claude.com/blog/the-ai-native-sdlc-playbook
- Waydev, *Anthropic's AI-Native SDLC playbook has a missing layer: measurement* — per-stage signals, plan.md drift: https://waydev.co/anthropics-ai-native-sdlc-playbook-has-a-missing-layer-measurement/
- GenAI Playbook, *six stages rebuilt around the artifact you commit*: https://www.genai-playbook.com/articles/ai-native-sdlc-playbook-en.html
- menuagentic, *The AI-Native SDLC Moves Review Upstream — Three Links Have No Check*: https://menuagentic.com/blogs/ai-native-sdlc-artifact-chain/

## 🔗 Related Internal Docs

- [[SPEC-intent-world-model-objective-layer]] — objective record rows (required/optional fields, storage root, path ownership, approval hash payload, two roots)
- [[PLAN-intent-world-model-objective-layer]] — ADR-006 two roots, ADR-008 derived state, ADR-012 `DELIVERABLE_STATE_PATHS`
- [[REVIEW-intent-world-model-objective-layer-2026-09-16]] — "Open items" (P2 leftovers listed in Open Question 6)
- [[RESEARCH-cell-dev-future-and-intent-layer-fit]] — why the record must sit where the work is
- `src/harness_maker/world.py` (`_OBJECTIVE_REQUIRED`, `_OBJECTIVE_OPTIONAL`, `_OBJECTIVE_ID_RE`, `approval_hash`, `_validate_objective_raw`), `src/harness_maker/worktree.py` (`DELIVERABLE_PREFIXES`, `DELIVERABLE_STATE_PATHS`, `_DELIVERABLE_RE`), `src/harness_maker/wrapup_land.py` (`derive_deliverable_globs`), `src/harness_maker/autopilot_caps.py` (`_plan_link`), `tests/structural/test_deliverable_single_source.py`
