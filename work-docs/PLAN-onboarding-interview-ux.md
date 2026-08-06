---
type: plan
task_slug: onboarding-interview-ux
status: complete
created: 2026-08-06
tags: [harness-maker, plan, python, onboarding, interview, second-opinion, cli-detection]
research_doc: "[[RESEARCH-first-interview-ux-2026-08-06]]"
interview_rounds: 4
adrs: 6
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Make the first interview disclose its silent defaults and offer detected second-opinion CLIs"
---

# PLAN — First-interview (onboarding) friendliness

## 🎯 Executive Summary

**TL;DR.** The fast path of `/harness-maker:make` silently fixes 10 of 14 configuration
axes and shows 5 of them. Nothing detects installed tooling, so the harness can never say
"codex is installed — want a second-opinion vote?". Axes silently disabled at install have
no guided way to be enabled later, and `/hm:health` is structurally silent about them. This
plan closes those, plus a quick-start line that names a command which does not exist.

**What.** RESEARCH §4 items P0-1..P0-4 and P1-5..P1-9. P2 (question batching, ref_folders as
multi-select, per-question skip options) is explicitly out of scope.

**Scope, restated inline.** The RESEARCH lives at `work-docs/RESEARCH-first-interview-ux-2026-08-06.md`
in the **base** repo and is an uncommitted deliverable, so it is not visible from this task
worktree. The item IDs used by the phases are therefore spelled out here:

| ID | Item |
|---|---|
| P0-1 | `commands/make.md:601` names `/hm:ai-readiness`, which does not exist → `/hm:health` |
| P0-2 | No installed-tool detection exists anywhere → add one |
| P0-3 | Detection must drive a conditional offer on the fast path |
| P0-4 | The fresh-install summary must disclose the axes it sets without asking |
| P1-5 | `/hm:configure` has no entry for second_opinion / autopilot / locale |
| P1-6 | `/hm:health` is silent in the installed-but-disabled state |
| P1-7 | The TTY second-opinion question is unexplained free text that drops typos |
| P1-8 | `consensus` / `caching` are asked with no explanation and change nothing |
| P1-9 | The quick-start has no verification step with success criteria |

**Why.** The user's own report — "why didn't it ask about second opinion when codex is
installed?" — is the visible symptom of a detection capability that does not exist at all.

**Key decisions.**
- Detection is a **new uncached CLI command**, not a `ProjectProfile` field (→ ADR-001).
- The fast path may ask **at most one** conditional question (→ ADR-002).
- Zero-runtime-effect axes leave the interview but keep their schema (→ ADR-003).
- Recovery is `/hm:configure` menu growth, **no new CLI surface** (→ ADR-004).
- The zero-headroom render ratchet is passed by **equivalent offset**, never by raising the
  frozen baseline (→ ADR-005).
- Prose recipes get a **structural contract test**, because prose has no execution surface
  (→ ADR-006).

**Estimated impact.** 1 new CLI command, 1 new module, 4 template/command files edited,
3 new test files, 1 test file extended. No schema migration.

## 📚 Prior Work

- `work-docs/RESEARCH-first-interview-ux-2026-08-06.md` — the finding set F1..F12 this plan
  implements, with the Hermes Agent benchmark that motivated the "detect → propose → confirm"
  ordering.
- CLAUDE.md, *"무언가를 고치거나 개선하기 전에"* item 2 — a prose recipe consumed by an LLM has
  no execution surface, so a render-grep test can only check its text. Four silent-skip bugs
  shipped in that shape. ADR-006 is the direct application.
- CLAUDE.md, `$0`–`$9` positional-parameter footgun — a gate scoped only to the artifact being
  fixed let the identical defect survive in `commands/make.md`, the new-install entry point.
  Phase 0 is scoped to avoid repeating that.
- PLAN-worktree-side-defaults ADR-001/007 (0.48.0) — the precedent for retiring knobs with zero
  runtime effect; `consensus`/`caching` are the same class (ADR-003).
- `[fail:design] verification-cache-key-nondeterministic` — a cache whose invalidation does not
  track what it claims to describe fails silently, because a permanently-wrong cache is
  indistinguishable from a correct one. That is exactly why ADR-001 refuses the cached field.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Detection location | Architecture | Where does installed-tool detection live, given `profile()` is 24h-cached and CLI installs do not invalidate it? | new uncached command / `ProjectProfile` field / live-overwrite inside `profile()` | New uncached command | Cache honesty preferred over saving one round trip | ADR-001 |
| 2 | Fast-path question budget | Scope | How many detection-driven questions may "Looks right" ask? | max 1 (second opinion only) / max 2 / zero, display only | Max 1 | Keeps the fast path fast while covering the largest gap | ADR-002 |
| 3 | Scope | Scope | How far does this PLAN go against RESEARCH §4? | P0+P1 / P0 only / everything | P0 + P1 | Recovery path must close or "decide later" is dishonest | — |
| 4 | Zero-effect axes | Contract | `consensus`/`caching` have no runtime effect — remove, explain, or delete outright? | interview-only removal / full removal / keep+explain | Interview-only removal | Full removal costs a `extra="forbid"` migration for no user-visible gain | ADR-003 |
| 5 | Recovery path shape | Architecture | How is the post-install "turn it on later" path built? | `/hm:configure` menu entries / menu + detection display / new `config set` command | `/hm:configure` menu entries | All CLI flags already exist; template + dispatch only | ADR-004 |
| 6 | Surface ratchet | Risk | Rendered-surface headroom measured at exactly 0. How do configure/health grow? | equivalent offset / regenerate baseline / both | Equivalent offset | Taken on the premise that raising had no precedent — later found false | ADR-005 (superseded) |
| 7 | Surface ratchet, reopened | Risk | The repo has a documented raise protocol used 4× (incl. `configure` +210 today), and the real pressure is configure entries on the `claude` variant only. Reconsider? | adopt the protocol / keep pure offset / offset then raise the shortfall | Adopt the existing protocol | New evidence from the plan-validator invalidated the round-3 premise; the round-3 rule would have held this change to a stricter bar than the repo holds itself | ADR-005 |

**Assumptions taken without a round** (gate result recorded in-session):
- The documented-commands gate is extended to slash-command names — 4/5, blocked on
  common-ground (CLAUDE.md already forbids scoping a gate to the artifact being fixed).
- The "not asked, defaulted to" disclosure is a compact table in the existing summary — 4/5,
  blocked on confidence.
- The health advisory fires when a CLI is detected and `second_opinion.models` is empty — 4/5,
  blocked on common-ground (RESEARCH P1-6 already specifies it).

## 📐 Architecture Decision Records

### ADR-001: Installed-tool detection is a separate, uncached CLI command
**Status:** Accepted (2026-08-06, via /hm:plan interview)
**Context:** The onboarding flow must know whether `codex` / `agy` / `cursor` are on PATH
before it can offer them. The obvious host, `ProjectProfile`, is served through
`detection_cache` with a 24h ceiling invalidated only by project-manifest mtime
(`detection_cache.py:103-150`) — installing a CLI touches no project manifest.
**Decision:** Add `harness-maker detect-tools --json`, a new uncached command backed by a new
`src/harness_maker/tool_detect.py`. `profile.py` and `detection_cache.py` are not touched.
**Consequences:**
- ✅ Detection is always current; a CLI installed five minutes ago is seen.
- ✅ The detection cache keeps describing only what its invalidation rule actually tracks.
- ⚠️ The slash command makes one extra subprocess call during fresh install.
- ⚠️ One more CLI subcommand to keep documented and tested.
**Rejected alternatives:**
- `ProjectProfile.available_tools` — rejected because a newly installed CLI would read as
  absent for up to 24h, defeating the feature's entire purpose, and the failure would be
  silent (identical in appearance to "genuinely not installed").
- Live-overwriting the field inside `profile()` — rejected because the on-disk cache would
  then persist a value the loader always discards, and `ProjectProfile` would mix cacheable
  and non-cacheable fields with nothing marking which is which.
**Source:** Interview #1

### ADR-002: The fast path asks at most one detection-driven question
**Status:** Accepted (2026-08-06, via /hm:plan interview)
**Context:** "Looks right" exists to install with zero questions. Every axis silently
defaulted there is an axis the user never knew about, but restoring all of them would delete
the fast path's reason to exist.
**Decision:** When detection is positive for `codex` and/or `agy`, "Looks right" asks exactly
one question — enable a cross-model second opinion, and which models. When detection is
negative it asks nothing. All other silently defaulted axes are **disclosed** in the summary
table rather than asked.
**Consequences:**
- ✅ The largest gap (second opinion) is covered without turning the fast path into a wizard.
- ✅ A user with no extra CLIs installed sees exactly today's flow.
- ⚠️ `targets` and Second Brain remain disclosure-only; a user who wants them takes "Adjust a
  few things" or `/hm:configure`. Both are already in that multi-select (`make.md:217-219`).
- ⚠️ `second_opinion` and `autonomy` were **not** in that multi-select, so before Phase 3 the
  detection-negative user — the common case of installing a CLI a week later — had no path
  inside `make` at all. Phase 3 adds both; this is what makes "decide later" true rather than
  contingent on Phase 6.
**Rejected alternatives:**
- Two questions (second opinion + one of targets/Second Brain) — rejected: the second
  question fires for almost every user (Cursor is widely installed), which is the wizard the
  fast path exists to avoid.
- Display only, zero questions — rejected: a summary line is skippable, and the user's report
  was specifically that they were never *asked*.
**Source:** Interview #2

### ADR-003: `consensus` and `caching` leave the interview but keep their schema
**Status:** Accepted (2026-08-06, via /hm:plan interview)
**Context:** Both are asked in the TTY interview via a bare `_ask_with_default` with no
explanation of valid values or meaning (`interview.py:161-162`). Tracing them shows
interview → `synthesize` → `harness.yaml` + one CLAUDE.md prose line, and **no** Python and
**no** stage template branches on their values.
**Decision:** Delete the two interview questions. Keep `InterviewAnswers` / `HarnessConfig`
fields, the `harness.yaml` keys, and the rendered prose. Values come from preset defaults.
**Consequences:**
- ✅ The worst interaction in the interview — a question with no explanation whose answer
  changes nothing — is gone.
- ✅ Zero migration: old `harness.yaml` files keep loading under `extra="forbid"`.
- ⚠️ Two config keys survive that nothing reads.
- ⚠️ **Named residual, accepted:** the surviving prose is not merely informational.
  `templates/stages/review.md.j2:61-67` presents `consensus` to the model executing `/hm:review`
  as a behavioural default — *"`consensus` — `single` | `cross-check (2/3)` | `k-of-n` (default:
  cross-check)"* — while the real threshold is hard-coded K=2 in
  `conditional_router.scope_aware_consensus`. So a user who sets `single` gets a silent no-op:
  the same defect this ADR deletes from the interview, relocated to a surface with more readers.
  It is **not** fixed here because `review.md.j2` carries its own per-command ceiling (29,848)
  in addition to the aggregate, making it a separate budget conversation. Follow-up: add a
  one-line "informational only — threshold is fixed at K=2" marker, or retire the key outright
  along with the full removal this ADR deferred.
**Rejected alternatives:**
- Full removal (fields + keys + prose) — rejected for this PLAN: `extra="forbid"` means every
  existing `harness.yaml` would fail to load without a silent-migration path plus tests, which
  is a schema project, not an onboarding-UX one. Recorded as a candidate follow-up.
- Keep and explain — rejected: the only honest explanation is "this value is displayed in
  your docs and changes no behavior", which removes any reason to ask it.
**Source:** Interview #4

### ADR-004: Post-install recovery is `/hm:configure` menu growth, not a new CLI surface
**Status:** Accepted (2026-08-06, via /hm:plan interview)
**Context:** `second_opinion`, `autonomy`, and `locale` have no entry in `/hm:configure`
(`configure.md.j2:28-75`), so an axis silently disabled at install can only be changed by
hand-editing `harness.yaml` or by `--reinterview` from a real TTY. The `make` CLI already
accepts `--second-opinion-models`, `--autonomy-level`, and `--locale`.
**Decision:** Add the three entries to `/hm:configure`'s menu and dispatch. No new CLI command.
**Consequences:**
- ✅ No new surface to document, test, or keep in sync; the flags are already covered.
- ✅ "Skip for now, change later" becomes a true statement.
- ⚠️ Grows a rendered command, which collides head-on with ADR-005 (see Phase 5).
- ⚠️ Partial-update semantics must be specified per flag or a menu edit can clobber a
  neighbouring setting.
**Rejected alternatives:**
- `harness-maker config set <key> <value>` (the Hermes equivalent) — rejected for this PLAN:
  arbitrary key-path validation plus a re-render trigger design is a phase of its own, and
  `/hm:configure` already covers every axis a user reaches for.
**Source:** Interview #5

### ADR-005: The surface ratchet is handled by this repo's existing compaction-first raise protocol
**Status:** Accepted (2026-08-06, via /hm:plan interview round 4 — **supersedes** the round-3
"equivalent offset only" decision, which was taken on a false premise)
**Context:** `test_aggregate_shipped_surface_does_not_grow` asserts `now <= was` over the summed
characters of the rendered command set. Measured 2026-08-06: claude frozen=361,582 now=361,582;
codex frozen=295,582 now=295,582 — **headroom is exactly zero.** Round 3 decided "equivalent
offset, never raise" on the belief that raising would be precedent-setting. That belief was
wrong, and two further facts reshape the constraint:

1. `test_command_size_budget.py:94-127` documents a **raise protocol with an explicit bar** —
   compact first, show the compaction ratio, prove the residue is *unguarded correctness*
   rather than prose, and quote ADR-011. It has been used **four times**. The most recent is
   `configure` +210 on **2026-08-06**, by PLAN-worktree-side-defaults, for the same defect class
   as ADR-004: *"the residue is not prose — it is the ONLY discoverable way to change the axis,
   and 'there is no supported way to change this' is the defect this PLAN exists to fix."*
2. `configure.md.j2` and `health.md.j2` render **only into the `claude` variant**
   (`synthesize.py:556,562`; the codex file list at `:665-699` carries the stage skills, loop,
   loop-p5-batch and help — not these two). So the per-variant analysis is vacuous for them, and
   the `{% if is_codex %}` caveat does not apply. Further, the baseline renders **this repo's own
   `harness.yaml`** (`_surface_baseline.py:93-120`), which has `second_opinion.models` set — a
   health advisory correctly gated on empty `models` therefore contributes **zero measured
   characters**.

**Decision:** Follow the existing protocol, unchanged, on the `claude` variant only. Compact
first; then, if a residue remains, raise the baseline by exactly that residue, with the
justification comment in the same shape as the precedents — raw addition, compaction ratio, and a
per-item statement of what correctness would be deleted by compressing further.

**The raise is a four-part edit to `tests/structural/surface_baseline.json`, not a constant.**
`test_command_size_budget.py` holds only the prose precedents and `_ATOMIC_RATCHET`, and
`test_the_atomic_table_covers_every_atomic_command:340-354` excludes `configure` and `health`
from that table — so those two files have **no per-command ceiling**, and the JSON is the only
binding number. A raise must move, together:
1. `surface.claude.configure.chars`
2. `surface.claude.health.chars`
3. `aggregate_chars.claude` — which `test_the_committed_numbers_are_not_zeros:89-116` asserts
   equals the per-command sum, so it cannot be bumped alone
4. `payload_digest` — recomputed via `_surface_baseline.payload_digest`, asserted by
   `test_the_committed_numbers_carry_the_generators_digest:140-155`

`render_sha` is deliberately left unchanged by a targeted raise. **Full regeneration via
`build_baseline()` is not available in a task worktree**: it calls `assert_sha_is_durable`
(`_surface_baseline.py:155-180`), which hard-refuses when HEAD is not an ancestor of
`main`/`origin/main` — precisely the state of `hm/<slug>` — and its error text is about
squash-land durability, so it reads as unrelated to the budget task. Regeneration is a base
checkout operation; the targeted four-part edit is what the precedents actually did.
**Consequences:**
- ✅ Consistent with four precedents and today's `configure` raise instead of inventing a
  stricter local rule for the same file.
- ✅ Removes the planned HALT: the residue has a sanctioned destination.
- ⚠️ Compaction is still mandatory and comes first — this is not licence to add freely. The bar
  is the residue being unguarded correctness, and the executor must show the ratio.
- ⚠️ The health advisory's bytes are **invisible to the ratchet** (it renders to nothing under
  the measured harness). Its correctness must be proven by render fixtures, never by a green
  aggregate test.
**Rejected alternatives:**
- Pure equivalent offset with no raise (the round-3 decision) — rejected once the protocol and
  its four precedents were found: it would impose a stricter bar on this change than the repo
  imposes on itself, with a HALT as the failure mode.
- Putting the additions only in the unbudgeted plugin-owned `commands/make.md` — rejected: the
  recovery path (F3) and the advisory (F4) must exist in the *rendered* harness, which is the
  only thing a consuming project has.
**Source:** Interview #6, reopened by Interview #7 after the plan-validator surfaced the protocol

### ADR-006: Prose recipes are gated by a structural contract test, not by read-through
**Status:** Accepted (2026-08-06, promoted from cross-model second opinion — codex finding
`498985f277bc89da`, corroborated by antigravity `9c658ea52816e5a9`)
**Context:** Phases 3 and 6 change branch logic that an LLM executes from prose. This repo has
shipped four silent-skip bugs in exactly that shape, and CLAUDE.md records the reason: a prose
recipe has no execution surface, so tests can only grep its text.
**Decision:** Any phase that changes control flow inside a command markdown file ships a
structural contract test asserting the *branch structure*, not merely the presence of
substrings — both fast-path branches exist, the no-detection branch reaches dispatch without a
question, at most one conditional question is defined, and the selected value flows to the
named flag.
**Consequences:**
- ✅ The branch contract is machine-checked, so a later prose edit that flattens it fails.
- ⚠️ A structural test over markdown is inherently approximate; it proves shape, never that an
  LLM executes it. Phase 7's acceptance scenarios cover the rest.
**Rejected alternatives:**
- Manual read-through as the exit criterion — rejected: it is the exact gate that has already
  failed four times here.
**Source:** Cross-model second opinion, reconciled in Step 4

## 🏗️ Technical Design

### Current state

| Concern | Today | Evidence |
|---|---|---|
| Real interview surface | `commands/make.md` (plugin-owned, unbudgeted) | 678 lines, AskUserQuestion-driven |
| TTY interview | near-dead, no stdin under slash commands | `interview.py:139-181`, `make.md:665-673` |
| Tool detection | none | `profile.py:94`; `shutil.which` only post-selection at `cli.py:1464`, `interview.py:520` |
| Fast-path disclosure | 5 of 14 axes | `make.md:180-207` |
| Fast-path branch | "Looks right" jumps straight to §4.6 | `make.md:215` |
| Recovery path | absent for second_opinion / autonomy / locale | `configure.md.j2:28-75` |
| Health coverage | gated on the axis already being on | `health.md.j2:61` |
| Quick-start | names `/hm:ai-readiness`, which does not exist | `make.md:601` |
| Zero-effect axes | `consensus`, `caching` | no template or Python reads their value |
| Surface budget | headroom 0 on both variants | measured 2026-08-06 |

### Affected components

- **New:** `src/harness_maker/tool_detect.py`; `tests/unit/test_tool_detect.py`;
  `tests/integration/test_detect_tools_cli.py`; `tests/structural/test_make_fastpath_contract.py`;
  `tests/e2e/test_onboarding_paths.py`; `tests/manual/ONBOARDING_ACCEPTANCE.md`;
  `work-docs/BASELINE-onboarding-offset-ledger.md`.
- **Modified:** `commands/make.md`; `src/harness_maker/cli.py`; `src/harness_maker/interview.py`;
  `src/harness_maker/templates/commands/hm/configure.md.j2`;
  `src/harness_maker/templates/commands/hm/health.md.j2`;
  `tests/structural/test_documented_commands_exist.py`; `CHANGELOG.md`; the five version files.
- **Deliberately untouched:** `profile.py`, `detection_cache.py`, `models.py` schema fields.

### Contract — `harness-maker detect-tools --json`

```json
{"codex": {"installed": true}, "antigravity": {"installed": false}, "cursor": {"installed": true}}
```

- Uncached. One `shutil.which` per tool. Binary names: `codex`, `agy`, `cursor`.
- `agy` maps to the JSON key `antigravity`, matching `SECOND_OPINION_MODELS`.
- `installed` means **the binary is on PATH**. It does **not** mean authenticated — no login
  probe is performed, and every user-facing string must say so (codex finding
  `5f60bf16ec0a3fcd`). Authentication failure remains the existing graceful-degrade path.
- `cursor` has exactly one consumer: the §4.3 detection display line. It is shown with wording
  that states no question follows and points at "Adjust a few things" for `targets`. It never
  triggers a question — ADR-002 caps the fast path at one, and that one belongs to second
  opinion. Announcing a detection with no offer is itself the "why didn't it ask?" complaint
  this PLAN exists to fix, so the wording carrying its own next step is load-bearing, not
  decoration.
- `obsidian_vault` is **not** in the contract. A global-vault search has no defined rule, would
  need home-directory traversal, and would emit a personal path into JSON — out of scope for a
  second-opinion-detection feature (codex finding `d791a4097cba4ebc`).
- Exactly one JSON object on stdout; diagnostics on stderr; result independent of cwd.
- Never reads or writes `detection_cache`.

### Data flow — fresh install

```
/harness-maker:make
  §4.1  profile --json          (cached, project signals)
        detect-tools --json     (uncached, tool signals)          ← new
  §4.2  smart defaults
  §4.3  summary  = 5 existing lines
                 + "not asked, defaulted to" table (completeness-defined)
                 + detection line when positive
  §4.4  Looks right ─┬─ detection positive → ONE question → §4.6
                     └─ detection negative → §4.6                  ← branch made explicit
  §4.6  dispatch (adds --second-opinion-models when the question was answered)
```

The summary table's contents come from an **explicit allowlist**; its *completeness* is enforced
by a separate drift arm that classifies every `HarnessConfig` top-level field as `asked` /
`disclosed` / `internal` and fails on an unclassified one. Contents-by-derivation was rejected —
it either drags in internal blocks or collapses back to the fixed list that codex finding
`363c74e68a0f5112` was accepted to remove. See Phase 3 for the two arms and the classification
of `consensus` / `caching` / `permissions.deny_dangerous`.

### Health advisory — execution contract

The advisory's condition has two halves, gated at **different times**. Keeping them apart is
what makes both ADR-001 and ADR-005's zero-cost claim true at once:

- **Render time — the `models` half.** The whole block is wrapped in
  `{% if not config.second_opinion.models %}`. Freezing this at render is safe because the only
  supported way to change `models` is `/hm:configure`, which re-renders. This wrapper is also
  why the block costs **zero measured characters**: the baseline renders this repo's own
  harness, whose `models` is non-empty (`.claude/harness.yaml:125`), so the block is absent from
  the measured surface entirely.
- **Run time — the detection half.** Inside that wrapper, a shell-out to `detect-tools --json`.
  This half cannot be frozen at render; that is ADR-001's whole reason, and the valid half of
  antigravity finding `75327c0bbae753da`.

So the advisory fires only when `second_opinion.models` is empty **and** at least one model CLI
is present. Missing command, non-zero exit, or unparseable JSON produce no advisory and no
failure — `/hm:health` never blocks on it. Its bytes are **not** ratchet-visible, so they are
recorded separately in the Phase 5 ledger and never counted toward the residue.

### Configure — preserve/clear semantics

Each new entry states, in the template, what an unchanged value does (codex finding
`4ee3418ebff8def7`):
- `--second-opinion-models ""` disables; omitting the flag preserves the current list; per-model
  sub-blocks (`codex.hermetic`, `antigravity.model`) survive a models-list change.
- `--autonomy-level gated` turns auto-advance off while preserving persistence and caps;
  `--autonomy-persistent` is passed only on an explicit choice.
- A `locale` change applies to both the live conversation and the re-render.

## 📝 Implementation Plan

### Phase 0 — Extend the documented-commands gate (RED first)
Status: DONE
- `depends_on:` `[]` · `parallel_group:` `serial-gate` · `merge_hazards:` none
- **Scope in:** `tests/structural/test_documented_commands_exist.py`. **Out:** everything else.
- Extend the scanner to slash-command references. Cover **both** surface forms — `/hm:<name>`
  and the Codex `@hm-<name>` form, which the templates render conditionally (codex finding
  `cd69459cb2252a41`). Source the valid-name set from the **template/registry**, not from
  checked-in `.claude/commands/**`, whose contents depend on the local checkout's config
  (codex finding `702c865624aa1d2b`). Scan `commands/**/*.md` — the plugin's own surface, the
  one the previous gate's own docstring warns about omitting.
- Add non-vacuity arms: a real `/hm:health` reference is accepted; a synthetic
  `/hm:does-not-exist` is rejected.
- **Exit:** `uv run pytest tests/structural/test_documented_commands_exist.py` FAILS, naming
  `/hm:ai-readiness` at `commands/make.md:601`; the two non-vacuity arms PASS.
- **Risk:** low · **Rollback:** revert the test file (nothing depends on it yet).

### Phase 1 — Quick-start: correct command + verification step (P0-1, P1-9)
Status: DONE
- `depends_on:` `[0]` · `parallel_group:` `serial-make` · `merge_hazards:` `commands/make.md`
  is also edited by Phase 3 — these two must not run concurrently.
- **Scope in:** the quick-start block of `commands/make.md` (≈ lines 597-606). **Out:** the rest
  of the file.
- Replace `/hm:ai-readiness` with `/hm:health`. Promote it to the first line as an explicit
  verification step with named success criteria (commands listed, no missing-asset findings,
  advisory lines readable), following the Hermes "verify the install works" pattern.
- **Exit:** Phase 0's test is GREEN.
- **Risk:** low · **Rollback:** Phase 0.

### Phase 2 — `detect-tools` command (P0-2)
Status: DONE
- `depends_on:` `[]` · `parallel_group:` `parallel-a` · `merge_hazards:` none
- **Scope in:** new `src/harness_maker/tool_detect.py`; command registration in `cli.py`;
  `tests/unit/test_tool_detect.py`; `tests/integration/test_detect_tools_cli.py`.
  **Out:** `profile.py`, `detection_cache.py`, `models.py`.
- Implement the §Contract above.
- Unit tests monkeypatch PATH for present and absent, both tools.
- Integration tests use Typer's `CliRunner` (codex finding `0cb905dbfdb8d704`) and assert:
  the command is registered under the expected name; stdout parses as exactly one JSON object;
  diagnostics go to stderr; the result is identical from two different cwds; `agy` present maps
  to `antigravity: {installed: true}`; and **no** `detection_cache` file is read or written
  (asserted against an isolated `cache_dir`).
- **Exit:** both test files green; `ruff check` and `mypy --strict` clean on the new module.
- **Risk:** low · **Rollback:** delete the module and its registration.

### Phase 3 — Fast-path branch contract + disclosure table (P0-3, P0-4)
Status: DONE
- `depends_on:` `[1, 2]` · `parallel_group:` `serial-make` · `merge_hazards:` shares
  `commands/make.md` with Phase 1; the dependency edge is what serialises them (codex finding
  `91473a940e80f490`, antigravity `23c5d03d766e3603`).
- **Scope in:** `commands/make.md` §4.1, §4.3, §4.4; new
  `tests/structural/test_make_fastpath_contract.py`. **Out:** §5, §6, §6.5.
- Add the `detect-tools --json` call to §4.1 beside the profile scan.
- §4.3: add the completeness-defined "not asked, defaulted to" table, plus a detection line when
  positive. Update the **"Looks right" option label** so it no longer promises an
  unconditionally question-free install (antigravity finding `e8398d0fa0d11094`).
- §4.4: replace the single "jump to §4.6" instruction with two explicit branches — detection
  positive → one second-opinion question → §4.6; detection negative → §4.6. Without this the
  question added anywhere else is **unreachable**, because §4.4 today jumps straight past it
  (codex finding `88bc5ee332adccd6`).
- Add `second_opinion` and `autonomy` to the **"Adjust a few things"** multi-select (§4.4), which
  today lists only preset / locale / dev_mode / targets / grade_threshold / mechanical_checks /
  wrapup_docs / ref_folders / sibling_repos / second_brain (`make.md:217-219`). `commands/make.md`
  is unbudgeted, so this costs nothing and is the only in-`make` path for a detection-negative
  user.
- Fold the pre-dispatch `shutil.which` prose at `make.md:274-276` into the §4.1 `detect-tools`
  call so a single detection implementation remains.
- Write the structural contract test per ADR-006.
- **Exit:** `test_make_fastpath_contract.py` green with arms for: detect-tools invoked in §4.1;
  both fast-path branches present; the no-detection branch reaching dispatch with no question;
  at most one conditional question defined; the answer flowing to `--second-opinion-models`;
  `second_opinion` and `autonomy` present in the "Adjust a few things" list; and the disclosure
  table's axis set matching the **enumerated set below**. Plus
  `test_no_positional_params_in_commands.py` still green.
- **The disclosure set is enumerated here, not derived from dispatch argv.** The dispatch block
  (`make.md:562-578`) passes 14 flags and carries **no** `--worktree` and no
  `--autonomy-persistent`; `worktree.enabled` is set from the preset by
  `cli._apply_worktree_enabled` and decides whether every later `/hm:` stage runs in
  `.worktrees/<slug>/` — the highest-impact silent axis of them all. An argv-derived test would
  go green while dropping it. Required rows: `second_opinion.models`, `autonomy.level`,
  `autonomy.persistent`, `worktree.enabled`, `targets`, `dev_mode`, `focus`, `domains`,
  `default_model`, `ref_folders`, `sibling_repos`, `second_brain`, `wrapup_docs`. The test's
  expected set is built from `HarnessConfig` fields / `synthesize` inputs, with
  `worktree.enabled` and `autonomy.persistent` carrying their own named arms so a future argv
  refactor cannot silently drop them.
- **Two mechanisms, not one derivation.** "Build the expected set from `HarnessConfig`" and
  "these 13 rows" are different sets — a literal field walk drags in `delivery_metrics`,
  `work_docs`, `interview.deep_gate`, `schema_version`, which nobody wants in an onboarding
  summary. So the test has two arms:
  1. **Allowlist arm** — the disclosed set is an explicit constant: the 13 rows above **plus
     `permissions.deny_dangerous`** (default `False`, i.e. the destructive-command baseline is
     silently *not* applied — a security-relevant silent default belongs in a disclosure table).
     The table must equal it.
  2. **Drift arm** — enumerate `HarnessConfig`'s top-level fields and fail when one is
     classified as none of `asked` / `disclosed` / `internal`. This gives completeness a real
     gate without forcing the table's contents to be derived, which is what would have
     re-created the fixed-list defect under a new label.
  `consensus` and `caching` are classified **`internal`**, not `disclosed`: ADR-003 makes them
  silently preset-defaulted, and disclosing an axis with zero runtime effect is noise. That
  classification is the thing ADR-003's follow-up would flip if the keys are ever retired.
- **Risk:** medium — prose control flow · **Rollback:** Phase 1.

### Phase 4 — TTY interview cleanup (P1-7, P1-4)
Status: DONE
- `depends_on:` `[2]` · `parallel_group:` `parallel-b` · `merge_hazards:` none
- **Scope in:** `src/harness_maker/interview.py` (`_ask_second_opinion`, `interview()`, module
  docstring) and its unit tests. **Out:** `models.py`, templates.
- **Why touch a near-dead path at all:** `--reinterview` from a real terminal remains the only
  way to re-ask the dimensions the slash command does not cover (workflows, reviewer enablement,
  anti-rot — `make.md:665-673`), so this prompt is reachable, just rarely.
- Rewrite `_ask_second_opinion` as numbered choices annotated per model with
  `installed` / `not installed`, worded as **binary present, authentication unverified**. An
  unrecognised entry re-prompts instead of being dropped with a log line. The existing
  antigravity model-pin follow-up is unchanged.
- **Multi-select representation** (codex finding `5f60bf16ec0a3fcd`, second half): both models
  may be enabled at once, and the current prompt accepts a comma list (`interview.py:463-464`).
  The numbered form must preserve that — the options are enumerated as `1) codex  2) antigravity
  3) both  4) none`, with the free-text comma list still accepted for backward compatibility.
  Tests cover the "both" selection through both entry forms.
- Delete the `consensus` and `caching` questions from `interview()`; the fields keep their
  defaults. Update the module docstring, which still lists both as interview steps (codex
  finding `fe2ef3868f70dfce`), and any prompt-order or snapshot test that encodes the sequence.
- **Exit:** new unit tests for the prompt (both detection states, re-prompt on bad input);
  `answers_from_harness_yaml` round-trip green; full `tests/unit` green.
- **Risk:** low · **Rollback:** revert `interview.py`.

### Phase 5 — Compaction-first budget ledger (analysis only, no behaviour change)
Status: DONE
- `depends_on:` `[2]` · `parallel_group:` `serial-surface` · `merge_hazards:` none
- **Scope in:** `work-docs/BASELINE-onboarding-offset-ledger.md`. **Out:** every template.
- Measure on the **`claude` variant only** (ADR-005 fact 2): the raw byte cost of the three
  configure entries with their preserve/clear prose. Record the health advisory's cost
  separately and mark it **not ratchet-visible** — under the measured harness it renders to
  nothing, so it never reaches the aggregate.
- Then compact, in the shape the four precedents use: at least two passes, with the before/after
  ratio recorded. Enumerate candidate cuts in `configure.md.j2`, each with an explicit
  load-bearing / not-load-bearing judgement.
- **Exit:** the ledger states (a) raw addition, (b) post-compaction residue with the ratio, and
  (c) for each residue item, the correctness that compressing it further would delete. Net ≤ 0
  means no raise is needed; a positive residue is carried into Phase 6 as a
  protocol-conforming raise. There is **no HALT** exit — ADR-005 gives the residue a sanctioned
  destination.
- **Risk:** low · **Rollback:** none needed (analysis only).

### Phase 6 — configure entries + health advisory (P1-5, P1-6)
Status: DONE
- `depends_on:` `[5]` · `parallel_group:` `serial-surface` · `merge_hazards:`
  `configure.md.j2` and `health.md.j2` share **one** aggregate character budget — both edits and
  their offsets must land in this single phase, or the ratchet fails between them.
- **Scope in:** both templates; new render tests. **Out:** `commands/make.md`, `interview.py`.
- Configure: add `second_opinion` / `autopilot` / `locale` menu entries and their dispatch
  branches with the preserve/clear semantics from §Technical Design.
- Health: add the runtime advisory per §Health advisory — execution contract.
- Apply the compaction from the Phase 5 ledger. If a residue remains, perform the four-part
  `tests/structural/surface_baseline.json` edit specified in ADR-005 (`configure.chars`,
  `health.chars`, `aggregate_chars.claude` = the per-command sum, recomputed `payload_digest`;
  `render_sha` untouched), and put the justification comment in `test_command_size_budget.py`
  beside the precedents (raw addition, compaction ratio, per-item unguarded correctness, ADR-011
  quoted). Do **not** invoke `build_baseline()` — it refuses from this branch.
- **Exit (this phase, not deferred — codex finding `a5ccf3b280ccb0dd`):**
  `test_aggregate_shipped_surface_does_not_grow` GREEN, either at the unchanged constant or at a
  protocol-conforming raise; render tests covering advisory-on and advisory-off fixtures and the
  three configure dispatch argument shapes; a measured byte delta matching the Phase 5 ledger
  within ±2%. The advisory's correctness is proven **only** by the render fixtures — the
  aggregate test cannot see it (ADR-005).
- **Risk:** medium · **Rollback:** revert both templates and, if it was edited, the four fields
  in `surface_baseline.json` (Phase 5's ledger survives).

### Phase 7 — End-to-end acceptance (codex finding `f0881c831b73173c`)
Status: DONE
- `depends_on:` `[3, 4, 6]` · `parallel_group:` `serial-close` · `merge_hazards:` none
- **Scope in:** `tests/e2e/test_onboarding_paths.py`; `tests/manual/ONBOARDING_ACCEPTANCE.md`.
- Scenarios: (1) no tools → Looks right asks zero extra questions; (2) codex only → exactly one
  question, and both enable and decline produce the right dispatch; (3) agy only, and both
  present; (4) `/hm:configure` enables/disables second opinion, changes autonomy, changes
  locale; (5) `/hm:health` shows the advisory in the installed-but-disabled state and stays
  silent otherwise; (6) malformed or missing `detect-tools` output degrades without failing.
- Mechanise what a fixture can drive (PATH-stubbed `detect-tools`, CLI dispatch assertions,
  render assertions). The remainder — an LLM actually following the prose — is a dated manual
  checklist, per the repo's existing IDE-behaviour precedent.
- **Exit:** the e2e file green; the manual checklist filled in with dated results and every row
  either passed or explicitly recorded as failed.
- **Risk:** medium · **Rollback:** Phase 6.

### Phase 8 — Docs + version sync
Status: DONE (with a recorded scope carve-out)
- `depends_on:` `[7]` · `parallel_group:` `serial-close` · `merge_hazards:` none
- **Scope in:** `CHANGELOG.md`; the five version files (`.claude-plugin/plugin.json`,
  `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`,
  `src/harness_maker/__init__.py`); `README*.md` and `docs/` where they name commands;
  `tests/structural/test_documented_commands_exist.py` (gate extension).
  **Out:** every template and source module touched by Phases 0-7.
- **Dead-slash-name cleanup, moved here from Phase 0** (Phase A.5 reviewer, phase 0). The
  Phase 0 gate scans `commands/**` only. Measured 2026-08-06, the docs surface still names
  retired commands: `README.md:522,524,794` (`/hm:ai-readiness`, `/hm:refresh`),
  `README.md:523,792,831,902,920,935` + `README.ko.md:424` (`/hm:personalization-audit`),
  plus 12+ in `docs/**` including the retired fused workflows. Several sit in roadmap or
  history prose, where the fix is a judgement call, not a rename — which is why this is a
  closing phase and not a one-line edit inside Phase 1. Resolve each, then extend
  `_plugin_command_docs()` to include `README*.md` and `docs/**` (excluding `docs/adr/**`,
  on the existing historical-record reasoning) so the surface stays clean.
- **Exit addition:** the extended gate is GREEN over `commands/**` + `README*.md` + `docs/**`.
- CHANGELOG entry; the five-file version bump (`.claude-plugin`, `.cursor-plugin`,
  `.codex-plugin`, `pyproject.toml`, `__init__.py`) per CLAUDE.md; README/docs updates naming
  `detect-tools`.
- **Exit:** full `pytest` green; `ruff check` + `ruff format --check` + `mypy --strict` clean;
  `test_documented_commands_exist.py` green with the new command name documented.
- **Risk:** low · **Rollback:** Phase 7.

## 🧪 Testing Strategy

**Unit.** `tool_detect` for present/absent per tool and the `agy`→`antigravity` mapping;
`_ask_second_opinion` for both detection states and re-prompt-on-bad-input; interview
question-order after the `consensus`/`caching` deletion.

**Integration.** Typer `CliRunner` over `detect-tools --json` — registration, single JSON object
on stdout, stderr separation, cwd independence, and no cache I/O against an isolated
`cache_dir`.

**Structural.** The extended documented-commands gate (both `/hm:` and `@hm-` forms, with
non-vacuity arms); the fast-path branch contract; the unchanged aggregate surface ratchet.

**Render.** Advisory-on and advisory-off fixtures for `health.md.j2`; the three configure
dispatch argument shapes.

**E2E + manual.** Phase 7's six scenarios, mechanised where a fixture can drive them and
recorded in a dated manual checklist where only an LLM's execution can settle it.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Compaction leaves a residue that does not clear the protocol's "unguarded correctness" bar | low | the raise is unjustified and should be refused at review | Phase 5 states the bar per residue item before Phase 6 spends any budget; if an item is prose rather than correctness, it is cut instead of carried. Phases 0-4 ship independently either way. |
| R8 | The health advisory ships broken and nothing notices, because the ratchet cannot see it | medium | F4 stays open while looking closed | ADR-005 records the blind spot explicitly; Phase 6's exit requires advisory-on/off render fixtures, and Phase 7 scenario 5 exercises the installed-but-disabled state end to end. |
| R2 | The prose branch contract passes while an LLM still skips the question | medium | the reported bug persists | ADR-006 structural test **plus** Phase 7 scenario 2, which exercises the enable and decline paths separately. |
| R3 | The disclosure table drifts as new axes are added | medium | F1 quietly returns | The contract test compares the table against an enumerated set built from `HarnessConfig` / `synthesize` inputs — **not** dispatch argv, which omits `worktree.enabled` and `autonomy.persistent` entirely — with a named arm for each CLI-derived axis. |
| R4 | "installed" is read as "ready to use" and a user enables a model whose login expired | medium | a confusing skip at review time | Wording is fixed by contract ("binary present, authentication unverified"); the existing graceful degrade already covers the runtime case. |
| R5 | The health advisory's runtime shell-out slows or noises `/hm:health` | low | mild | One `shutil.which`-backed call; any failure yields no advisory and no error. |
| R6 | Editing `commands/make.md` in two phases produces a conflict | low | rework | Phase 3 `depends_on: [1]` and both sit in `serial-make`. |
| R7 | The `@hm-` Codex form is missed by the extended gate | medium | the same class of dead reference survives on the Codex surface | Phase 0 covers both forms explicitly and sources names from the registry, not from a rendered checkout. |

## ✅ Success Criteria

- [x] `/hm:ai-readiness` no longer appears in the **plugin command surface** (`commands/**`),
      and a gate fails if it returns. *(Phase 1.)*
- [x] The same is true of `README*.md` and `docs/**`, with the gate extended to cover them.
      *(Phase 8 — see its scope note; measured 2026-08-06 as 11 lines across `/hm:ai-readiness`,
      `/hm:personalization-audit`, `/hm:refresh`, several in roadmap/history framing that needs
      a judgement call rather than a rename.)*
- [x] `harness-maker detect-tools --json` exists, is uncached, and reports `codex` / `antigravity`
      / `cursor` presence correctly from any cwd.
- [x] With `codex` installed, "Looks right" asks exactly one second-opinion question; with no
      tool installed it asks none.
- [x] The fresh-install summary discloses every axis that is set without being asked, including
      `worktree.enabled` and `autonomy.persistent`, which never appear in the dispatch arguments.
- [x] `second_opinion` and `autonomy` are selectable from "Adjust a few things".
- [x] `/hm:configure` can turn second opinion, autopilot, and locale on or off after install.
- [x] `/hm:health` surfaces an advisory in the installed-but-disabled state and is silent
      otherwise.
- [x] The TTY interview no longer asks `consensus` or `caching`, and its second-opinion question
      shows per-model installation state.
- [x] The aggregate rendered surface has not grown on either variant.
- [x] Full test suite, `ruff`, and `mypy --strict` are clean.

## 🔍 Plan Validation

**Cross-model second opinion (Step 4 pre).** Production preset with
`second_opinion.models: ["codex", "antigravity"]` — both mandatory, both `status: invoked`.
Codex returned 15 findings, antigravity 5. Folded into this PLAN:

| Finding | Model | Severity | Disposition |
|---|---|---|---|
| `88bc5ee332adccd6` fast-path question unreachable at `make.md:215` | codex | P0 | accepted → Phase 3 rewrites the §4.4 branch |
| `498985f277bc89da` Phase 3 has no real exit criterion | codex | P0 | accepted → ADR-006 + contract test |
| `f0881c831b73173c` no end-to-end acceptance phase | codex | P0 | accepted → Phase 7 |
| `75327c0bbae753da` health advisory cannot be a render-time condition | antigravity | P0 | accepted → runtime execution contract; byte cost budgeted in Phase 5 |
| `3cf16c64dfb6b7db` Phase 5 offset is a hope, not a plan | codex | P1 | accepted → split into a measurement phase with a per-variant ledger and a halt exit |
| `741dff9accf84ec1` advisory execution contract missing | codex | P1 | accepted → §Health advisory contract |
| `cd69459cb2252a41` gate input set is unstable; `@hm-` form unchecked | codex | P1 | accepted → Phase 0 sources names from the registry, covers both forms |
| `d791a4097cba4ebc` `obsidian_vault` detection undefined | codex | P1 | accepted → dropped from the contract |
| `0cb905dbfdb8d704` no CliRunner integration test | codex | P1 | accepted → Phase 2 integration arms |
| `363c74e68a0f5112` the "8-row" table is a count, not a requirement | codex | P1 | accepted → completeness-defined, `dev_mode` included |
| `4ee3418ebff8def7` configure preserve/clear semantics undefined | codex | P1 | accepted → §Configure semantics |
| `91473a940e80f490` Phase 3 `depends_on` contradicts its own hazard note | codex | P1 | accepted → `[1, 2]`, `serial-make` |
| `a5ccf3b280ccb0dd` Phase 5 defers its own verification to the closing phase | codex | P1 | accepted → Phase 6 carries its own exit tests |
| `702c865624aa1d2b` new gate could pass vacuously | codex | P2 | accepted → non-vacuity arms |
| `5f60bf16ec0a3fcd` "installed" conflated with "authenticated" | codex | P2 | accepted → wording fixed by contract |
| `9c658ea52816e5a9` manual read-through cannot verify the branch | antigravity | P2 | accepted → duplicate of `498985f277bc89da`, same fix |
| `23c5d03d766e3603` Phase 3 dependency error | antigravity | P2 | accepted → duplicate of `91473a940e80f490` |
| `fe2ef3868f70dfce` `interview.py` docstring still lists the deleted questions | codex | P3 | accepted → Phase 4 scope |
| `e8398d0fa0d11094` "Looks right" label still promises zero questions | antigravity | P3 | accepted → Phase 3 updates the label |
| `1a0cdcda18e46d51` Phase 4 leaves `consensus`/`caching` in `make.md`'s 14 questions | antigravity | P1 | **rejected** — factually wrong. `make.md:223-281` enumerates locale, preset, dev_mode, targets, focus, mechanical_checks, grade_threshold, domains+model, wrapup docs, ref_folders, sibling_repos, Second Brain, second opinion, autopilot. Neither axis is asked there. |

**plan-validator, pass 1: `MAJOR_REVISION`.** Eight critiques, two critical. Both critical
findings were verified against the repo before acceptance, and both held:

| # | Critique | Resolution |
|---|---|---|
| C1 (critical) | Phase 3's exit compared the disclosure table to **dispatch argv**, which carries no `--worktree` and no `--autonomy-persistent` → the test would have gone green while dropping `worktree.enabled`, the axis that decides where every later stage writes | Phase 3 now enumerates the required set explicitly and derives the expected set from `HarnessConfig` / `synthesize` inputs, with named arms for both CLI-derived axes. R3 rewritten. |
| C2 (critical) | ADR-005 mis-modelled the ratchet: `configure`/`health` render **only** into the `claude` variant, so the per-variant analysis was vacuous; and the advisory, gated on empty `models`, contributes **0** measured chars because the baseline renders this repo's own harness | ADR-005 rewritten. Interview round 4 reopened the decision after finding the documented four-precedent raise protocol; the HALT exit is gone, and the advisory's ratchet-invisibility is now a recorded blind spot with R8 and render-fixture coverage. |
| W3 | ADR-005 ignored the repo's own compaction-first raise protocol | Superseded by the round-4 decision. |
| W4 | ADR-002 claimed "Adjust a few things" as a recovery path; it lists neither `second_opinion` nor `autonomy` | Phase 3 adds both (`commands/make.md` is unbudgeted); ADR-002's consequences corrected. |
| W5 | ADR-003 relocates the `consensus` trap into `review.md.j2:61-67`, which presents it to the reviewing model as a behavioural default while K=2 is hard-coded | ADR-003 consequence amended to a named accepted residual with a follow-up; not fixed here because `review` carries its own per-command ceiling. |
| W6 | The RESEARCH defining every P0/P1 ID is absent from the task worktree | Scope restated inline as a table in the Executive Summary. |
| S7 | `cursor` in the contract with no named consumer | Consumer named: the §4.3 display line, with wording that states no question follows. |
| S8 | Phase 4's justification unstated; a second detection implementation left at `make.md:274-276` | Justification added to Phase 4; the duplicate folded into Phase 3's `detect-tools` call. |

The validator also independently confirmed the rejection of antigravity `1a0cdcda18e46d51`
by reading `commands/make.md:217-219` and `:223-281`, and refuted the second half of
antigravity `75327c0bbae753da` ("offset likely impossible") using the baseline generator.

**plan-validator, pass 2: `MAJOR_REVISION`.** All eight pass-1 critiques verified resolved. Both
criticals were re-checked at source: C1 confirmed fixed; C2's three factual claims confirmed
correct (the protocol at `test_command_size_budget.py:94-127`; `configure`/`health` in
`synthesize.py`'s `_base_files` only, absent from `_codex_target_files:665-699`; `models`
non-empty in this repo's harness). Three new defects, all introduced by the revision itself, all
now fixed:

| # | Critique | Resolution |
|---|---|---|
| P2-C1 (critical) | Phase 6 said to raise "the baseline constant" in `test_command_size_budget.py`. **No such constant exists** — the binding numbers live in `tests/structural/surface_baseline.json`, `configure`/`health` have no per-command ceiling at all (`test_the_atomic_table_covers_every_atomic_command:340-354` excludes them), the aggregate must equal the per-command sum, `payload_digest` must be recomputed, and `build_baseline()` **hard-refuses** from a task branch via `assert_sha_is_durable`. The phase could not have reached its exit as written. | ADR-005 and Phase 6 now name the artifact and specify the four coupled fields, leave `render_sha` alone, and state that regeneration is a base-checkout operation. Rollback line corrected. |
| P2-W2 | The advisory's byte cost was asserted **both ways** — §Health advisory said the bytes count toward ADR-005, ADR-005 and Phase 5 said they are invisible. The render-time gate that reconciles them was never stated, so an executor could legitimately ship an unconditional block and blow the residue. | §Health advisory now splits the condition into a render-time `{% if not config.second_opinion.models %}` wrapper and a runtime detection shell-out inside it, with the reason each half is gated where it is. The contradicting sentence is gone. |
| P2-W3 | Phase 3 gave the disclosure test two non-equal definitions (13 enumerated rows *and* "built from `HarnessConfig` fields"), and the completeness rule admitted axes the list omits — `permissions.deny_dangerous`, plus `consensus`/`caching`, which ADR-003 itself converts to silent defaults. An executor would hard-code the 13 and re-create the fixed-list defect under a new label. | Split into an allowlist arm (the 13 + `permissions.deny_dangerous`) and a drift arm classifying every top-level field as `asked`/`disclosed`/`internal`. `consensus`/`caching` classified `internal`, with the reason stated. |

Also noted, not a defect: the repo has **five** raise entries, not four. The count is corrected
here; ADR-005's argument is unaffected.

**Validator loop closed at pass 2** per this stage's "re-run once only" rule. The three pass-2
defects were fixed rather than accepted, and each fix was verified against the cited source
before landing — but no third validator pass confirms them, so that verification is mine, not
the validator's.

---

## 📌 Execution notes (filled by /hm:execute, 2026-08-06)

### Deviations from the plan as written

1. **Phase 6 shipped implementation before its render tests.** The TDD ordering (A → A.5 → B
   → C → D) held for Phases 0, 2, 3 and 4 — each has a recorded RED with the right failure
   reason. For Phase 6 the templates were edited first so the byte cost could be measured for
   the Phase 5 ledger, and
   `tests/unit/test_render_configure_health_second_opinion.py` was written afterwards. It
   passes, but it never went RED against the pre-change template, so it is weaker evidence
   than the other phases' tests.

2. **A third baseline invariant surfaced that neither the PLAN nor the validator knew about.**
   `tests/structural/test_baseline_delta_attribution.py` requires every changed
   `surface_baseline.json` key to have an attribution row in `work-docs/BASELINE-DELTA-P7.md`,
   and the aggregate figure in that document to MATCH the baseline. ADR-005's "four coupled
   fields" is therefore **five** artifacts. The rows were appended; the gate caught this, which
   is what it is for.

3. **Phase 8's docs cleanup was cut down to the READMEs.** The PLAN sized it from the Phase-0
   reviewer's estimate of ~11 lines. Measured during execution it is **~40 sites**, and
   `docs/HOW-IT-WORKS.md` gives `hm:refresh`, `hm:ai-readiness` and `hm:personalization-audit`
   whole numbered sections (6.1, 6.2, 6.3). Resolving those means deciding what replaced each
   capability — a documentation rewrite, not a rename. What shipped: both READMEs are clean and
   the gate now covers `commands/**` + `README*.md`. `docs/**` is knowingly still uncovered.

### Follow-ups this work deliberately did not take

| Item | Why deferred | Evidence |
|---|---|---|
| `docs/**` retired-command cleanup + gate extension | ~40 sites; three full sections in `HOW-IT-WORKS.md` need a rewrite, not a rename | `_plugin_command_docs()` docstring |
| `consensus` in `review.md.j2:61-67` presented to the reviewing model as a behavioural default while K=2 is hard-coded | `review` carries its own 29,848 per-command ceiling — a separate budget conversation | ADR-003 consequences |
| Full removal of the `consensus` / `caching` keys | `extra="forbid"` makes it a schema migration | ADR-003 rejected alternatives |
| P2 items (14-question batching, ref_folders multi-select, per-question skip) | Out of scope by Interview #3 | Executive Summary |
