---
generated_by: harness-maker
harness_maker_version: 0.9.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: codex/stage_skill.md.j2
provenance: official
name: hm-review
description: Invoke the harness-maker review stage procedure documented in AGENTS.md.
  Use the user's input as the goal or topic for this stage.
content_hash: 1af57b238c94a16c70d4e75173f998dc91dfc05cff6dd5ef28294fb5e0121931
---

# hm-review

Follow the **review** stage procedure documented in **AGENTS.md**.
Use the user's input as the goal, topic, or slug for this stage.

Invoke when the user asks to run the review stage of the harness-maker workflow,
or when the task context matches the review stage description.

See AGENTS.md for the full procedure, exit criteria, and quality bar.

<!-- @hm:user:extensions -->
<!-- Project-specific additions to the hm-review skill. Preserved across upgrades. -->
<!-- @hm:/user:extensions -->
