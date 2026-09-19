---
type: research
task_slug: mission-context-loop
status: complete
created: 2026-09-18
tags: [harness-maker, research, product-direction, intent, world-model, context-engineering, escalation, close-out]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://block.xyz/inside/from-hierarchy-to-intelligence
  - https://www.danstroot.com/posts/2026-04-04-inside-blocks-ai-native-organization
  - https://carlotorniai.substack.com/p/intelligence-over-hierarchy-blocks
  - https://www.forbes.com/sites/josipamajic/2026/04/01/jack-dorsey-bets-4000-jobs-that-ai-can-replace-the-org-chart/
  - https://arxiv.org/html/2604.25000
  - https://arxiv.org/abs/2602.20478
  - https://www.anthropic.com/engineering/harness-design-long-running-apps
  - https://docs.cline.bot/best-practices/memory-bank
  - https://www.kaivlya.com/blog/tech/cursor-memory-bank
  - https://code.claude.com/docs/en/memory
  - https://www.infoq.com/news/2026/02/openai-harness-engineering-codex
  - https://madplay.github.io/en/post/harness-engineering
  - https://dev.to/rulestack/how-cursor-claude-code-and-codex-actually-load-your-project-rules-and-why-yours-get-ignored-1l1j
  - https://codersera.com/blog/agents-md-vs-claude-md-vs-cursor-rules-comparison-2026/
related_docs:
  - "[[RESEARCH-intent-world-model-objective-layer]]"
  - "[[RESEARCH-cell-dev-future-and-intent-layer-fit]]"
  - "[[PLAN-intent-world-model-objective-layer]]"
  - "[[PLAN-objective-gap-proposal]]"
  - "[[PLAN-assumption-entry-and-evidence-locator]]"
  - "[[PLAN-observed-harness-gaps]]"
  - "[[PLAN-intent-layer-ops]]"
summary: "Loop = vocabulary only; fix World Model: subject-keyed current facts + mid-conversation capture, probe S0 first"
---

# RESEARCH — Mission / Context-Gap / World-Model-Delta loop: fit for harness-maker

## 🎯 Recommended Direction

**TL;DR (revised after the D1–D4 dig-deeper pass): the loop itself is vocabulary; the real,
measured weakness is the World Model node. Its problem is not *where* facts are stored. The
problem is that no store keeps **one authoritative current answer per subject**, and none has a
capture path for what the DRI says mid-conversation.**

In a 30-entry wiki sample, 9 entries are superseded or contradicted by later entries or by
`CLAUDE.md`. `CLAUDE.md` itself still describes a Cursor command mirror that `synthesize.py` no
longer renders.

Recommended shape (informational — `/hm:plan` decides):
- **Storage:** subject-keyed current-state facts, stored in the harness's existing memory
  machinery.
- **Recall:** portable retrieval (`memory_retrieve`), not host-native path rules.
- **Assumptions store:** used only for uncertain beliefs.
- **Host auto-memory:** used only for personal preferences.

Probe with the smallest slice first (§D "Staged first slice"), after the `observed-harness-gaps`
sibling lands its execute-recall fix. Slimming harness-maker's own 64 KB `CLAUDE.md` is a
separate repo chore, not a product feature.

**Original TL;DR (loop-level verdict, still valid): adopt the diagram as *vocabulary and a one-page mapping doc*, not as a mechanism.
harness-maker already implements roughly 80% of the loop under other names. The parts that are
genuinely missing are already being built by three in-flight sibling tasks. One residual hole
remains: capture of mid-task context gaps. Hold it until those siblings land and the intent
layer passes its own withdrawal criterion.**

Rationale. The diagram describes the loop the intent layer (landed 2026-09-16, `3edcca62` →
`cff4f6df`) was built to be, in the vocabulary of Block/Sequoia's "From Hierarchy to
Intelligence" (ICs, DRIs, company world model). Walking it node by node (table below) gives:
- Mission Protocol, Escalation, Close-out, Initial Context and AI Context are **covered**.
- Context Contract, Gap Capture, Research/Evidence, World Model Delta and DRI are **partial**.
- Nothing is wholly absent.

Two independent analyses reached the same verdict: this session's own code walk and a Codex
second opinion that read the same files.

The binding trade-off is better reuse of consequential knowledge against the recurring cost of
capturing, approving, loading and maintaining it. Two facts decide it:
- The intent layer is two days old and carries a pre-registered withdrawal criterion
  (`.claude/intent.yaml:1-4`: 10 wrapups with no `observed:` and no fired `revisit_when` →
  remove).
- `hm world status` on base today shows zero recorded assumptions and one `proposed` objective.

Building a larger "Mission Context Loop" surface on top of state that has not yet proven it is
maintained is the "rebuild the machine" move that
[[RESEARCH-cell-dev-future-and-intent-layer-fit]] explicitly withdrew.

Impact class: the loop vocabulary is **internal maintainer value**. The World Model fix (§D)
is **user-facing workflow value** for consumer projects. The DRI stops re-explaining
code-absent facts, and corrections replace the old truth instead of piling up beside it.

## 🔍 Refinement Decisions

- Discovery lens: **User-workflow** (how practitioners actually maintain agent "world models" —
  Cline/Cursor memory bank, Anthropic long-running harness handoff), **Technical architecture**
  (node-by-node mapping to this repo's code), **Research** (closure-gap/delegation-envelope
  framework, codified-context). No `--deep` interview; topic was concrete.
- Cross-model: Codex (via `codex:codex-rescue`, read-only) independently mapped the diagram to
  the repo; its conclusion matched this session's. Its citations were spot-checked
  (`owners: []` at `intent.yaml:91`; wrapup has no `#### 5.5`, jumps 5.4 → 5.6).
- Dig-deeper pass on D1–D4 (operator request, second Codex run). Codex **refuted** two
  first-pass claims:
  - "wiki is a task log": the sample shows 21 of 30 entries are durable facts.
  - "Python reranks": the agent picks from ≤30 lexical candidates.

  It also relocated D3's store to `.claude/world/assumptions.yaml`. Spot-checked:
  `execute.md.j2:57-59` (first-40/60-lines skim), `memory_retrieve.py:6` (rerank in the Claude
  turn), `synthesize.py:726-742` vs `CLAUDE.md:38,117` (stale Cursor-mirror claim). All
  confirmed. Section D carries the corrected diagnosis.

### Node-by-node mapping (Local capability x diagram node)

| Diagram element | Status | Where it lives today |
|---|---|---|
| Context Contract | partial | `intent.yaml` (mission, non_negotiables, non_scope, unknowns), `harness.yaml` (autonomy level, permissions), CLAUDE.md, PLAN Contract Boundaries. No per-task *authority* contract. |
| Mission Protocol | covered | 7 atomic `/hm:` stages + autopilot pipeline; objective playbook `work-docs/INTENT-<ID>.md` |
| Gap Capture | partial | `intent.unknowns`, `hm world gap` (outcome gaps), plan Step 1 ranked ambiguities, RESEARCH Open Questions, execute blocker notes. **No capture of non-blocking mid-task gaps.** |
| Escalation Rule | covered | `stuck` agent (A.5 retry exhausted / Phase D unfixable / ADR conflict, `execute.md.j2:563-587`), autopilot mandatory gates + caps (`autopilot_caps.py`), answer-gated writes |
| Close-out Rule | covered | `/hm:wrapup` Steps 1–7.7: verification, memory 5.1–5.4, Second Brain 5.6, world state 5.7, single squash-land |
| DRI | partial | Human lock-in everywhere (`objective approve` is human-only), but `owners: []` — sole maintainer is implicitly DRI |
| AI IC | covered | executor / autoloop-coder: bounded scope, report-back |
| Initial Context | covered | plan Step 0.5 (objective), `memory_retrieve` warm tier, RESEARCH doc read via frontmatter |
| Context Gap → Research/Evidence | partial | `/hm:research`; `hm world assume observe`, `outcome measure`. Assumption *entry* missing (sibling task) |
| World Model | covered, narrowly | `intent.yaml` + assumptions/outcomes/objectives (`world.py`) + `.claude/memory/` wiki/failures + Second Brain vault. Three stores, one per durability tier |
| AI Context | covered as a *view* | `memory_retrieve` top-K + plan Step 0.5 line — a projection, not a maintained file (correct) |
| Mission Close-out → World Model Delta | partial | Individual writes exist (5.1–5.7); no single "delta" object — and none needed |
| Delta → next Mission | partial | Recorded lessons are not guaranteed recall (`memory_retrieve` excludes zero-overlap candidates) — the `observed-harness-gaps` sibling fixes this |

## 🛠️ Approaches Found

### A. Vocabulary + mapping doc only (recommended)

| Field | Content |
|---|---|
| Approach | One reference doc (e.g. `docs/reference/operating-loop.md`) that defines the terms and maps each node to the existing mechanism (table above). No rendered-template, schema or CLI change. |
| Assumption | The value of the diagram is shared vocabulary for future decisions, not new behaviour. |
| Evidence | Codex + own walk: ~80% covered. Anthropic's harness guidance: "every component in a harness encodes an assumption about what the model can't do on its own" — add only against a demonstrated gap. |
| Trade-off | Zero behaviour change; the mid-task hole stays open for now. |
| Compatibility | Perfect — nothing rendered, nothing in always-loaded context. |
| Risk | low |

Content the doc should fix (from Codex, adopted):
- **Mission ≠ task.** `intent.mission` is the enduring project purpose. The diagram's "Mission"
  is a bounded **task** (one PLAN, optionally linked to an `objective:`). Do not introduce a
  third "mission" object.
- **World Model vs AI Context.**
  - World Model = durable, revisable claims with evidence and uncertainty.
  - AI Context = the per-task selection fed to the model. It is a **view**, never a maintained
    document.
  - Initial Context is simply the first AI Context.
- **Delta acceptance.**
  - The human DRI accepts changes to intent, scope, binding decisions and disputed assumptions.
  - The AI may write routine task evidence (wiki/failures) within its existing authorization.
- **Stop = task complete, not knowledge complete.** Close-out permits open unknowns (`no_data`
  stays legal).
- **The final arrow does not spawn work.** It means "available to the next separately
  authorized task" — matching `objective` staying `proposed` until a human approves it.

### B. A + one mid-task gap rule (deferred candidate)

| Field | Content |
|---|---|
| Approach | Add a rule to execute (and the autoloop body): when new evidence could change implementation, acceptance or scope, record `claim/question → evidence → consequence → disposition` inline in the PLAN phase. At wrapup, 5.7 offers to turn unresolved ones into `hm world assume add` entries. |
| Assumption | Mid-task discoveries are currently lost, and losing them costs rework. |
| Evidence | **Structural only.** Interactive execute says "surface it before writing tests — don't guess" (`execute.md.j2:9`). Autoloop DD#8 says "When ambiguous, log the decision and proceed" (`docs/reference/autoloop-pattern.md:86`). The two modes have opposite rules, and neither log feeds the world model. There is **no measured incidence** of a lost discovery causing rework. |
| Trade-off | New prose in execute (a surface-budget-ratcheted file) + a new 5.7 branch, for a benefit not yet measured. |
| Compatibility | Depends on `assume add` (sibling, not landed); collides with every sibling's 5.7 edit. |
| Risk | medium (surface growth, allowance-fold churn, unmaintained entries) |

### C. Full "Mission Context Loop" subsystem (reject)

| Field | Content |
|---|---|
| Approach | Explicit contract file, mission register, gap queue, delta ledger with acceptance state, escalation-rule DSL. |
| Assumption | A single orchestrating object improves outcomes over the existing distributed writes. |
| Evidence | Against it: Block's public model gives no maintenance mechanism for its world model, and critics flag drift and missing challenge/audit paths (Torniai). Closure-gap framework (arXiv 2604.25000) is conceptual — "not an empirical report". Memory-bank practitioners report that `activeContext`/`progress` "drift the fastest" and need weekly manual review. The prior research withdrew the equivalent machine. |
| Trade-off | Large surface, a fourth state store, a new always-loaded cost, maintenance nobody has shown they do. |
| Compatibility | Violates 제1목표 ("복잡한 설계를 지양") and the "no new state root" decision. |
| Risk | high |

### D. Where does code-absent project knowledge live? (operator follow-up — the real weak node)

The operator's point: "World Model" is the weakest node. What a DRI actually accumulates is
project knowledge that is *not in the code*, and today that seems to land only in
memory/failures. Measured inventory on base (2026-09-18):

| Store | Holds | Written by / when | Read back by | Shared |
|---|---|---|---|---|
| `CLAUDE.md` (426 lines / 64 KB) | hard-won current truths + inline corrections ("Corrected 2026-07-17") | human + AI, ad hoc | **every turn** (always loaded) | git |
| `.claude/memory/wiki.md` (260 entries, 1140 lines) | one summary per finished work unit, by category | wrapup 5.1 is the only production call site (the CLI itself is stage-agnostic) | `memory_retrieve`: ≤30 lexical candidates, the agent picks 6 (research/plan); execute skims the first 40 lines only | git |
| `.claude/memory/failures.md` (155 entries) | failure patterns + count | AI, wrapup 5.2 | same | git |
| `.claude/intent.yaml` + `.claude/world/assumptions.yaml` | mission, outcomes, unknowns; assumptions (**file absent — 0 recorded**) | human, answer-gated | `hm world status`, plan Step 0.5 | git |
| `work-docs/PLAN-*` ADRs, `RESEARCH-*` | decision rationale | per task | **not indexed** — only if a later task greps for it | git |
| Second Brain vault | cross-project durable notes | wrapup 5.6 | `second_brain search` in research | separate repo |
| Claude Code auto-memory (31 indexed notes for this repo) | preferences + project facts | host, any turn | host loads `MEMORY.md` index | **per-user, not git, not Cursor/Codex, invisible to `memory_retrieve`** |
| `ref_folders` | external docs | human | `refdocs-search` skill | varies |
| `.claude/memory/{semantic,episodic,profile}/` | — | nothing writes them | — | **directories absent — dead tiers** |

Diagnosis. Facts are cited; inferences are labelled. This supersedes the first-pass diagnosis,
which Codex partly refuted.

1. **The problem is supersession, not genre.** Codex classified a 30-entry wiki sample spanning
   May–September: 21 durable facts, 6 gotchas, 3 task logs. The first pass called wiki "a task
   log"; that was **wrong**. The real defect is that 9 of the 30 have a concrete
   supersession or contradiction:
   - `per-session-worktree-marker` → caller-session content matching
   - `snapshot-regen-on-main…` → location-independent pins
   - `nine-lens-axis…` → seven lenses
   - `reviewer-fanout-is-language-conditional` recommends the `reviewers.enabled` lever that
     `CLAUDE.md` retracts
   - `step-sensitivity-classes` says 39 while `CLAUDE.md` says 30, unresolved

   `upsert-wiki` already replaces by exact slug (`memory_md.py:314-366`). But wrapup 5.1 has no
   search-before-write step, unlike failures 5.2, so a new task writes a new slug beside the old
   truth instead of replacing it.
2. **Always-loaded truth goes stale too.** `CLAUDE.md:38,117` still says Cursor gets a
   `.cursor/commands/hm-*.md` mirror; `synthesize.py:726-742` renders only `harness.mdc`,
   `hooks.json` and `mcp.json` (verified). Codex's byte classification of `CLAUDE.md` (426 lines,
   64,120 B):

   | Class | Lines | Share of bytes |
   |---|---|---|
   | (a) always-needed policy and pointers | 127 | 13.8% |
   | (b) subsystem-specific knowledge relevant only when touching named paths | 253 | **72.8%** |
   | (c) incident narrative and corrections | 46 | 13.4% |

   (b) and (c) together are the relocation *ceiling* (86%), not a promised saving. **Scope
   caveat:** this is harness-maker's own `CLAUDE.md`. The consumer Production template is about
   33 lines, so for consumers the payoff is capture and recall, not shrinking.
3. **No capture path from conversation.** Wrapup 5.1 is the only production call site of
   `upsert-wiki`. The CLI itself is stage-agnostic (`memory_md.py:798-825`), so the missing piece
   is an *instruction*, not a mechanism. The host competes for the same moment: Claude Code's
   documented behaviour is that "remember X" goes to **auto-memory**, which is machine-local and
   not in git.
4. **Recall is narrow, and weakest in execute.**
   - `memory_retrieve` loads only wiki and failures, emits up to 30 lexical-overlap candidates,
     and the *agent* picks 6. There is no Python rerank (`memory_retrieve.py:6`, `:386-405`).
   - PLAN ADRs and RESEARCH docs are not indexed.
   - execute skims only the **first 40 lines** of wiki and the first 60 of failures
     (`execute.md.j2:57-59`). Recent facts live at the bottom, so execute never sees them. The
     `observed-harness-gaps` sibling (Phase 3) switches execute to `memory_retrieve`.
5. **Host path-scoped loading exists but is unused and not portable as the sole mechanism.**
   - Claude Code: `.claude/rules/*.md` with `paths:` loads only when matching files are read and
     reloads after `/compact`; unscoped rules load at launch. Docs target is `CLAUDE.md` under
     200 lines.
   - Cursor: `.mdc` `globs`.
   - Codex: nested `AGENTS.md`.
   - harness-maker renders none of these for knowledge: there is no `.claude/rules` code, and
     Cursor gets a single `harness.mdc` with `alwaysApply: true`.
   - Cross-cutting facts (external systems, business rules, ops) have no path to scope on, and
     planning needs knowledge before any scoped file is read.

Candidate homes, re-scored:

| Option | Current-state | Capture any time | Recall | Always-loaded cost | Shared + 3-IDE | Verdict |
|---|---|---|---|---|---|---|
| D1 subject files (one current-state file per subject) + root index/pointers | ✔ by construction | needs capture instruction + writer | via `memory_retrieve` (extend loader) | low (pointers only) | ✔ git | **storage shape to aim for** |
| D2 wiki `fact` entries, slug = subject, search-before-write | ✔ if slug reused (LLM judgment) | CLI exists; instruction missing | already retrieved | none | ✔ git | **cheapest probe** |
| D3 `.claude/world/assumptions.yaml` (sibling: `assume add` + locator) | ✔ claim/evidence/status | ✔ after sibling lands | ✗ not in `memory_retrieve`; derived staleness not yet wired in sibling | none | ✔ git | **uncertain beliefs only** |
| D4 host auto-memory | partial (`modified:` stamp) | ✔ native | Claude Code only | 200 lines / 25 KB index | ✗ machine-local, not Cursor/Codex | **personal preferences only** |
| (D5) host path-scoped rules as the recall channel | ✔ | — | only when a matching file is read | 0 until matched | ✗ three formats, none rendered today | **later optional adapter**, never sole |

Location: human-authored knowledge belongs under `.claude/memory/` (e.g.
`.claude/memory/knowledge/<subject>.md`). Content ownership and directory are separate
questions. `.claude/` already holds user-owned, re-render-preserved content (`intent.yaml`,
memory entry blocks, content-hash-exempt memory — `reconcile.py:593-621`). Existing human docs
in `docs/` are referenced, never relocated or duplicated (`docs/` is outside the orphan sweep,
`reconcile.py:90-93`).

#### Staged first slice (proposal)

- **S0 — probe (smallest).**
  - A capture instruction: a skill section plus one pointer line in the rendered `CLAUDE.md`,
    `AGENTS.md` and `.mdc`. When the DRI states a code-absent project fact or corrects one, the
    agent searches existing entries, reuses the subject slug on a correction, and writes via the
    existing `hm memory_md upsert-wiki` with category `fact`, to the git-shared checkout store,
    **not** host auto-memory.
  - Add search-before-write to wrapup 5.1 (mirror 5.2).
  - Zero new storage and zero new Python beyond, at most, a category literal.
  - Sequenced after `observed-harness-gaps` lands, because execute recall depends on it.
- **S1 — only if S0 shows real captures.** A fixed count and window gets pre-registered in the
  PLAN.
  - `hm memory_md upsert-fact --subject <s>` writing `.claude/memory/knowledge/<s>.md`.
  - `memory_retrieve` reads those files with source paths.
  - execute re-reads the subject files a PLAN names.
- **Never (now):**
  - embeddings, vector DB or knowledge graph
  - reviving the absent `semantic/episodic/profile` tiers
  - a background doc-gardening agent
  - Python heuristics deciding contradiction or supersession
  - auto-creating an assumption per DRI statement
  - the same fact kept current in two stores
  - generated knowledge bodies a re-render could replace

Where S0 and Codex's recommendation differ: Codex proposes going straight to S1 (subject files).
Its reason is that wiki keys are task-derived, paragraphs are mixed, and wiki writes to the base
root. This doc stages it because the intent layer's lesson is to prove the capture habit exists
before building the store. Codex's objection is an Open Question for `/hm:plan`, not settled.

## ⚠️ Pitfalls

- **Host auto-memory competes for the capture moment.** Claude Code documents that "remember X"
  goes to auto-memory (machine-local, not in git, invisible to Cursor/Codex). A harness capture
  instruction that does not say *which* store wins will split facts between two stores silently.
  The instruction must route shared project facts to the checkout store and leave personal
  preferences to auto-memory.
- **Supersession needs search-before-write.** Exact-slug replace only works when the writer
  finds and reuses the old slug. wrapup 5.2 (failures) searches first; 5.1 (wiki) does not. That
  is the mechanical root of the 9-of-30 stale entries.
- **Path rules silently not firing.** Cursor rules with a vague description and no globs are
  never pulled, and in every host "reading the file is not the same as weighting it once context
  fills". Path-scoped loading is a discovery aid, not a recall guarantee.
- **Worktree vs base root.** `memory_md` writes to the base root (it strips worktree paths)
  while retrieval is cwd-relative (`memory_md.py:71-91`, `memory_retrieve.py:434-435`). A
  capture made inside a task worktree must land where the next task reads it. This seam already
  bit wrapup ([[project-wrapup-memory-base-seam]]).

- **Stale world model is the dominant real-world failure.** It matters more than any missing
  node. Cline/Cursor memory-bank users report that the fast-moving files drift first; the
  symptom is the model's suggestions drifting. Block's critics raise the same issue at company
  scale ("what happens when the intelligence layer optimizes for measurable signals…", "who
  monitors the model's priorities"). In this repo the fix is derived staleness, which is
  underway in the `assumption-entry-and-evidence-locator` sibling. More stored state would not
  fix it.
- **Write ≠ recall.** A delta that is written but never retrieved closes nothing. This repo has
  hit that exact bug: zero-overlap exclusion in `memory_retrieve`, addressed by the
  `observed-harness-gaps` count-floor.
- **Diagram-as-prompt tax.** Pasting the loop into CLAUDE.md or every stage adds per-turn
  carry. 77% of spend happens outside `/hm:` stages, and CLAUDE.md is already far over the
  cell-evidence target (see [[RESEARCH-context-carry-economics-2026-07-28]]).
- **"AI IC" is an adaptation.** Block's ICs are people who own a layer. Treating the AI as an
  accountable IC blurs the fact that accountability stays with the DRI; the existing "AI
  executes, human approves" split is the correct one.
- **Surface-allowance handoff.** Every sibling touches wrapup 5.7 and declares an allowance
  that expires at wrapup with no automatic fold (`[fail:design] surface-allowance-lacks-autofold`,
  count:1, and hit three tasks in a row). Starting approach B concurrently guarantees a
  re-freeze collision.
- **Mode divergence hidden as "escalation".** Interactive execute halts on ambiguity; autoloop
  logs and proceeds. Any future gap rule must pick one semantic per mode explicitly rather than
  paper over the difference.

## ❓ Open Questions

1. **Doc only, or is the mid-task rule (B) wanted after the siblings land?** Deciding B needs
   evidence first. Is there a remembered case where an execute/autoloop discovery was lost and
   caused rework? Without one, B stays deferred.
2. **Doc location.** Options: a new `docs/reference/operating-loop.md`, or a section in an
   existing design doc. Either way it must not be referenced from always-loaded CLAUDE.md
   beyond a one-line pointer.
3. **Fill `owners:`?** For a sole maintainer, DRI is implicitly the user. Is populating
   `owners:` in the dogfood `intent.yaml` worth it (no consumer reads it today), or should it
   stay empty until a multi-person consumer project exists?
4. **Sequencing gate.** Proposed: start no work beyond the doc until all three hold:
   `assumption-entry-and-evidence-locator`, `intent-layer-ops` and `observed-harness-gaps`
   have landed, **and** `hm world gap`'s withdrawal reader (from `intent-layer-ops`) shows the
   layer in use.
5. **S0 probe or straight to S1?** Codex argues for subject files immediately (task-derived
   wiki keys, mixed paragraphs, base-root writes). This doc argues for S0 first, to prove the
   capture habit exists. If S0: which count and window are pre-registered as the S1 trigger?
6. **Capture routing vs auto-memory.** Which facts go to the git store and which stay in host
   auto-memory? Is the rule "shared project fact → git, personal preference → host" enough?
7. **Correction of a wrong fact.** When a correction lands, should the old statement be kept
   anywhere (archive or history section), or does git history suffice? The (c) class of
   `CLAUDE.md` suggests people want the "why it changed".
8. **Dogfood `CLAUDE.md` slimming.** Should it be a separate repo chore moving (b) and (c)
   sections to `docs/reference/*` behind pointers, like the two existing pointers do? Fix the
   stale Cursor-mirror lines (`CLAUDE.md:38,117`) now or inside that chore?
9. **Wrapup numbering gap** (side finding): Step 5.5 does not exist (5.4 → 5.6). Cosmetic, or
   a removed step whose references linger? Check before any 5.x edit.

### In-flight sibling sessions (overlap + ordering)

| Sibling task (other session) | State | Covers which part of the diagram |
|---|---|---|
| `assumption-entry-and-evidence-locator` | PLAN ready | Gap Capture (`assume add`), World Model freshness (content-fingerprint locator, derived staleness), 5.7 assumption list |
| `intent-layer-ops` | PLAN planning, execution notes | Whether the World Model layer survives (withdrawal reader in `gap`), measure evidence → definition hash |
| `observed-harness-gaps` | executed, not landed | World Model → AI Context (execute warm tier via `memory_retrieve`, count-floor recall), Delta → next task (proposals consumer) |
| `opus5-selfreview-vs-harness-gates` | planning / CHANGES_REQUESTED | Not related (review gate budget) |

## 📚 Sources

- Block — "From Hierarchy to Intelligence" (Dorsey & Botha, 2026-03-31): https://block.xyz/inside/from-hierarchy-to-intelligence (primary; fetch failed with header overflow — content taken from the two secondaries below)
- Dan Stroot, "Inside Block's AI-Native Organization": https://www.danstroot.com/posts/2026-04-04-inside-blocks-ai-native-organization — two world models (customer / company), DRIs "pull in people as needed… authority comes from ownership", 2–3 layers
- Carlo Torniai, "Intelligence Over Hierarchy: Block's Bet and Its Blind Spots": https://carlotorniai.substack.com/p/intelligence-over-hierarchy-blocks — model drift, no challenge/audit mechanism
- Forbes, "Jack Dorsey Bets 4,000 Jobs…": https://www.forbes.com/sites/josipamajic/2026/04/01/jack-dorsey-bets-4000-jobs-that-ai-can-replace-the-org-chart/
- "Toward a Science of Intent: Closure Gaps and Delegation Envelopes" (arXiv 2604.25000): https://arxiv.org/html/2604.25000 — semantic/evidentiary/procedural/institutional gaps → clarify/retrieve/simulate/escalate; **no empirical evaluation**
- "Codified Context: Infrastructure for AI Agents in a Complex Codebase" (arXiv 2602.20478): https://arxiv.org/abs/2602.20478 — hot constitution + specialist agents + cold spec docs, 283 sessions, observational
- Anthropic, "Harness design for long-running application development": https://www.anthropic.com/engineering/harness-design-long-running-apps — file-based handoff, sprint contracts removed as models improved, "every component encodes an assumption…"
- Cline Memory Bank docs: https://docs.cline.bot/best-practices/memory-bank
- Kaivlya, "Memory Bank System": https://www.kaivlya.com/blog/tech/cursor-memory-bank — activeContext/progress drift fastest, weekly review
- Claude Code memory docs: https://code.claude.com/docs/en/memory — CLAUDE.md < 200 lines; `.claude/rules/` `paths:` loads on matching read and reloads after compact; auto-memory = "project context Claude can't derive from the code", machine-local, 200-line/25 KB index
- OpenAI harness engineering (via InfoQ / MadPlay summaries; primary returned 403): https://www.infoq.com/news/2026/02/openai-harness-engineering-codex , https://madplay.github.io/en/post/harness-engineering — AGENTS.md ~100-line map, `docs/` system of record, background doc-gardening agent opening cleanup PRs
- "How Cursor, Claude Code, and Codex actually load your project rules": https://dev.to/rulestack/how-cursor-claude-code-and-codex-actually-load-your-project-rules-and-why-yours-get-ignored-1l1j — globs / nested CLAUDE.md / nested AGENTS.md as the shared locality mechanism; vague rules never pulled
- Cursor reads nested AGENTS.md: https://codersera.com/blog/agents-md-vs-claude-md-vs-cursor-rules-comparison-2026/
- Codex second opinion ×2 (read-only, this session): (1) node mapping + verdict "vocabulary/docs only"; (2) D1–D4 deep-dive: CLAUDE.md byte classification, 30-entry wiki sample (21 fact / 6 gotcha / 3 log, 9 superseded), retrieval/recall corrections, staged recommendation

## 🔗 Related Internal Docs

- [[RESEARCH-intent-world-model-objective-layer]] — original intent/world-model proposal review
- [[RESEARCH-cell-dev-future-and-intent-layer-fit]] — "keep the state, drop the machine"; Block/Sequoia DRI/IC evidence
- [[PLAN-intent-world-model-objective-layer]], [[PLAN-objective-gap-proposal]] — landed intent layer + gap verb
- [[PLAN-assumption-entry-and-evidence-locator]], [[PLAN-intent-layer-ops]], [[PLAN-observed-harness-gaps]] — in-flight siblings (other worktrees)
- [[RESEARCH-context-carry-economics-2026-07-28]] — per-turn carry cost
- `.claude/intent.yaml` (withdrawal criterion, `owners: []`), `src/harness_maker/world.py`, `templates/stages/{plan,execute,wrapup}.md.j2`, `templates/agents/stuck_body.md.j2`, `docs/reference/autoloop-pattern.md` (DD#8)
