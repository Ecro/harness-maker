---
type: baseline-delta
task_slug: ai-native-sdlc-vs-intent-world
created: 2026-09-19
---

# BASELINE-DELTA — ai-native-sdlc-vs-intent-world

## 1. Pre-change pin (ADR-007) — captured before any source edit

Per-arm sha256 of the rendered `plan`, `review`, `spec`, `execute`, `wrapup` and `loop`
commands, plus the lengths of the four commands this task grows. Computed in this worktree at
commit 7009771d (base `main` fb8bfaca) with the recipe of
`tests/structural/test_mission_context_loop_invariance._live`.

`tests/structural/test_ai_native_sdlc_invariance.py` parses the fenced block below:
- `plan` and `review` must stay byte-identical (Contract Boundaries);
- `spec`, `execute`, `wrapup` and `loop` may grow by at most the PLAN's
  `surface_allowance.commands.<name>` per arm while it is declared, and are re-pinned at Phase 5.

> **Re-pinned at Phase 5 (retirement):** the `spec`, `execute`, `wrapup` and `loop` hashes and
> lengths below are the final render (section 3 gives the growth over the pre-change values).
> `plan` and `review` are the original pre-change values and did not move. From here all six
> commands are byte-identical to this pin, with zero allowance.

```json
{
 "arms": {
  "ask@flag_off": {
   "execute": "ed144e30840b1437ed91d54f2b210f1ef7df6832eaeb94bac86e0d344f04dc38",
   "loop": "203c41e2f1daeb127e560c7c8d620884a90e3e729bdaf6605086f0b56fcd0e67",
   "plan": "81dc8c79079a62b8db32166407a2076c5219585899b6ccf6d3242e0a48cc0322",
   "review": "b5b33953cc7253db83d5409e7337ea3ef164282002667c479499c243750301b7",
   "spec": "d897025c414daa4f56be2ad70c35c315e1e7facb15002fd88bd2754c5a1e0351",
   "wrapup": "c4ca088bd965b3d53b21cc73a8c0930d993715a93e3751df422adfeafa0ff3ee"
  },
  "ask@flag_on": {
   "execute": "f2df32974275560486b585a03d38893945dc4c8d9429d4efca234186332d23bb",
   "loop": "0ca73e8966e60e5214b977eac905aedda4978532b1fbb186d04d43b19f24db26",
   "plan": "69da1e3c7309bf833ba2217a0a7b6bbd99d514de9199460aba0a6d7ac8b5af8d",
   "review": "487f9494974bb2484c4a63f5214db68d3105b31e0f66cb825225b4cd7b054b91",
   "spec": "dd1aebd8a211b62a0124658b0548a754ca7f6075e7be4a43cc3b7a7482ea3c8b",
   "wrapup": "be472377d74bc6545359b02f3ac75da55abff216b354bd37dc13dfaef2130702"
  },
  "auto_safe@block": {
   "execute": "e1deab7bfa969339a356ac40122d344d7b5beb3b6eee579aec6e35e39fd926e5",
   "loop": "e7afd6205c75ab81ec6874fc0cadc0a93677906d6a807819f13935fd16afc059",
   "plan": "4df698bdecbb917cc5192f1e421b79cee7647351464a8adcb9ee510711746131",
   "review": "4a6bf81db83003f7a5b9362b9842ad01372c3d93bbd399dfd6df8ac28d83ac53",
   "spec": "adfe119f457a5eb89ca5c8dad08f21298cae15aa76121a6248b073d68c04738d",
   "wrapup": "5b6045f7c7615beaab16b6d5a8c261b225356d9274d80b375a409c595cfb18c1"
  },
  "auto_safe@warn": {
   "execute": "e1deab7bfa969339a356ac40122d344d7b5beb3b6eee579aec6e35e39fd926e5",
   "loop": "e7afd6205c75ab81ec6874fc0cadc0a93677906d6a807819f13935fd16afc059",
   "plan": "e879ede63d1b4e4b83f971f826256d81d6b45791fb6fe50fe47e9d597fe17284",
   "review": "4497f48460432496f9234ce4632f2e179d4bfb0e757fcad9d17edae9c9c747c2",
   "spec": "8cb5899082814111169886bf3de3f769b5008e8d8cdf3f349727626d2b22f4b6",
   "wrapup": "b083b5000058b625e0c33351afed8b90ce2e9581e22480fa0d53cb2e7e481d3f"
  }
 },
 "harness_maker_version": "0.57.1",
 "len": {
  "ask@flag_off": {
   "execute": 45718,
   "loop": 45907,
   "spec": 33358,
   "wrapup": 43977
  },
  "ask@flag_on": {
   "execute": 50383,
   "loop": 51289,
   "spec": 34664,
   "wrapup": 49316
  },
  "auto_safe@block": {
   "execute": 51627,
   "loop": 51265,
   "spec": 35251,
   "wrapup": 52551
  },
  "auto_safe@warn": {
   "execute": 51627,
   "loop": 51265,
   "spec": 35251,
   "wrapup": 54105
  }
 }
}
```

## 2. Inherited fold

None: `mission-context-loop` retired its allowance before landing (its PLAN carries no
`surface_allowance`), so this task starts from a baseline with zero open allowances.

## 3. This task's growth

Declared in the PLAN's `surface_allowance` in the same change as the growth (Phase 4, ADR-007).
Measured with `_surface_baseline.measure_surface` against the committed baseline (the
aggregate figures are quoted in the Phase 5 retirement section, not here — quoting the
inherited aggregate would make this document claim ownership of a baseline it did not freeze):

| Variant | Command | chars | round trips | Why |
|---|---|---|---|---|
| claude | spec | +4497 | +1 | `spec` joins the judgment-gated partial (its gate prose replaces the gate-first Step 1), Step 0 `--exempt` stamp, "Approve this SPEC and end interview", irreversible-decision rule, 🔒 section, v3 schema note + example, Step 5 stamp |
| claude | execute | +1122 | 0 | Phase C escalation rule for an unlisted irreversible decision |
| claude | wrapup | +928 (+938 ask@flag_off) | +1 | approval-status check + approve-or-keep before `wrapup_land` |
| claude | loop | +418 (0 when isolation is off) | 0 | `[finalize] hold:` means HALT, not converge |
| codex | hm-spec / hm-execute / hm-wrapup / hm-loop | +2707 / +1122 / +959 / +418 | +2 / 0 / +1 / 0 | same content, Codex call forms |
| — | aggregate | claude +6965, codex +5206 | | |

`plan` and `review` are byte-identical to the §1 pin in every arm.

### 3.1 Retirement (Phase 5, ADR-007) — attribution of every moved key

Owning phase: **Phase 4** grew the surface; **Phase 5** re-froze `tests/structural/surface_baseline.json`
and deleted the PLAN's `surface_allowance` (zero allowances remain). This document owns the new
baseline under ADR-010: the freeze is attributed here, row by row, rather than recomputed to
absorb the growth — `ratchet-rebaselined-by-its-own-subject` is avoided because every row below
names the Phase 4 edit that produced it, and the numbers were measured before the freeze.

Aggregate direction: **larger** — claude 437 732 → **444 697** (+6 965), codex 372 826 →
**378 032** (+5 206).

| Key | Before | After | Attribution |
|---|---|---|---|
| claude `spec` chars / round trips | 30 754 / 6 | 35 251 / 7 | judgment-gated partial prose + approve/exempt stamps + irreversible-decision rule + 🔒 section + v3 schema; +2 approve calls, −1 `gate-blocked` |
| claude `execute` chars | 50 505 | 51 627 | Phase C escalation rule for an unlisted irreversible decision |
| claude `wrapup` chars / round trips | 51 623 / 32 | 52 551 / 33 | `approval-status` check + approve-or-keep before `wrapup_land` |
| claude `loop` chars | 50 847 | 51 265 | `[finalize] hold:` means HALT, not converge |
| codex `hm-spec` chars / round trips | 28 026 / 5 | 30 733 / 7 | same as `spec`, Codex call forms |
| codex `hm-execute` chars | 49 379 | 50 501 | same as `execute` |
| codex `hm-wrapup` chars / round trips | 49 847 / 30 | 50 806 / 31 | same as `wrapup` |
| codex `hm-loop` chars | 49 755 | 50 173 | same as `loop` |
| `aggregate_chars` | 437 732 / 372 826 | 444 697 / 378 032 | sum of the rows above |
| `render_sha` | e5eea25f | fb8bfaca | merge-base of `hm/ai-native-sdlc-vs-intent-world` — the generator refuses a task-branch HEAD |
| `payload_digest` | 3c09322d… | ea3a80b1… | recomputed from the new surface by the committed generator |

Per-command ratchet (`tests/structural/test_command_size_budget.py::_ATOMIC_RATCHET`):
`execute` 49 290 → 50 383 and `spec` 32 114 → 34 664 (pinned-install-ref render), same edits.
