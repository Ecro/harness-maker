---
generated_by: harness-maker
harness_maker_version: 0.7.3
generated_at: '2026-01-01T00:00:00+00:00'
source_template: stages/wrapup.md.j2
provenance: official
content_hash: b885c00f707b22051a41c5fc01cac1c32691e1736dd7a105f29d108db4a6b517
---
# Stage: wrapup

> Atomic stage. **Single commit owner**: integrates execute's staged changes + memory + PLAN status updates into ONE user-facing commit with Co-Authored-By: Claude.


## Communication Protocol

- Be direct. No flattery, no preamble.
- The commit message describes the **why**, not the diff. Future readers (including future-you at 2 a.m.) need intent, not file lists.
- If a quality gate fails, surface the failure verbatim and STOP — do not paper over with "mostly works" language.
- Memory entries are written in the user's voice — concise, specific, traceable.

## Purpose

Close the loop on a unit of work:
1. Run the final verification pass (build / tests / lint).
2. Capture lessons in repo memory so the next session benefits.
3. Update PLAN status to mark phases done.
4. Create the **single commit** for this work unit (execute already staged its changes; this stage adds memory + PLAN updates and commits everything).

## When to Run

- After `review` (when review ran).
- Before pushing to a shared branch.
- Whenever a logical work unit completes (feature flag flipped, ticket closed, demo-ready).

> When invoked as part of a fused workflow, always run — do not skip based on the conditions above.

## Inputs

- All artefacts from prior stages: SPEC, PLAN, REVIEW, code, tests.
- `.claude/memory/wiki.md`, `.claude/memory/failures.md`, `.claude/memory/session/<today>.md`.
- The currently-staged changes from `/hm:execute` Step 5 (`stage-only` mode).
- TODO source if the project tracks tasks in a structured place (optional).

## Procedure

### Step 1 — Pre-flight checks

Before touching anything, verify state:

1. **Working tree state**: there should be staged changes (from execute) OR clean (if execute was skipped). If there are *unstaged* changes that don't trace to execute's worktree merge, surface them — they may be drift.
2. **Worktree finalize state**: any `.worktrees/execute-*` directories should be cleaned up by execute Step 5 (`stage-only`) already. If one persists, log a warning — it means execute exited with `fail` or stage-only failed. **Multi-repo**: when sibling repos are configured, `finalize stage-only` merges all repos' worktrees into their respective main branches; if any sibling's merge failed, the marker file is kept and the directory remains — resolve manually before committing.
3. **PLAN existence**: `work-docs/PLAN-{slug}.md` exists (skip wrapup with a clear error otherwise).

### Step 2 — Final verification pass

Run the project's full check suite once before committing. Catch regressions wrapup-stage edits could introduce:

```bash
# Pick the toolchain that matches the project. Examples:
!uv run pytest -x                      # Python
!uv run ruff check src/ tests/          # lint
!uv run mypy --strict src/              # type
# Rust: cargo test && cargo check
# Node: pnpm test && pnpm build
```

If any fail: STOP, surface the failure, do NOT proceed. Reverting an executed-merge is more painful than diagnosing here.

### Step 3 — Drift gate (advisory)

Diff intent (SPEC scenarios + PLAN phase scopes) against the actual staged changes:

- **Files staged but NOT in any PLAN phase scope** → log to `.claude/memory/pending-drift.md`.
- **Files in PLAN scope but NOT staged** → log incomplete-phase warning to `pending-drift.md`.
- **SPEC scenarios with no test coverage in the diff** → log missing-coverage warning.

This is advisory; do not block the commit. The next session reads `pending-drift.md` to catch up.

### Step 4 — PLAN status update

Update `work-docs/PLAN-{slug}.md`:

1. **Frontmatter**: `status: planning` → `status: complete`.
2. **Checkboxes**: replace every `- [ ]` with `- [x]` in the body. At wrapup time the plan's phases are either done or explicitly deferred — the checkbox state should reflect that.

Use a single Edit / Write call (atomic). Verify by reading back: assert `status: complete` is present and zero `- [ ]` remain.

### Step 5 — Memory append

#### 5.1 Wiki

Append (or update) one entry under `.claude/memory/wiki.md`:

```markdown
## [wiki:<category>] <slug> | <YYYY-MM-DD>
<one-paragraph summary of the pattern / convention / gotcha learned>
```

- **category**: `pattern` | `convention` | `gotcha` | `architecture` | `tooling` | `api` | `other`.
- **slug**: kebab-case, ≤40 chars, derived from the work unit.
- If a `[wiki:<same-slug>]` entry already exists: replace its body with the updated learning (do NOT duplicate).

#### 5.2 Failures

For each new failure pattern that emerged this work unit, append (or increment count) under `.claude/memory/failures.md`:

```markdown
## [fail:<category>] <slug> | <YYYY-MM-DD> | count:<N>
<symptom + cause + fix in one paragraph>
```

- **category**: `import` | `test` | `render` | `hook` | `lint` | `type` | `runtime` | `design` | `other`.
- **count**: increment when the same `<category>:<slug>` already exists; do NOT duplicate sections.
- **Qualifies as failure**: incorrect API usage, wrong syntax, convention misunderstanding, build failures, tool mistakes, workflow violations.
- **Does NOT qualify**: user preference changes, expected errors, normal debugging cycles, design evolution.

#### 5.3 Failure-driven proposal

When a failure entry's `count >= 3`, write a skill / agent / rule proposal to `.claude/memory/pending-proposals.md`:

```markdown
## Proposal: {short-title} ({YYYY-MM-DD})
**Triggered by:** [fail:<category>] <slug> (count: 3)
**Proposed mechanism:** {new skill | rule update | agent | hook}
**Rationale:** {why an automated guard would have prevented this 3 times}
```

The user reviews proposals later and decides whether to ingest into the harness.

#### 5.4 Session log

Append to `.claude/memory/session/<YYYY-MM-DD>.md` (today's date):

```markdown
## [decision:<slug>] <what was decided> | <HH:MM> UTC | stage:wrapup
<one paragraph: non-obvious constraint, key trade-off, or surprise from this work unit>
```

Create the file (with README header) if it doesn't exist. **Omit** when the work unit was trivial (typo fix, doc-only) — session log is for non-obvious decisions.

### Step 6 — Stage memory + PLAN updates

```bash
!git add .claude/memory/ work-docs/PLAN-{slug}.md work-docs/REVIEW-{slug}-*.md 2>/dev/null
```

(REVIEW-*.md is optional — only present when `/hm:review` ran.)

### Step 7 — Single commit

Write the commit message: `<type>(<scope>): <subject ≤72 chars>` followed by a body explaining **why**, not **what**. The diff already says what.

```bash
!git commit -m "$(cat <<'EOF'
<type>(<scope>): <subject>

<body — explains why this change exists, what trade-off was accepted, and
which constraint forced the chosen approach. Cite ADR-NNN or Interview-#N
when the rationale lives in the PLAN.>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

**Type** (per CLAUDE.md `<type>(<scope>): <subject>` convention): `feat | fix | chore | ci | test | docs | refactor`.

The commit captures: the staged execute changes + the memory updates + the PLAN status update — **all in one commit**.

### Step 8 — Push (manual; never automatic)

Wrapup does **NOT** auto-push. The user explicitly requests push when ready:

```bash
# (User runs separately when they want to push)
!git push
```

If the user asks to push during wrapup, that is fine — but never push without an explicit request.

## Outputs

- **One** git commit including: implementation diff (from execute), wiki + failures + session log + PLAN status updates.
- `.claude/memory/pending-drift.md` entries when drift was detected.
- `.claude/memory/pending-proposals.md` entries when failure count crossed threshold.
- Updated `.claude/memory/session/<today>.md` for non-trivial work units.

## Quality Bar

- **Exactly one** commit per wrapup invocation. (Verify: `git log` shows one new commit relative to wrapup start.)
- Commit message subject ≤72 chars; body explains **why**, not what.
- `Co-Authored-By: Claude` line present.
- Wiki entries are searchable: `rg -F "[wiki:" .claude/memory/wiki.md` returns the new entry.
- Failure entries deduplicate by slug (count++ in heading, not duplicate sections).
- Session log captures non-obvious decisions; trivial work units do NOT add noise.
- PLAN frontmatter `status: complete` and zero `- [ ]` remain in the body.
- Final verification pass GREEN before commit.

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific wrapup checklist items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the wrapup stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
