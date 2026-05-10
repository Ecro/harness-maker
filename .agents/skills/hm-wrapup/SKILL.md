---
generated_by: harness-maker
harness_maker_version: 0.9.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: codex/stage_skill.md.j2
provenance: official
name: hm-wrapup
description: Invoke the harness-maker wrapup stage procedure documented in AGENTS.md.
  Use the user's input as the goal or topic for this stage.
content_hash: d1c6472eaf825f8a21ac72637feff8208883dc11c205afe49752a75b6eea9ad8
---

# hm-wrapup

Follow the **wrapup** stage procedure documented in **AGENTS.md**.
Use the user's input as the goal, topic, or slug for this stage.

Invoke when the user asks to run the wrapup stage of the harness-maker workflow,
or when the task context matches the wrapup stage description.

See AGENTS.md for the full procedure, exit criteria, and quality bar.

<!-- @hm:user:extensions -->
<!-- Project-specific additions to the hm-wrapup skill. Preserved across upgrades. -->
<!-- @hm:/user:extensions -->
