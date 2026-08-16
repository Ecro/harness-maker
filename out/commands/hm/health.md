---
generated_by: harness-maker
harness_maker_version: 0.52.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/health.md.j2
provenance: official
description: Two-layer harness audit — structural integrity plus personalization drift.
content_hash: b16b0c64191d45f0b5d01ffa6e3f68ff8f0cf46a6b361f0193fc57ad692db222
---
# /hm:health

> Two-layer health audit (ADR-007 supersedes ADR-006; ADR-002 amended).
> Layer 1 Structural · Layer 2 Personalization.
> 100% structured-question gated — no auto-apply (ADR-001).

## Layers

| Layer | What it measures |
|-------|------------------|
| `structural`     | ai_readiness 3-layer score (CLAUDE.md, ADRs, frontmatter, etc.) + `silent_intent_miss_rate` sub-check |
| `personalization`| ADR-011 rubric: L1 conversion (0.4) + L2 stability (0.3) + L3 cadence (0.3) |

CVE detection lives in `/hm:verify` (`secscan/dependency_cves.py` via OSV.dev),
not here. ADR-0007 removed the external_risks layer after 2026-05-22 runtime
evidence showed 91% noise on a representative run.

### Layer 1 sub-check — `silent_intent_miss_rate` (ADR-008)

Reads `.claude/observability/silent-intent-miss-*.jsonl` audit logs (one per
task slug; appended by `harness_maker.observability.intent_miss.record_intent_miss`
when REVIEW flags mis-specification on a slot previously marked common-ground
at LLM-inference ≥ 0.95, or when a user reopens such a slot in-session).

Compute `silent_intent_miss_rate = miss_events / common_ground_marks_total` and
surface as a Layer 1 ActionItem when rate exceeds the calibrated threshold.
Initial default = `0.10` (10% miss); this is narrative-only for the first
release pending telemetry-driven calibration — promote to
`harness.yaml.observability.silent_intent_miss_threshold` when post-ship data
justifies a different value. When triggered, the suggested remediation is
either raising `interview.deep_gate.common_ground.llm_inference_threshold` or
flipping the ADR-012 kill-switch (`llm_inference_enabled: false`).

## Run

```bash
!uv run --with $HOME/harness-maker hm cli health . --session-id "$HM_SESSION_ID" --json-output .claude/observability/.health.tmp.json
```

Then read `.claude/observability/dashboard.md` to inspect the two sections.

## Worktree backlog drain (ADR-009)

Run the gated, biased-to-preserve worktree sweep here so the orphan-branch /
stale-marker backlog does not accumulate between `worktree create` calls (the
create-only trigger leaves it unbounded when a project pauses). It is advisory
and never deletes unmerged work — preserved branches surface as a count only.


```bash
!uv run --with $HOME/harness-maker hm worktree drain .
```


Surface the one-line summary as a Layer 1 ActionItem when the preserved count is
non-zero (`run prune-branches to review`).


## Cross-model second opinion is OFF — is a CLI sitting unused?

The smoke check above only exists once `second_opinion.models` is non-empty, so the common
state "the CLI is installed but the harness never asks it anything" was silent for its whole
lifetime. This is the inverse check. It must probe at RUN time — a render-time answer would
freeze at install and go stale the moment a CLI is added.

```bash
!uv run --with $HOME/harness-maker hm cli detect-tools --json
```

If the command is missing, exits non-zero, or its output does not parse: print nothing and
move on. This is advisory — `/hm:health` must never fail or block on it.

If `codex` or `antigravity` reports `installed: true`, surface ONE Layer 1 advisory:
the CLI is on PATH but casts no vote, and `/hm:configure`
→ "Cross-model second opinion" enables it. Say `installed` means the binary resolves —
authentication is not checked here. If neither is installed, print nothing: a user without
these tools does not need to be told about them on every audit.


## Autopilot auto-advance smoke check — not applicable

`autonomy.level` is `ask`, so the level is chosen per session and is not knowable at
render time. The smoke check takes a concrete `--level`, and interpolating a meta-level
into it would make the probe fail on an argument error and report that as a degraded
harness (ADR-007). Report one line: autopilot smoke skipped — level resolved per session.

<!-- @hm:economics-doctor -->
## Economics reader liveness (no score impact)

A **positive** smoke: a reader that silently stopped understanding the transcript format
looks exactly like "this project has no history". Measures the INSTRUMENT, never the spend
— it must never carry a cost threshold, and it feeds no readiness dimension.

```bash
!uv run --with $HOME/harness-maker hm economics doctor --root .
```

Report the JSON as a Layer 1 ActionItem:
- `status: ok` → pass. Mention `turns_priced` + `coverage`; a coverage well under ~0.9
  means partial format drift, so quote it even on a pass.
- `status: n/a` → **pass, not a finding.** No transcript store exists for this project —
  expected on a fresh clone, in CI, and under Cursor or Codex (neither writes Claude Code
  session transcripts).
- `status: fail` → **surface it.** Transcript files exist but zero turns priced: the
  reader is silently degraded, most likely a transcript-format change. Every economics
  figure reads as zero until it is fixed.
<!-- @hm:/economics-doctor -->

<!-- @hm:delivery-metrics -->
## Delivery-metrics narrative (1-2 lines, no score impact)

```bash
!uv run --with $HOME/harness-maker hm delivery_metrics trend --root . --limit 1
```

Surface ONE narrative line from the newest snapshot: CFR as raw `failed/total`
counts (+unit, or the `not_applicable` reason verbatim) and churn as
`churned/added` LOC (+`partial` flag or its `not_applicable` reason), with the
baseline deltas. Narrative-only by design — the readiness score is never
affected (Goodhart guard, SPEC Non-Goal 3). **Empty ledger (the feature has
never been run here) → print nothing but a one-line suggestion to run
`/hm:metrics` once** — the narrative only appears once there is data.
<!-- @hm:/delivery-metrics -->
## Per-item structured question (ADR-001 hard rule)

For each unresolved item across the two layers, present:
- **structural**: file-level remediation suggestion (e.g. "add docs/adr/").
- **personalization**: each ADR-011 ActionItem with priority P0/P1.

Use `AskQuestion` (Cursor) or `AskUserQuestion` (Claude Code) per item with three options:
- `accept` → apply the suggested change
- `reject` → record decision, leave alone
- `defer` → keep in queue

Append every answer to `.claude/observability/health/decisions.jsonl`.

Never auto-apply. Never batch into yes/no over multiple items.

## Autoloop behavior

Stop after writing the dashboard. The structured-question step requires
interactive mode; autoloop must not synthesize a default answer.

<!-- @hm:user:extensions -->
<!-- Project-specific /hm:health hooks. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
