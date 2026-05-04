---
generated_by: harness-maker
harness_maker_version: 0.4.8
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/loop.md.j2
provenance: official
content_hash: 1860e507554c82164d47b6a4cb9e3fd2be8a52dc7a2c3c052a9c03880ae8db04
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
         [--time 8h] [--max-iter 30] [--workflow exec-rev-wrap]
         [--convergence <predicate>] [--dry-run]
```

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
- `--max-iter <N>` — max iterations (default `30`).
- `--workflow <name>` — fused workflow each `feature`-mode iteration invokes
  (default `exec-rev-wrap`). Must exist in `.claude/commands/hm/`.
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
  notes:
    - <any additional clarifications from follow-ups>
```

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

### 5. Run the autoloop

You are the driver. Track state via `TodoWrite` and your working memory.

- Create one task per feature in `TodoWrite` (feature mode) or one task
  named `improve-cycle` (improve mode). Task description holds AC or
  stopping_criteria.
- Note the start timestamp: `Bash` → `date +%s`.
- Maintain counters: `iter` (0), `failed_streak` (0), `completed` (list).

#### Safety rails (always on, never skip)

1. `iter >= max_iter` → halt `stop_reason="max_iter (N) reached"`
2. `elapsed >= time_h * 3600` → halt `stop_reason="time_cap (Nh) reached"`
3. `failed_streak >= 3` → halt `stop_reason="3 consecutive failures"`
4. Same feature retried ≥ 3 times → halt and report blocker
5. Ping every 5 iterations: `autoloop ping: iter=<N> target=<name>`
6. Convergence check **before** each iteration body

#### 5-A. Feature mode loop body

Each iteration:

1. **Cap + convergence checks** (see safety rails)
2. **Pick next feature**: first in spec order not in `completed`
3. **Increment `iter`**
4. **Invoke workflow**: pass feature name + AC + objective to the configured
   fused workflow. Read the workflow command file under
   `.claude/commands/hm/<workflow>.md` and execute **every stage it defines,
   in order, without skipping any** — individual stage "When to Run" skip
   conditions apply only to standalone invocation, not when driven by the
   loop. The loop's decision to call this workflow is itself the authority
   to run all its stages.
5. **Update state**:
   - Success → mark completed in `TodoWrite`, append to `completed`,
     reset `failed_streak = 0`
   - Failure → `failed_streak += 1`, log what failed

Convergence check: evaluate predicate against `completed` list.

#### 5-B. Improve mode loop body

Each iteration is one full review → fix → test → review cycle:

1. **Cap checks** (see safety rails)
2. **Increment `iter`**
3. **Read target** — read all files in `--target` scope. If scope is large
   (>500 lines total), read in passes: first by structure (headings, class/
   function signatures), then full content of flagged areas.
4. **Review** — using the context (purpose, invariants, priority) as the
   review lens, identify all issues. Classify each:
   - `critical`: breaks invariants or correctness
   - `high`: trade-off that contradicts the stated priority (e.g., sacrifices
     a higher-ranked property for a lower-ranked one — optimizing performance
     at the expense of safety when priority is `safety > performance`)
   - `medium`: actionable quality concern that doesn't contradict the priority
   - `low`: minor style, non-blocking
   Output a ranked issue list.
5. **Evaluate stopping criteria** (LLM judgment) — read the
   `stopping_criteria` from context and judge: does the current codebase
   satisfy it given the issue list? If yes → `converged = True`, skip fix.
6. **Fix** — address all critical + high issues. Address medium issues if
   iter budget allows (estimate: ≤ max_iter/3 iters remaining). Never make
   changes that would cause context invariants to be violated.
7. **Run tests** — use whatever test command is appropriate for the project
   (check for `Makefile`, `pyproject.toml`, `package.json` test scripts).
   If no test infrastructure is found, consult the `test_reliability` context
   dimension: if it confirms no tests exist, skip this step and note it in
   the re-review; otherwise flag the absence of tests as a medium issue.
   Record: passed / failed / skipped counts.
8. **Re-review** — brief re-read of changed files. Confirm fixes landed,
   no regressions introduced.
9. **Update state**:
   - `converged = True` (from step 5) → mark `improve-cycle` completed in
     `TodoWrite`, `completed = ["improve-cycle"]`, `stop_reason = "converged"`
   - `converged = False` → continue loop. **What counts as failure** in
     improve mode is test failure only (step 7): tests passing but
     stopping_criteria not yet met is NOT a failure — it means progress
     is being made. `failed_streak += 1` only when tests fail; reset to 0
     when tests pass.

---

### 6. Report

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
