---
type: matrix
task_slug: workflow-loop-efficiency
phase: 6
created: 2026-08-05
status: complete
subjects: 41
summary: "Which harness surfaces are now redundant with native Claude Code capability"
---

# Native-capability redundancy matrix

The user's question that opened this scope: *"is a command like `/hm:loop` still needed?
the model's own harness already provides things like goal."* Generalised — **which of our 41
shipped surfaces exist only because the host could not do it when they were written?**

## How to read this

**Decision axis is Claude Code only** (locked at SPEC interview R2): if a native equivalent
replaces it there, the verdict is `retire`, and the resulting capability loss on Cursor /
Codex is accepted. So the `cursor` / `codex` columns are *impact* columns, not inputs to
the verdict.

**Evidence for the `native` column is the live tool surface of this session**, not recall.
Every capability marked ✅ was observed as a callable or deferred tool in this very
conversation; anything I could not observe is `unverified` rather than `none`, because
"I did not see it" and "it does not exist" are different claims and only one of them is
mine to make. My knowledge cutoff (May 2026) predates this harness version (0.47.0,
2026-08), so recall is not admissible here.

**The judgment is deliberately NOT gated** (SPEC AC-007, and `test_redundancy_matrix.py`
asserts coverage only). Acting on any `retire` below is **stage 2**. A matrix that gated its
own conclusions would be an executor grading its own homework — the defect AC-007's
`oracle_evidence` was written to avoid.

### Column values

| Column | Values |
|---|---|
| `native` | the observed Claude Code equivalent, or `none`, or `unverified` |
| `cursor` | `parity` / `loss` / `unknown` — impact if retired |
| `codex` | `parity` / `loss` / `unknown` — impact if retired |
| `verdict` | `keep` / `retire` / `merge` |

---

## Observed native surface (the evidence base)

Callable this session: `Agent`, `Artifact`, `AskUserQuestion`, `Bash`, `Edit`, `Read`,
`ReportFindings`, `ScheduleWakeup`, `SendUserFile`, `Skill`, `ToolSearch`, `Workflow`,
`Write`.

Deferred but present by name: `CronCreate/Delete/List`, `EnterPlanMode`, `ExitPlanMode`,
`EnterWorktree`, `ExitWorktree`, `Monitor`, `SendMessage`, `TaskCreate/Get/List/Output/
Stop/Update`, `WebFetch`, `WebSearch`, `LSP`, `NotebookEdit`, `PushNotification`,
`RemoteTrigger`, `DesignSync`, `EndConversation`.

Named in the host system prompt: `/code-review ultra` (user-triggered multi-agent cloud
review of the branch or a PR — explicitly *not* launchable by me), a per-project file-based
**memory** directory with a `MEMORY.md` index, and `/loop` with both interval and dynamic
(`ScheduleWakeup`) pacing.

---

## Commands (15)

| Subject | native | cursor | codex | verdict |
|---|---|---|---|---|
| `hm:research` | `none` — `WebSearch`/`WebFetch` are retrieval primitives; the staged RESEARCH document, `mtime_warn_days` cache contract and downstream `research_doc:` binding are ours | loss | loss | **keep** |
| `hm:spec` | `none` — no native acceptance-criteria elicitation; the oracle axis (`oracle_source`/`oracle_evidence`) has no host equivalent | loss | loss | **keep** |
| `hm:plan` | ⚠️ **partial** — `EnterPlanMode`/`ExitPlanMode` ✅ cover *interactive planning with an approval gate*. They do **not** produce a persisted PLAN with ADRs, phases, `depends_on`, or a validator pass | loss | loss | **merge** — see §Merge candidates |
| `hm:execute` | `none` — native has no TDD phase machine, no RED gate, no PLAN-phase exit criteria | loss | loss | **keep** |
| `hm:review` | ⚠️ **partial** — `/code-review ultra` ✅ exists and is a multi-agent branch/PR review. It is **user-triggered and billed, and cannot be launched by the model**, so it cannot serve an automated loop | loss | loss | **keep** (see note) |
| `hm:verify` | `none` observed | loss | loss | **keep** |
| `hm:wrapup` | `none` — no native commit/memory/promotion pipeline | loss | loss | **keep** |
| `hm:loop` | ⚠️ **substantial** — native `/loop` ✅ exists with both interval and dynamic pacing (`ScheduleWakeup`), and `Workflow` ✅ provides deterministic multi-agent orchestration with phases, `pipeline()`, budget control and resume | loss | loss | **merge** — the user's original question; see §Merge candidates |
| `hm:loop-p5-batch` | ⚠️ `Workflow`'s `pipeline()` ✅ is the same fan-out-over-items shape, with a real concurrency cap and resume | loss | loss | **merge** |
| `hm:health` | `none` — readiness signals are harness-specific by construction | loss | loss | **keep** |
| `hm:metrics` | `none` — reads our own ledgers | loss | loss | **keep** |
| `hm:configure` | `none` — edits `harness.yaml` | loss | loss | **keep** |
| `hm:help` | `none` — host `/help` lists host commands, not ours | parity | parity | **keep** |
| `hm:make` | `none` — the renderer itself | loss | loss | **keep** |
| `hm:uninstall` | `none` | loss | loss | **keep** |

> **`hm:review` note.** `/code-review ultra` is the closest native equivalent in the whole
> matrix and it still does not qualify: the host prompt states plainly that it is
> user-triggered, billed, and that the model must not attempt to launch it. An auto-fix
> loop that cannot invoke its own reviewer is not a loop. This is a **capability** overlap
> with no **invocability** overlap, and only the second one matters for automation.

## Agents (15)

Every agent here runs through the native `Agent`/`Task` mechanism — that is not redundancy,
it is the substrate. The question for each row is whether the *role definition* is native.

| Subject | native | cursor | codex | verdict |
|---|---|---|---|---|
| `code-reviewer` | `none` — `Agent` is the dispatcher, not the rubric | loss | loss | **keep** |
| `security-reviewer` | `none` | loss | loss | **keep** |
| `performance-reviewer` | `none` | loss | loss | **keep** |
| `concurrency-reviewer` | `none` | loss | loss | **keep** |
| `ux-reviewer` | `none` | loss | loss | **keep** |
| `security-auditor` | `none` | loss | loss | **keep** |
| `judgment-reviewer` | `none` | loss | loss | **keep** |
| `test-reviewer` | `none` | loss | loss | **keep** — but its *barrier* is what P3's ledger is measuring; retirement would be an evidence decision, not a redundancy one |
| `code-verifier` | `none` | loss | loss | **keep** — mode A's dispatch was removed in P1; mode B (cross-model PIDA) has no native analogue |
| `consensus-arbiter` | ⚠️ `Workflow`'s adversarial-verify / judge-panel patterns ✅ are documented in the host tool description and cover the same shape | loss | loss | **merge** |
| `plan-validator` | `none` observed | loss | loss | **keep** — same caveat as `test-reviewer`: P3 is gathering the evidence |
| `stuck` | `none` | loss | loss | **keep** |
| `executor` | ⚠️ overlaps the generic native `general-purpose` / `claude` agent types ✅ | loss | loss | **merge** |
| `autoloop-coder` | ⚠️ same overlap as `executor`, plus `Workflow`'s own subagent default | loss | loss | **merge** |
| `stage-delegate` | `none` — exists to cut main-loop context carry, which no native agent targets | loss | loss | **keep** |

## Skills (11)

| Subject | native | cursor | codex | verdict |
|---|---|---|---|---|
| `agent-quality-rubric` | `none` | loss | loss | **keep** |
| `ai-readiness-rubric` | `none` | loss | loss | **keep** |
| `security-scanner` | `none` | loss | loss | **keep** |
| `refdocs-search` | `none` — `WebSearch` ✅ does not read configured local `ref_folders` | loss | loss | **keep** |
| `context-linter` | `none` | loss | loss | **keep** |
| `conditional-router` | `none` | loss | loss | **keep** |
| `targeted-test-selection` | `none` | loss | loss | **keep** |
| `verify-before-completion` | `none` | loss | loss | **keep** |
| `second-opinion-gate` | `none` — cross-vendor CLI invocation is ours | loss | loss | **keep** |
| `autoloop-driver` | ⚠️ **substantial** — `Workflow` ✅ is a deterministic driver with phases, fan-out, budget and resume; `/loop` ✅ covers self-paced iteration | loss | loss | **merge** |
| `worktree-isolator` | ⚠️ `EnterWorktree` / `ExitWorktree` ✅ exist natively | loss | loss | **merge** — but see the warning below |

---

## Merge candidates — and why not one of them is a `retire`

Seven rows came out `merge` and **zero** came out `retire`, which is worth stating plainly
because it is the opposite of what the opening question expected.

**`hm:loop` + `autoloop-driver` + `hm:loop-p5-batch` (the user's actual question).** Native
`/loop` and `Workflow` genuinely overlap the *driving* mechanics — iteration, pacing,
fan-out, budget, resume. What they do not carry is the **stage contract**: per-iteration
receipts, Gate 0 verdicts, the ADR-halt rule, session-scoped loop markers, and the
5-layer worktree defense that the loop's `create`/`finalize` path is wired into. A retire
would drop mechanics we could re-adopt and, with them, safety rails that took three
contamination incidents to build. **The honest verdict is: adopt `Workflow` as the driver
underneath, keep the stage contract on top.** That is a merge, and it is stage-2 work.

**`worktree-isolator` — the one to be most careful with.** `EnterWorktree`/`ExitWorktree`
exist, but this harness's worktree layer is not isolation-for-convenience: it is the
per-task feature-branch model, the session registry, the queue/dirty/UUID/fence/scope
5-layer defense, and the landed-marker reaping. CLAUDE.md records that
`worktree-finalize-pulls-orphan-wip-into-main` recurred **three times**. Swapping in a
native primitive that does not know about any of it is how a fourth happens.

**`consensus-arbiter`, `executor`, `autoloop-coder`.** Real overlap, low stakes, and the
merge is mostly deletion of our own wrapper. These are the cheapest three.

**`hm:plan`.** `EnterPlanMode` should probably *front* our plan stage rather than replace
it — native approval UX, our persisted artifact.

## What this matrix does not establish

- **It is not a decision.** SPEC AC-007 gates coverage, not judgment; stage 2 decides.
- **`cursor` / `codex` columns are mostly `loss` by construction**, since the surfaces are
  ours. They are recorded because the locked policy *accepts* that loss, and an accepted
  cost should still be written down.
- **`unverified` is used where I could not observe.** No row asserts a native absence I did
  not check, and no row claims a native capability I only remember.
