# Privacy

> **TL;DR:** harness-maker writes telemetry **only to your local disk** under `.claude/observability/` inside your project. Nothing is transmitted off your machine by this tool. There is no opt-out env var (see ADR-004 in `work-docs/PLAN-oss-readiness-audit.md`); you control telemetry by deleting the files. A unit test (`tests/unit/test_privacy_doc_schema.py`) fails any PR that adds a telemetry field without updating this document.

## What is recorded

harness-maker writes four kinds of JSONL files under your project's `.claude/observability/` directory:

| File | Schema source | Purpose |
|---|---|---|
| `metrics-{YYYY-MM-DD}.jsonl` | [`telemetry.py`](src/harness_maker/telemetry.py) `_build_entry` | Per-tool-use + per-stop hook output. Powers cache-diagnostics, cost dashboards, and the ai-readiness rubric's "cadence" layer. Daily rotation. |
| `adaptive/overrides.jsonl` | [`telemetry.py`](src/harness_maker/telemetry.py) `OverrideRecord` | One row per axis-level edit to `harness.yaml` (manual override of an interview default). Feeds `/hm:personalization-audit`. |
| `review-{YYYY-MM-DD}.jsonl` | [`review_telemetry.py`](src/harness_maker/review_telemetry.py) `ReviewTelemetryRecord` | One row per `/hm:review` iteration. Records reviewer counts, verifier drop rate, grade transitions. Daily rotation. |
| `silent-intent-miss-{slug}.jsonl` | [`observability/intent_miss.py`](src/harness_maker/observability/intent_miss.py) `IntentMissEvent` | One row when the inequality gate's LLM-inference common-ground answer is later contradicted (slot was wrongly skipped). |

## Where it's stored

```
<your-project>/
└── .claude/
    └── observability/
        ├── metrics-2026-05-19.jsonl
        ├── metrics-2026-05-18.jsonl       # daily rotation
        ├── adaptive/
        │   └── overrides.jsonl
        ├── review-2026-05-19.jsonl
        └── silent-intent-miss-<slug>.jsonl
```

All paths are inside your project root (or `CLAUDE_PROJECT_DIR` / `CURSOR_PROJECT_DIR` if set). The telemetry hook resolves the project directory via an env-var-first chain documented in [`telemetry.py`](src/harness_maker/telemetry.py) lines 194–204 and explicitly rejects the bare stdin `cwd` field (which was a path-traversal primitive prior to 0.7.1).

## JSON schemas (every field documented)

### `metrics-{YYYY-MM-DD}.jsonl` — common fields (all events)

| Field | Type | Description |
|---|---|---|
| `timestamp` | string | ISO-8601 UTC timestamp |
| `span_id` | string | 16-char hex random per-event |
| `trace_id` | string | Source `conversation_id` (Claude Code) or random hex |
| `event` | string | One of `post_tool_use`, `stop`, `unknown` |

### `metrics-{YYYY-MM-DD}.jsonl` — `post_tool_use` event additional fields

> **Retired in schema 2:** `input_tokens`, `output_tokens`, `cache_read_tokens`,
> `cache_creation_tokens` and `cost_usd` are no longer written. The Claude Code
> `PostToolUse` payload carries no `usage` object, so every one of them was
> structurally zero on every line ever recorded. Token accounting now reads Claude
> Code's own session transcripts (see `harness_maker.economics`); nothing new is
> written to disk for it and nothing leaves the machine.

| Field | Type | Description |
|---|---|---|
| `tool_name` | string | Name of the tool that just ran (e.g., `Read`, `Bash`) |
| `metrics_schema_version` | int | Entry-shape version (`2` since the token-field retirement). An **absent** key means schema 1. |
| `tool_input` | string (optional) | Whitelist-projected, value-redacted, 256-char-capped JSON serialization of the tool input. Path traversal–free per the 0.7.1 ADR-107 hardening. |

### `metrics-{YYYY-MM-DD}.jsonl` — `stop` event additional fields

| Field | Type | Description |
|---|---|---|
| `status` | string \| null | Cursor agent stop status |
| `loop_count` | int \| null | Loop count if reported |
| `duration_ms` | int \| null | Agent turn duration in milliseconds |
| `model` | string \| null | Model identifier used in this turn |
| `conversation_id` | string \| null | Conversation correlator |

### `adaptive/overrides.jsonl` — `OverrideRecord`

| Field | Type | Description |
|---|---|---|
| `schema_version` | int | Schema version (currently 1) |
| `ts` | string | ISO-8601 UTC timestamp |
| `axis_path` | string | Dot-notation path of the harness.yaml axis being overridden (e.g., `reviewers.grade_threshold`) |
| `before` | any | Previous value (may be null on first-time set) |
| `after` | any | New value |
| `source` | string | One of `configure-exit`, `session-start`, `git-fallback` (`OverrideSource` Literal in `telemetry.py`) |
| `reason` | string | Free-form note (default empty string) |

### `review-{YYYY-MM-DD}.jsonl` — `ReviewTelemetryRecord`

| Field | Type | Description |
|---|---|---|
| `ts` | string | ISO-8601 UTC timestamp (CLI auto-stamps if omitted) |
| `slug` | string | Task slug (max 200 chars) |
| `round` | int | Review iteration number (≥ 1) |
| `pass1_n` | int | Total findings from Pass 1 (redacted-context review) |
| `verifier_kept_n` | int \| null | Pass 1.5 verifier KEEPs. **null** since ADR-001 removed the dispatch — null means the verifier did not run, which is a different fact from "ran and kept nothing". Rows written before the removal keep their integers. |
| `verifier_dropped_n` | int \| null | Pass 1.5 verifier DROPs. Same nullability, and both fields are both-or-neither. |
| `verifier_false_drop_n` | int \| null | Labeled-fixture only — verifier dropped a real bug |
| `verifier_false_keep_n` | int \| null | Labeled-fixture only — verifier kept a false positive |
| `fixture_label` | string \| null | Labeled-fixture identifier (null on real runs) |
| `pass2_kept_n` | int | Findings surviving Pass 2 (full-context review) |
| `consensus_passed_n` | int | Findings surviving consensus filter |
| `wall_time_ms` | int | Wall-clock time of the review round |
| `build_break_count` | int | How many auto-fixes broke the build |
| `auto_fix_reverted_n` | int | How many auto-fixes were reverted because of build break |
| `fallback` | string \| null | Set only when the verifier model was unavailable and a fallback path ran |

<!-- @hm:privacy:review-telemetry-measure-c -->

Measure C (PLAN-review-round-inflation). These four are `null` rather than `0` when unmeasured, so a row written by a harness version that predates them stays distinguishable from one that measured zero:

| Field | Type | Description |
|---|---|---|
| `terminal` | bool \| null | Discriminator: `null` = never measured, `false` = a non-terminal round, `true` = the single end-of-review row that carries the three counters below |
| `unreviewed_fix_count` | int \| null | Fixes applied in the terminal round, which the loop never re-reviewed |
| `regression_attributed_n` | int \| null | Distinct findings attributed to a previous round's fix |
| `attribution_unknown_n` | int \| null | Distinct findings whose origin could not be attributed either way |
| `lenses_exercised` | list[str] \| null | Which mandatory review lenses delivered a result this round. Lens **ids** only (`design`, `functionality`, `robustness`, `consistency`, `security`, `concurrency`, `tests`) — never finding text. `[]` means every dispatch failed; `null` means a harness version that predates the field |
| `confirm_pass_ran` | bool \| null | Whether a confirmation pass ran over the frozen diff |
| `confirm_pass_new_severe_n` | int \| null | Count of new severe findings the confirmation pass surfaced. Present only when `confirm_pass_ran` is true |
| `churn_ratio` | float \| null | How much of the most-churned file this repair round rewrote, 0–1. `null` = no file was measurable (all binary/deleted), or a harness version that predates the field |
| `churn_max_path` | str \| null | Repo-**relative** path of the file that ratio came from — a path, never file content. Stays on disk with the rest of the row |
| `churn_measured_n` | int \| null | How many touched files contributed to the ratio |
| `churn_excluded_n` | int \| null | How many were excluded (binary, deleted, empty post-tree) |
| `disposition_counts` | dict[str, int] \| null | How many findings this round landed on each of the four dispositions (`accepted`, `rejected`, `duplicate`, `unresolved`). **Counts keyed by a closed vocabulary — never a finding, a file path, a summary or an authority citation.** `{}` = a round with no findings; `null` = a harness version that predates the field |

<!-- @hm:/privacy:review-telemetry-measure-c -->

### `silent-intent-miss-{slug}.jsonl` — `IntentMissEvent`

| Field | Type | Description |
|---|---|---|
| `slot` | string | The interview slot identifier that was wrongly skipped |
| `trigger` | string | What surfaced the miss: `review-mismatch`, `session-reopen` (`Trigger` Literal in `observability/intent_miss.py`) |
| `original_mark_source` | string | Where the original "common-ground" mark came from (e.g., `llm-inference:0.97`) |
| `original_mark_confidence` | float | The confidence value the inference recorded |
| `detected_at` | string | ISO-8601 UTC timestamp |
| `notes` | string | Free-form context (default empty) |

<!-- @hm:privacy:feedback-module -->
## Optional feedback module (opt-in, default off)

harness-maker ships an opt-in maintainer-dogfooding feedback module
(`feedback.enabled` in `harness.yaml`, defaults to `false`; togglable only
via the `/hm:configure` interview — no CLI flag, no env var). When `false`,
the module is a dead Jinja branch — **zero file IO, zero token cost, zero
behavior change**. The "Nothing is transmitted off your machine by this tool"
guarantee above remains literally true.

When toggled on, dispatcher wrappers emit a Jinja-conditional block asking
the current turn's LLM to inspect local telemetry, decide whether a
HARNESS-SELF issue occurred (hook error, silent-intent-miss, /hm:review
build-break, plan-validator hang, dispatcher render regression), and if so
write a draft to `.claude/observability/feedback/{YYYY-MM-DD}-{slug}-{hash}.md`
plus print a one-line footer with the exact `gh issue create --web --body-file`
command. The footer is the only network call — and it is the maintainer
invoking the `gh` CLI from their own terminal, not harness-maker.

### `FeedbackDraft` schema (5 top-level fields)

| Field | Type | Description |
|---|---|---|
| `harness_maker_version` | string | Output of `harness-maker --version` |
| `ide` | string | One of `claude-code`, `cursor`, `codex` |
| `os` | string | `platform.system()` + release |
| `stage` | string | Atomic stage name (e.g., `research`, `execute`) |
| `task_slug` | string | Task identifier from PLAN frontmatter |
| `trigger_signal` | object (`TriggerSignal`) | Numeric evidence — see schema below |
| `error_message` | string \| null | Optional, ≤256 chars, run through `_SECRET_PATTERNS` |
| `file_paths` | list[string] | Optional, **hard-rejected** unless every entry starts with `.claude/` |

### `TriggerSignal` nested schema (3 fields)

| Field | Type | Description |
|---|---|---|
| `id` | string | Signal type, e.g. `hook-error`, `silent-intent-miss`, `build-break` |
| `count` | int (≥0) | Occurrence count |
| `duration_ms` | int (≥0) \| null | Optional latency evidence |

### Dedup

Filename hash is `sha256(trigger_signal_id, task_slug, YYYY-MM-DD)[:16]` —
identical inputs on the same day silently return the existing path; next-day
re-emergence produces a fresh draft.
<!-- @hm:/privacy:feedback-module -->

## What is **never** recorded

- File contents you read or edit. The `tool_input` field captures only the keys, not file bodies.
- Your messages or model output. Tokens are counted but content is not stored by harness-maker (Claude Code / Cursor itself may store transcripts — that's a separate matter).
- Credentials, API keys, environment variables. The `_redact_value` and `_project_tool_input` functions in `telemetry.py` explicitly redact secret-shaped values before write.
- Your personal information. Anonymous identifiers (`span_id`, `trace_id`) are random per-run.

## Where it is **never** sent

Nowhere. harness-maker does not make outbound network requests to send telemetry. The crawler that fetches Anthropic blog posts / GitHub releases / arXiv / OSV CVEs (anti-rot pipeline) does make outbound HTTPS requests, but those are for *reading* upstream content into your local cache — they do not include any of your telemetry as request bodies or query parameters.

You can verify this with:

```bash
# Search the source for any HTTP POST / PUT / send that includes telemetry data:
rg -n "post|put|requests\.send|httpx\.send|aiohttp" src/harness_maker/telemetry.py src/harness_maker/review_telemetry.py src/harness_maker/observability/
# Expect: no matches.
```

## How to disable

There is no env var to disable telemetry (deliberate — see ADR-004). To opt out:

```bash
# Delete the observability directory; the hook continues to fire but write failures
# are caught and logged to stderr (won't break your workflow).
rm -rf .claude/observability/
```

Or remove the telemetry hook entirely from `.claude/hooks/hooks.json` (and `.cursor/hooks.json` if you use Cursor).

If you do not want any local files written, comment out or delete the `hooks` registration. The rest of harness-maker still functions; you lose the cache-diagnostics layer of the ai-readiness rubric and the personalization-audit signal.

## Retention

- `metrics-*.jsonl` and `review-*.jsonl` rotate daily — old files are not auto-pruned. You decide retention by deleting files.
- `adaptive/overrides.jsonl` and `silent-intent-miss-*.jsonl` are append-only single files; same deletion-controlled retention.

## Schema drift defense

The unit test [`tests/unit/test_privacy_doc_schema.py`](tests/unit/test_privacy_doc_schema.py) AST-walks the telemetry source files and asserts every field defined on a telemetry-record model is documented above. Adding a field without updating this file will fail PR CI.

## Reporting a privacy concern

If you believe harness-maker is writing or transmitting data not documented above, file a security report via the [SECURITY policy](SECURITY.md) — a documented-vs-actual mismatch is a P0 issue per the P0 definition.
