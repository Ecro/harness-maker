---
type: plan
task_slug: autopilot-stop-gate
status: in-progress
created: 2026-10-15
tags: [harness-maker, plan, autopilot, hooks, stop-hook]
lane: full
spec: specs/SPEC-autopilot-stop-gate.md
adrs: 8
summary: "loop_gate --mode stop-hook refuses once when this turn authorized a stage it never invoked"
---

# PLAN: autopilot stop gate

Lane **full** (from the SPEC). One branch added to `hooks/loop_gate._stop_hook`; no render,
settings, CLI or ledger-format change.

## Phases

1. **Fixtures.** Byte-copy the 35 eval-2 hm ledgers and reduce each transcript to the fields the
   gate reads (ADR-007) under `tests/fixtures/autopilot_stop_gate/<cell>/`, plus a `manifest.json`
   with the source sha256 of each file.
2. **RED.** `tests/unit/test_autopilot_stop_gate.py`: AC-001 golden table (22 rows), AC-002
   differential against `git show df070f6c:src/harness_maker/hooks/loop_gate.py`, AC-003 replay
   (end states + every Skill-call cut), AC-004 reason substrings. Confirm each fails for the
   missing branch, not for a fixture bug.
3. **GREEN.** Implement the branch in `loop_gate.py`.
4. **Gate + docs.** ruff, ruff format, mypy --strict, full pytest; CHANGELOG Unreleased entry.

## ADRs (locked)

- **ADR-001 — placement and precedence.** The check runs inside `_stop_hook` after both loop-marker
  checks and only when neither blocked. `stop_hook_active` stays the first check and
  `is_claude_copy_in_cursor` stays first in `main()`.
- **ADR-002 — an id is required.** The gate runs only when the payload carries a non-empty
  `session_id` (sanitized, the same key `autopilot_autoarm` writes). An id-less payload shares the
  degraded marker, so ownership cannot be shown; it fails open. Claude Code always sends an id.
- **ADR-003 — which authorization.** For each stage in `marker.pipeline`,
  `find_unconfirmed_authorization(to=stage, since=marker.created_at)` (the collapse pairing,
  no second implementation). Each pending row is tested against the transcript; when several would
  refuse, the latest `ts` is named.
- **ADR-004 — transcript reading.** `isSidechain` records are ignored. A record counts only when
  its `timestamp` parses and is strictly after the row's `ts` (both as UTC instants). "Started" is
  an assistant `tool_use` named `Skill` with `input.skill == "hm:<stage>"` (a leading `/` is
  tolerated). "A later turn" is any `type: user` record that is not `isMeta` and whose content is
  not a non-empty list made only of `tool_result` blocks; ambiguity reads as a later turn, which
  fails open. A transcript with no `type: user|assistant` record carrying a `message` dict fails
  open with a warn line.
- **ADR-005 — fail open, one line.** Any exception in the check, an unreadable/absent transcript,
  or an authorization row whose `ts` does not parse: exit 0, no stdout, exactly one
  `[loop-gate] warn:` line on stderr.
- **ADR-006 — peers.** A peer is any file `other_keyed_markers` returns that parses as an
  `AutopilotMarker`, carries a `claude_session_id` and is `fresh`. Any peer → fail open, silently
  (a peer is a normal state, not an error).
- **ADR-007 — fixtures.** Ledgers are byte copies. Transcripts keep only `user` records and the
  `assistant` records that carry a `Skill` tool_use — the only records whose content can change the
  decision. Kept fields: `type`, `timestamp`, `isMeta`/`isSidechain` (when true), `origin.kind`,
  a `toolUseResult: true` marker, content block `type`s, and for `Skill` only `input.skill`
  (`args`, the task slug, is text and is dropped). String content becomes `""`. The reducer was a
  one-off and is not committed; `manifest.json` records the source hashes.
- **ADR-008 — reason delivery.** The block prints `{"decision": "block", "reason": …}` on stdout
  and exits 2, as the SPEC says. With exit 2 Claude Code reads the reason from **stderr**, so the
  autopilot block also writes the reason there. The loop-marker block is left byte-for-byte as it
  is (AC-002); its stdout-only reason is a pre-existing question outside this SPEC. `now` is a
  keyword-only parameter on `_stop_hook` so the 18 h freshness window is testable on fixed dates.
