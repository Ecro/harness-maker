---
type: spec
task_slug: mission-context-loop
status: approved
created: 2026-09-19
tier: 2
tags: [harness-maker, spec, python, memory, world-model, knowledge-capture, retrieval]
test_framework: pytest
research_doc: "[[RESEARCH-mission-context-loop]]"
summary: "S0: capture DRI-stated code-absent facts mid-conversation into the git-shared wiki; recall from the writer's root"
---

# SPEC — mission-context-loop (World Model S0: capture + current-state + recall root)

## 🎯 Intent

A DRI's project knowledge that is not in the code has no harness capture path in a rendered
harness. Examples: how an external system behaves, ops quirks, corrections of wrong beliefs.
The shared wiki is written only at `/hm:wrapup` 5.1, by the AI, summarising its own task. When
the DRI says "remember X", Claude Code's documented default saves it to host auto-memory, which
is machine-local and invisible to git, Cursor and Codex.

Corrections do not replace the old truth either. In a 30-entry sample of this repo's wiki,
9 entries were superseded or contradicted by later entries. And a fact captured mid-task is
written to the base root but recalled from the worktree, so the next stage cannot see it
([[RESEARCH-mission-context-loop]] §D).

## 🌅 Outcomes

- A DRI can tell the agent, in any conversation and in any of the three IDEs, to remember a
  code-absent project fact. The fact lands in the git-shared `.claude/memory/wiki.md` as a
  `[wiki:fact]` entry, not in host auto-memory.
- Correcting a recorded fact replaces that entry in place. The replacement keeps one
  `Supersedes:` line. No second entry about the same subject appears.
- A fact captured while task A is in progress is recallable by any stage of any task before
  A lands. The recall reader roots where the writer writes.
- `/hm:wrapup` 5.1 searches before it writes, the way 5.2 already does, so a task's summary
  reuses the existing subject slug.
- The always-loaded instruction cost is bounded: one routing pointer per always-loaded file,
  at most 300 characters each.

## 📋 In-Scope Scenarios

### S1: explicit request records a shared fact
**Given** a rendered harness and a conversation, inside or outside any `/hm:` stage
**When** the DRI asks the agent to remember a project fact that is not derivable from the code
(e.g. "the staging API rate-limits at 10 req/s")
**Then** the agent searches existing memory first. It reuses a slug only when the match is a
`[wiki:fact]` entry; a non-fact match gets a new fact slug. Otherwise it writes one entry via
`hm memory_md upsert-wiki --category fact --slug <subject>`.
**And** the entry is in the base root's `.claude/memory/wiki.md`, not in host auto-memory.

### S2: correction replaces the recorded fact
**Given** a `[wiki:fact] staging-api-rate-limit` entry exists
**When** the DRI states the recorded fact is wrong and gives the current truth
**Then** the agent reuses the slug `staging-api-rate-limit`, and the entry body becomes the
current truth plus one `Supersedes: <old claim> (first recorded <date>)` line, which carries
the date the fact was FIRST recorded forward across corrections.
**And** the wiki contains exactly one heading with that slug.

### S3: personal preference stays out of the shared store
**Given** a rendered harness
**When** the DRI states a personal working preference ("I prefer short answers")
**Then** the agent does not write it to `.claude/memory/wiki.md`. It is left to the host's own
memory.

### S4: inferred facts are not recorded
**Given** the agent notices something it believes is a project fact, without the DRI asking to
record it or correcting a recorded fact
**When** the conversation continues
**Then** no wiki entry is written for it.

### S5: a fact captured mid-task is recallable before the task lands
**Given** task A runs in `.worktrees/a/`, and a fact was captured during A (written to the base
root, uncommitted)
**When** any stage runs `hm memory_retrieve` with its default memory dir from inside
`.worktrees/b/` (or `.worktrees/a/`)
**Then** the candidates include the captured fact.
**And** an explicitly passed `--memory-dir` is used unchanged.

### S6: wrapup reuses an existing subject slug
**Given** the wiki already holds an entry about the subsystem this task changed
**When** `/hm:wrapup` reaches 5.1
**Then** the rendered step instructs a `memory_retrieve` search before `upsert-wiki`, and reuse of
a matching **non-`fact`** slug, carrying forward what is still true in the old body.
**And** the step forbids reusing a `[wiki:fact]` slug. A fact changes only on the DRI's
explicit correction (S2), so wrapup can never overwrite it.

### S7: a failed capture is surfaced, never silently rerouted
**Given** `upsert-wiki` exits non-zero (e.g. malformed tier markers)
**When** the agent attempts S1 or S2
**Then** the agent surfaces the CLI's stderr to the DRI. It does not save the fact to host
auto-memory as a fallback.

## 🚫 Non-Goals

- **S1 of the research** (subject files `.claude/memory/knowledge/<subject>.md`,
  `upsert-fact`). This is gated on the transition criterion below.
- Agent-initiated capture, whether proposed or automatic (S4 forbids it).
- Host-native path-scoped rules (`.claude/rules/`, `.mdc` globs, nested `AGENTS.md`) as a recall
  channel.
- Reviving `.claude/memory/{semantic,episodic,profile}/`, embeddings, vector search, knowledge
  graphs.
- Changing `/hm:execute`'s warm-tier loading. The `observed-harness-gaps` sibling owns it.
- Slimming this repo's own `CLAUDE.md`, or backfilling the 9 superseded dogfood entries
  (repo chores, not product behaviour).
- New files under `.claude/memory/`, and any change to `_HUMAN_MEMORY_TIER_PATHSPEC`, the
  path-ownership classifier, or dirt filters.
- Python heuristics deciding whether two claims contradict or supersede. That decision is LLM
  judgment.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | repo standard; render tests + unit tests on `memory_retrieve` / `memory_md` |
| Storage | existing `.claude/memory/wiki.md` via `upsert-wiki` only | no new state file ⇒ no pathspec / dirt-filter / fold changes (count:3 "update every reader" class) |
| Always-loaded cost | pointer ≤ 300 characters per rendered variant (4 `CLAUDE.md` + `AGENTS.md` + `harness.mdc`) | every always-loaded byte is carried every turn |
| Targets | skill renders for Claude Code (`.claude/skills/`), Cursor (reads `.claude/skills/` natively), Codex (`.agents/skills/`) | non-negotiable: one source, three hosts |
| Determinism | render performs no shell-out; output byte-stable | non-negotiable |
| User state | `@hm:user:*` blocks in `CLAUDE.md` / `AGENTS.md` / wiki preserved across re-render | non-negotiable |
| Recall root | default memory dir resolves by the same rule as `memory_md._base_root`; explicit `--memory-dir` wins | reader must root where the writer writes |
| Language | Python only | project rule |
| S1 / withdrawal criterion (pre-registered) | From the UTC date of the release tag that ships S0 through that date + 28 (inclusive, UTC calendar dates), count `## [wiki:fact]` headings dated inside the window in this repo's `.claude/memory/wiki.md`: **≥ 5 → file S1 as a candidate task; 0 → remove the skill and the pointers**; 1–4 → keep S0, no S1 | decided before the data exists; not re-interpreted after it fires |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (render) + manual | `test_ac_004_skill_carries_capture_contract`, `test_ac_005_pointer_present_and_bounded`; manual: in a dogfood session say "remember <fact>", confirm a `[wiki:fact]` entry in base `wiki.md` and no new file under host auto-memory |
| S2 | unit + manual | `test_ac_003_same_slug_upsert_replaces_and_keeps_supersedes`; manual: correct the fact from S1, confirm one heading and a `Supersedes:` line |
| S3 | unit (render) + manual | `test_ac_004_skill_carries_capture_contract` (routing tokens); manual: state a preference, confirm `wiki.md` unchanged |
| S4 | unit (render) | `test_ac_004_skill_carries_capture_contract` (no-inference token) |
| S5 | unit | `test_ac_001_default_memory_dir_is_writer_root`, `test_ac_002_explicit_memory_dir_wins` |
| S6 | unit (render) | `test_ac_006_wrapup_51_searches_before_write` |
| S7 | unit (render) | `test_ac_004_skill_carries_capture_contract` (surface-stderr / no-fallback token) |
| — | unit (render) | `test_ac_007_wiki_template_documents_fact_and_supersedes` |

### AC-001: default memory dir resolves to the writer's root
Property. For any cwd under `<base>/.worktrees/<name>/…`, the default memory dir equals the
directory `memory_md` writes to. For a cwd at `<base>`, it is `<base>/.claude/memory`.

### AC-002: an explicit memory dir is used unchanged
Mechanical. A `--memory-dir` value is never re-rooted.

### AC-003: same-slug upsert replaces in place and keeps the Supersedes line
Property. `upsert-wiki` twice with the same slug yields one heading, and its body equals the
second body's canonical form `body.strip("\n")`, including a `Supersedes:` line. The domain is
bodies without `## [x:y]` heading-shaped lines or `@hm:user` markers, which the writer rejects.

### AC-004: the rendered skill carries the capture contract
Golden tokens, fixed here before the template is written. Every rendered copy of the
`project-knowledge` skill (Claude Code path, and Codex path when `codex` ∈ targets) contains:
`upsert-wiki`, `--category fact`, `memory_retrieve`, `Supersedes:`, `auto-memory`,
`never record an inferred fact`, `surface the stderr`, `reuse only a [wiki:fact] slug`.

### AC-005: every always-loaded file carries a bounded pointer
Parametric over the rendered 4 `CLAUDE.md` variants, `AGENTS.md` and `.cursor/rules/harness.mdc`.
Each contains the `project-knowledge` pointer section. That section is ≤ 300 characters and
names `project-knowledge` and `auto-memory`. The `AGENTS.md` row must also name
`.agents/skills/project-knowledge/SKILL.md`, because Codex starts skills only on an explicit
mention.

### AC-006: wrapup 5.1 searches before it writes
Mechanical. In every rendered wrapup arm, the 5.1 section invokes `memory_retrieve` before
`upsert-wiki`, instructs slug reuse, and contains `never reuse a [wiki:fact] slug`.

### AC-007: wiki templates document the fact category and Supersedes convention
Mechanical. Both `wiki.en.md.j2` and `wiki.ko.md.j2` render a category list containing `fact` and
a format note containing `Supersedes:`.

## ❓ Open Questions

(none — scope, trigger, placement, correction format, recall root and the S1/withdrawal criterion
were locked in interview Rounds 1–2)

## 🔍 Refinement Decisions

- Round 1: scope = **S0 only**, with a pre-registered S1 transition. Trigger = **explicit request +
  correction of a recorded fact** (no agent-proposed or automatic capture). Placement = **skill +
  one pointer line in each always-loaded file**. Correction = **replace body + one `Supersedes:`
  line**.
- Round 2: **recall-root fix included** (`memory_retrieve` default dir → writer's base root).
  S1/withdrawal = **28-day window, ≥5 fact entries → S1 candidate, 0 → remove**.
- Defaults taken without asking: pytest; non-goals listed above; the pointer budget of 300
  characters follows the `context_discipline` precedent of a fixed per-variant cap.
- /hm:plan validation round (2026-09-19): AC-003 narrowed to canonical bodies. Reuse rules
  split so that wrapup never reuses a fact slug and the skill reuses only fact slugs
  (validator C1, critical). The Codex pointer names the skill path (C4). These tighten
  S1/S6 and AC-004/005/006 without widening scope.
- Plan-level (how, not what): where the day-28 evaluation is anchored so it actually runs,
  sequencing after the `observed-harness-gaps` sibling (both touch `memory_retrieve.py`), and
  whether the pointer is a shared partial.
