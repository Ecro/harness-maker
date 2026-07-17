---
type: research
task_slug: antisycophancy-2026-05
status: complete
created: 2026-05-16
tags: [harness-maker, research, anti-sycophancy, agent-prompts, communication-protocol, registry, drift-detection]
mtime_warn_days: 14
libs_fetched: []
sources:
  - user-supplied:SYCOPHANCY.md (vault canonical registry, command args)
  - arxiv:2602.23971 (user-cited; "Ask don't tell" — Question Reframing; not independently verified)
  - arxiv:2604.00478 (user-cited; "The Silicon Mirror" — Dynamic Behavioral Gating; not independently verified)
  - ICLR-2025:CAUSM (user-cited; Causal Head Reweighting; not independently verified)
related_docs:
  - "[[RESEARCH-harness-trends-2026-05]]"
  - "[[RESEARCH-harness-gap-cot-2026-05]]"
  - "[[PLAN-llm-code-review-2026]]"
summary: "Promote single communication partial to variant family + extend to skills/commands + add drift-verify routine."
---

# 🎯 Recommended Direction

harness-maker should absorb the maintenance toil currently sitting in the user's
hand-curated `SYCOPHANCY.md` registry by **promoting the existing single
`_partials/communication.md.j2` into a three-variant family** (FULL /
FULL+REFRAME / SOFT), extending injection to **skills and commands** (not just
agents), and shipping a **drift-detection routine** (`rg -c` style count
verification) inside `/hm:verify` or the existing `agent-quality-rubric`.

This is informational; `/hm:plan` decides the binding shape. The change is
small in code (Jinja partial swap + render-time variant selector) but high
leverage in user workflow: it eliminates a repeating manual "edit registry →
propagate → grep-count → spot-check" procedure that the user is doing by
hand across their entire vault.

# 🔍 Refinement Decisions

- **Discovery lens:** User-workflow / product opportunity (primary) +
  Technical architecture / implementation (secondary). Academic / arXiv lens
  declined — the user-cited paper IDs are 2026 vintages that I cannot
  verify in this session; the architectural value of the proposal does not
  depend on whether those papers say exactly what's claimed. Reference them
  as motivation, not as load-bearing evidence.
- `--deep` not set; Phase 0 / 0.5 skipped per stage rules.

# 🛠️ Approaches Found

## A. Variant family + skill/command injection + drift-verify (Recommended)

| Field | Content |
|-------|---------|
| Approach | Split `_partials/communication.md.j2` into `communication_full.md.j2`, `communication_reframe.md.j2`, `communication_soft.md.j2`. Add render-time variant selector (frontmatter key on agent/skill/command, e.g. `communication_variant: full \| reframe \| soft`). Inject into commands/stages (already done inline) and skills (currently nothing). Add a one-shot drift-verify call inside `/hm:verify` or `agent-quality-rubric` that runs the user's step-5 `rg -c` counts and reports drift. |
| Assumption | Most reviewer agents want FULL+REFRAME ("reframe submission as a question"); generalist coders want FULL; idea-/exploration-shaped agents want SOFT. Variant assignment is stable enough to encode at template level (not runtime). |
| Evidence | (1) Existing partial at `src/harness_maker/templates/agents/_partials/communication.md.j2` already does FULL-equivalent and is included by every reviewer + executor + stuck agent (12 includes). (2) The user's SYCOPHANCY.md mapping shows 6 FULL, 12 FULL+REFRAME, 30 SOFT agents in their vault — three-way split is the pattern that emerges in real use. (3) Stages already inline a near-identical block at lines 8-10 of every `templates/stages/*.md.j2`; partial swap would deduplicate. |
| Trade-off | Adds frontmatter surface (one more required field per template). Variant boundary needs LLM judgment occasionally — code-verifier could be FULL or FULL+REFRAME depending on framing. Mitigation: default to FULL, opt-in REFRAME via frontmatter. |
| Compatibility | High. Render pipeline already supports partial includes with `{% include %}`. `agent-quality-rubric` skill already grades structural signals; adding "communication protocol block present + correct variant" is one more check. |
| Risk | low. No runtime behavior change; build-time only. Backwards-compat: missing `communication_variant` → default FULL (current behavior preserved). |

## B. Generate-and-ship SYCOPHANCY.md as a user-doc

| Field | Content |
|-------|---------|
| Approach | Render `SYCOPHANCY.md` (the registry document itself) into user projects as a generated artifact with content_hash, including the agent/skill variant mapping. Treat it as a read-only reference for the user (and for human-driven audits), not as the source of truth — the source is the per-template frontmatter. |
| Assumption | Users want to *see* the variant mapping as a doc, not just inspect frontmatter across 50 files. The registry has audit value beyond its propagation function. |
| Evidence | The user is currently maintaining SYCOPHANCY.md by hand precisely because they want one place to look. Auto-generating it from the same metadata that drives rendering eliminates the dual-source-of-truth problem. |
| Trade-off | One more generated file in `.claude/`. Risk of users editing the generated doc and confusing themselves about authoritative-ness. Mitigation: standard `generated_by` frontmatter + `@hm:user:notes` block-merge marker for user annotations. |
| Compatibility | High — same render pipeline. Pairs naturally with A; A produces the variant assignments, B surfaces them as a doc. |
| Risk | low. |

## C. Runtime sycophancy detector hook

| Field | Content |
|-------|---------|
| Approach | A SessionEnd or PostToolUse hook that scans the assistant's transcripts for the user's detection patterns ("Great question!", >3 affirmations, opinion reversal without new evidence) and writes flags into `.claude/observability/`. |
| Assumption | The build-time variant injection is insufficient; runtime drift needs to be caught and surfaced. |
| Evidence | The user's DETECTION table specifies per-occurrence and threshold-based logging — runtime is the only place that signal exists. |
| Trade-off | High false-positive rate. "Excellent point" appears legitimately ("the existing solution is an excellent point of reference"). Opinion reversal detection requires NLP-grade comparison, not regex. Building this badly is worse than not building it. CLAUDE.md "LLM 활용 원칙" warns against regex/keyword filters when LLM judgment is more accurate — applies here. |
| Compatibility | Medium. Hook infrastructure exists but is target-specific (`.claude/hooks/hooks.json` vs `.cursor/hooks.json` vs `.codex/hooks.json`). |
| Risk | high. Don't ship a noisy detector. If pursued, gate behind explicit opt-in `harness.yaml.sycophancy_detector: enabled` flag, and treat outputs as advisory observations, not blocking. Recommended to **defer** unless concrete prior evidence in the user's vault shows the build-time approach failed. |

# ⚠️ Pitfalls

- **Don't bloat agent prompts.** CLAUDE.md context lint says ≤100 lines for
  Side-preset agents, ≤200 for Production. The SYCOPHANCY-FULL block alone
  is 5 lines; +REFRAME adds ~6 more; bundled wrong it could push
  short-prompt agents over the line lint warning. Variant injection must
  respect the existing context-linter skill thresholds.
- **Variant mismatch is worse than no variant.** A SOFT idea-agent that
  inherits FULL ("don't fold on pushback unless new evidence") will refuse
  to update brainstorm directions based on user vibes — which is exactly
  what the SOFT variant exists to prevent. Default must be safe-by-mismatch:
  FULL on generalist, FULL+REFRAME explicit on evaluator (matches existing
  partial behavior), SOFT requires opt-in frontmatter.
- **`rg -c` verification is fragile to template changes.** User's step-5
  expects exact counts (`expect 18` for FULL agents). If harness-maker
  generates the count from frontmatter at render time (instead of asking
  the user to maintain it), this becomes self-healing. Don't ship the
  count as a literal in a generated doc — derive it.
- **Cursor `.mdc` and Codex TOML frontmatter strictness.** CLAUDE.md flags
  that Cursor strict-rejects unknown frontmatter fields (Phase 1 manual
  verification pending). If `communication_variant` is added as
  frontmatter, the Cursor `.mdc` renderer may need to lift it into a
  sidecar or comment block. Codex TOML similarly — schema not verified.
- **Academic citations risk overclaiming.** The user's SYCOPHANCY.md cites
  arXiv:2602.23971 / 2604.00478 / ICLR 2025 CAUSM. I did not verify these
  exist or that they support the specific FULL/REFRAME/SOFT decomposition
  the user attributes to them. If harness-maker generates user docs that
  echo these citations, it should mark them `user-supplied; not
  independently verified` or omit them, per CLAUDE.md sycophancy rules
  about evidence-grounded claims.
- **Don't duplicate inline blocks across stages.** Every
  `templates/stages/*.md.j2` currently has the same 3-5 line communication
  block inlined at the top (lines 8-10). This is drift bait. Stage
  templates should `{% include %}` the same partial, not paste.

# ❓ Open Questions (for `/hm:plan` to lock down)

1. **Variant assignment policy.** Auto-derive from agent role (reviewer →
   REFRAME, executor → FULL, idea-* → SOFT) or require explicit frontmatter
   `communication_variant`? Auto-derive is less work for users but encodes a
   heuristic. Explicit is verbose but auditable.
2. **Should harness-maker generate `SYCOPHANCY.md` as a user-facing doc?**
   (Approach B). Yes ↔ users want a single page to audit; No ↔ frontmatter
   inspection + the variant mapping built into render is enough.
3. **Stage template deduplication.** Should the 7 stage templates also use
   `{% include "agents/_partials/communication_full.md.j2" %}` (or a
   stage-specific variant), or stay inline? They are conceptually closer
   to "instructions for Claude" than "agent personality", so the variant
   choice is non-obvious.
4. **Skills coverage.** The user's SYCOPHANCY.md ships FULL onto 10 skills
   and FULL+REFRAME onto 1 (`concurrent-test-review`). Should
   harness-maker's 12 skills auto-receive a variant? Some skills are
   purely procedural (e.g. `worktree-isolator` runs Python) and don't
   benefit from communication-tone guidance.
5. **Drift-verify wiring.** Add into `/hm:verify` (one-shot, command), into
   `agent-quality-rubric` (per-agent score signal, Bronze flag), or both?
   Single location avoids duplication; both gives faster signal at the
   cost of redundancy.
6. **Cursor / Codex parity.** Phase 1 manual checklist says
   `.cursor/rules/*.mdc` strict-rejects unknown frontmatter — needs
   verification before adding `communication_variant`. Codex TOML
   `developer_instructions` schema may need the variant inlined into the
   body string rather than carried as metadata.
7. **Defer or include runtime detector (Approach C)?** Strong default is
   *defer* — the build-time variant + verify routine likely satisfies the
   user's actual pain. Revisit only if vault telemetry shows real
   sycophancy in shipped agents.

# 📚 Sources

- User-supplied SYCOPHANCY.md (provided in `/hm:research` command args; treated
  as canonical project artifact).
- `src/harness_maker/templates/agents/_partials/communication.md.j2`
  (existing single-variant partial, last_reviewed_at 2026-05-08).
- `src/harness_maker/templates/agents/_partials/hard_rules.md.j2`
  (existing fabrication / evidence rules — overlaps with FULL preamble
  semantics, should be deduplicated together with variant work).
- `src/harness_maker/templates/stages/*.md.j2` (7 stage files; all carry
  an inline communication block at lines 8-10 — drift candidate).
- `src/harness_maker/templates/skills/` (12 skills; none currently carry a
  communication-protocol block).
- `src/harness_maker/templates/commands/hm/*.md.j2` (5 generators; tone
  reference unverified, ad-hoc).
- arXiv:2602.23971, arXiv:2604.00478, ICLR 2025 CAUSM — user-supplied
  citations; **not independently verified in this research**. Listed for
  traceability only.
- CLAUDE.md "LLM 활용 원칙 (최우선)" — repo principle: prefer LLM
  judgment over keyword/regex filters. Bears on Approach C (runtime
  detector) feasibility.
- CLAUDE.md "Context Lint (v1.6)" — line budgets that constrain how much
  preamble each variant can carry.

# 🔗 Related Internal Docs

- [[RESEARCH-harness-trends-2026-05]] — section on "Agentic Verification
  with Typed Boundaries" frames the same architectural shift this proposal
  fits into (build-time discipline > runtime detection).
- [[RESEARCH-harness-gap-cot-2026-05]] — discusses the meta-harness
  evolution direction; variant + verify routine is a small concrete step
  in that direction.
- [[PLAN-llm-code-review-2026]] — existing reviewer infrastructure that
  would consume the REFRAME variant.
