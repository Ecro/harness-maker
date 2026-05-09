---
generated_by: harness-maker
harness_maker_version: 0.7.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/loop.md.j2
provenance: official
content_hash: 9e9f00d25aa19a3d8e2e5ea5b44f4504b77b57603f03a11f5936b25e93c735f0
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
         [--time 8h] [--max-iter 30] [--per-iter-workflow exec-rev]
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
- `--max-iter <N>` — max iterations (default `30`).
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

### 5. Engage worktree (loop top — once, before any iter)

If `harness.yaml.worktree.scope` includes `execute`, create one worktree
that wraps the **entire loop**. Per-loop (not per-iter) — improve and
feature mode both default to one squash-merge at convergence. Per-iter
worktree would explode commit count.

```bash
!uv run --with /home/noel/harness-maker python -m harness_maker.worktree create execute "$(pwd)"
```

Read the **single line** the command prints. Two cases:

- **Absolute path** like `/path/to/repo/.worktrees/execute-20260507T0010Z`
  → isolation engaged. **Treat that exact string as `<WT>` for every
  subsequent operation in this loop**: every Read/Write/Edit call, every
  `cd` for tests/lints, every workflow-command invocation. Do NOT use a
  shell variable — each `!` block is a fresh subshell.
- **Empty output** → `worktree.scope` does not include `execute`. No
  isolation; operate in `cwd`. Skip the finalize step at the end.

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
- Maintain counters: `iter` (0), `failed_streak` (0), `completed` (list).

#### Safety rails (always on, never skip)

1. `iter >= max_iter` → halt `stop_reason="max_iter (N) reached"`
2. `elapsed >= time_h * 3600` → halt `stop_reason="time_cap (Nh) reached"`
3. `failed_streak >= 3` → halt `stop_reason="3 consecutive failures"`
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

For each iter (until convergence or any safety rail fires):

1. **Cap + convergence checks** (safety rails above)
2. **Pick work unit** (mode-specific):
   - **feature**: next uncompleted feature from spec; no remaining → mark
     converged and exit loop.
   - **improve**: read target → review → identify issues → evaluate
     stopping_criteria. No issues OR criteria met → mark converged and
     exit loop.
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
     `failed_streak = 0`.
   - Workflow returned failure → `failed_streak += 1`, log what failed.
     For improve mode, "failure" means **tests failed** — tests passing
     but stopping_criteria not yet met is NOT a failure (progress is
     being made).

### 7. Loop close — UNIFIED

When the loop halts (convergence, safety rail, or hard error):

1. **Run wrapup ONCE**: read `.claude/commands/hm/wrapup.md` and execute
   the wrapup stage (commits, SESSION-md if `--session`, memory append
   to `wiki.md` / `failures.md`). Operate inside `<WT>` if engaged.

2. **Decide finalize status — explicit rule, not judgment**:

   | Halt reason | Finalize status | Why |
   |---|---|---|
   | `converged = True` | `success` | clean stopping criteria met |
   | `iter >= max_iter` | `fail` | budget exhausted without convergence |
   | `elapsed >= time_h * 3600` | `fail` | time cap fired |
   | `failed_streak >= 3` | `fail` | repeated failures, evidence valuable |
   | Hard error (uncaught) | `fail` | preserve for debug |

   Do NOT classify max-iter or time-cap halts as "partial success" — the
   user explicitly bounded the run; un-merged worktree is more useful
   than a half-baked squash that contaminates main.

3. **Finalize worktree** (only if engaged in step 5):

   ```bash
   !uv run --with /home/noel/harness-maker python -m harness_maker.worktree finalize <WT> <STATUS>
   ```

   On `success`: `worktree.merge` does a squash-merge into the loop's
   parent branch and then `cleanup --force` removes `<WT>`. **If squash
   conflicts** (e.g. main has concurrent edits to `.claude/memory/wiki.md`
   from another session), the merge step exits 1; finalize leaves `<WT>`
   in place. Treat this as a fail-equivalent: emit the conflicting file
   list in step 4 and instruct the user to resolve manually with
   `cd <WT> && git status && git merge --abort` or similar.

4. **Emit final report** (next section).

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
