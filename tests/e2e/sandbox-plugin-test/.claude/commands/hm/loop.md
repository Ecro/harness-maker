---
generated_by: harness-maker
harness_maker_version: 0.3.4
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/loop.md.j2
provenance: official
content_hash: 491d3a6254edbdddbdb5a18fd77159180a0500b12671c04c49c78d54cacddd15
---
# /hm:loop

> Run a bounded autoloop: parse goal/spec → iterate the configured fused
> workflow against each feature → halt on convergence, time cap, iter cap, or
> 3 consecutive failures.

This command is **prompt-driven**. You (Claude) act as the autoloop driver:
parse the input, track state, invoke the per-iteration workflow, and enforce
the safety rails. Do NOT try to import any Python module — `harness_maker.*`
exists only in the harness-maker development repository, not in the projects
this command runs in.

## Usage

```
/hm:loop <goal>
/hm:loop --spec <path> [--time 8h] [--max-iter 30] [--workflow exec-rev-wrap] [--convergence <predicate>] [--dry-run]
```

`<goal>` and `--spec <path>` are mutually exclusive input forms. If both are
present, `--spec` wins.

## Arguments

`$ARGUMENTS` is parsed positionally + by flag:

- `<goal>` — free-form target description (legacy form). Split into a feature
  list on `;`, newline, or `·`. Period and comma stay inside features so
  `v1.2.3`, `https://api.x.com/v1`, and `3.14` survive intact.
- `--spec <path>` — path to a structured loop-spec YAML or any document the
  conditioning step should consume (e.g. `TECH_SPEC.md`, a previously written
  `.claude/loop-specs/<slug>.yaml`).
- `--time <Nh>` — max wall-clock duration (default `8h`). Halt with
  `stop_reason=time_cap` when exceeded.
- `--max-iter <N>` — max iterations (default `30`). Halt with
  `stop_reason=max_iter` when reached.
- `--workflow <name>` — fused workflow command each iteration body invokes
  (default `exec-rev-wrap`). Must exist in `.claude/commands/hm/`.
- `--convergence <predicate>` — overrides the spec's predicate. Allowed:
  `all-features-completed` (default), `any-feature-completed`,
  `min-2-features`, `min-5-features`, `first-iter`. Anything else: warn and
  fall back to default.
- `--dry-run` — single iteration; mark all features completed without
  invoking the workflow. Confirms parsing + state setup.

## Procedure

### 1. Parse `$ARGUMENTS`

Extract `--spec`, `--time`, `--max-iter`, `--workflow`, `--convergence`,
`--dry-run`. The remaining tokens form the free-form `<goal>`.

If neither `<goal>` nor `--spec` is present, halt with an error: tell the
user the command needs at least one input shape.

### 2. Resolve input → loop spec

Branch on what the user provided:

- **No `--spec`, only `<goal>`** — split `<goal>` on `;`, `\n`, or `·`. Each
  fragment becomes a feature with empty acceptance criteria. Skip to step 4.
- **`--spec <path>` and the file is loop-consumable YAML** — read it and use
  it directly. Skip to step 4. A file is loop-consumable when it parses as
  YAML mapping with at least: `objective` (string), `features` (non-empty
  list), and every feature having a `name`. (Provenance frontmatter `---\n...
  \n---\n` at the top is stripped before checking.)
- **`--spec <path>` exists but is NOT loop-consumable** — markdown like
  `TECH_SPEC.md`, prose, half-written YAML, etc. Run the conditioning
  interview (step 3) to produce a loop-spec from it.

### 3. Conditioning interview (when spec is non-conformant)

Goal: turn the user's input document into a reusable loop-spec. Use
`AskUserQuestion` for every elicitation — never invent answers.

**a. Show context.** Read the spec file. Quote roughly the first 30 lines
   so the user can see you understood it. If the file is huge (>2000 lines),
   read in chunks and summarise structure (top-level headings, section
   counts) — do not paste the whole thing.

**b. Objective.** Propose a single sentence drawn from the document (e.g.
   the README intro, the spec's first paragraph). Use `AskUserQuestion` to
   confirm or override.

**c. Features.** Propose a feature list extracted from the document
   (top-level headings, numbered roadmap items, "TODO" markers, definition-
   of-done checklists). Use `AskUserQuestion` with these options:
     - "Accept proposed list (N items)" — show the list inline
     - "Edit interactively" — drop into per-feature confirm/edit
     - "Type from scratch" — clear list, user dictates

   For huge specs (e.g. multi-thousand-line documents), do NOT propose
   hundreds of features. Cap the proposal at the **single coherent slice**
   most likely to fit one autoloop run (typically 3–10 features matching
   one phase, milestone, or roadmap section). Tell the user which slice
   you picked and why.

**d. Per-feature acceptance criteria.** For each feature, ask via
   `AskUserQuestion` whether to:
     - Accept auto-extracted ACs (when the source document has bullet
       points / DoD items under that feature)
     - Type ACs from scratch
     - Leave AC empty (exploratory features only)

   For a long feature list, batch this — present 3–5 features per
   `AskUserQuestion` call rather than one at a time.

**e. Convergence.** Use `AskUserQuestion`:
     - `all-features-completed` (recommended default)
     - `any-feature-completed` (stop after first success)
     - `min-2-features`
     - `min-5-features`
     - `first-iter` (one-shot)

**f. Persist.** Write the resulting loop-spec to
   `.claude/loop-specs/<slug>.yaml`. `<slug>` is derived from the input
   file's stem in lowercase-kebab-case (e.g. `TECH_SPEC.md` →
   `tech-spec`). If the target already exists, ask via `AskUserQuestion`
   whether to overwrite, append a numeric suffix, or abort. The YAML
   schema:

   ```yaml
   objective: <one-sentence purpose>
   convergence: all-features-completed
   features:
     - name: <short identifier>
       acceptance_criteria:
         - <observable check>
         - <observable check>
     - name: <next feature>
       acceptance_criteria: []
   ```

**g. Confirm.** Show the saved path + a one-line summary
   (`<N> features, convergence=<predicate>, objective="..."`) and use
   `AskUserQuestion` to get final go-ahead before step 4.

### 4. Run the autoloop

You are the driver. Track state in your working memory + via `TodoWrite`:

- Create one task per feature in `TodoWrite`. The task subject is the
  feature name; the description holds its acceptance criteria.
- Note the start timestamp (use `Bash` `date +%s` once at the beginning).
- Maintain three counters in your narrative: `iter` (starts at 0),
  `failed_streak` (starts at 0), `completed` (list of feature names).

Loop body:

1. **Cap checks (always before doing work):**
    - If `iter >= max_iter` → halt with `stop_reason="max_iter (N) reached"`.
    - If elapsed seconds (current `date +%s` − start) ≥ `time_h * 3600` →
      halt with `stop_reason="time_cap (Nh) reached"`.
    - If `failed_streak >= 3` → halt with `stop_reason="3 consecutive failures"`.
2. **Convergence check:**
    - Evaluate the chosen predicate against the current state:
      - `all-features-completed` — every feature is in `completed`
      - `any-feature-completed` — at least one feature is in `completed`
      - `min-N-features` — `len(completed) >= N`
      - `first-iter` — `iter >= 1`
    - If True → halt with `converged=True`, `stop_reason="converged"`.
3. **Pick next feature:** the first feature (in spec order) not in `completed`.
   If none remain but convergence didn't trigger, halt with
   `stop_reason="no_remaining_features"`.
4. **Increment `iter`.** Every 5th iteration log a ping line
   (`autoloop ping: iter=<N> feature=<name>`) so the user can see progress.
5. **Invoke the workflow.** Pass the feature's name + acceptance criteria
   to the configured fused workflow command:
    - In a normal Claude Code session, invoke `/hm:<workflow>` directly
      (e.g. via the `SlashCommand` tool when available) with a payload
      structured as: feature name, AC list, and the loop's overall
      objective for context.
    - If `--dry-run` is set, skip this step and treat the iteration as a
      success without doing any work.
6. **Update state:**
    - Workflow succeeded (the workflow's own `verify`/`wrapup` checks
      passed) → mark the feature task `completed` in `TodoWrite`, append to
      `completed` list, reset `failed_streak = 0`.
    - Workflow failed → `failed_streak += 1`. Do NOT mark the feature as
      completed. Log a brief failure note (what failed, what you tried).

Repeat from step 1.

### 5. Report

When the loop halts (any reason), emit a brief summary block:

```
loop done — converged=<bool> iter=<N>/<max_iter>
  objective: <objective or "(inline goal)">
  completed: <count>/<total>  [<feature names...>]
  stop_reason: <reason>
  spec: <spec path or "(inline goal)">
```

For non-converged halts, also list:
- which feature was being worked on when the loop stopped
- the last failure reason (if `failed_streak > 0`)
- a one-line suggestion for the user (e.g. "raise --max-iter", "narrow the
  failing feature's AC", "split feature X into 2")

## Safety Rails (always on, never skip)

- **3 consecutive failures** → halt with `stop_reason="3 consecutive failures"`
- **`max_iter` cap** → halt
- **`time_h` cap** → halt
- **Ping every 5 iterations** → INFO-level log
- **Convergence check** before each iteration — early exit when satisfied

If the loop appears to be stuck on a single feature for >3 iterations, do
NOT silently keep retrying. Report the blocker and halt.

## Reference

- Skill: `autoloop-driver` (orchestration guide + safety-rail rationale)
- Agent: `autoloop-coder` (per-iteration implementation worker, when the
  workflow delegates to it)
- Loop-spec schema: see step 3.f above
- Persisted loop-specs: `.claude/loop-specs/<slug>.yaml`

<!-- @hm:user:extensions -->
<!-- Project-specific autoloop overrides (custom safety rails, additional convergence predicates, etc.). Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
