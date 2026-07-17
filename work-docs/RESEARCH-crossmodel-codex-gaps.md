---
type: research
task_slug: crossmodel-codex-gaps
status: complete
created: 2026-06-07
tags: [harness-maker, research, codex, second-opinion, cross-model, observability]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: ["[[PLAN-codex-second-llm-integration]]", "[[PLAN-codex-mandatory-second-opinion]]", "[[RESEARCH-codex-second-llm-integration]]"]
summary: "Observability-first: ship H6 ledger + H4 health smoke before protocol-depth (H1/H2)"
---

# RESEARCH — Cross-Model (Codex) Gaps & Improvements

Source topic: `work-docs/AUDIT-crossmodel-codex-gaps-from-vault-2026-06-07.md` (8 findings H1–H8 carried over from an external vault session that built a `codex-duel` PIDA skill).

## 🎯 Recommended Direction

**Observability-and-safety first (AUDIT's own sequencing wave 1), not protocol-depth first.** Ship the H6 calibration ledger + H4 `/hm:health` Codex smoke-test before investing in PIDA debate (H1) or heterogeneous consensus (H2). Rationale: the *actually recurring* real-world failure here is **silent degradation** — local memory records the warn-and-proceed policy masking **three distinct silent Codex skips in a single week** (Bash-tool gate, strict-schema rejection, invalid CLI flag). Self-adjudication bias (H1) is a real design flaw but has produced no recorded incident, and the protocol-depth fixes are partly blocked by a known pipeline limitation (array-output envelope-stripping, ADR-004 deferred). The ledger also makes every other finding *measurable* before it gets built. This is primarily **maintainer/internal value** (trust, safety, calibration); the user-facing scope expansion (H8 `/duel`) is correctly the last wave.

## 🔍 Refinement Decisions

- **Discovery lens (Phase 0.75):** Technical architecture/implementation + Risk/compliance/safety. This is an internal architecture audit of an existing, shipped integration — not a broad trend/opportunity/roadmap topic, so the user-workflow product-discovery coverage guard does not bind. No web/Context7/arXiv search needed; the authoritative sources are the codebase and local memory.
- `--deep` not set → Phase 0 refinement interview and Phase 0.5 inequality gate skipped.

## 🛠️ Approaches Found

The 8 findings are real (all verified below). The strategic question is *sequencing/scope*, so the approaches below are three ways to package the work, not three competing fixes.

### Per-finding ground-truth (verification pass)

| Finding | Verdict | Code evidence |
|---|---|---|
| **H1** self-adjudication | Confirmed | `second_opinion_codex.md.j2:91-93` — `overall_assessment` stays "your own Claude-derived verdict (Codex is input you cannot silently discard, **not a verdict source**)". No oracle/test arbitration, no `[unresolved]` disposition; dispositions are `accepted|rejected|duplicate`, all Claude-decided. |
| **H2** additive bolt-on | Confirmed | `consensus-arbiter_body.md.j2:124` `{% include second_opinion_codex %}` appends *after* the all-Claude Step 4b reasoning-alignment vote. Codex is advisory, outside the K-of-N ring. |
| **H3** same-family judging | Confirmed | `llm_judge.py:63` `anthropic.Anthropic`; `:232,:300` `model="claude-sonnet-4-6"`. No Codex audit path for generated CLAUDE.md / agents / rubric YAML. |
| **H4** silent broken integration | Confirmed (strongly) | `health.md.j2` Layer 1/2 = ai_readiness + personalization + silent_intent_miss; **zero** Codex round-trip. Memory `[wiki:gotcha] codex-exec-is-noninteractive-no-approval-flag`: warn-and-proceed masked 3 silent skips in one week. |
| **H5** hermetic erases context | Confirmed (nuance) | `second_opinion_codex.md.j2:61-63` `--ignore-user-config --ignore-rules`. The prompt body *is* a curated `$prompt_tmp` (question+diff), but project `AGENTS.md`/Codex rules encoding decided constraints are stripped. |
| **H6** no calibration ledger | Confirmed (net-new) | `codex-second-opinion.jsonl` appears nowhere in `src/` — only in the AUDIT. Reconciliations are returned in-agent and discarded. |
| **H7** default-off under-use | Confirmed | `models.py:461` `enabled=False`; `interview.py:568-585` single y/N, no preset/risk binding; only `plan-validator` is mandatory (branch-on-name). No skip receipts. |
| **H8** no general routes | Confirmed | No `/duel` command or route taxonomy in `templates/commands/hm/`. **Constraint:** the referenced vault `codex-duel/SKILL.md` route table is NOT accessible from this session — it must be physically brought over before H8 can be planned. |

### Approach A — Observability-first incremental (matches AUDIT wave order)
- **Assumption:** the binding risk is *silence*, not *bias*; you cannot improve what you cannot measure.
- **Evidence for:** memory's 3-silent-skips incident; H6 was the cross-system #1 pick; H4 fix is exactly what the memory wiki prescribes ("when a feature is wrapped in warn-and-proceed, add a POSITIVE smoke/health check").
- **Trade-off:** does not address self-adjudication bias (H1) in wave 1 — accepts that bias persists while observability lands first.
- **Compatibility:** high. H6 ledger = new `.claude/observability/*.jsonl` (established pattern). H4 = one new check in `health.md.j2` + a CLI smoke command. No pipeline rework.
- **Risk:** low.

### Approach B — Protocol-depth first (port PIDA + heterogeneous consensus from vault)
- **Assumption:** the binding flaw is the model grading its own challenge (H1/H2).
- **Evidence for:** H1/H2 are genuine structural biases; the vault skill already has a working PIDA + 4-route taxonomy.
- **Trade-off:** **blocked dependency** — heterogeneous consensus (H2) requires reworking the code-reviewer/consensus-arbiter top-level JSON **array** output that the two-pass/verifier pipeline strips envelopes from (memory `[wiki:pattern] branch-shared-partial...`; ADR-004 of PLAN-codex-mandatory-second-opinion explicitly deferred this). H1 PIDA without a test oracle (plan-validator plans, it doesn't run tests) degrades to mostly `[unresolved]` → noise without arbitration design.
- **Compatibility:** medium-low. Touches the consensus pipeline.
- **Risk:** medium — biggest behavior change, hardest to verify, and unmeasurable until H6 exists.

### Approach C — Minimal trust-and-safety slice (H4 + H7 only)
- **Assumption:** just close the "broken-and-silent" + "absent-and-unaudited" gaps; defer everything else.
- **Evidence for:** smallest surface that removes the recorded recurring pain.
- **Trade-off:** leaves H6 (the measurement substrate) out, so H7's "mandatory + skip receipts" produces receipts no ledger consumes. Under-delivers vs A for marginal extra cost.
- **Compatibility:** high. **Risk:** low.
- **Verdict:** A strictly dominates C (A = C + the ledger that makes the receipts useful).

## ⚠️ Pitfalls

1. **warn-and-proceed is a bug-hider.** (`[wiki:gotcha] codex-exec-is-noninteractive-no-approval-flag`) — any *new* Codex code path must ship with a positive smoke check or it will silently fail like the prior three. This is the single most load-bearing lesson for this whole effort.
2. **Codex strict-output-schema is not vanilla JSON-Schema.** (`[wiki:gotcha] openai-codex-strict-output-schema-rules`) — any new schema (H6 ledger entry consumed by Codex, H3 audit findings, H8 Route-Q reconciliation table) must be **all-properties-required + nullable-union optionals + no `minimum/maxLength/pattern/format`**. The durable fix lives in the *source* template; live `.claude/schemas/*.json` is a gitignored render artifact.
3. **`tools:` is the hard gate, `permissions` is inert without it.** (`[wiki:gotcha] subagent-tools-field-hard-gates-bash-permission`) — any new agent/skill that calls `codex exec` needs bare `Bash` on its `tools:` line, or `Bash(codex exec:*)` in `permissions.allow` is dead. Keep the REVIEW-M7 interpreter deny quartet when granting Bash.
4. **codex exec flag drift by CLI version.** No `--ask-for-approval` on `exec`; valid flags differ across codex-cli releases. Verify any recipe change with a real round-trip.
5. **Codex model unavailability on ChatGPT-tier.** (`[fail:review] reviewer-subagent-model-unsupported`, count:3) — don't pin model IDs; inherit `~/.codex/config.toml` default. Relevant if H2/H3 spawn new Codex agents.
6. **H1 without an oracle → noise.** plan-validator has no test to arbitrate planning disputes; a naive PIDA port surfaces nearly everything as `[unresolved]`. The arbitration/degradation rule must be designed, not assumed.
7. **H5 curated bundle reintroduces non-determinism.** The whole point of hermetic was reproducibility; a project-context bundle must itself be deterministic (pinned excerpts, not live file reads) or it defeats the original ADR-006 goal.
8. **Vault sync cross-product leak.** (AUDIT provenance note) — `~/harness-maker/.claude/commands/{review,myplan,duel}.md` may be vault-shaped (gitignored, regenerable). Regenerate via `/harness-maker:make` before trusting local `.claude/`.

## ❓ Open Questions

(For `/hm:plan` to lock down via interview.)

1. **H1 arbitration:** for plan-validator (no test oracle), does a Codex-vs-Claude disagreement always surface as `[unresolved]`, or is there a third-Claude tie-breaker? Define the degradation when no oracle exists.
2. **H2 scope vs the deferred ADR-004:** rework the array-output pipeline to host Codex as a real vote, OR keep Codex advisory and add heterogeneous consensus *only* to plan-validator (which already has a reconciliation envelope)?
3. **H6 ledger fidelity:** where do `oracle_result` / `later_regression_link` come from? Is there a ground-truth signal, or does v1 log dispositions + skip-rate only (precision deferred)?
4. **H7 mandatory scope:** which presets get mandatory Codex — Production only, or Production + high-risk? Given `codex login` cannot be enforced at render time, does "mandatory" mean hard-block or "warn loudly + skip receipt"?
5. **H5 bundle contents + determinism:** exactly what enters the curated context (PLAN/SPEC, diff, harness-policy excerpts, invariants), and how is it kept reproducible?
6. **H8 in or out:** is `/duel` (Route Q/C/D) in scope for this PLAN, or its own follow-up? **Blocker:** the vault `codex-duel/SKILL.md` route table must be physically copied into this repo first — it is not readable from this session.
7. **PLAN partitioning:** confirm the AUDIT's 4-wave sequence, or split into (P1) trust+observability = H4+H6+H7, (P2) protocol depth = H1+H2+H3, (P3) scope = H5+H8?

## 📚 Sources

- Internal — `src/harness_maker/templates/agents/_partials/second_opinion_codex.md.j2`
- Internal — `src/harness_maker/templates/agents/consensus-arbiter_body.md.j2`
- Internal — `src/harness_maker/templates/commands/hm/health.md.j2`
- Internal — `src/harness_maker/models.py:440-491` (`CodexSecondOpinionConfig`)
- Internal — `src/harness_maker/interview.py:568-585` (`_ask_codex_second_opinion`)
- Internal — `src/harness_maker/llm_judge.py:63,232,300` (Claude-only judge)
- Memory — `[wiki:gotcha] codex-exec-is-noninteractive-no-approval-flag`, `[wiki:gotcha] openai-codex-strict-output-schema-rules`, `[wiki:gotcha] subagent-tools-field-hard-gates-bash-permission`, `[wiki:pattern] branch-shared-partial-on-name-for-per-agent-divergence`, `[wiki:architecture] codex-second-llm-integration`, `[fail:review] reviewer-subagent-model-unsupported`
- External (NOT accessible this session) — vault `codex-duel/SKILL.md` route taxonomy (H8 reference)

## 🔗 Related Internal Docs

- [[PLAN-codex-second-llm-integration]] — the shipped integration (ADRs 001-009)
- [[PLAN-codex-mandatory-second-opinion]] — plan-validator MUST; ADR-004 deferred the array-output rework (binds H2)
- [[RESEARCH-codex-second-llm-integration]], [[RESEARCH-codex-shell-invocation]], [[RESEARCH-codex-usage-guide]]
- [[REVIEW-codex-mandatory-second-opinion-2026-05-25]], [[REVIEW-codex-second-llm-integration-2026-05-24]]
- [[PLAN-codex-finding-schema-strict-mode]] — strict-schema rules (binds H3/H6/H8 new schemas)
