---
type: plan
task_slug: harness-economics-observability
status: complete
created: 2026-07-25
tags: [harness-maker, plan, python, observability, cost, telemetry]
research_doc: "[[RESEARCH-harness-economics-observability]]"
interview_rounds: 3
adrs: 10
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Spend-classification economics from transcript JSONL; no per-run cost/output ratio"
---

# PLAN — Harness economics observability

## 🎯 Executive Summary

**TL;DR** — Read per-turn token usage from Claude Code's own session transcripts,
classify every turn's spend by *function* (REWORK / VERIFY / PRODUCE / OTHER, with
a CARRY overlay), and report the mix per stage through an extended `/hm:metrics`.
Retire the zero-token hook telemetry and re-point cache diagnostics at the same
reader.

**What.** A new `harness_maker.economics` module (pure classification layer) plus
`harness_maker.economics_source` (transcript adapter), surfaced as a cost section
on `/hm:metrics` reporting, per stage and per agent: turns, mean context per turn,
attributed wall-clock, output tokens, list-price-equivalent cost, and the
spend-category mix.

**Why.** External feedback reports that spec-driven and test modes burn tokens and
take a long time. The harness cannot currently answer *where* that spend goes:
`telemetry.py` records four token fields on every `PostToolUse` event and **all of
them are always zero** (measured: 0 non-zero in 2175 lines) because the payload
carries no `usage`.

> **Corrected premise (2026-07-25, verified by running the code).** An earlier
> draft of this PLAN and of the RESEARCH doc claimed the zero fields made
> `ai_readiness` Layer 3 score every turn as a cache *miss*. That is false.
> `cache_diagnostics.py:235-241` skips all-zero entries *before* classification,
> so `diagnose_cache` returns `_no_data` — measured live on this repo:
> `hit_rate=0, score=50 (neutral), sample_size=0, primary_failure="no_data"` —
> and `improvement.py:177-179` emits no ActionItem for `no_data`. Layer 3 is
> **inert (permanently neutral, 5 % of the composite), not wrong**. Interview #9
> re-confirmed the delete-and-re-point decision under this corrected premise.

**Key decisions.**

- Ground truth is the transcript JSONL, not any hook (ADR-001).
- **No per-run cost-per-deliverable ratio** — enforced in the data layer by
  schema test, and *instructed* (not enforced) in the prose layer (ADR-002).
- Four ordered spend categories with an explicit precedence ladder, plus a CARRY
  overlay; no LLM in the classifier (ADR-003).
- Surface is `/hm:metrics`, with no on/off switch (ADR-004).
- Zero-token telemetry fields removed behind a record `schema_version` bump; the
  path-taking `diagnose_cache` is **deleted**, not retained (ADR-005).
- Unattributed spend is always its own bucket; the adjacency estimate is bounded
  and sits in a separate column (ADR-006).
- Project-local scope, but the base project directory **and** its
  `--worktrees-*`-encoded siblings are enumerated (ADR-007).
- External second-opinion model cost declared unmeasured (ADR-008).
- Drift defence = never-crash parser + structured ingestion diagnostics + a live
  smoke in the `/hm:health` **command template**, not a readiness signal (ADR-009).
- Pricing is per-turn from each turn's own `message.model`, against a versioned
  price table (ADR-010).

**Measured baseline** (this repo, Opus list pricing): 6 recent sessions = $440
main loop + $25 subagents; largest single session (17.7 h, 1779 turns) = $1 539,
of which **cache-read 81 %**, cache-write 10 %, output 9 %; mean context 471 k
tokens/turn; subagent turns carry 5–7× less context than main-loop turns.

---

## 🚫 Non-Goals

Explicit prohibitions. `/hm:execute` must treat each as out of scope even though
the RESEARCH doc or an intuitive reading suggests otherwise.

1. **No cost ÷ deliverable ratio of any kind, per run.** Not per commit, per SPEC
   AC, per test, per file, per confirmed finding. RESEARCH's "cost per
   deliverable" row is superseded and annotated as such in that document.
   Aggregate-over-many-runs yield is permitted only as described in ADR-002.
2. **No `ABANDONED` category.** Dropped at Interview #10 — `delivery_metrics` has
   no task-slug or branch adapter (verified: zero matches for
   `task_slug|worktree|hm/|abandon`), `worktree task-land` deletes `hm/<slug>`
   after squash-landing, and `refs/hm-landed/v1/*` has **0 refs in this repo**.
   Classifying spend as abandoned from absence-of-branch is a judgment built on an
   inferred property — the `[fail:design] namespace-prefix-mistaken-for-authorship`
   pattern.
3. **No code or prompt optimisation in this task** (Interview #4). Measuring first,
   optimising later, so the baseline and the change are not entangled in one commit.
4. **No live in-stage advisory.** Post-hoc reporting only.
5. **No cross-project rollup** (ADR-007).
6. **No estimation of external model cost** (ADR-008).
7. **No readiness *scoring* dimension for economics.** ADR-009's smoke measures
   reader liveness only and must never carry a spend threshold or feed a score.
8. **No OpenTelemetry exporter** in this task (ADR-001 rejected alternative).

---

## 📚 Prior Work

- `[wiki:architecture] cfr-churn-metrics` — the structural precedent: a pure
  classification layer split from an adapter layer, `/hm:metrics` as a manual,
  read-only, zero-network command, and deliberate Non-Goals (no readiness
  dimension, no gate). Note the 0.36.0 amendment: `delivery_metrics.enabled` was
  removed — a command inert until invoked needs no on/off switch. ADR-004 follows.
  Also the precedent for CLI co-location: `delivery_metrics.py` hosts its own
  subparsers beside its pure functions and is registered as
  `ModuleSpec("subparser", …)`; this PLAN does the same.
- `[wiki:architecture] hooks-load-from-settings-not-hooksjson` — bounds the claim.
  `metrics.jsonl` is the pre-0.7.1 legacy name; the dated files hold thousands of
  real entries. The finding is "the token fields are structurally zero", **not**
  "telemetry never ran".
- `[fail:design] namespace-prefix-mistaken-for-authorship` — do not build on an
  inferred property. This PLAN was bitten by exactly that during its own review
  (the Layer 3 misreading corrected above) and drops ABANDONED for the same
  reason. Every transcript field depended on here was confirmed in live artifacts.
- `[wiki:tooling] command-surface-registry` — new subcommands need a
  `command_registry.py` entry plus `misroute_guard` wiring; CI gates T-C1/T-C2
  enforce parity.
- `[wiki:architecture] session-tier-slim` — precedent for deleting a write-heavy,
  read-thin path once shown to have no real consumer (ADR-005).
- `[[RESEARCH-harness-economics-observability]]` — field inventory, measured
  baseline, prior art (`ccusage`, `cccost`, OTel), and eight pitfalls.

---

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Deliverable denominator | Scope | How far to define the "output" side cost is measured against? | file-only / file+git / file+git+quality / cost-only | **Rejected the question** | User: a deterministic-test denominator makes multi-round review that hardens security/perf look uneconomic. Any cost÷output ratio puts verification spend in the numerator only. | ADR-002 |
| 2 | Command surface | Architecture | Which surface carries the model? | `/hm:metrics` ext / new `/hm:economics` / CLI-only / `/hm:health` dim | `/hm:metrics` extension | Inherits the non-gate framing; no extra always-listed command. | ADR-004 |
| 3 | Dead telemetry | Contract | What to do with the always-zero token fields and the score built on them? | delete+rewire / keep+N-A / delete+remove / defer | Delete fields, re-point Layer 3 | Premise later corrected → re-confirmed at #9. | ADR-005 |
| 4 | Task scope | Scope | Observe only, observe+diagnose, or observe+optimise? | observe / observe+diagnose / observe+optimise | Observe + automatic diagnosis | Optimisation is a separate task; no live advisory. | ADR-004 |
| 5 | Spend taxonomy | Architecture | Keep the proposed category taxonomy? | 5-cat / 3-cat / 5-cat+LLM / other | Categories as proposed, deterministic only | Reduced to 4 + overlay at #10 when ABANDONED was dropped. | ADR-003 |
| 6 | Unattributed 64 % | Contract | How to handle turns with no `attributionSkill`? | bucket+estimate / bucket only / attribute all | Explicit bucket **plus** a separate adjacency-estimate column | Estimate never overwrites the honest bucket. | ADR-006 |
| 7 | Measurement scope | Scope | Current project only, or all projects? | current / all-projects / current+siblings | Current project only | Sibling worktree-encoded dirs of the *same* project added at #10 review — still project-local. | ADR-007 |
| 8 | External model cost | Observability | `codex` / `agy` spend never enters the transcript. | unmeasured / count invocations / parse logs | Declare unmeasured, always annotated | No dependency on undocumented external formats. | ADR-008 |
| 9 | ADR-005 re-confirmation | Risk tolerance | Layer 3 is inert (neutral 50, 5 % weight), not wrong. Keep delete+re-point? | keep full / Layer 3 only / defer | **Keep full delete + re-point** | Accepts telemetry schema change, `cost_usd` removal, `PRIVACY.md` update, risk `high`. | ADR-005 |
| 10 | ABANDONED fate | Scope | No adapter, no provenance (0 landed refs). | drop to Non-Goal / provenance-only / build oracle phase | **Drop from v1, record as Non-Goal** | Taxonomy becomes 4 categories + CARRY overlay. | ADR-003 |

Resolved without a round (5-term gate, common ground): review-driven REWORK is
legitimate — determined by the user's Interview #1 principle that verification-
caused work is not waste (applied in ADR-003); the smoke's location — determined
by the existing second-opinion smoke precedent (ADR-009); pricing table source,
file paths, naming — EIG below ε, defensible defaults taken.

---

## 📐 Architecture Decision Records

### ADR-001: Transcript JSONL is the token ground truth
**Status:** Accepted (2026-07-25, via /hm:plan interview)
**Context:** The harness needs per-turn token counts. The `PostToolUse` payload
has no `usage` key (0 non-zero in 2175 measured lines). Claude Code's session
transcripts carry full `message.usage`, `message.model`, harness-native
attribution (`attributionSkill`, `attributionAgent`, `attributionPlugin`), and
task identity signals (`cwd`, `gitBranch`).
**Decision:** Read cost from `~/.claude/projects/<enc-cwd>/<sessionId>.jsonl` and
`<sessionId>/subagents/agent-*.jsonl`. Add no new instrumentation.
**Consequences:**
- ✅ No new hooks, permissions, or capture-side render changes; the join keys
  already exist.
- ✅ Subagent spend separates cleanly from main-loop spend, which is where the
  largest measured lever lives.
- ⚠️ Post-hoc only — cannot observe a running stage.
- ⚠️ Reads outside the project root and depends on an undocumented internal
  format (mitigated by ADR-009).
**Rejected alternatives:**
- *OpenTelemetry export* — officially documented and gives authoritative
  per-request cost, but needs an OTLP collector and the standard integrations
  ship data off-machine, contradicting the 100 %-local telemetry rule.
- *Repair the hook path* — refuted by measurement; the only hook carrying a
  transcript reference is `Stop`, which reduces to this ADR with a worse trigger.
**Source:** Interview #3 + RESEARCH measurement.

### ADR-002: No per-run cost-per-deliverable ratio — enforced in data, instructed in prose
**Status:** Accepted (2026-07-25, via /hm:plan interview)
**Context:** The interview opened by asking how far to define the "output" side of
a cost÷output ratio. The user rejected the framing: with any quality-blind
denominator, the cost of review rounds that harden security or performance lands
in the numerator and nothing lands in the denominator, so quality investment
scores as uneconomic. Optimising against such a metric cuts exactly the layers the
harness exists to provide.
**Decision:** The model never divides cost by a deliverable count for a single
run. Spend is classified by function (ADR-003) and the **mix** is reported.
Verification spend is a first-class legitimate category. A per-reviewer or
per-stage **yield** figure (cost per confirmed finding) may be computed **only
over a distribution of many runs**, and only above a stated minimum sample —
below it the report says *under-powered* instead of printing a number.

Enforcement is split, honestly:

| Layer | Mechanism | Strength |
|---|---|---|
| Data | `EconomicsReport` schema contains no field that is a cost divided by any count; a schema test asserts this | **enforced** |
| Prose | `metrics.md.j2` carries an explicit negative instruction forbidding the interpreter from dividing cost by any delivery count; a render-grep test asserts the block is present | **instruction, not enforcement** |

**Consequences:**
- ✅ The data layer cannot express the bug the user identified.
- ✅ "Uneconomic" gets a precise definition: high CARRY, high unprompted REWORK —
  never VERIFY.
- ✅ Consistent with measurement: subagents (mostly VERIFY) are 5 % of spend while
  cache-read (CARRY) is 81 %. Review was never the cost problem.
- ⚠️ The prose constraint is a prompt instruction. `/hm:metrics` prints CFR and
  churn ratios in the same output, so numerator and denominator are one sentence
  apart in the interpreter's context. The render-grep test proves the instruction
  is *present*, never that the generated prose obeys it. Same honesty as
  `executor_body.md.j2`'s "Scope — instruction, not enforcement".
- ⚠️ All figures are **list-price equivalents** used as a *relative* between-stage
  signal, labelled as such; this project runs on a subscription where marginal
  cash cost is not list price.
**Rejected alternatives:** cost per landed commit / per passing test / per SPEC AC
— all the same defect with a different quality-blind denominator.
**Source:** Interview #1 (user objection); enforcement split from plan-validator
critique #4.

### ADR-003: Four ordered spend categories with an explicit precedence ladder, plus a CARRY overlay
**Status:** Accepted (2026-07-25, via /hm:plan interview)
**Context:** ADR-002 requires classifying each turn by function. An earlier draft
called PRODUCE/VERIFY/REWORK a partition while defining REWORK as "a
PRODUCE-classified turn" — mutually exclusive, so no implementation could satisfy
both and the phase gate was unsatisfiable.
**Decision:** Exactly one label per turn, assigned by an **ordered ladder**
evaluated top-down, first match wins:

| Order | Category | Rule |
|---|---|---|
| 1 | `REWORK` | the turn writes (`tool_use` ∈ {Write, Edit, NotebookEdit}) to a normalised path already written earlier **in the same task**, **and** no VERIFY turn for that task precedes it since that path's last write, **and the turn is not itself verify-attributed** |
| 2 | `VERIFY` | (`attributionSkill ∈ {hm:review, hm:verify}` or `attributionAgent` is a reviewer/validator agent) **and the turn writes no path** |
| 3 | `PRODUCE` | the turn writes to at least one path (includes review-driven fixes, which reach here because rule 1 excluded them) |
| 4 | `OTHER` | everything else — reading, reasoning, searching, conversation |

`CARRY` is **not a category**: it is an arithmetic overlay reported per stage as
carry cost (`cache_read`) versus work cost (`cache_write + output`).

Multi-tool turns: a turn writing several paths is REWORK only if **every** written
path meets rule 1; mixed turns fall through to PRODUCE. Paths are normalised to
repo-relative before comparison, so the same logical file written from
`.worktrees/<slug>/` and from the base compares equal — without this, the
Production-default feature-branch model under-counts REWORK.

> **Rule 2's writes-nothing clause is required for ladder consistency** (found by the
> Phase A.5 test-reviewer, 2026-07-25). Without it the ladder is internally inconsistent:
> a turn attributed to `hm:review` that *writes* — the review stage's auto-fix loop landing
> a fix — is excluded from REWORK by rule 1's VERIFY-clause and then captured by rule 2 as
> VERIFY, contradicting Phase 1's exit criterion (which requires PRODUCE) and inflating
> VERIFY with work that actually produced a fix. With the clause the ladder is total and
> consistent: REWORK (rewrite, no intervening verify) > VERIFY (checks, writes nothing) >
> PRODUCE (writes) > OTHER.

**Rule 1's VERIFY-clause is load-bearing.** The harness's designed happy path is
execute writes → review finds issues → the same files are rewritten. Counting
those fixes as REWORK, while ADR-002 calls REWORK uneconomic, would re-introduce
through the taxonomy the exact bug the ratio ban removed. Review-driven rewrites
are PRODUCE; only unprompted rewrites are REWORK. This follows directly from the
user's Interview #1 principle.

**Consequences:**
- ✅ The classifier is a pure function over parsed turn records — property-testable
  exactly like `delivery_metrics.classify_cfr_full`; "exactly one label from the
  ordered ladder" is a satisfiable property.
- ✅ No LLM participates, so the observer does not pollute what it measures.
- ⚠️ REWORK requires task identity (below); turns with no resolvable task get
  `PRODUCE`, never `REWORK`, and the report states REWORK coverage as a
  percentage so the absent case is visible rather than a silent zero.
- ⚠️ `OTHER` will be large. It is reported, never hidden.
**Rejected alternatives:**
- *Include ABANDONED* — dropped at Interview #10, see Non-Goals 2.
- *5 categories + an LLM correction layer* — better boundary accuracy, but the
  report generator would consume tokens proportional to history size.
**Source:** Interviews #5 and #10; ladder and VERIFY-clause from codex P1 and
plan-validator critiques #3 and #12.

### ADR-004: Surface is `/hm:metrics`, no on/off switch, diagnosis included
**Status:** Accepted (2026-07-25, via /hm:plan interview)
**Decision:** Extend `/hm:metrics` with a cost section plus an interpretation step
naming which stages carry uneconomic spend and why. No new slash command; no
`enabled` flag; a tuning-only `economics:` block. Scope stops at diagnosis.
**Consequences:**
- ✅ Command surface count unchanged, so the harness's always-resident context cost
  does not grow — which matters for a task about context cost.
- ✅ Inherits the existing non-gate framing verbatim.
- ⚠️ `/hm:metrics` grows from ~1.5 k to an estimated ~3 k tokens, paid per
  invocation, not per session.
- ⚠️ Users wanting cost without CFR/churn still load the whole command.
**Rejected alternatives:** new `/hm:economics` (+1 always-listed command);
`/hm:health` dimension (scoring invites gating — rejected by the cfr-churn
precedent); CLI-only (no interpretation, which Interview #4 chose).
**Source:** Interviews #2 and #4.

### ADR-005: Retire the zero-token telemetry fields behind a schema bump; delete the path-taking `diagnose_cache`
**Status:** Accepted (2026-07-25, via /hm:plan interview; premise corrected and
re-confirmed at Interview #9)
**Context:** `telemetry.py` writes four token fields that are structurally zero.
`cache_diagnostics.py:235-241` skips all-zero entries before classification, so
`diagnose_cache` returns `_no_data` — verified live: `score=50` neutral,
`sample_size=0` — and `improvement.py:177-179` emits no ActionItem for `no_data`.
Layer 3 is therefore **inert, not wrong**, and is 5 % of the composite. The user
re-confirmed the full delete-and-re-point under this corrected premise.
**Decision:**
1. Remove the four token fields from the telemetry record and **add a new
   `METRICS_SCHEMA_VERSION` key to the `post_tool_use` entry built by
   `telemetry._build_entry`** (set to `2`).
   **Do NOT touch `telemetry.SCHEMA_VERSION` (`telemetry.py:250`)** — that constant
   versions `OverrideRecord` / `.claude/observability/adaptive/overrides.jsonl` and
   is used as a reader filter at `:359, :381-385`; bumping it would make
   `_read_overrides` silently drop every existing override line and turn
   `tests/unit/test_telemetry.py:431-440, :673-680` red. The metrics entry has no
   version key today (`_build_entry`, `telemetry.py:135-175`), which is why this is
   an **add**, not a bump.
   **Absent case is the convention**: a metrics line with no `METRICS_SCHEMA_VERSION`
   key is schema 1 (pre-retirement, token fields present-but-zero). Readers must
   apply that default rather than rejecting the line.
2. Add `diagnose_cache_from_turns(turns, model, window_turns)` as the pure core
   and **delete** the path-taking `diagnose_cache(metrics_path, …)`. Retaining it
   as a "thin adapter" is wrong: once the writer stops emitting the fields, the
   all-zero skip makes it return `_no_data` unconditionally and forever, for
   historical lines too. A retained function that provably answers "no data" for a
   file full of lines is a second phantom-data path in a PLAN whose purpose is
   removing them.
3. Migrate the **three** production call sites (`ai_readiness.py:66, 93, 132`) and
   preserve the `CacheDiagnosis` deserialization contract at `ai_readiness.py:184`.
   Deleting the symbol also breaks two consumers outside `src/`, both in scope:
   **`tests/unit/test_cache_diagnostics.py`** (17 `diagnose_cache(` calls across its
   I/O-edge-case and scenario sections) and **`.claude-verify.sh:609`**, whose R3
   Monitoring gate imports the symbol by name and is *not* run by pytest — so no
   other exit criterion in this PLAN would catch it. Disposition must be explicit
   per test: the behavioural ones port to `diagnose_cache_from_turns` and become the
   pinned-value fixtures Phase 5 already promises; the ones that exercise the removed
   I/O path (file discovery, legacy-name fallback) are deleted with that path. The
   three `test_classify_*` node IDs pinned in
   `specs/SPEC-cache-diagnostics.machine.yaml:15-17` exercise `_classify_turn`, not
   `diagnose_cache`, and **must keep their exact node names** or `spec_inventory`
   verification breaks.
4. Resolve `window`'s double meaning explicitly. Today it is passed as
   `days=window` (file selection, `cache_diagnostics.py:229`) *and* used as an
   entry-count cap (`:243`) with one default of 50. The new core takes
   `window_turns` (an explicit turn count) and the adapter takes a separate
   `days` argument; neither silently inherits the other's meaning.
5. Delete `_estimate_cost` / `cost_usd` from `telemetry.py`, update
   `tests/unit/test_telemetry.py:279-297` (which asserts `cost_usd > 0`), and
   update `PRIVACY.md:52` where `cost_usd` is documented as part of the schema.
6. Re-point `improvement.py:177-190`, whose Layer 3 ActionItem hardcodes
   `target=".claude/observability/metrics.jsonl"` — a file that will no longer hold
   the data.
**Consequences:**
- ✅ Cache efficiency becomes a real measurement for the first time; one reader
  serves both features.
- ✅ Removes a field set that looks like data and is not.
- ⚠️ Historical `ai_readiness` composites become non-comparable across this
  boundary (bounded: cache is 5 % of the blend). CHANGELOG must say so.
- ⚠️ This is a disk-schema change and the rollback is **code-only**. A revert
  restores the writer but not the ledger. `METRICS_SCHEMA_VERSION` makes the
  *forward* boundary machine-readable — post-change lines are self-identifying —
  but it does **not** retro-version the ~2175 existing lines, which stay
  version-less. The honest statement is therefore: the marker makes new lines
  distinguishable and the absent-key default (schema 1) makes old ones
  interpretable; it does not make the file uniform. The regression guard asserts
  only on newly-written lines so it cannot contradict a reverted writer.
**Rejected alternatives:** keep fields + mark Layer 3 N/A (leaves a dead write
path); delete fields + drop Layer 3 (discards a now-cheap real signal); defer
(Interview #9 re-confirmed against it).
**Source:** Interviews #3 and #9; corrections from plan-validator critiques #1, #6,
#7, #8.

### ADR-006: Unattributed spend is a permanent explicit bucket; the adjacency estimate is bounded and separate
**Status:** Accepted (2026-07-25, via /hm:plan interview)
**Context:** 347 of 622 measured main-loop turns carry no `attributionSkill` and
account for $281 of $440 — 64 % of spend.
**Decision:** Always report an `unattributed` bucket with its true total. Beside
it, report an `est. attributed` column derived from the nearest **preceding**
attributed turn, bounded by all four of:
- same session file, **and**
- ≤ `adjacency_max_gap_min` (default 10) minutes since that turn, **and**
- ≤ `adjacency_max_turns` (default 20) turns of lookback, **and**
- no change of `cwd`, `gitBranch`, or resolved task in between.
Beyond any bound the turn stays unattributed. The estimate never overwrites the
honest bucket, is always labelled, and the report states estimator coverage
(what fraction of unattributed spend the estimate claimed).
**Consequences:**
- ✅ A per-stage table that silently dropped 64 % of spend would look precise and
  be wrong by ~3×; this makes the gap structurally visible.
- ✅ Bounds stop the failure mode the measured data invites: one 17.7 h session
  spanned research→plan→execute, so an unbounded lookback would attribute hours of
  unrelated manual work to whichever stage last set `attributionSkill`.
- ⚠️ Still a heuristic; adjacent manual debugging inside a bound is over-attributed.
**Rejected alternatives:** bucket only (leaves most spend uninterpretable);
attribute everything by adjacency (clean-looking table on an invisible heuristic).
**Source:** Interview #6; bounds from codex P1 and plan-validator reconciliation.

### ADR-007: Project-local scope, including this project's worktree-encoded sibling directories
**Status:** Accepted (2026-07-25, via /hm:plan interview)
**Context:** Claude Code encodes the *launch* cwd into the project directory name.
Sessions launched at the repo root capture worktree activity fine — verified: 1060
of 2678 turns in this repo's base-dir sessions have a `cwd` inside `.worktrees/`.
But a session launched *from inside* a worktree gets its own directory. Verified on
this machine: four such directories exist for sibling repos
(`-home-noel-spoton--worktrees-*`, `-home-noel-danta--worktrees-*`). The miss
mechanism is real and has fired in practice; it simply has not fired for
harness-maker yet.
**Decision:** Resolve the base directory from the project's cwd encoding **and**
enumerate sibling directories matching `<base-enc>--worktrees-*`. Both belong to
this same project, so the scope stays project-local. No cross-project rollup, no
`--all-projects` flag. The report states how many directories were scanned.
**Consequences:**
- ✅ Closes a blind spot that would silently under-report exactly the stages
  (`execute`, `plan`) that run under worktree isolation.
- ✅ Still opens no other project's data.
- ⚠️ Prefix matching could in principle collide with a differently-named project
  whose encoding shares the prefix; the scanned-directory count in the report makes
  such a case visible.
**Rejected alternatives:** base directory only (documented blind spot — too weak
once the mechanism was shown to have fired); `--all-projects` (reads other
projects).
**Source:** Interview #7; correction from codex P0 after main-loop verification.

### ADR-008: External second-opinion model cost is declared unmeasured
**Status:** Accepted (2026-07-25, via /hm:plan interview)
**Decision:** `codex` and `agy` spend is never estimated. Every report carries a
fixed annotation naming which external models are enabled and stating their cost
is excluded.
**Consequences:**
- ✅ No dependency on two undocumented external usage formats.
- ✅ The incompleteness is visible rather than implied.
- ⚠️ With both models mandatory on every review and plan in the Production preset,
  the true total is understated by an unknown amount.
**Rejected alternatives:** count invocations from `second-opinion.jsonl` (a count
beside dollar figures reads as a cost); parse each CLI's logs (most brittle).
**Source:** Interview #8.

### ADR-009: Drift defence is a never-crash parser + structured ingestion diagnostics + a live smoke in the health *template*
**Status:** Accepted (2026-07-25, via /hm:plan interview)
**Context:** ADR-001 depends on an undocumented format. The failure mode that
matters is not a crash but silent zeroing — and, worse, silent *partial* zeroing,
which a binary "did we price anything" check cannot catch.
**Decision:** Three parts.
1. **Never-crash parser.** Unknown keys ignored; lines without `usage` skipped;
   malformed input never raises.
2. **Structured ingestion diagnostics** on every report: directories scanned, files
   discovered / read / failed, lines parsed / skipped by reason, turns with usage,
   unknown model strings, and a coverage percentage. Partial degradation shows up
   as a coverage drop, not as a plausible-looking smaller number.
3. **Live smoke as a Bash step in `templates/commands/hm/health.md.j2`** — the same
   place and pattern the second-opinion smoke already uses — invoking
   `economics doctor`. It reports FAIL when transcript directories exist and hold
   sessions but zero turns price, and N/A when no store exists (fresh clone, CI,
   Cursor, Codex).

**It is deliberately NOT a `readiness.py` signal**, for two reasons that hold
against source:
- `compute_readiness(project_dir, preset)` (`readiness.py:1603`) takes **no
  transcript root**. A signal would need one threaded through it *and* through the
  three `ai_readiness` entrypoints *and* through the serialized
  `finalize_from_verdicts_json` shape (`ai_readiness.py:170-173`) — a signature
  migration this task does not scope.
- The only alternative is calling `Path.home()` inside a scored path, which makes
  the entire existing readiness/health test suite HOME-dependent — the failure
  CLAUDE.md checkpoint 7 exists to prevent.

Supporting: `readiness.py:1606-1607`'s own docstring puts Layer 3
`cache_efficiency` on the orchestrator's side of the line, not readiness'.
Economics belongs on the same side.

> **Two earlier justifications are retracted as false against source.** (a) "no N/A
> state" — `Signal` has no tri-state field, but the repo has a pervasive N-A
> *idiom* (`passed=True` with no penalty, or conditional omission) at
> `readiness.py:527, :564-566, :579-586, :613-614, :632-633, :657`, documented in
> CLAUDE.md for `permissions_deny_present`. (b) "dimension weights sum to 100, so a
> new signal re-weights `observability_setup`" — `_score_signals`
> (`readiness.py:222-229`) computes `earned = sum(weight for passed signals)`
> clamped to 100, and its own comment names the ">100 additive passed-weight sum";
> adding a signal requires no re-weighting. Recording the retraction rather than
> deleting it, because a future reader who checks these will otherwise re-open a
> settled decision — the same self-inflicted trap this PLAN's Prior Work cites.
**Consequences:**
- ✅ A format change surfaces as a failing health step, not as a report of $0.
- ✅ Zero readiness signature change, zero re-weighting, zero new HOME dependency.
- ✅ Keeps Non-Goal 7 intact: the smoke measures instrument liveness, never spend.
- ⚠️ A template-level smoke is only seen when `/hm:health` is run.
**Rejected alternatives:** a `readiness.py` signal (above); strict schema
validation (turns a benign additive change into a hard failure); no check
(reproduces the failure this task exists to fix).
**Source:** Derived from `[fail:design] namespace-prefix-mistaken-for-authorship`;
mechanism corrected by plan-validator critique #5 and codex P1.

### ADR-010: Price each turn from its own recorded model, against a versioned price table
**Status:** Accepted (2026-07-25, via /hm:plan interview)
**Context:** An earlier draft exposed a single `economics.price_model: opus` while
the data flow already carried `model` per `TurnRecord`. Real sessions are
mixed-model — this repo's own transcripts contain `claude-opus-4-8` and
`claude-opus-5` in the same window. Separately, `message.usage.cache_creation`
splits into `ephemeral_5m_input_tokens` and `ephemeral_1h_input_tokens`, which are
priced differently, while `COST_PER_MTK` has one `cache_write` rate per model
corresponding to the 5-minute tier.
**Decision:**
- Price every turn from its own `message.model`, mapped to a `COST_PER_MTK` row by
  model family. `economics.price_model` is demoted to a **fallback for unrecognised
  model strings only**, and unpriced tokens are reported separately rather than
  silently dropped.
- Add a `price_table_version` (and its effective date) to the report so historical
  reports stay reproducible.
- Split `cache_write` into 5m and 1h rates. If a single rate is retained for a
  model, the report must annotate any window where `ephemeral_1h_input_tokens > 0`
  that the figure is an approximation.
**Consequences:**
- ✅ Mixed-model windows are priced correctly instead of at one assumed rate.
- ✅ The 1-hour-TTL case is not silently mispriced — which matters because
  `cache_diagnostics.py:156-157` actively advises users to enable extended TTL for
  long planning sessions, i.e. the harness would otherwise understate cost for
  users who followed its own advice.
- ⚠️ Two more report fields and a table to keep current.
**Rejected alternatives:** single configured model (contradicts the per-turn data);
ignore the TTL tiers (bounded error — cache-write is 10 % of spend — but lands
precisely on the long sessions this model exists to explain).
**Source:** codex P1 + plan-validator critique #11.

---

## 🏗️ Technical Design

### Current state (verified against source)

| File | Fact |
|---|---|
| `telemetry.py:42-46` | `COST_PER_MTK` per model, one `cache_write` rate |
| `telemetry.py:99-118, 148-154` | `_estimate_cost` / `cost_usd` / the four zero token fields |
| `cache_diagnostics.py:229, 243` | `window` used as `days=` **and** as an entry cap |
| `cache_diagnostics.py:235-241` | all-zero entries skipped → `_no_data`, score 50 |
| `ai_readiness.py:66, 93, 132` | three `diagnose_cache(` call sites |
| `ai_readiness.py:184` | `CacheDiagnosis.model_validate` — a schema dependency, not a call site |
| `improvement.py:177-190` | Layer 3 ActionItem hardcodes `metrics.jsonl`; returns none for `no_data` |
| `delivery_metrics.py` | **zero** matches for `task_slug\|worktree\|hm/\|abandon` |
| `readiness.py:124-137` | `Signal` = `passed: bool` + `weight`, no N/A state |
| `command_registry.py:51` | `ModuleSpec("subparser", …)` — the pattern to copy |

### Affected components

| Component | Change |
|---|---|
| `harness_maker/economics.py` *(new)* | pure classification + pricing + aggregation + subparsers |
| `harness_maker/economics_source.py` *(new)* | directory resolution, transcript iteration, ingestion diagnostics |
| `harness_maker/cache_diagnostics.py` | add `diagnose_cache_from_turns`; **delete** the path-taking function |
| `harness_maker/ai_readiness.py` | 3 call sites migrate; `:184` deserialization contract preserved |
| `harness_maker/improvement.py` | Layer 3 ActionItem target re-pointed |
| `harness_maker/telemetry.py` | remove 4 token fields + `_estimate_cost` + `cost_usd`; **add** `METRICS_SCHEMA_VERSION` to `_build_entry` (≠ `SCHEMA_VERSION`, which owns `overrides.jsonl`) |
| `tests/unit/test_cache_diagnostics.py` | 17 `diagnose_cache(` call sites ported or deleted (ADR-005 item 3) |
| `.claude-verify.sh:609` | R3 Monitoring gate imports `diagnose_cache` by name — not covered by pytest |
| `templates/skills/ai-readiness-rubric/SKILL.md.j2:34` | rendered skill still names `metrics.jsonl` as the Layer 3 source |
| `templates/cursor/hooks.json.j2:21` | rendered comment references `cost_usd` |
| `docs/HOW-IT-WORKS.md`, `docs/HOW-IT-WORKS.ko.md:2530` | both carry the Layer 3 `cache_diagnostics` row |
| `harness_maker/models.py` | `EconomicsConfig` |
| `harness_maker/synthesize.py`, `interview.py` | forward writer + reverse mapper for the new block (checkpoint 6) |
| `templates/harness-yaml/{Side,Production}.yaml.j2` | the `economics:` block |
| `harness_maker/command_registry.py` | `economics` subcommands + `misroute_guard` |
| `templates/commands/hm/metrics.md.j2` | cost section + interpretation + ratio-prohibition block |
| `templates/commands/hm/health.md.j2` | `economics doctor` smoke step |
| `PRIVACY.md`, `tests/unit/test_telemetry.py` | `cost_usd` removal fallout |

### Task identity (required by ADR-003 rule 1)

`TurnRecord.task_slug` is derived deterministically, first match wins:
1. `gitBranch` matches `hm/<slug>` → `<slug>`
2. `cwd` contains `/.worktrees/<slug>/` → `<slug>`
3. otherwise `None`

**Absent case is explicit** (CLAUDE.md's recurring absent-case failure class): a
turn with `task_slug is None` can never be REWORK — it falls to PRODUCE — and the
report states REWORK coverage as *turns with a resolvable task ÷ writing turns*, so
"REWORK 0" is distinguishable from "REWORK unmeasurable here". Slug reuse across
time is bounded by the report window; sessions spanning several tasks resolve
per-turn, not per-session.

### Data flow

```
~/.claude/projects/<enc-cwd>/            ─┐  base dir
~/.claude/projects/<enc-cwd>--worktrees-*/ │  sibling dirs (ADR-007)
  ├── <sid>.jsonl                          │
  └── <sid>/subagents/agent-*.jsonl       ─┘
                     ▼
   economics_source.iter_turns()      [adapter — I/O, never raises,
                     ▼                 emits IngestionDiagnostics]
   TurnRecord(model, usage, attribution_skill, attribution_agent,
              is_sidechain, task_slug, written_paths, ts, cwd, git_branch)
                     ▼
   economics.classify_turn()   [pure — ordered ladder, one label]
   economics.price_turn()      [pure — per-turn model, versioned table]
   economics.aggregate()       [pure — per stage/agent/category, CARRY ratio,
                     ▼                 unattributed bucket + bounded estimate,
                                       mean context/turn, attributed wall-clock]
              EconomicsReport (+ IngestionDiagnostics)
                     ▼
   python -m harness_maker.economics report --root . --json
                     ▼
   /hm:metrics → markdown + interpretation      /hm:health → economics doctor
```

The same `TurnRecord` stream feeds `diagnose_cache_from_turns`, so both features
parse once.

**Derived column definitions** (previously promised but undefined):
- *mean context per turn* = mean of `input + cache_read + cache_creation` over the
  stage's turns.
- *attributed wall-clock* = sum of gaps between consecutive turn timestamps within
  a contiguous same-attribution run, each gap capped at `idle_gap_cap_min`
  (default 5). Main-loop and subagent runs overlap in real time, so wall-clock is
  reported **per scope** (main / subagent) and is explicitly **not** additive
  across scopes — the report says so rather than presenting a misleading total.

### API changes

```
python -m harness_maker.economics report  --root . [--days N] [--json]
python -m harness_maker.economics stages  --root . [--days N]
python -m harness_maker.economics doctor  --root .
```

CLI subparsers live in `economics.py` beside the pure functions, matching
`delivery_metrics.py` and its `command_registry.py:51` registration. Purity is
provided by the pure/adapter module split, not by module-per-concern.

```yaml
economics:
  window_days: 30
  price_model: opus            # ADR-010: fallback for unrecognised models only
  adjacency_estimate: true
  adjacency_max_gap_min: 10
  adjacency_max_turns: 20
  idle_gap_cap_min: 5
  min_yield_sample: 20         # below this, yield reports "under-powered"
```

---

## 📝 Implementation Plan

> **Execution status** (updated by `/hm:execute`, 2026-07-25 — uncommitted; `/hm:wrapup` owns the commit)
>
> | Phase | Status | Evidence |
> |---|---|---|
> | 1 — Pure layer | **DONE** | 46 tests; A.5 gate PASS after one FAIL round (8 blocking issues fixed) |
> | 2 — Transcript adapter | **DONE** | 33 tests; A.5 gate PASS after one FAIL round (`files_failed` phantom-counter fixed); RED gate observed before implementation |
> | 3 — CLI + registry + config | **DONE** | 13 tests; full suite green; 8 harness.yaml snapshots regenerated (1 line each) |
> | 4 — `/hm:metrics` cost section | **DONE** | 14 render-grep tests; snapshot diff limited to `commands/hm/metrics.md` |
> | 5 — Telemetry retirement + Layer 3 re-point | **DONE** | A.5 gate PASS after one FAIL round (3 blocking: my creation-tier tests were invariant over the dimension they claimed); RED gate observed; 18 core tests + 3 ported TTL tests; the 17 removed I/O tests deleted with the path, the 3 SPEC-pinned `test_classify_*` node IDs preserved |
> | 6 — Health smoke + docs | **DONE** | 7 render tests incl. a Non-Goal-7 guard asserting `readiness.py` gained no economics signal |
>
> **REVIEW round 1 + 2 findings are folded in** (see `REVIEW-…-2026-07-25.md`): 9 fixes +
> 21 regression tests in round 1, then the three open P1s in round 2 (session-scoped verify
> window, worktree `--root` resolution, the whole config surface pinned end-to-end).
>
> **Amendments made during execution** (both from Phase A.5 findings, both applied to
> ADR-003): rule 2 gained a *writes-nothing* clause, and rule 1 gained a *not itself
> verify-attributed* clause. Without them a `hm:review`-attributed turn that writes a fix
> classified as VERIFY and then as REWORK respectively — re-introducing, through the
> taxonomy, the exact "verification counted as waste" defect ADR-002 exists to prevent.
>
> **Deferred from the config schema:** `min_yield_sample` was specified in the ADR-004
> config block but no phase implements aggregate yield, so the key was omitted rather than
> shipped dead. Yield remains permitted-but-unimplemented per ADR-002.
>
> **API correction:** `report` always emits JSON, so the `--json` flag in the ADR-004 API
> block was dropped rather than shipped as a no-op. A `--transcript-root` override and a
> `--now` instant (mirroring `delivery_metrics`' testing flag) were added so every Phase 3
> gate is CI-runnable and clock-independent.

### Phase 1 — Pure layer (`economics.py`)
- **depends_on:** `[]`
- **parallel_group:** `serial-core`
- **merge_hazards:** none (new file)
- **Scope.** In: `TurnRecord`, `SpendCategory`, `classify_turn` (ordered ladder),
  `price_turn` (per-turn model + versioned table + 5m/1h tiers), `aggregate`
  (per stage/agent/category, CARRY ratio, unattributed bucket, bounded adjacency
  estimate, mean context, attributed wall-clock), `EconomicsReport`;
  `tests/unit/test_economics_pure.py`. Out: all I/O, CLI, templates.
- **Exit criterion.** `uv run pytest tests/unit/test_economics_pure.py -q` green,
  including property tests for: **exactly one label per turn from the ordered
  ladder** (including a turn that both writes and carries `hm:review` → PRODUCE via
  rule 1's VERIFY-clause); pricing linearity and per-token-type independence;
  mixed-model pricing (two models in one window priced at their own rates);
  aggregate conservation (Σ category costs == Σ turn costs); the ADR-006 invariant
  that the honest unattributed total is never mutated by the estimate; and each
  adjacency bound rejecting at its boundary. Plus a **schema test asserting
  `EconomicsReport` exposes no cost-divided-by-count field** (ADR-002).
- **Risk:** low
- **Rollback:** none needed — additive new file with no consumers.

### Phase 2 — Transcript adapter (`economics_source.py`)
- **depends_on:** `[1]`
- **parallel_group:** `serial-core`
- **merge_hazards:** none (new file)
- **Scope.** In: cwd→project-dir encoding, `<base-enc>--worktrees-*` sibling
  enumeration (ADR-007), main + `subagents/` iteration, `written_paths` extraction
  with repo-relative normalisation, task-slug derivation, `IngestionDiagnostics`,
  never-raise parsing; `tests/unit/test_economics_source.py` + a checked-in fixture
  store. Out: aggregation (Phase 1), CLI (Phase 3).
- **Exit criterion.** Unit tests green against a fixture store covering: a normal
  assistant turn; a subagent turn with `attributionAgent`; a multi-tool turn
  writing two paths; the same logical file written from a worktree path and a base
  path (must normalise equal); a line with no `usage`; a truncated line; an unknown
  extra key; a sibling `--worktrees-*` directory (must be discovered); and an
  unknown model string. The last four must not raise, must not be priced, and must
  each increment their own `IngestionDiagnostics` counter.
- **Risk:** medium — depends on an undocumented external format.
- **Rollback:** revert to Phase 1.

### Phase 3 — CLI + registry + config
- **depends_on:** `[2]`
- **parallel_group:** `serial-core`
- **merge_hazards:** `command_registry.py` — CI gates T-C1/T-C2 assert
  registry↔source parity; conflicts with any concurrent branch adding a subcommand.
- **Scope.** In: `report` / `stages` / `doctor` subparsers, `command_registry.py`
  entry + `misroute_guard`, `EconomicsConfig` in `models.py`, the `economics:` block
  in **both** `templates/harness-yaml/{Side,Production}.yaml.j2`, the forward writer
  in `synthesize.py`, and the reverse mapper in
  `interview.answers_from_harness_yaml` (checkpoint 6 is only half-covered without
  both directions). Out: `/hm:metrics`.
- **Exit criterion (CI-runnable).** `economics report --root <fixture> --json`
  produces a schema-valid report whose per-stage totals match **pinned expected
  numbers** from the Phase 2 fixture store; T-C1/T-C2 pass; a round-trip test
  writes then re-reads the `economics:` block unchanged.
  *Non-gating evidence:* the same command against the real local store, recorded
  in the phase notes.
- **Risk:** medium — touches the config schema's bidirectional contract.
- **Rollback:** revert to Phase 2.

### Phase 4 — `/hm:metrics` cost section
- **depends_on:** `[3]`
- **parallel_group:** `render`
- **merge_hazards:** `templates/commands/hm/metrics.md.j2` and every rendered
  snapshot; must not land concurrently with another change to that file. Snapshot
  regeneration required.
- **Scope.** In: the cost section (honest vs estimated columns, coverage line,
  ingestion diagnostics summary, list-price-equivalent label, external-model
  annotation), the **ratio-prohibition instruction block** (ADR-002 prose layer),
  the interpretation step (which must state that review-driven REWORK is expected
  and legitimate wherever REWORK is elevated), snapshot regeneration,
  `tests/unit/test_render_metrics_economics.py`. Out: the existing CFR/churn
  sections.
- **Exit criterion.** Render-grep tests assert the presence of: the non-gate
  framing, the unattributed bucket, the estimate label, the list-price label, the
  external-model annotation, and the ratio-prohibition block; full snapshot suite
  green.
- **Risk:** low
- **Rollback:** revert template + snapshots to Phase 3.

### Phase 5 — Telemetry retirement + Layer 3 re-point
- **depends_on:** `[3]`
- **parallel_group:** `rewire`
- **merge_hazards:** `ai_readiness.py` scoring output and its snapshots/fixtures;
  `PRIVACY.md`; `tests/unit/test_telemetry.py`.
- **Scope.** In: remove the four token fields + `_estimate_cost` + `cost_usd`; add
  `METRICS_SCHEMA_VERSION = 2` to the `post_tool_use` entry (**not** a bump of
  `telemetry.SCHEMA_VERSION`, which owns `overrides.jsonl`); rewrite
  `tests/unit/test_cache_diagnostics.py`'s 17 `diagnose_cache(` call sites per the
  ADR-005 item-3 disposition; update `.claude-verify.sh:609`'s R3 import list; add
  `diagnose_cache_from_turns(turns, model, window_turns)` and **delete**
  `diagnose_cache(metrics_path, …)`; migrate `ai_readiness.py:66, 93, 132` and
  preserve the `:184` deserialization contract; re-point `improvement.py:177-190`;
  update `PRIVACY.md:52` and `tests/unit/test_telemetry.py:279-297`; CHANGELOG entry
  recording the score discontinuity and the schema bump. Out: removing Layer 3.
- **Exit criterion (CI-runnable).** `uv run pytest -q` green; a **fixture-backed**
  test asserts `diagnose_cache_from_turns` returns exact pinned values (hit rate,
  `primary_failure`, counters) for fixtures covering: zero-usage turns,
  cache-creation-only, mixed models, malformed lines, and an empty window.
  Specifically: `diagnose_cache_from_turns` over an **all-zero-usage** fixture
  returns `primary_failure="no_data"`, `score=50`, `sample_size=0` — pinning the
  pre-migration behaviour as a property of the new core — and over the real-usage
  fixture returns a pinned **non-neutral** hit rate. (The earlier
  "before the migration / after" phrasing was unsatisfiable: the same phase deletes
  the callable and the fields, so no post-phase test can exercise the old path.)
  The three `test_classify_*` node IDs in
  `specs/SPEC-cache-diagnostics.machine.yaml:15-17` still exist; `bash
  .claude-verify.sh`'s R3 Monitoring gate passes; the regression guard asserts
  newly-written telemetry lines carry none of the four fields and do carry
  `METRICS_SCHEMA_VERSION`.
  *Non-gating evidence:* `/hm:health` against the real store showing a non-neutral
  cache score, recorded in the phase notes.
- **Risk:** high — changes a live scoring contract and a user-disk schema.
- **Rollback:** revert to Phase 3. **Code-only** — the ledger is forward-only; the
  `schema_version` bump is what keeps a post-revert mixed file machine-readable,
  and the regression guard asserts only on newly-written lines so it does not
  contradict a reverted writer.

### Phase 6 — Health smoke + docs
- **depends_on:** `[4, 5]`
- **parallel_group:** `serial-close`
- **merge_hazards:** `templates/commands/hm/health.md.j2` and its render snapshots.
- **Scope.** In: the `economics doctor` Bash step in `health.md.j2` (FAIL when
  directories hold sessions but zero turns price; N/A when no store exists);
  documentation drift from ADR-005 —
  `templates/skills/ai-readiness-rubric/SKILL.md.j2:34` (a **rendered** skill that
  still names `metrics.jsonl` as the Layer 3 source),
  `templates/cursor/hooks.json.j2:21` (rendered comment referencing `cost_usd`),
  and **both** `docs/HOW-IT-WORKS.md` and `docs/HOW-IT-WORKS.ko.md:2530`;
  `README.md` if the surface is listed; CHANGELOG. Out: any `readiness.py` change
  (explicitly excluded by ADR-009).
- **Exit criterion (CI-runnable).** A render test asserts the smoke step is present
  in `health.md.j2`; a unit test asserts `economics doctor` exits N/A against an
  empty fixture root, FAIL against a populated-but-unpriceable fixture root, and OK
  against the normal fixture store; a test asserts `readiness.py`'s signal list is
  unchanged (Non-Goal 7 guard); a render-grep asserts the rendered
  `ai-readiness-rubric` skill no longer names `metrics.jsonl` as the Layer 3 source.
  *Non-gating evidence:* `/hm:health` run locally.
- **Risk:** low
- **Rollback:** drop the step; Phases 1–5 stand.

---

## 🧪 Testing Strategy

**Unit (pure, no I/O).** Property tests per Phase 1's exit criterion, plus the
ADR-002 schema test.

**Unit (adapter, fixture-backed).** A checked-in miniature transcript store
including a `--worktrees-*` sibling directory and a `subagents/` directory,
exercising every line shape in Phase 2's exit criterion. **No test reads the real
`~/.claude/`** — the transcript root is a parameter pinned to a tmp path by an
autouse fixture (CLAUDE.md checkpoint 7). This is consistent because ADR-009 put
the live smoke in a command template rather than in `readiness.py`, so no scored
code path needs `Path.home()`.

**Render.** Snapshot + grep tests for `metrics.md.j2` and `health.md.j2` per
Phases 4 and 6.

**Integration (`INTEGRATION=1`, non-gating).** Run `economics report` against the
real local store and assert non-zero priced turns and a non-empty stage breakdown —
the drift canary. Recorded as phase evidence, never a CI gate, because fresh
clones, CI, Cursor, and Codex have no transcript store by design.

**Regression guards.** (a) newly-written telemetry lines carry none of the four
removed fields; (b) `readiness.py`'s signal set is unchanged by this task.

**Manual.** One `/hm:metrics` run after Phase 4, read for plausibility against the
RESEARCH baseline ($440 / 6 sessions, 81 % carry).

---

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Transcript format drifts; reader prices 0 or partially | medium | high | ADR-009: never-crash parser + ingestion diagnostics with coverage % (catches *partial* drift, which a binary check cannot) + `economics doctor` smoke + `INTEGRATION=1` canary |
| 2 | Layer 3 re-point moves `ai_readiness` scores | high | low-medium | Bounded — cache is 5 % of the blend and the pre-state is neutral 50, so the move is small and upward-informative; CHANGELOG records it; Phase 5 revertible |
| 3 | Adjacency estimate over-attributes | medium | low | ADR-006 four-way bounds; honest bucket first; estimator coverage reported |
| 4 | List-price figures read as a bill | medium | medium | ADR-002 label on every figure; framed as a relative between-stage signal |
| 5 | Cost numbers become a target; review layers get cut | medium | high | ADR-002 data-layer ban (schema test) + prose instruction + ADR-003's VERIFY-clause so review-driven fixes are never labelled waste; no gate, no readiness dimension |
| 6 | Task-slug derivation fails for manual sessions → silent REWORK 0 | high | medium | Absent case defined: never REWORK, and REWORK **coverage %** is reported so unmeasurable is distinguishable from zero |
| 7 | `command_registry` parity gates fail | medium | low | Phase 3 exit runs T-C1/T-C2 |
| 8 | Yield reported from too few runs | medium | medium | `min_yield_sample` (default 20); below it the report says under-powered |
| 9 | Telemetry schema change strands the ledger on revert | medium | medium | ADR-005 adds `METRICS_SCHEMA_VERSION` (new key, **not** a bump of the `overrides.jsonl` constant) with absent-key ⇒ schema 1; regression guard scoped to newly-written lines; rollback documented as code-only, and the marker is stated to make new lines self-identifying — not to make the file uniform |
| 11 | Deleting `diagnose_cache` breaks consumers outside `src/` | high | medium | ADR-005 item 3 scopes `tests/unit/test_cache_diagnostics.py` (17 calls) and `.claude-verify.sh:609`; Phase 5's exit adds the R3-gate run and the `test_classify_*` node-ID preservation, because pytest alone cannot catch the shell gate |
| 10 | Reading `~/.claude/` surprises a user | low | medium | ADR-007 project-local (base + own worktree siblings); read-only; nothing leaves the machine; documented in Phase 6 |

---

## ✅ Success Criteria

- [x] `economics report` against the **fixture store** produces pinned expected
      per-stage totals; against the real store it prices a non-zero number of turns
      and its per-stage totals reconcile to the whole-history total.
- [x] Every turn carries exactly one label from the ADR-003 ladder; a turn that both
      writes and carries `hm:review` is PRODUCE, not REWORK.
- [x] `EconomicsReport`'s schema contains no cost-divided-by-count field, asserted
      by test; `metrics.md.j2` contains the ratio-prohibition block, asserted by
      render-grep (ADR-002 — data enforced, prose instructed).
- [x] The unattributed bucket carries its true total; the adjacency estimate is a
      separate labelled column and every bound is exercised by a test.
- [x] Ingestion diagnostics (directories scanned, files read/failed, lines
      skipped by reason, unknown models, coverage %) appear in the report.
- [x] Turns are priced from their own `message.model`; the report states
      `price_table_version` and annotates any 1-hour-TTL approximation.
- [x] Sibling `--worktrees-*` project directories are discovered; the report states
      how many directories were scanned.
- [x] `telemetry.py` no longer writes the four fields, `cost_usd`, or
      `_estimate_cost`; `_build_entry` emits `METRICS_SCHEMA_VERSION = 2` while
      `telemetry.SCHEMA_VERSION` is **unchanged** and the `OverrideRecord` tests
      (`tests/unit/test_telemetry.py:431-440, :673-680`) stay green; `PRIVACY.md`
      and `tests/unit/test_telemetry.py:279-297` are updated.
- [x] `diagnose_cache(metrics_path, …)` is deleted; the three `ai_readiness` call
      sites use `diagnose_cache_from_turns`; the `:184` deserialization contract
      still validates; `improvement.py`'s Layer 3 target is re-pointed;
      `tests/unit/test_cache_diagnostics.py` and `.claude-verify.sh`'s R3 gate are
      updated and passing; the three `test_classify_*` SPEC node IDs are intact.
- [x] No rendered artifact still names `metrics.jsonl` as the Layer 3 source or
      documents `cost_usd` (`ai-readiness-rubric` skill, `cursor/hooks.json.j2`,
      both `HOW-IT-WORKS` files).
- [x] `/hm:health` runs `economics doctor` (FAIL / N-A / OK proven by test) and
      `readiness.py`'s signal set is unchanged.
- [x] `uv run pytest` green; `ruff check`, `ruff format --check`, `mypy --strict`
      clean.

---

## 🔍 Plan Validation

**Round 1 — cross-model second opinion (main-loop supplied).**

| Model | Status | Outcome |
|---|---|---|
| `codex` | `invoked` | 16 findings (2×P0, 7×P1, 6×P2, 1×P3) |
| `antigravity` | `failed` | exit 0 but the fail-closed adapter found 0 JSON payloads; ledger row written to `.claude/observability/second-opinion.jsonl`. Verdict for this model is absent, not negative. |

**Round 1 — `plan-validator`: `MAJOR_REVISION`** (5 critical, 6 warning, 2
suggestion). Every critical is resolved in this revision:

| # | Critical | Resolution |
|---|---|---|
| 1 | The motivating Layer 3 claim was false — cache_efficiency is inert (`no_data`, score 50), not scoring every turn a miss | Verified live by running `diagnose_cache`; RESEARCH and PLAN both corrected; Interview #9 re-confirmed ADR-005 under the corrected premise; Phase 5's exit criterion rewritten against the real baseline |
| 2 | ABANDONED relies on a `delivery_metrics` git adapter that does not exist; provenance absent (0 landed refs) | Interview #10 → dropped from v1, recorded as Non-Goal 2; "no new git machinery" claim removed |
| 3 | Phase 1's partition property was unsatisfiable against ADR-003's REWORK-as-PRODUCE-subtype definition | ADR-003 rewritten as an ordered 4-rung ladder with `OTHER` as a first-class rule and an explicit multi-tool rule; Phase 1's property restated |
| 4 | ADR-002's "cannot be expressed" was aspirational; Success Criterion unfalsifiable | Split into an enforced data-layer schema test and an explicitly-labelled prose instruction, matching `executor_body.md.j2`'s own "instruction, not enforcement" wording |
| 5 | A `readiness.py` signal forces `Path.home()` into readiness, breaks test isolation, and re-weights a scored dimension | ADR-009 moves the smoke to `health.md.j2` as a Bash step (the second-opinion precedent); a regression guard asserts `readiness.py`'s signal set is unchanged |

Warnings resolved: affected-components table corrected (three call sites, not four;
`improvement.py`, `synthesize.py`, `interview.py`, `PRIVACY.md`,
`tests/unit/test_telemetry.py`, both harness-yaml templates added); the path-taking
`diagnose_cache` is deleted rather than retained as a permanently-`no_data` shim;
`window`'s double meaning resolved into `window_turns` + `days`; Phase 5's rollback
documented as code-only with a `schema_version` bump; wall-clock and mean-context
given definitions and an owning phase; a `## Non-Goals` section added; ADR-010
added for per-turn and TTL-tier pricing.

Suggestions resolved: ADR-003 rule 1 carries the VERIFY-clause so review-driven
fixes are PRODUCE (the taxonomy no longer re-introduces the Interview #1 bug); all
three environment-dependent phase gates split into CI-runnable fixture assertions
plus non-gating local evidence.

Reconciliations where the validator **refuted** a codex finding, accepted as
refuted: codex P0-2's severity (the worktree blind spot is real but had not fired
for this repo — kept as a mechanism fix in ADR-007, not a P0 outage); codex P2 on
Phase 1 rollback (an additive file with no consumers genuinely has nothing to roll
back — the concern was re-filed against Phase 5); codex P3 on CLI co-location
(`delivery_metrics.py` establishes co-location as this repo's convention).

**Round 2 — re-validation (`plan-validator`, final pass): `MAJOR_REVISION`.**

All **five** round-1 criticals confirmed `RESOLVED`, each verified against source
rather than accepted on assertion. The validator additionally re-verified seven
factual claims this PLAN makes (`cache_diagnostics.py:235-241`→`_no_data`;
exactly three `diagnose_cache(` call sites plus the `:184` deserialization;
`compute_readiness` takes no transcript root; the `health.md.j2` Bash-smoke
precedent, which is broader than stated — codex, antigravity, `autopilot_ledger`
and `delivery_metrics` steps all live there; `delivery_metrics.py` + T-C1/T-C2
supporting CLI co-location; `improvement.py:177-190`; `telemetry.py`'s
`_estimate_cost`/`cost_usd` and `PRIVACY.md:52`). All seven confirmed.

The `MAJOR_REVISION` verdict is driven by **two new criticals the round-1 revision
itself introduced**, both now fixed in this document:

| # | New critical | Fix applied |
|---|---|---|
| A | "Bump the record's `schema_version`" had no target — `telemetry.SCHEMA_VERSION` (`:250`) versions `OverrideRecord`/`overrides.jsonl` and is a reader filter at `:359, :381-385`; bumping it would silently drop every existing override line. The metrics entry has no version key at all. | ADR-005 item 1 rewritten: **add** `METRICS_SCHEMA_VERSION` to `_build_entry`, explicitly do not touch `SCHEMA_VERSION`, absent-key ⇒ schema 1. The rollback-reachability consequence is restated honestly (new lines self-identify; the ~2175 old lines stay version-less). |
| B | Deleting `diagnose_cache` breaks 17 call sites in `tests/unit/test_cache_diagnostics.py` and `.claude-verify.sh:609`'s R3 gate — the latter outside pytest, so no exit criterion caught it. Phase 5's "pytest green" was unreachable. | Both added to ADR-005 item 3, the affected-components table, Phase 5's scope, and Phase 5's exit criterion (R3 gate run + `test_classify_*` node-ID preservation). New Risk 11. |

Warnings and the suggestion also applied: ADR-009's two refuted justifications
(`Signal` "no N/A state"; "weights sum to 100 ⇒ re-weighting") are **retracted in
place** with the source evidence, leaving the decision resting on its two sound
reasons; Phase 5's unsatisfiable "before/after" clause replaced with the equivalent
satisfiable property on the new core; three rendered/doc artifacts
(`ai-readiness-rubric` skill, `cursor/hooks.json.j2`, `HOW-IT-WORKS.ko.md`) added to
Phase 6.

The validator judged phase exit criteria **falsifiable and CI-runnable for Phases
1, 2, 3, 4 and 6**, with Phase 5 failing only on the two defects fixed above, and
found the decomposition itself clean (acyclic 1→2→3→{4,5}→6, disjoint file
ownership between the `render` and `rewire` groups, every phase with a reachable
rollback).

**Status of this document:** the re-validation budget (one re-run, per the stage
contract) is spent. The two round-2 criticals are resolved by construction from the
validator's own source-cited remedies, but that resolution has not itself been
re-validated by a third pass. Recorded as a known limitation rather than claimed as
verified.
