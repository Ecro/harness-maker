---
generated_by: harness-maker
harness_maker_version: 0.9.3
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/loop.md.j2
provenance: official
content_hash: fbc3a5df1b0c23f919ee33eeb8e59159539a352e9561eab8fe4eb2cce81864ae
---
# /hm:loop

> Start a bounded autoloop. Claude conducts a coverage-driven adaptive
> interview to establish full context, then iterates the configured workflow
> until the stopping criteria are met or a safety cap fires.

This command is **prompt-driven**. You (Claude) act as the autoloop driver:
parse input, detect mode, run the adaptive interview, track state, invoke
the per-iteration workflow, and enforce safety rails. Do NOT try to import
any Python module — `harness_maker.*` exists only in the harness-maker
development repository, not in the projects this command runs in.

## Usage


```
/hm:loop <goal>
/hm:loop --spec <path> [--mode feature|improve] [--target <path>]
         [--time 8h] [--max-iter 50] [--per-iter-workflow exec-rev]
         [--convergence <predicate>] [--dry-run]
```


> **Breaking from pre-0.5.5**: per-iter workflow defaults to `exec-rev`
> (was `exec-rev-wrap*`). Wrapup runs **once** at loop close instead of
> per iter. The whole loop runs inside one `.worktrees/execute-<ts>/`
> worktree (improve and feature mode both). To restore the old per-iter
> wrap behavior pass `--per-iter-workflow exec-rev-wrap` explicitly.


## Arguments

`$ARGUMENTS` is parsed positionally + by flag:

- `<goal>` — free-form target description. Split into features on `;`,
  newline, or `·`. Period and comma stay inside features.
- `--spec <path>` — path to a loop-spec YAML or any document (e.g.
  `TECH_SPEC.md`, `.claude/loop-specs/<slug>.yaml`). Wins over `<goal>`.
- `--mode feature|improve` — explicit mode override. When omitted, mode is
  auto-detected from goal keywords.
- `--target <path>` — scope for `improve` mode (file, directory, or module
  name). Defaults to the entire project if omitted.
- `--time <Nh>` — max wall-clock duration (default `8h`).
- `--max-iter <N>` — max iterations (default `50`).
- `--failed-streak-cap <N>` — max consecutive failures before halting (default `5`). Raise when features are expected to fail multiple times before succeeding.
- `--per-iter-workflow <name>` (alias `--workflow`) — fused workflow each
  iter invokes. Default: `exec-rev` (execute + review only — wrapup is
  deferred to loop close to avoid commit-per-iter). Recommended overrides:
  `plan-exec-rev` for big features needing per-iter planning. Must exist
  in `.claude/commands/hm/`.
- `--convergence <predicate>` — overrides the spec's predicate. Allowed:
  `all-features-completed` (default), `any-feature-completed`,
  `min-2-features`, `min-5-features`, `first-iter`, `stopping-criteria`.
- `--dry-run` — single iteration; mark all features completed without
  invoking the workflow.


---

## Procedure

### 1. Parse `$ARGUMENTS`


Extract all flags. Remaining tokens form the free-form `<goal>`.


If neither `<goal>` nor `--spec` is present, halt with an error.

### 2. Detect mode

```
explicit --mode flag present?
  → use it

else if --spec points to an existing loop-spec (mode: improve)?
  → improve

else if goal/spec text contains improve-signal keywords?
  (improve, refactor, quality, clean, optimize, 코드 품질, 리팩토링, 개선, cleanup, code review)
  → improve

else
  → feature (default)
```

### 3. Resolve input → loop spec

Branch on input shape:

**A. `--spec <path>` and the file is a conformant loop-spec YAML**
A file is conformant when it parses as a YAML mapping containing `objective`
and either non-empty `features` (feature mode) or `mode: improve`. Strip
provenance frontmatter (`---\n...\n---\n`) before checking.
→ Load it directly. Proceed to step 4.

**B. No `--spec`, only `<goal>`, mode = feature**
Split `<goal>` on `;`, `\n`, or `·` into features with empty AC.
→ Proceed to step 4 with the feature list pre-populated. The interview
  still runs to collect the five context dimensions; it does not re-ask
  for the feature list.

**C. `--spec <path>` exists but is NOT conformant, OR any improve-mode input**
→ Run the adaptive interview (step 4) to build the spec from scratch.

### 4. Adaptive interview — establish full context

**Goal**: start the loop with zero ambiguity. Use LLM judgment throughout —
not keyword matching or pattern rules.

#### 4-0. Derive slug (before reading any context file)

Compute the slug now — it is needed to find an existing context file in 4-A.

Derivation priority:
1. `--spec` file's stem in lowercase-kebab-case (e.g. `TECH_SPEC.md` → `tech-spec`)
2. `--target` path's last two components joined by `-` (e.g. `src/auth/` →
   `src-auth`, `src/auth/handler.py` → `auth-handler`)
3. First 4 words of the goal in lowercase-kebab-case

In all cases, sanitize to ASCII: transliterate or drop non-ASCII characters,
replace spaces and special characters with `-`, collapse multiple `-` into
one, strip leading/trailing `-`. If the result is empty after sanitization
(e.g., a pure Korean goal with no ASCII), fall back to
`loop-<first-8-chars-of-uuid4>`.

#### 4-A. Read and extract (LLM-driven)

Read all available source material:
- The `--spec` file (if provided), in full
- Existing `work-docs/loop-context/<slug>.yaml` (if present — reuse answers
  from prior runs; the slug from 4-0 tells you which file to look for)
- For improve mode: read the `--target` files/directory structure

Then, for each of the **five required context dimensions**, use your full
comprehension to extract an answer if the source material clearly states it:

| Dimension | What counts as "clearly stated" |
|-----------|--------------------------------|
| **purpose** | An explicit description of what the code/system does and who calls it |
| **invariants** | Explicit "must not change", "breaking change", API contracts, protocol specs |
| **priority** | An explicit ranking among performance / readability / safety |
| **test_reliability** | Explicit test coverage data, CI setup, or a description of test scenarios |
| **stopping_criteria** | An explicit Definition of Done, exit criteria, or quality bar |

If the source only hints at a dimension (vague, implicit, partial) — mark it
as **unresolved** and ask. Do not invent answers.

#### 4-G. Loop intensity + exit criteria (mandatory — runs before 4-B)

Before interviewing for missing dimensions, lock in the loop's quality bar.

Ask via `AskUserQuestion` (single call, two independent questions):

**Q1 — Loop intensity:**

| Option | What it guarantees |
|--------|--------------------|
| `quick` | Tests pass + lint clean |
| `standard` *(recommended)* | + mypy clean, review grade ≥ B |
| `thorough` | + review grade = A, all AC verified |
| `maximum` | + security scan clean, no regressions vs baseline |

**Q2 — Additional exit criteria (free-form text or "none"):**

> Any measurable conditions specific to this goal that must be satisfied before the loop can converge? (Examples: "< 100 ms p99 latency", "no CVEs in deps", "all SPEC scenarios green")

After the user answers:

1. Set `loop_intensity` from Q1.
2. Populate `exit_criteria_checklist` with the intensity-tier defaults below,
   then append any user-specified Q2 items as `ExitCriterion` entries
   (set `cmd=""` for qualitative items; adapt `cmd` values to the actual
   project toolchain — use `uv run pytest` for Python, `cargo test` for Rust,
   `npm test` for Node.js, etc.):

```yaml
# quick
- {label: "all tests pass",  cmd: "pytest -q --tb=short", required: true}
- {label: "lint clean",      cmd: "ruff check .",         required: true}

# standard adds:
- {label: "type check clean",  cmd: "mypy --strict .", required: false}
- {label: "review grade >= B", cmd: "",               required: true}

# thorough replaces "grade >= B" with:
- {label: "type check clean",              cmd: "mypy --strict .", required: true}
- {label: "review grade = A",              cmd: "",               required: true}
- {label: "all acceptance criteria verified", cmd: "",            required: true}

# maximum adds to thorough:
- {label: "security scan clean",                cmd: "",  required: true}
- {label: "no regressions vs prior iter baseline", cmd: "", required: true}
```

Each tier is **cumulative**: `thorough` includes all `standard` items plus its
own additions; `maximum` includes all `thorough` items plus its own.

#### 4-B. Interview for missing dimensions

For each unresolved dimension, ask via `AskUserQuestion`. Present what you
found in the source (if anything) and ask the user to confirm or complete it.

Ask dimensions in this order:
1. purpose
2. invariants
3. priority
4. test_reliability
5. stopping_criteria

Batch up to two related dimensions per `AskUserQuestion` call when they are
short (e.g., priority + test_reliability). Never batch stopping_criteria with
others — it deserves its own focused question.

**4-B post-hook (ADR-008) — runs immediately after stopping_criteria is
finalized:**

Re-read the finalized `stopping_criteria` text. Using LLM judgment, extract
every **measurable condition** it contains — items with a specific metric,
threshold, or command that can be mechanically checked. For each extracted
condition that is NOT already in `exit_criteria_checklist`:

1. Propose it as a new `ExitCriterion` (set `cmd` if a shell command can
   check it, otherwise leave `cmd=""`).
2. Ask via `AskUserQuestion`: "Add to exit checklist? {proposed label}"
   Options: **Add (required)** / **Add (warning only)** / **Skip**.

This ensures measurable stopping conditions become first-class checklist
items rather than staying buried in prose.

#### 4-C. Ambiguity resolution (LLM judgment)

After receiving each answer, evaluate whether it is **actionable**:

- **Actionable**: specific enough that a future Claude reading only this
  context file could make correct implementation decisions without asking again
- **Not actionable**: vague scope ("make it better"), unresolved conflict
  ("both speed and safety"), missing metric ("good coverage"), unconstrained
  qualifier ("important things")

If not actionable, generate a targeted follow-up question (LLM-generated,
not a fixed script) and ask via `AskUserQuestion`. Continue until actionable.

There is no maximum question count. The loop does not start until all five
dimensions are actionable.

#### 4-D. For feature mode: extract feature list

After context is established, if mode = feature and features are not yet
defined:

- If input was a `--spec` file: propose features extracted from it (headings,
  roadmap items, TODO markers, DoD checklists). Cap proposal at one coherent
  slice of 3–10 features. Ask via `AskUserQuestion` to accept / edit / retype.
- If input was a free-form `<goal>`: use the already-split feature list.
  Ask via `AskUserQuestion` to add AC for each feature (batch 3–5 per call).

For `improve` mode: features list stays empty. The iteration cycle is the
"feature".

#### 4-E. Convergence

Ask via `AskUserQuestion` only if the stopping_criteria answer didn't make
the convergence predicate obvious:

- `feature` mode: translate stopping_criteria into one of the named
  predicates (`all-features-completed`, `any-feature-completed`,
  `min-N-features`, `stopping-criteria`).
- `improve` mode: always `stopping-criteria` (LLM evaluates each iteration).

#### 4-H. 3-Layer Deep Interview Gate

Runs after steps 4-B through 4-E complete, before persisting context (4-F).
This gate surfaces implicit requirements missed by the 5-dimension interview.

**Layer 1 — GCIC Gap Check**

Map the 5 collected dimensions to 4 underspecification axes
(0.0 = absent · 0.5 = partial · 1.0 = clear):

- **Goals**: `purpose` + `stopping_criteria` clearly define the desired end-state?
- **Constraints**: `invariants` covers all inviolable boundaries?
- **Inputs**: `test_reliability` captures available tooling and starting state?
- **Context**: `priority` + `immediate_task` capture team/environment adequately?

Dimensions already scored 1.0 from the 5-dimension interview are skipped.
For any axis < 0.7, apply the **CLARITI filter** before asking:
1. Task Relevance: "Does knowing this axis change loop execution decisions?" (0–1)
2. User Answerability: "Can the user answer this now?" (0–1)
→ Ask only if **both ≥ 0.7**. Otherwise log `"LLM-inferred"`.

**Layer 2 — Implicit Probing**

Read all collected context. Dynamically generate 1–3 reverse questions from
the most contextually relevant candidate types (apply CLARITI filter to each):

Five candidate types (use short label to track across rounds):
- **WRONG**: "What would make you say the result is **wrong**?" → implicit rejection criteria
- **METHOD**: "What assumptions about **how** this will be done?" → implicit method constraints
- **STAKEHOLDER**: "Who else reviews/uses this output and by what standard?" → implicit stakeholders
- **STYLE**: "What **format or style** constraints apply?" → style (hardest to elicit)
- **PERF**: "What **performance or scale** expectations exist?" → implicit benchmarks

**MUST NOT reuse a type label** from a previous round (track: WRONG/METHOD/STAKEHOLDER/STYLE/PERF used).
Batch Layer 1 and Layer 2 questions into one `AskUserQuestion` call (max 4).

**Layer 3 — Ambiguity Score (display and gate)**

After receiving answers, compute and display:

```
Ambiguity Score: {X.X}/1.0  (Goal×40% + Constraint×30% + SC×30%)
  Goals:             {g:.1f}/1.0  ✅ or ⚠️  (threshold 0.8)
  Constraints:       {c:.1f}/1.0  ✅ or ⚠️
  Success Criteria:  {sc:.1f}/1.0 ✅ or ⚠️
  Weighted total:    {g*0.4 + c*0.3 + sc*0.3:.2f}
  → PASS or NEEDS  (streak: {N}/2)
```

Inputs/Context gaps resolved in Layer 1 are absorbed into Goals/Constraints scores
respectively. Score monotonicity rule: score must not decrease round-over-round given
the same answers; a drop ≥ 0.1 requires a one-line `[score-drop-reason]: ...` note
appended to the Layer 3 display block, then applied.

**Convergence**: total ≥ 0.8 AND all dims ≥ 0.7, **2 consecutive rounds** → PASS
→ proceed to step 4-F (Persist context).

On **NEEDS**: return to Layer 1 (focus on failing axis); generate new Layer 2
probes (no repeats). Max **3 rounds**. After 3 NEEDS, offer via `AskUserQuestion`:
- A: "Proceed — accept current ambiguity and start loop"
- B: "Refine further — return to Layer 1 with new focus"

#### 4-F. Persist context

Save to `work-docs/loop-context/<slug>.yaml` using the slug derived in
step 4-0.

If the file already exists, merge: keep existing answers for dimensions that
haven't changed, update dimensions where the user gave new answers, append
new notes.

```yaml
slug: <slug>
source: <spec path or "(inline goal)">
created_at: <ISO date>
updated_at: <ISO date>
context:
  purpose: <actionable answer>
  invariants:
    - <item>
  priority: <ranked>
  test_reliability: <actionable answer>
  stopping_criteria: <actionable answer>
  loop_intensity: <quick|standard|thorough|maximum>
  exit_criteria_checklist:
    - label: <criterion description>
      cmd: <shell command or "">
      required: <true|false>
  notes:
    - <any additional clarifications from follow-ups>
runtime:
  convergence_streak: 0
  checklist_fail_counts: {}          # {criterion_label: int}
  criterion_ambiguity_counts: {}     # {criterion_label: int}
  last_test_result:
    exit_code: null
    failing: []
```

The `runtime:` block is **ephemeral per-run state** — it is cleared at loop
start and never merged across runs (unlike `context:`, which persists). After
any `/compact`, re-read this block and restore the counters before continuing.

Save the loop-spec to `.claude/loop-specs/<slug>.yaml`:

```yaml
mode: <feature|improve>
objective: <one-sentence derived from purpose>
target: <--target value or "">
convergence: <predicate>
context_ref: work-docs/loop-context/<slug>.yaml
features:
  - name: <feature name>
    acceptance_criteria:
      - <observable check>
```

Show the user: saved paths + one-line summary, then ask `AskUserQuestion`
for final go-ahead before starting the loop.

---

### 5. Engage worktree (loop top — once, before any iter)

If `harness.yaml.worktree.scope` includes `execute`, create one worktree
that wraps the **entire loop**. Per-loop (not per-iter) — improve and
feature mode both default to one squash-merge at convergence. Per-iter
worktree would explode commit count.


```bash
!uv run --with /home/noel/harness-maker python -m harness_maker.worktree create execute "$(pwd)"
```


Read **all non-empty output lines** the command prints. Three cases:

- **Empty output** → `worktree.scope` does not include `execute`. No
  isolation; operate in `cwd`. Skip the finalize step at the end.
- **One absolute path** like `/path/to/repo/.worktrees/execute-20260507T0010Z`
  → single-repo isolation. **Treat that exact string as `<WT>` for every
  subsequent operation in this loop**: every Read/Write/Edit call, every
  `cd` for tests/lints, every workflow-command invocation. Do NOT use a
  shell variable — each `!` block is a fresh subshell.
- **Multiple lines** → multi-repo isolation. Line 1 = primary repo worktree
  (`<WT>`). Lines 2+ = sibling repo worktrees (`<WT-sibling-N>`). Use `<WT>`
  for primary-repo operations and `<WT-sibling-N>` for sibling-repo edits.

After confirming the worktree path (or deciding to operate in cwd), **create
the loop-active marker** in the project root:


```bash
!touch .hm-loop-active
```


This activates the Stop hook guard — the session will not terminate while
this file exists. The marker is gitignored by the harness worktree setup.

> **Cursor users**: the Claude Code Stop event guard is not available in
> Cursor IDE. The `.hm-loop-active` marker activates advisory stderr output
> on each Bash tool call but cannot block session termination. **Do not
> close the Cursor IDE window manually while the loop is running.** To
> recover a loop broken by accidental close: `rm .hm-loop-active` then
> re-run `/hm:loop --spec <spec-path>` with the remaining features.

Per-iter standalone `/hm:execute` (e.g. inside an invoked workflow's
execute stage) calls `worktree create` again — its idempotency check
detects we're already inside `.worktrees/<name>/` and returns the
existing path. No nested worktrees.

**Enforcement layer**: `worktree_gate` (a PreToolUse hook installed by
`/harness-maker:make`) blocks Write/Edit/MultiEdit calls whose target is
outside `<WT>` while a loop is active. This is technical insurance for
the prompt-driven `<WT>` substitution; LLM drift across long contexts
gets caught instead of silently corrupting main. **Bash-driven writes
(`>`, `sed -i`, `python -c "open(...)"`) are NOT gated** — for shell
ops always `cd <WT>` first so the cwd stays inside isolation.

### 6. Run the autoloop — UNIFIED iteration body

You are the driver. Track state via `TodoWrite` and your working memory.

- Create one task per feature in `TodoWrite` (feature mode) or one task
  named `improve-cycle` (improve mode). Task description holds AC or
  stopping_criteria.
- Note the start timestamp: `Bash` → `date +%s`.
- Maintain counters: `iter` (0), `failed_streak` (0), `convergence_streak` (0),
  `completed` (list), `checklist_fail_counts` ({}), `criterion_ambiguity_counts` ({}).
- **Post-`/compact` recovery**: after any compaction event, reload
  `convergence_streak`, `checklist_fail_counts`, and `criterion_ambiguity_counts`
  from `work-docs/loop-context/<slug>.yaml` `runtime:` section (see step 4-F
  for the persistence schema). If the `runtime:` section is absent, reinitialize
  all counters to their zero values — this is safe because Gate 3 and Gate 4
  skip or reset on missing baseline, and the escape hatch merely takes one
  extra cycle to fire.

#### Safety rails (always on, never skip)

1. `iter >= max_iter` → halt `stop_reason="max_iter (N) reached"`
2. `elapsed >= time_h * 3600` → halt `stop_reason="time_cap (Nh) reached"`
3. `failed_streak >= --failed-streak-cap` (default 5) → halt `stop_reason="N consecutive failures"`
4. Same feature retried ≥ 3 times → halt and report blocker
5. Ping every 5 iterations: `autoloop ping: iter=<N> target=<name>`
6. Convergence check **before** each iteration body

#### Per-iter workflow selection

Each iter invokes one fused workflow command:

- **Default**: `exec-rev` (execute + review). Wrapup is **deferred to
  loop close** (step 7) — running wrapup per iter would commit + merge
  on every iter, defeating the per-loop worktree.
- **`--per-iter-workflow plan-exec-rev`**: include plan stage per iter.
  Recommended for big features where each iter needs fresh planning.
- **`--per-iter-workflow <other>`**: explicit override. The configured
  default workflow (`exec-rev-wrap-ver`) is used only if the
  user explicitly passes `--per-iter-workflow exec-rev-wrap-ver`
  — otherwise prefer the leaner `exec-rev`.

Choose once at loop start, store as `WORKFLOW`.

#### Workflow file validation (before iter 1)

The chosen `WORKFLOW` must exist as `.claude/commands/hm/<WORKFLOW>.md`.
The default `exec-rev` is rendered only if `exec-rev` is in the harness's
`fused_workflows` map — custom harnesses may have stripped it. If the
file is missing, **halt** with this user-facing error:

```
loop halted — per-iter workflow '<WORKFLOW>' not found at
.claude/commands/hm/<WORKFLOW>.md.

Either:
  • re-run with --per-iter-workflow <one of exec-rev, exec-rev-wrap, exec-rev-wrap-ver, res-spec-plan>
  • or re-render the harness with `exec-rev` in fused_workflows
    (run /harness-maker:make → "Update")
```

Do NOT silently fall back to a different workflow — that masks
intent and could iterate over the wrong stages.

#### Iteration body (same for feature and improve mode)

> **Context advisory**: Every 10 iterations (`iter % 10 == 0`) or when you
> notice the context window is more than 60% full, run `/compact` before
> starting the next iteration. Long loops lose spec details to compaction;
> proactively compacting keeps the full specification in context.

For each iter (until convergence or any safety rail fires):

1. **Cap + convergence checks** (safety rails above)
2. **Pick work unit** (mode-specific):
   - **feature**: next uncompleted feature from spec; no remaining → run
     the convergence check below, then exit loop.
   - **improve**: read target → review → identify issues → run the 4-gate
     convergence check below. All four gates pass → mark converged and
     exit loop.

   **4-gate convergence check (improve mode: every iter; feature mode: when no features remain):**

   Run the four gates in order. ALL must pass (for the current iteration)
   before incrementing the convergence streak. Any gate failure = iteration
   is not converged.

   **Gate 1 — Mechanical** (skip items where `cmd=""`):
   For each `ExitCriterion` where `cmd != ""`, run the command inside `<WT>`:

   ```bash
   !cd <WT> && <criterion.cmd>
   ```

   - Exit 0 → criterion passes.
   - Exit non-0 → criterion fails.
     - `required: true` → Gate 1 fails → stop gate evaluation.
     - `required: false` → log warning, continue to next criterion.

   **Gate 2 — LLM individual evaluation** (runs regardless of cmd):
   For each `ExitCriterion` in the checklist, evaluate whether its `label`
   is satisfied given the current state of `<WT>` (read relevant files,
   test output, review grade). Evaluate **each criterion independently**
   — do not aggregate or average. For each:
   - "Clearly satisfied" → passes. Reset `criterion_ambiguity_counts[label]` to 0.
   - "Clearly not satisfied" → fails. Reset `criterion_ambiguity_counts[label]` to 0.
   - "Ambiguous" → **deadlock detector**: increment `criterion_ambiguity_counts[label]`.
     Persist the updated map to `runtime.criterion_ambiguity_counts` in the
     loop-context file. If the count reaches 3, ask via `AskUserQuestion`:
     options **"Continue anyway"** / **"Accept criterion as met"** /
     **"Remove criterion"**. This prevents infinite loops on unresolvable
     qualitative bars.
   - `required: true` AND (fails OR "Ambiguous" with count < 3) → Gate 2 fails.
   - `required: false` AND fails → log warning only.

   **Gate 3 — Regression check** (skip on iter 1 or when no baseline exists):
   The baseline is **exit-code + set of failing test names** (not raw output
   text), stored as `runtime.last_test_result` in `work-docs/loop-context/<slug>.yaml`.
   After each iteration, update `last_test_result` with the current result.

   Compare current iter result against prior baseline:
   - No prior baseline (iter 1 or post-compaction with no persisted baseline)
     → Gate 3 passes unconditionally; save current result as new baseline.
   - Tests pass now AND prior baseline also showed passing → Gate 3 passes.
   - Tests pass NOW but prior baseline showed failing → Gate 3 passes (improvement).
   - Tests FAIL now but prior baseline showed passing → Gate 3 fails (regression).
     Log which test names flipped from passing to failing.
   - Tests fail in both → Gate 3 passes (no new regression; Gate 1 catches
     the failing tests via `cmd`-based criteria).

   **Gate 4 — Streak** (2 consecutive iters):
   `convergence_streak` is the **single canonical reset site** — do NOT
   reset it in the "Update state" block (step 6.5):
   - Gates 1 + 2 + 3 all pass this iter → `convergence_streak += 1`.
     Persist to `runtime.convergence_streak` in loop-context file.
   - Any gate fails → `convergence_streak = 0`.
     Persist the reset.
   - `convergence_streak >= 2` → mark `converged = True`, exit loop.

   This streak requirement prevents false convergence from single-iter
   flukes. For `quick` intensity where the checklist is minimal, it still
   prevents exiting on the very first passing iter.

3. **Increment `iter`**.
4. **Invoke per-iter workflow**: read
   `.claude/commands/hm/<WORKFLOW>.md` and execute **every stage it
   defines, in order, without skipping any**. Operate inside `<WT>`:
   substitute the absolute worktree path for every Read/Write/Edit call;
   tests / lints / type checks run via `cd <WT> && <cmd>`. Stage "When
   to Run" skip conditions apply only to standalone invocation, not
   under loop dispatch.
5. **Update state**:
   - Workflow returned success (review verdict ≥ grade_threshold and
     tests pass) → mark completed, append to `completed`, reset
     `failed_streak = 0`. The 4-gate check (above) then decides whether
     to increment or reset `convergence_streak`.
   - Workflow returned failure → `failed_streak += 1`, log what failed.
     The 4-gate check runs regardless — Gate 1/2 failure will reset
     `convergence_streak` via Gate 4. Do NOT independently reset
     `convergence_streak` here.
     For improve mode, "failure" means **tests failed** — tests passing
     but stopping_criteria not yet met is NOT a failure (progress is
     being made).

### 7. Loop close — UNIFIED

When the loop halts (convergence, safety rail, or hard error):

1. **Exit criteria checklist gate** (skipped when `converged = False` — safety
   rail halts skip the gate entirely):

   When `converged = True`, evaluate all items in `exit_criteria_checklist`
   one final time against the current state of `<WT>`:

   - **`required: false` items** that fail → emit a warning line per item,
     continue. Do NOT flip `converged` to `False`.

   - **`required: true` items** that fail:
     - Log the failure with the criterion label + (if `cmd != ""`) the
       command output.
     - Increment `checklist_fail_counts[label]`. Persist to
       `runtime.checklist_fail_counts` in loop-context file.
     - **Escape hatch (ADR-009)**: If `checklist_fail_counts[label] >= 3`,
       ask via `AskUserQuestion`:
       - **"Override — accept loop as converged despite failing criterion"**
       - **"Abort — mark loop as not converged, exit without wrapup"**
       - **"Remove criterion and accept"** (removes from `exit_criteria_checklist`)
       If count < 3, flip `converged = False` and re-enter the iteration
       body for one more cycle (do NOT increment `failed_streak`; the
       loop-active marker is still present so the Stop hook remains active).

   This gate fires for **both** feature and improve mode when `converged = True`.

2. **Delete the loop-active marker** — after the checklist gate confirms
   `converged = True` (or after a safety rail fires), so re-entry cycles
   remain under the Stop hook guard:


   ```bash
   !rm -f .hm-loop-active
   ```


3. **Run wrapup ONCE**: read `.claude/commands/hm/wrapup.md` and execute
   the wrapup stage (commits, SESSION-md if `--session`, memory append
   to `wiki.md` / `failures.md`). Operate inside `<WT>` if engaged.

4. **Decide finalize status — explicit rule, not judgment**:

   | Halt reason | Finalize status | Why |
   |---|---|---|
   | `converged = True` | `success` | clean stopping criteria met |
   | `iter >= max_iter` | `fail` | budget exhausted without convergence |
   | `elapsed >= time_h * 3600` | `fail` | time cap fired |
   | `failed_streak >= --failed-streak-cap` | `fail` | repeated failures, evidence valuable |
   | Hard error (uncaught) | `fail` | preserve for debug |

   Do NOT classify max-iter or time-cap halts as "partial success" — the
   user explicitly bounded the run; un-merged worktree is more useful
   than a half-baked squash that contaminates main.

5. **Finalize worktree** (only if engaged in step 5):


   ```bash
   !uv run --with /home/noel/harness-maker python -m harness_maker.worktree finalize <WT> <STATUS>
   ```


   On `success`: `worktree.merge` does a squash-merge into the loop's
   parent branch and then `cleanup --force` removes `<WT>`. **If squash
   conflicts** (e.g. main has concurrent edits to `.claude/memory/wiki.md`
   from another session), the merge step exits 1; finalize leaves `<WT>`
   in place. Treat this as a fail-equivalent: emit the conflicting file
   list in step 6 and instruct the user to resolve manually with
   `cd <WT> && git status && git merge --abort` or similar.

6. **Emit final report** (next section).

---

### 8. Report

When the loop halts (any reason):

```
loop done — converged=<bool> iter=<N>/<max_iter>  mode=<mode>
  objective: <objective>
  target: <target or "(all features)">
  completed: <count>/<total>  [<names...>]
  stop_reason: <reason>
  spec: <spec path>
  context: work-docs/loop-context/<slug>.yaml
```

For non-converged halts, also emit:
- In-flight feature/cycle when stopped
- Last failure reason (if `failed_streak > 0`)
- One concrete suggestion (raise `--max-iter`, narrow stopping_criteria,
  split a failing feature, etc.)

For `improve` mode convergence, emit a brief quality summary:
- Issues found in final review (by severity count)
- Test result from last cycle
- Which stopping_criteria items are satisfied

## Reference

- Skill: `autoloop-driver` (orchestration rationale + safety-rail invariants)
- Agent: `autoloop-coder` (per-iteration implementation worker)
- Loop-spec schema: `.claude/loop-specs/<slug>.yaml`
- Context store: `work-docs/loop-context/<slug>.yaml`

<!-- @hm:user:extensions -->
<!-- Project-specific autoloop overrides (custom safety rails, convergence predicates, etc.). Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
