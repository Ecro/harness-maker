---
generated_by: harness-maker
harness_maker_version: 0.4.8
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/atomic_command.md.j2
provenance: official
content_hash: ade6f25cd31ea71907b81df4882ffeaefc6602ec3a85705915c1b1f9db8d85ec
---
# Stage: plan

> Atomic stage. Implementation planning with phase decomposition.


## Purpose

Convert acceptance criteria into a concrete sequence of implementation
phases. Each phase has a verifiable exit criterion so that progress can
be measured and stalled work can be diagnosed.

## When to Run

- After `spec` (or after `research` when `spec` is skipped)
- Before `execute` for any change touching more than 2-3 files or
  introducing new architectural elements

## Inputs

- SPEC (if available) or research notes + user requirements
- Existing TECH_SPEC.md, ADRs, prior PLANs in `work-docs/`
- Codebase structure (modules, conventions, test layout)

## Procedure

1. Restate the goal in one sentence. If it changed during research, note that.
2. Identify architectural touchpoints: which modules change, which contracts
   shift, what new files appear.
3. Decompose into phases. Each phase MUST have:
   - A clear scope (what's in)
   - An exit criterion (a command or check that proves the phase is done)
   - An estimate of risk (low / medium / high)
4. Order phases by dependency. Earlier phases unblock later ones.
5. Identify rollback points — checkpoints from which work can resume on
   failure without redoing prior phases.
6. Call out risks and unknowns. For each, list the mitigation.

## Outputs

- `work-docs/PLAN-{slug}.md` with frontmatter:
  - `type: plan`, `task_slug:`, `created:`, `tags:`
  - `spec: "[[SPEC-{slug}]]"` (when SPEC exists)
- Numbered phase list with scope + exit criterion + risk for each
- Risk register with mitigations
- Rollback strategy

## Quality Bar

- An independent reader can predict the file diff per phase
- Each exit criterion is checkable (script, test, manual checklist)
- Risks are concrete, not platitudes ("might break things")

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the plan stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
