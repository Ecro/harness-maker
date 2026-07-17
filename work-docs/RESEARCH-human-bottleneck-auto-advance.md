---
type: research
task_slug: human-bottleneck-auto-advance
status: complete
created: 2026-06-20
tags: [harness-maker, research, autonomy, human-in-the-loop, workflow, auto-advance]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://arxiv.org/abs/2506.12469
  - https://arxiv.org/html/2411.12924v1
  - https://arxiv.org/html/2511.08798v2
  - https://arxiv.org/html/2502.13069v1
  - https://arxiv.org/pdf/2602.01532
  - https://arxiv.org/pdf/2603.21489
  - https://www.anthropic.com/engineering/claude-code-auto-mode
  - https://code.claude.com/docs/en/permission-modes
  - https://cursor.com/docs/agent/security
  - https://www.anthropic.com/research/measuring-agent-autonomy
  - https://github.com/roboticforce/agent-guardrails
  - https://zenity.io/blog/current-events/ai-agent-database-deletion-pocketos
related_docs:
  - "[[CLAUDE.md]]"
  - "[[docs/reference/autoloop-pattern.md]]"
  - "[[PLAN-deep-interview-question-criteria]]"
  - "[[project_review_grade_gate]]"
summary: "Auto-advance only in the low-risk AND low-uncertainty quadrant; gate the few irreversible/ambiguous boundaries; reuse worktree+EIG+ledger substrate already present"
---

# RESEARCH — Reducing the human as workflow bottleneck (auto-advance)

## 🎯 Recommended Direction

**Ship a layered "autonomy" feature that turns the human from an *every-stage gate* into an *exception handler*.** The decision of whether to auto-advance past a STOP boundary is governed by **two orthogonal axes the entire 2024-2026 literature converges on**: (1) **reversibility/risk** of the pending action, and (2) **uncertainty/ambiguity** of whether a human answer would change the outcome. Auto-advance is safe — and *safer than the status quo* — in the **low-risk AND low-uncertainty quadrant**; keep a hard human gate whenever **either** axis is high.

This maps almost 1:1 onto primitives harness-maker **already owns**, so this is largely a *wiring* job, not new infrastructure:

| User goal | Existing substrate to reuse |
|---|---|
| Auto-advance engine (skip the STOP) | **Fused workflows** already chain stages with no inter-stage STOP |
| On-demand "flip it on for this task session" | **`.claude/.hm-loop-active`** session-marker pattern (gitignored, session-UUID-scoped) |
| "Safe because reversible" | **`.worktrees/` isolation** — executor confined to `.worktrees/**`, reviewers read-only, 5-layer finalize defense |
| "Stop only on genuine ambiguity" | **5-term EIG inequality gate** (plan/spec deep interview) |
| Audit after the fact | **`.claude/observability/*.jsonl`** + `iter_receipts` + `/hm:health` smoke-test |
| Runaway guards | **`autoloop_driver.py`** caps (max_iter=50, time_cap, failed_streak_cap=5) |

**Rationale:** The user's frustration is not only a velocity problem — it is a *safety* problem. A STOP after every atomic stage trains the user to rubber-stamp (automation-bias / approval-fatigue research: ~93% of prompts get reflexively approved), which *degrades* the signal value of the one gate that actually matters (the irreversible merge/push). Removing low-value gates **raises** the attention paid to the kept ones. So "fewer but meaningful gates" is the safety-optimal design, not a compromise.

**Primary impact = internal maintainer/user workflow value** (this is the dogfooding workflow itself), with the design then shipping to harness users as a `harness.yaml` axis.

---

## 🔍 Refinement Decisions

- **Discovery lenses (all four):** User-workflow/product opportunity (primary — this is a "remove the friction users hit" request), Technical architecture (how to wire it into stages/config), Research/academic (when-to-interrupt theory), Risk/compliance (what must never auto-advance).
- **Method:** 7-agent parallel `Workflow` fan-out (internal codebase map · academic/arXiv HITL · framework interrupt mechanisms · coding-agent auto-approval UX · product/UX patterns · risk/safety must-gate · config-design synthesis). 520k tokens, 139 tool uses, ~50 external sources.
- **Scope locked in:** auto-advance = *skip the inter-stage STOP boundary*, **NOT** skip the in-stage human decision gates (plan architecture interview, review CHANGES_REQUESTED). This distinction is the spine of the whole design.

---

## 🗺️ The complete human-bottleneck map (the broader ask)

Every point where the human gates or could gate the workflow, classified by whether it should stay gated:

| # | Gate | Location | Reversibility | Verdict |
|---|------|----------|---------------|---------|
| 1 | **Atomic-stage STOP boundaries** (×6-7) "STOP — do not proceed without user command" | every `stages/*.md.j2` terminal | two-way (next stage is reversible) | **AUTO-ADVANCE** — the #1 bottleneck, mostly low-value |
| 2 | RESEARCH Phase 4 "Ready to proceed? Y/N" | `research.md.j2:256-275` | two-way | AUTO-ADVANCE (gate only if open-questions remain) |
| 3 | SPEC interview + Step 3.0 confirm | `spec.md.j2:72-139` | two-way | AUTO-ADVANCE when SPEC `status: approved` |
| 4 | **PLAN deep interview (≈5 AskUserQuestion)** | `plan.md.j2:177-334` | **one-way-ish** (wrong architecture compounds downstream) | **KEEP** — but make EIG-dynamic (ask 0 when unambiguous) |
| 5 | PLAN validator escalation (MAJOR_REVISION → proceed/abort) | `plan.md.j2:342-396` | one-way-ish | KEEP (surface as `unresolved`, never silently bypass) |
| 6 | EXECUTE TDD gates (A.5 test-review, B RED, D all-green) | `execute.md.j2:210-293` | two-way (inside worktree) | AUTO-FIX w/ attempt cap, escalate on cap |
| 7 | **REVIEW grade-gate (CHANGES_REQUESTED)** | `review.md.j2:336-424` | one-way-ish (ships defects) | **KEEP** — already config-driven (grade_threshold/auto_fix/max_review_rounds) |
| 8 | VERIFY 5-check gate | `verify.md.j2:41-152` | one-way (blocks unsafe land) | KEEP (only `--force` bypass, intentional) |
| 9 | **WRAPUP merge-back + git push** | `wrapup.md.j2` | **one-way** (escapes the sandbox) | **HARD GATE always** — the single irreversible door |
| 10 | `/hm:make` onboarding interview | `make.md.j2` | n/a (setup) | out of scope (one-time) |

**Key insight (from HULA, arXiv 2411.12924):** humans accept **82%** of agent plans unmodified but only **8-25%** of code reaches a PR — i.e. they rubber-stamp the *early* gates and do real filtering at the *late/output* gate. So the asymmetric policy is empirically grounded: **auto-advance the early/middle gates, keep a human at the irreversible end.**

---

## 🛠️ Approaches Found

### Approach 1 — Autonomy-level enum (RECOMMENDED PRIMARY)
| Field | Content |
|---|---|
| **Approach** | A small 3-value user-facing enum in `harness.yaml.autonomy.level` — `gated` / `auto_safe` / `full` — deciding how far a stage auto-advances. Maps onto the existing atomic→fused→loop spectrum. |
| **Assumption** | Most stage boundaries are two-way doors; the few one-way ones are enumerable. |
| **Evidence** | **Cross-vendor convergence**: Claude Code permission-modes (6 modes, Shift+Tab + `defaultMode`), Cursor 3.6 Run Modes (4 levels), Windsurf Cascade (Off/Auto/Turbo), AutoGen `human_input_mode` (ALWAYS/NEVER/TERMINATE), Aider flags. Feng et al. "Levels of Autonomy for AI Agents" (arXiv 2506.12469) gives the theoretical backbone (operator→observer ladder + "autonomy certificate" = per-context max level). |
| **Trade-off** | More config surface than a boolean; mitigate by shipping 3 memorable named levels (Windsurf's Off/Auto/Turbo legibility) backed by richer internals. |
| **Compatibility** | High — `harness.yaml` already holds `fused_workflows` + `autoloop` dict; the fused mechanism IS the auto-advance engine. ~7 terminal-block edits + one enum key. |
| **Risk** | medium |

Level → behavior:
- `gated` (default, absent-case) = today's STOP-after-every-stage.
- `auto_safe` = auto-advance the two-way boundaries (research→spec→plan-entry, execute→review→wrapup-entry) **but STOP at**: plan architecture interview, review CHANGES_REQUESTED, the wrapup merge/push.
- `full` = existing `/hm:loop`.

### Approach 2 — "Ask only when mandatory" via EIG/ambiguity gate (HIGHEST FIT, HIGHER RISK)
| Field | Content |
|---|---|
| **Approach** | Auto-advance by default; the stage's own LLM judges per-turn whether a genuine high-EIG ambiguity remains that it cannot resolve from CLAUDE.md/TECH_SPEC/deliverables. Generalizes the plan-stage 5-term inequality gate to every boundary. |
| **Assumption** | The model can reliably self-detect "nothing here needs a human." |
| **Evidence** | SAGE/Structured-Uncertainty clarification (arXiv 2511.08798) cuts clarifications 45-59% via EVPI/EIG; ClarifyGPT detects ambiguity by *consistency across multiple generations* (no new infra). Matches CLAUDE.md's own mandate "모호함 감지는 LLM이 직접, regex 금지." |
| **Trade-off** | **LLM confidence is miscalibrated** (arXiv 2502.13069: weak models under-ask, 90% false-negative on Haiku-class). A silent false "all-clear" → costly wrong direction. |
| **Compatibility** | High — reuses existing `inequality_gate` + plan-validator PIDA (KEEP/REFUTE→`unresolved`). |
| **Risk** | high — **only run the gate-skip judgment on Opus/Sonnet, never a Haiku-class self-check; bias toward gating on uncertainty.** |

### Approach 3 — Optimistic execution + worktree rollback (THE KEYSTONE)
| Field | Content |
|---|---|
| **Approach** | Frame auto-advance as *optimistic + reversible*: run forward inside the isolated worktree, review-after instead of approve-before, gate only the irreversible merge/push. |
| **Assumption** | Wrong work is cheaply discardable. |
| **Evidence** | async-SWE-agents survey (arXiv 2603.21489) lists optimistic execution + batching + async-notify as the core non-blocking strategies; Augment/MindStudio worktree playbooks ("simplest rollback = delete the branch"). |
| **Trade-off** | Reversibility covers worktree state, **not** side-effects that escape it (push, external API, destructive Bash). Optimistic work on a wrong assumption still wastes compute. |
| **Compatibility** | **DIRECT** — harness-maker already executes in `.worktrees/` with finalize-stash + landed-marker recovery. This is what makes Approaches 1 & 2 *defensible*: the only one-way door is the wrapup merge. |
| **Risk** | low |

### Supporting mechanisms (compose with the above)
- **Three config surfaces** (the user's exact ask), ranked by safety: on-demand session marker (SAFEST — ephemeral, re-consented, auto-expires) > ask-once-at-session-start > persistent `harness.yaml` (riskiest — set-and-forget invites complacency). Precedence: **session marker > start-prompt > yaml**, never-auto list overrides all three.
- **Audit ledger** — every auto-advanced boundary writes a receipt `{stage_from, stage_to, reversibility_class, never_auto_checked, ambiguity_score, token_spend, ts}` to an append-only `observability/*.jsonl`; every *skipped* gate logs a skip-receipt (mirrors the existing Codex skip-receipt pattern). `/hm:health` adds a positive smoke-test (auto-advance ran but no ledger entries = broken).
- **Progressive trust** (optional, later): Anthropic telemetry shows full-auto-approve organically rises 20%→40% over 750 sessions while interrupts *also* rise (5%→9%) — "let it run, step in when wrong." A `after_N_clean_runs` promotion could self-tune, fed by iter-receipts.

---

## ⚠️ Pitfalls

1. **Agent-frontmatter `permissions` are silently ignored by Claude Code** (CLAUDE.md's own 2026-06-02 correction). The never-auto deny-list **MUST** live in `settings.json` deny + a `PreToolUse` hook, **never** in agent frontmatter — frontmatter is intent-only, not a control.
2. **Prose rules do not stop a tool call.** PocketOS deleted a DB in 9 seconds *while quoting its own rule against it*; Cursor Plan Mode `rm -rf`'d ~70 tracked files despite the user typing "DO NOT RUN ANYTHING." The only thing between a tool call and the disk is the dispatcher → enforce at the permission/hook layer.
3. **Static denylists are bypassable** (Cursor's pre-1.3 denylist was evaded — Backslash, Jul 2025 — and *deprecated* in favor of classifier+sandbox). Don't make a regex denylist the *safety* boundary; it's a convenience layer under the worktree sandbox + host-IDE auto-mode classifier. Aligns with CLAUDE.md "LLM judgment over rule-based."
4. **Absent-case = feature black hole** (CLAUDE.md 2026-06-08 memory). Old `harness.yaml` without an `autonomy` key MUST silent-fallback to `gated` (fully gated). Never default a pre-feature config to auto-advance.
5. **No token/cost cap exists project-wide.** `autoloop_driver.py` caps iterations/time/failed-streak but is "token-unlimited by design." A runaway clarification loop once produced a **$47k / 11-day** bill elsewhere. An interactive auto-advance session inherits *weaker* caps than `/hm:loop` → must add `max_steps`, `time_cap_min`, and a NEW `token_budget`/`cost_budget_usd` soft-warn/hard-halt.
6. **Stale session marker footgun.** Like `.hm-loop-active`, the autopilot marker must be gitignored + session-UUID-scoped, or it silently leaves auto-advance on into the next session / for collaborators.
7. **Settings.json deny is session-wide** and can block the harness's *own* `python -m harness_maker` self-calls (CLAUDE.md). The never-auto deny must be surgical (specific destructive patterns) or use agent-identity hooks — not blanket interpreter bans.
8. **`bypassPermissions` / `--dangerously-skip-permissions` nullifies all four enforcement layers.** Auto-advance must refuse to combine with bypass mode, or loud-warn.
9. **Don't suppress the plan interview.** `/hm:loop` already runs without AskUserQuestion — acceptable *only* because it is opt-in fully-autonomous. An interactive `auto_safe` session must NOT inherit that suppression (CLAUDE.md: "architectural 결정 가정 금지").

---

## ❓ Open Questions (for `/hm:plan` to lock)

1. **Granularity:** ship Approach 1 (enum) alone as the legible MVP, or enum + Approach 2 (EIG dynamic) together? (Recommend: enum first, EIG-dynamic as an opt-in `auto_classified` tier later.)
2. **Per-stage map (Approach B/per-edge):** expose a power-user `auto_advance` edge map, or hide it behind the 3-value enum? Brittle on workflow reorder — defer?
3. **Stop-hook feasibility spike:** can a Claude Code `Stop`/`SubagentStop` hook *re-invoke a new slash command* to chain stages, or must auto-advance rely on fused-concatenation (rendering the next stage's template inline)? This determines the implementation host. **Phase-0 spike required.**
4. **Cross-IDE parity:** `Stop` hooks + `defaultMode` are Claude-specific. What is the Cursor / Codex equivalent for the auto-advance trigger and the never-auto enforcement? (Codex uses `.codex/hooks.json` PascalCase; Cursor `permissions.json`.)
5. **Never-auto list location & on/off coupling:** confirm it ships as a *separate always-on* list (not gated behind the existing `permissions.deny_dangerous` opt-in), since auto-advance specifically removes the human who'd otherwise catch these.
6. **Cost cap:** introduce `token_budget`/`cost_budget_usd` now (new project-wide capability) or defer? Telemetry is 100% local so counting is feasible.
7. **Which exact STOP boundaries change wording:** the bypass insertion point is the `_partials/stage_end_summary.md.j2` + each stage terminal — needs exact-wording review so the boundary still "survives context compaction" in `gated` mode.

---

## 📚 Sources

**Academic / arXiv (2024-2026):**
- Levels of Autonomy for AI Agents — https://arxiv.org/abs/2506.12469
- Human-In-the-Loop Software Development Agents (HULA, 82% plan-accept / 8-25% PR) — https://arxiv.org/html/2411.12924v1
- Structured Uncertainty-guided Clarification (SAGE, EVPI/EIG, 45-59% fewer Qs) — https://arxiv.org/html/2511.08798v2
- Interactive Agents to Overcome Ambiguity in SE (model miscalibration) — https://arxiv.org/html/2502.13069v1
- PRISM "festina lente" risk×uncertainty proactivity — https://arxiv.org/pdf/2602.01532
- ReDAct uncertainty-threshold deferral (~15% escalate) — https://arxiv.org/html/2604.07036v1
- async-SWE-agents non-blocking strategies (batching/optimistic/async) — https://arxiv.org/pdf/2603.21489
- ClarifyGPT consistency-based ambiguity detection (survey) — https://arxiv.org/html/2508.00083v1
- Trust calibration / human-AI complementarity — https://arxiv.org/pdf/2510.26518

**Industry / framework docs:**
- Anthropic — Claude Code "auto mode" classifier (the reference design) — https://www.anthropic.com/engineering/claude-code-auto-mode
- Claude Code permission modes — https://code.claude.com/docs/en/permission-modes
- Anthropic — Measuring agent autonomy (20%→40% auto-approve telemetry) — https://www.anthropic.com/research/measuring-agent-autonomy
- Cursor 3.6 Run Modes / security — https://cursor.com/docs/agent/security
- LangGraph interrupt()/Command(resume)/checkpointer — https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- LangChain Agent Inbox (4-way response taxonomy) — https://github.com/langchain-ai/agent-inbox
- OpenAI Agents SDK needs_approval/interruptions — https://openai.github.io/openai-agents-python/tools/
- Temporal wait_condition + Signal durable approval — https://temporal.io/blog/human-in-the-loop-approvals
- Windsurf Cascade Off/Auto/Turbo — https://docs.devin.ai/windsurf/plugins/cascade/cascade-overview
- Aider --yes-always / --auto-commits — https://aider.chat/docs/config/options.html

**Risk / incidents / governance:**
- agent-guardrails (deny-list + PreToolUse hook enforcement pattern) — https://github.com/roboticforce/agent-guardrails
- PocketOS 9-second DB deletion (prose rule failed) — https://zenity.io/blog/current-events/ai-agent-database-deletion-pocketos
- Cursor Plan Mode destructive-ops incident — https://www.mintmcp.com/blog/cursor-plan-mode-destructive-operations
- Backslash — Cursor autorun denylist bypass — https://www.backslash.security/blog/cursor-ai-security-flaw-autorun-denylist
- Rubber-stamp risk / automation bias — https://cybermaniacs.com/cm-blog/rubber-stamp-risk-why-human-oversight-can-become-false-confidence
- Token/cost runaway guardrails ($47k case) — https://leanopstech.com/blog/agentic-ai-cost-runaway-token-budget-2026/
- AI agent audit trails / governance — https://galileo.ai/blog/ai-agent-compliance-governance-audit-trails-risk-management

**Internal (codebase):**
- `src/harness_maker/templates/stages/{research,spec,plan,execute,review,verify,wrapup}.md.j2` (STOP boundaries, gates)
- `src/harness_maker/templates/commands/hm/{loop,workflow_command}.md.j2` (fused/loop auto-advance mechanisms)
- `src/harness_maker/models.py` (HarnessConfig — no autonomy axis exists; closest = `fused_workflows`, `default_workflow`)
- `src/harness_maker/autoloop_driver.py` (caps: max_iter=50, time_cap, failed_streak_cap=5; token-unlimited)
- `src/harness_maker/worktree.py` + `iter_receipts.py` (reversibility containment + receipt substrate)
- `docs/reference/autoloop-pattern.md` (DD#8 autonomous decision protocol)

---

## 🔗 Related Internal Docs

- [[CLAUDE.md]] — §보안/권한 (frontmatter-permissions-not-enforced correction), §Multi-session worktree (5-layer defense), §Communication variant, absent-case memory note
- [[docs/reference/autoloop-pattern.md]] — DD#8 "log and proceed" autonomous protocol; 4-gate convergence
- [[PLAN-deep-interview-question-criteria]] — the 5-term EIG inequality gate this design generalizes
- [[project_review_grade_gate]] (memory) — review fix→re-review loop, the model for a config-driven gate
- [[feedback_ask_thoroughly_when_planning]] (memory) — plan-stage AskUserQuestion must persist
