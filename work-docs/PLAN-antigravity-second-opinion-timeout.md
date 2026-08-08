---
type: plan
task_slug: antigravity-second-opinion-timeout
status: complete
created: 2026-08-08
tags: [harness-maker, plan, second-opinion, antigravity, agy, observability]
research_doc: "[[RESEARCH-antigravity-second-opinion-timeout]]"
interview_rounds: 4
adrs: 7
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Cut antigravity loss 39.2%→~2% by retiring the Pro(High) default and adopting agy's real JSON schema path"
---

# PLAN — antigravity second-opinion timeout

## 🎯 Executive Summary

**TL;DR** — antigravity's 39.2 % second-opinion loss rate has two independent
causes, both measured, both fixable in one change set: the shipped model default
(`Gemini 3.1 Pro (High)`) cannot finish a real review inside the 240 s budget,
and the invoker parses `agy`'s free-form stdout when `agy` has had a real
structured-output mode all along.

**What** — Retire the `Gemini 3.1 Pro (High)` shipped default **at all five
shipped sites** in favour of `Gemini 3.6 Flash (High)`; invoke `agy` with
`--output-format json --json-schema` against the packaged finding schema and read
its `structured_output` under a four-case decision table; record `duration_s` on
every per-invocation ledger row; add a Python-owned budget-proximity advisory to
the health smoke; and correct the "agy has NO output schema" claim wherever it is
asserted.

**Why** — Measured on `.claude/observability/second-opinion.jsonl` (112 rows) and
by controlled probe on 2026-08-08:

| Model | 41 KB prompt | Outcome |
|---|---|---|
| `Gemini 3.1 Pro (High)` (shipped default) | 4 m 04 s | timeout, exit 1, 0 bytes |
| `Gemini 3.6 Flash (High)` (chosen) | 27–28 s ×3 | `structured_output` present 3/3, 3–4 findings |
| `Gemini 3.6 Flash (Medium)` | 14 s | valid, incl. one `critical` |
| `Gemini 3.5 Flash (High)` | 18 s | SUCCESS but **no `structured_output` key** |

Antigravity's 20 losses: **8 timeout**, **9 parse**, **2 quota** (out of scope —
already reported correctly), **1 legacy** vacuous-invocation row (fixed upstream).
ADR-001 addresses the first group and ADR-002 the second. **The 8 timeout rows
were not individually re-attributed** — that mapping is inference, and ADR-004's
duration field is what will confirm or refute it.

**Key decisions** — ADR-001 (model tier), ADR-002 (structured output + four-case
chain), ADR-003 (shipped defaults only, five sites), ADR-004 (duration on every
per-invocation row), ADR-005 (Python-owned health advisory), ADR-006 (correct the
schema claim).

**Estimated impact** — antigravity loss 39.2 % → expected ~2 % (quota only),
matching codex's measured 2.1 %. The antigravity leg's wall-clock drops from up
to 300 s (timeout path) to ~28 s.

## 🚫 Non-Goals

Promoted here so a later phase cannot reopen them without a new ADR:

1. **Raising `--print-timeout` / `AGY_TIMEOUT_S`.** Rejected in ADR-001.
2. **A retry-at-a-faster-tier branch.** Gated out in interview Round 2 on EIG.
3. **Migrating existing pinned `harness.yaml` values.** Rejected in ADR-003.
4. **Quota exhaustion (2 losses).** Already reported accurately by the CLI and
   surfaced verbatim in `skip_reason`; nothing to fix.

## 📚 Prior Work

- [[RESEARCH-antigravity-second-opinion-timeout]] — the measurement this PLAN acts on.
- [[PLAN-second-opinion-invocation-and-slug-cap]] — moved both CLI calls into
  `second_opinion_invoke`. Commit `b80c3c2c` landed 2026-07-25; the first timeout
  row is 2026-07-27. The timeouts are the visible cost of the invocation finally
  delivering a real prompt. That PLAN also records the `stage`-gains-`"health"`
  incident: widening a Python `Literal` **and** the shipped JSON enum, where a
  parity test compared names and was invariant over enum values. ADR-004 is the
  same dual-surface shape and is scoped accordingly.
- `[[fail:tooling]] agy-print-flag-swallows-next-flag` — root-cause class: *an
  external CLI's flag arity assumed rather than read.* **ADR-002 is that class
  caught a second time**: six sites assert "agy has NO `--output-schema`", which
  is true as spelled and false as understood.
- `[[wiki:architecture]] second-opinion-invoker` — *"an external contract a
  rendered prompt asks the model to execute must be exercisable by a test, or it
  will be wrong and report success."* ADR-005 is scoped to obey this: the
  threshold lives in Python, not in template prose.
- **`.claude/memory/session/2026-07-09.md` — this is the second time.** A prior
  session hit the same symptom and concluded: *"not a bug: `Gemini 3.1 Pro (High)`
  is a high-reasoning-effort tier whose tail latency exceeded the … cap on one
  call (reproduced p50 ~28s, so it was a tail event, not systemic)."* The remedy
  applied then was to **raise `--print-timeout` 120s → 240s**. Two things follow.
  First, that session's own p50 measurement (~28 s) is indistinguishable from what
  `Gemini 3.6 Flash (High)` delivers today — so the tier was already known to be
  the variable, and the diagnosis stopped one step short. Second, **raising the
  timeout has now been tried and did not hold**: eight timeout rows accumulated
  after that change, which is the empirical case behind Non-Goal 1 and ADR-001's
  rejection of a further increase. A p50 that fits the budget while the tail does
  not is a reason to change the tail, not to widen the window.
- CLAUDE.md absent-case rule (`[fail:design]`, count 8) — a feature activating on
  an optional field must define the absent case. `structured_output` is exactly
  such a field, which is why ADR-002's fallback is mandatory, not defensive.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Model tier | Dependencies | Which model replaces `Gemini 3.1 Pro (High)`? | 3.6 Flash (High) / 3.6 Flash (Medium) / 3.1 Pro (Low) / Pro+fallback | **3.6 Flash (High)** | 28 s, 3–4 findings, 12 % of budget | ADR-001 |
| 2 | Contract shape | Contract | Adopt `--output-format json --json-schema` in this PLAN? | same PLAN / separate / adopt but keep fail-closed | **Same PLAN** | Covers 17 of 20 losses in one cycle | ADR-002 |
| 3 | Scope boundaries | Scope | Shipped default, or this project's harness.yaml only? | shipped / project-local / both+migration | **Shipped default** | Explicit user values preserved | ADR-003 |
| 4 | Observability | Observability | Make the health smoke realistically sized? | record elapsed + warn / realistic prompt / leave as-is | **Record elapsed + warn** | Zero added cost | ADR-005 |
| 5 | Observability | Observability | How much envelope telemetry lands in the ledger? | duration every call / health only / +status+usage / end | **Duration every call** | Makes budget creep visible | ADR-004 |
| 6 | Failure handling | Failure handling | `structured_output` present but failing `validate_payload`? | fail-closed / fall back to `response` / fall back + ledger tag | **Fail-closed** | A broken schema contract must stay visible | ADR-002 |
| 7 | Contract shape | Contract | Antigravity's schema source + resolution-failure behaviour? | packaged always + no-schema argv on failure / packaged + skip / share codex key | **Packaged always, degrade to no-schema argv** | Must not create a new skip class | ADR-002 |
| 8 | Contract shape | Contract | `duration_s` vs the strict-mode schema invariant (the two are not simultaneously satisfiable) | narrow the glob + keep `required` exclusion / add to `required` / drop `additionalProperties:false` / abandon ADR-004 | **Narrow the glob, keep the exclusion** | Raised at `/hm:execute` before Phase 1 test authoring | ADR-007 |

Round 8 was opened during `/hm:execute`: `tests/unit/test_schema_strict_mode.py`
globs **every** `templates/schemas/*.json` and requires every property to appear
in `required`, which ADR-004 forbids for `duration_s`. Neither validator pass saw
it — pass 2 was given the ledger schema's shape but not the second test that
governs it. Surfaced rather than guessed, per this stage's under-specification
rule.

Rounds 6–7 were opened by the plan-validator's MAJOR_REVISION. Two further
candidates were gated out and recorded as decisions rather than rounds:

- *"Keep the fail-closed extractor as a fallback?"* — failed the **confidence**
  term (τ = 0.7): the probe produced the absent case, and CLAUDE.md's absent-case
  rule settles it. Locked in ADR-002.
- *"Retry a timeout at a faster tier?"* — failed the **EIG** term: at 28 s against
  a 240 s budget the branch would essentially never fire.

Corrections raised by the validator that were **factual, not choices** — the
five-site literal count, `readiness.py` not owning the smoke, and the shipped
ledger JSON Schema's `required` list — were applied directly rather than asked
about; they fail EIG (an error has one correct resolution).

## 📐 Architecture Decision Records

### ADR-001: Retire `Gemini 3.1 Pro (High)` as the shipped antigravity default
**Status:** Accepted (2026-08-08, via /hm:plan interview #1)
**Context:** The shipped default did not complete a real-sized second-opinion call
inside agy's 240 s `--print-timeout`: measured 4 m 04 s → timeout, exit 1, zero
output bytes, on a 41 KB prompt.
**Decision:** Make `Gemini 3.6 Flash (High)` the shipped default.
**Consequences:**
- ✅ 27–28 s across three runs — 12 % of budget, so the measured cold-start
  variance (15 s / 19 s / 117 s on a trivial prompt) no longer reaches the cap.
- ✅ Returned 3–4 findings on the prompt the old default returned nothing for.
- ⚠️ Lower single-call reasoning depth than a Pro tier. Accepted: one voice in a
  k-of-N pool with K fixed at 2, and Codex holds the deep slot.
- ⚠️ **Claim scope.** What is measured is that *Pro (High) is unsuitable as the
  shipped default for this workload at this budget* (n = 1 on one 41 KB prompt).
  The probe does not isolate tier from model family, reasoning level, prompt
  size, service load or cold start, and the 8 historical timeout rows were not
  re-attributed individually. The decision does not need the stronger claim.
**Rejected alternatives:**
- `Gemini 3.6 Flash (Medium)` — 14 s and did surface a `critical`, but High costs
  only 14 s more against a 240 s budget; nothing here pressures us to buy speed.
- `Gemini 3.1 Pro (Low)` — unmeasured. Choosing it repeats the mistake being fixed.
- Raise the timeout — the 4 m 04 s run produced **zero** output bytes, so nothing
  suggests it was near completion, and agy's own default `--print-timeout` is
  5 m, i.e. the harness already runs below the vendor default. It converts a loud
  recorded skip into a silent multi-minute stall.
- Pro(High) with a Flash fallback on timeout — pays the full 4 minutes first.
**Source:** Interview #1

### ADR-002: Use agy's real structured-output mode under an explicit four-case decision table
**Status:** Accepted (2026-08-08, via /hm:plan interviews #2, #6, #7)
**Context:** The invoker parses `agy`'s free-form stdout through
`codex_adapter.extract_antigravity_payload`, because six sites assert that "`agy`
has NO `--output-schema`". Probed 2026-08-08: `agy --output-format json
--json-schema <path>` is accepted and returns an envelope carrying a
schema-conformant `structured_output` — even where a prose reply would have
defeated the extractor. Verified separately that an **absolute base-root** schema
path works with cwd inside `.worktrees/<slug>/` (rc = 0, ~10 s, valid dict):
`--json-schema` is consumed by the agy CLI process's own argument handling, while
`--sandbox` governs the tools exposed to the model.
**Decision:**
1. **Schema source** — antigravity **always** uses the packaged finding schema,
   decoupled from `second_opinion.codex.output_schema_path` (CLAUDE.md documents
   that key as codex-specific). Do **not** reuse `resolve_schema_path` verbatim.
2. **Resolution failure** — if the packaged schema cannot be materialised, fall
   back to **today's no-schema argv** and proceed. It must never create a new
   `skipped` class in a PLAN whose purpose is cutting the skip rate.
3. **Payload acquisition — four cases, in order:**

   | # | Condition | Outcome |
   |---|---|---|
   | 1 | stdout is not parseable JSON | `failed`, reason names the envelope |
   | 2 | envelope `status` is not `SUCCESS` | `skipped`, carrying agy's own message |
   | 3a | `structured_output` is a dict, `validate_payload` accepts | use it |
   | 3b | `structured_output` is a dict, `validate_payload` rejects | **`failed` — fail-closed, no fall-through to `response`** |
   | 4a | `structured_output` absent or non-dict, `response` is a `str` | `extract_antigravity_payload(envelope["response"])` |
   | 4b | `structured_output` absent or non-dict, `response` missing or non-`str` | `failed` |

   These **six** numbered paths are the set referenced by the Data-flow diagram,
   Phase 2's exit criterion, and Success Criterion 3 — the same set at the same
   granularity in all four places.

4. `AGY_OUTPUT_CONTRACT` stays appended to the prompt — case 4 depends on it.
5. **Ownership flag** — whatever creates a temp schema returns a delete
   permission that must be appended to `owned` on the antigravity branch too.
**Consequences:**
- ✅ Removes the parse-failure class on the primary path; yields `status` and
  `duration_seconds` for free (ADR-004 consumes the latter).
- ✅ Reuses the schema Codex already enforces — one artifact, two models.
- ✅ Case 2 attributes an agy-side error to agy rather than to our parser, which
  is the misattribution the invoker's excerpt logic exists to prevent.
- ⚠️ `structured_output` is **not guaranteed**: absent on a `status: SUCCESS`
  reply from `Gemini 3.5 Flash (High)`, present 3/3 on the chosen model. 3-for-3
  is not an invariant, so case 4 is load-bearing.
- ⚠️ Case 3's fail-closed choice can discard a usable payload sitting in
  `response`. Accepted deliberately: a silently-tolerated schema violation is how
  this whole defect stayed hidden for weeks.
- ⚠️ Four branches to keep tested instead of one.
**Rejected alternatives:**
- Replace the extractor outright — makes an absent `structured_output` a hard
  failure; the absent case is already observed (CLAUDE.md count-8 class).
- Fall back to `response` on a schema-violating `structured_output` — higher
  recall, but a broken schema contract becomes invisible (Interview #6).
- Share `second_opinion.codex.output_schema_path` — a user's custom codex schema
  would silently change antigravity's contract (Interview #7).
- Skip on schema-resolution failure — creates a new loss class (Interview #7).
- Defer to a separate PLAN — leaves loss at ~23 % and needs a second cycle for a
  change sharing every test file with ADR-001.
**Source:** Interviews #2, #6, #7

### ADR-003: Change the shipped defaults at all five sites; never rewrite an explicit user value
**Status:** Accepted (2026-08-08, via /hm:plan interview #3; site count corrected by validator)
**Context:** The literal is **not** in two places. `rg -n "Gemini 3\.1 Pro" src/ README.md`
returns five shipped sites plus documentation:

| # | Site | Role |
|---|---|---|
| 1 | `src/harness_maker/models.py:467` | `AntigravityConfig.model` default |
| 2 | `src/harness_maker/second_opinion_invoke.py:28` | `DEFAULT_ANTIGRAVITY_MODEL` |
| 3 | `templates/harness-yaml/Production.yaml.j2:98` | **fresh-install render fallback** |
| 4 | `templates/harness-yaml/Side.yaml.j2:98` | **fresh-install render fallback** |
| 5 | `templates/agents/_partials/second_opinion_antigravity.md.j2:22` | recipe display default |
| — | `README.md:659` | documentation example |
| — | `models.py:459` | docstring illustration |

> **⚠️ Corrected during Phase 1 implementation.** This ADR originally said sites
> 3–4 are "what a fresh `/harness-maker:make` writes … fixing only 1–2 would ship
> a new harness still pinned to the timing-out model", and the plan-validator
> raised the site count on that reasoning. **The reasoning is wrong.**
> `InterviewAnswers.second_opinion` / the blueprint field are
> `second_opinion: SecondOpinionConfig` — **non-Optional with a default**
> (`models.py:980`, `:1179`) — so `config.second_opinion` is never falsy on a
> synthesized blueprint and those two `{% if config.second_opinion else … %}`
> branches are **unreachable**. A fresh install inherits site 1, the Python
> default. Proven by `test_fresh_install_harness_yaml_pins_the_flash_default`,
> which was written to assert the validator's claim and refuted it instead.
>
> The five-site change is still correct — a stale literal is a documentation lie
> the next reader will trust, and this PLAN's own ADR-006 exists because exactly
> that happened. But sites 3–4 were never load-bearing, and the corrected record
> matters more than the tidier story: the same "an untested half became the
> assertion" shape is what ADR-006 is cleaning up.
**Decision:** Change sites 1–5, `README.md:659`, and the `models.py:459`
docstring illustration. Do **not** add a migration pass rewriting an existing
`harness.yaml`'s explicit `model` value.
**Consequences:**
- ✅ New harnesses, and harnesses that never set the key, get the fix on
  `/harness-maker:make --update` — no schema migration (the field is free-text).
- ⚠️ Sites 3–5 are Jinja templates, so this pulls the six-gate template ratchet
  into Phase 1. Sized accordingly.
- ⚠️ A harness that *explicitly* pinned the old model keeps timing out until its
  owner edits one line. Accepted: silently overwriting an explicit user setting
  is the state-preservation violation CLAUDE.md checkpoint 1 exists for, and we
  cannot distinguish a deliberate pin from an old interview default.
- ⚠️ This repo's own `.claude/harness.yaml` carries the explicit old value, so it
  needs that one-line edit itself (Phase 6).
**Rejected alternatives:**
- Project-local edit only — leaves the shipped default a footgun for every other
  consumer and every fresh install.
- Default change plus auto-migration — cannot distinguish deliberate pins.
**Source:** Interview #3

### ADR-004: Record `duration_s` on every per-invocation ledger row
**Status:** Accepted (2026-08-08, via /hm:plan interview #5)
**Context:** A slow model is invisible until it crosses the timeout, at which
point the row says `skipped` and the elapsed time is gone. This degradation was
diagnosable only by re-probing the CLI by hand.
**Decision:** Add `duration_s: float | None = None` to `SecondOpinionRecord`,
populated on **per-invocation rows only** (`finding_ref == "n/a"`); per-finding
disposition rows carry `null`. Source it from the invoker's own wall-clock
measurement around `subprocess.run` — not from agy's envelope — so codex and
every exception branch are covered symmetrically. Emit a genuine `float` (`float(...)`) to normalise the stored type.

> **⚠️ Corrected during Phase 3.** This ADR claimed an `int` "would raise inside
> `_emit_row`, whose contract swallows exceptions". **Measured: it does not.**
> pydantic strict mode accepts `int` for a `float` field (lossless widening), so
> the cast never prevented the row-deletion it was credited with. The real
> row-deleting input class is a **non-numeric** value (a string, a `timedelta`),
> which does raise — that is what
> `test_duration_type_contract_under_strict_mode` now asserts. The cast stays
> (type normalisation is worth one call); the justification was wrong.
**Dual-surface obligation:** `templates/schemas/second-opinion-ledger.schema.json`
has `additionalProperties: false` and a `required` list naming all ten current
fields. Add `duration_s` to `properties` as `{"type": ["number", "null"]}` and
**not** to `required`. `tests/unit/test_codex_ledger.py::test_json_schema_matches_model_fields`
asserts `properties == model_fields`, so it forces the properties half — but it
does **not** inspect `required`, so the 112-row-breaking mistake would pass it.
**Consequences:**
- ✅ Budget creep becomes a trend rather than a cliff — the signal that would have
  caught this in July.
- ✅ Wall-clock covers codex symmetrically; the field is not antigravity-only.
- ⚠️ `additionalProperties: false` means the shipped schema rejects every *new*
  row until the properties half lands; the two halves must ship together.
- ⚠️ Rollback is not fully reachable: rows already written with `duration_s` are
  rejected by both validators after a code revert. The field is append-only in
  practice (see Phase 3 rollback).
**Rejected alternatives:**
- Also record `status`/`usage` — codex returns no equivalent; asymmetric rows for
  information nothing consumes yet.
- Health-smoke-only timing — leaves real review-call latency unmeasured.
- Source the value from agy's envelope — misses codex and every failure branch.
**Source:** Interview #5

### ADR-005: A Python-owned budget-proximity advisory on the health smoke
**Status:** Accepted (2026-08-08, via /hm:plan interview #4; ownership corrected by validator)
**Context:** The smoke prompt says "Do not analyse anything"; probed at 117 s
against a 240 s cap on the old default. Health was green at 49 % margin while
every real call failed. **`readiness.py` contains zero references to
`second_opinion_invoke`** — the per-model smoke lives in
`templates/commands/hm/health.md.j2` and is executed by the LLM.
**Decision:** Keep the trivial smoke. Put the threshold comparison **in Python**:
add `duration_s` to `invoke()`'s returned JSON (not only to the ledger row, so the
value crosses the process boundary), and have the invoker emit a machine-checkable
advisory line when a call's duration exceeds a fixed fraction of the timeout
budget. `health.md.j2` only **relays** it.
**Consequences:**
- ✅ Zero added cost per health run; this regression would have surfaced on
  2026-07-27 rather than 2026-08-08.
- ✅ Testable at/over/under the boundary against a Python function — not a
  render-grep, which is the failure mode four shipped silent-skip bugs share.
- ⚠️ Advisory-only, so it can be ignored. Deliberate: failing health on a latency
  heuristic would be a flaky gate.
- ⚠️ **A green smoke remains non-predictive of a 40 KB review prompt.** ADR-005
  narrows the gap; it does not close it. Phase 6 must therefore not use green
  health as sufficient evidence (see its exit criterion).
**Rejected alternatives:**
- A realistically-sized (~40 KB) smoke — proves the real path but costs 20–30 s
  per health run when healthy and 4 minutes when the tier is wrong.
- Threshold as prose in `health.md.j2` — an LLM-judged latency check with no
  execution surface; the exact class CLAUDE.md records four shipped bugs for.
- Leave health untouched — the same silent degradation class recurs.
**Source:** Interview #4

### ADR-006: Correct the "agy has NO output schema" claim at every assertion site
**Status:** Accepted (2026-08-08, derived from ADR-002)
**Context:** The false claim is asserted at **seven** sites:
`second_opinion_invoke.py`, `codex_adapter.py`,
`src/harness_maker/second_opinion_oracle.py:6` (*"antigravity has no CLI-level
schema at all"* — a different wording, which is why the first draft's `rg`
pattern would have passed with the claim intact),
`templates/agents/_partials/second_opinion_antigravity.md.j2`,
`templates/skills/second-opinion-gate/SKILL.md.j2`, project `CLAUDE.md`, and the
`[[wiki:architecture]] second-opinion-multi-model` entry in `.claude/memory/wiki.md`.
Left in place it is a standing instruction not to look for the flag — the
mechanism that hid this for the feature's whole lifetime. The oracle site matters
beyond documentation: it justifies a **security** control (external `file` paths
are unconstrained because no schema validates them), so the correction must
preserve that control while fixing the premise.
**Decision:** Correct every site in the same change set, stating what is true: the
flag is `--json-schema`, it requires `--output-format json`, and it yields a
best-effort `structured_output` that can be absent.
**Consequences:**
- ✅ Kills the load-bearing falsehood rather than routing around it.
- ⚠️ Two sites are Jinja templates → six-gate ratchet in Phase 5.
**Rejected alternatives:**
- Fix code, leave prose — the prose is what a future reader consults first.
**Source:** derived from Interview #2

### ADR-007: Scope the strict-mode schema invariant to codex `--output-schema` assets
**Status:** Accepted (2026-08-08, via /hm:execute interview #8 — discovered during implementation)
**Context:** ADR-004 requires `duration_s` in `properties` but **not** in
`required`, so the shipped schema stays truthful about the 112 rows written
before the field existed. But `tests/unit/test_schema_strict_mode.py` globs
**every** `templates/schemas/*.json` and asserts *every property appears in
`required`* — so ADR-004 as locked would fail that test. The two obligations are
not simultaneously satisfiable. Neither validator pass caught this: pass 2 was
told the ledger schema's shape but not that a second test governs it.
The invariant exists for a specific reason — `[fail:api]
codex-output-schema-strict-mode-required-completeness`, where OpenAI/Codex strict
structured-output mode rejected a vanilla JSON-Schema and every second-opinion
call silently fell back for weeks. That reason applies to
`second-opinion-finding.schema.json`, which **is** passed to `codex exec
--output-schema`. It does not apply to `second-opinion-ledger.schema.json`, which
[[PLAN-second-opinion-invocation-and-slug-cap]] records is *"rendered into **no**
user harness — its sole consumer is that parity test"*. The glob is over-reach.
**Decision:** Narrow the strict-mode parametrisation to schemas that are actually
used as a codex `--output-schema`, and add a test asserting the ledger schema is
excluded **deliberately** — so a future reader cannot mistake the exclusion for an
oversight, and a newly-added output-schema cannot silently escape the guard.
**Consequences:**
- ✅ Both surviving invariants stay true: the finding schema is still strict-mode
  clean, and the ledger schema stops being forced to contradict its own history.
- ✅ `duration_s` can be genuinely optional, which is what "written before this
  field existed" means.
- ⚠️ The guard's blast radius shrinks. Mitigated by making the exclusion explicit
  and asserted rather than implicit in a glob.
- ⚠️ A future schema that IS an output-schema must be added to the guard's set.
  The exclusion test names the criterion, so the omission is visible.
**Rejected alternatives:**
- Add `duration_s` to `required` as a nullable union — passes both existing tests,
  but the shipped schema would declare the harness's own 112 historical rows
  invalid. No runtime validator reads it, so the harm is a documented falsehood
  rather than a crash — which is precisely the class this repo keeps paying for.
- Drop `additionalProperties: false` — abandons the drift/typo protection the
  parity contract exists for.
- Abandon ADR-004's ledger field — gives up the signal that would have caught this
  regression in July.
**Source:** Interview #8 (raised by /hm:execute Step 3 before Phase 1 test authoring)

## 🏗️ Technical Design

### Current state

`second_opinion_invoke.invoke()` builds agy's argv in `build_agy_argv` as
`agy --sandbox --print <prompt> --print-timeout 240s --model <model>`, runs it
under `subprocess.run(timeout=AGY_TIMEOUT_S=300)`, and on exit 0 passes
`proc.stdout` to `codex_adapter.extract_antigravity_payload`. Statuses land on a
7-branch matrix. `codex_ledger` writes one row per invocation to the base repo.
`resolve_schema_path` serves the codex leg only: it reads
`cfg["codex"]["output_schema_path"]`, may materialise a packaged temp file,
returns `(path, we_created_it)`, and **raises `SecondOpinionSkipError` when an
explicitly-configured path is missing** — which is why ADR-002 does not reuse it.

### Affected components

| Component | Change | Phase |
|---|---|---|
| `src/harness_maker/models.py` | `AntigravityConfig.model` default (+ docstring) | 1 |
| `src/harness_maker/second_opinion_invoke.py` | `DEFAULT_ANTIGRAVITY_MODEL`; `build_agy_argv`; packaged-schema resolution; four-case acquisition; wall-clock; `duration_s` in the returned JSON; advisory line | 1, 2, 3, 4 |
| `templates/harness-yaml/Production.yaml.j2`, `Side.yaml.j2` | fresh-install fallback literal | 1 |
| `templates/agents/_partials/second_opinion_antigravity.md.j2` | display default (Ph 1) + prose correction (Ph 5) | 1, 5 |
| `src/harness_maker/codex_adapter.py` | envelope helper; comment correction | 2, 5 |
| `src/harness_maker/codex_ledger.py` | `duration_s` row field | 3 |
| `templates/schemas/second-opinion-ledger.schema.json` | `duration_s` in `properties`, **not** `required` | 3 |
| `templates/commands/hm/health.md.j2` | relay the Python advisory | 4 |
| `templates/skills/second-opinion-gate/SKILL.md.j2`, `CLAUDE.md`, memory entry | claim correction | 5 |
| `README.md` | example literal | 1 |
| `.claude/harness.yaml` (this repo) | explicit model value | 6 |

### Data flow (new)

```
prompt-file ─▶ invoke() ─▶ build_agy_argv(+ --output-format json
                              + --json-schema <packaged, absolute>)
                              │
                    subprocess.run  ──(wall-clock t)──┐
                              │                       │
                        exit 0, stdout                │
                              │                       │
                  len(stdout) > cap? ─▶ failed        │
                              │                       │
                        json.loads ──fail──▶ failed (case 1)
                              │                       │
                  status != SUCCESS ─▶ skipped (case 2)
                              │                       │
        structured_output is dict? ──yes──▶ validate_payload
                              │                ├─ok───▶ payload  (3a)
                              │                └─fail─▶ failed   (3b, closed)
                              no                       │
                              ▼                       │
        response is a str? ──no──▶ failed (4b)         │
                              │                       │
        extract_antigravity_payload(response)   (4a)   │
                              │                       │
                      adapt + ledger row ◀────────────┘  (duration_s)
```

**Size cap.** The claim that "`_MAX_ANTIGRAVITY_BYTES` still applies" is true of
today's code and false of this design: the cap lives *inside*
`extract_antigravity_payload`, which under the new flow sees only
`envelope["response"]` — a substring — and never runs at all on the primary path.
The cap is therefore **re-applied explicitly** against `len(proc.stdout)` before
`json.loads`, and pinned by a test feeding an oversized envelope.

### Design decisions

- The four cases are a **chain, not a race** — nothing merges two payload sources.
- Timing is measured by the invoker (ADR-004), so every branch has a duration and
  codex is covered by the same code.
- `--print-timeout 240s` and `AGY_TIMEOUT_S = 300` are unchanged. The ordering
  rationale (native fires first so agy's own diagnostic wins) is confirmed by
  every timeout row carrying agy's message.

## 📝 Implementation Plan

### Phase 1 — Model tier default, all five sites
- **depends_on:** `[]`
- **parallel_group:** `serial-defaults`
- **merge_hazards:** `second_opinion_invoke.py` (Phases 2–4);
  `second_opinion_antigravity.md.j2` (**shared with Phase 5** — Phase 1 owns the
  default literal on line 22, Phase 5 owns the prose); the two `harness-yaml/*.yaml.j2`
  templates pull the **six-gate ratchet** into this phase.
- **Scope — in:** `models.py:459,467`; `second_opinion_invoke.py:28`;
  `harness-yaml/Production.yaml.j2:98`; `harness-yaml/Side.yaml.j2:98`;
  `second_opinion_antigravity.md.j2:22`; `README.md:659`; the synthesize
  snapshots, render fixtures and structural baselines these disturb.
- **Scope — out:** argv construction, parsing, ledger, prose.
- **Exit criterion:** `rg -n "Gemini 3\.1 Pro" src/ README.md` returns **zero
  hits** — asserted by a test, not judged. (No allowlist: the scan roots are
  `src/` and `README.md`, so a `tests/` or `work-docs/` path can never appear in
  the output, and an allowlist naming them would be dead text.) **And**
  `uv run pytest tests/unit/test_models_codex_second_opinion.py tests/unit/test_second_opinion_invoke.py tests/unit/test_interview_codex_second_opinion.py tests/structural/ -q`
  passes with synthesize snapshots regenerated and baseline deltas attributed in
  `work-docs/BASELINE-DELTA-P7.md`.
  > **Three unit files assert the old default and will fail until updated:**
  > `test_models_codex_second_opinion.py:33`, `test_interview_codex_second_opinion.py:71`,
  > and `test_second_opinion_invoke.py:253,261` (golden argv). The interview file
  > was absent from the first draft of this criterion, which would have let Phase 1
  > report green and surfaced the failure inside Phase 2's review window,
  > mis-attributed to the argv change.
  >
  > **Leave the `Gemini 3.1 Pro (Low)` fixtures alone** —
  > `test_second_opinion_invoke.py:177,193,872` and
  > `tests/integration/test_antigravity_sandbox_probe.py:53` use a deliberately
  > *non-default* value to prove config plumbing reads the user's setting. Changing
  > them would silently delete that coverage.
  >
  > Out of scope here by design: `CHANGELOG.md`, `.claude/memory/session/2026-07-09.md`
  > (historical records), and `.claude/harness.yaml` (Phase 6 owns it).
- **Risk:** medium (gate count, not logic)
- **Rollback:** revert to base.

### Phase 2 — Structured-output path + four-case chain
- **depends_on:** `[1]`
- **parallel_group:** `serial-invoker`
- **merge_hazards:** `second_opinion_invoke.py` (Phases 1, 3, 4);
  `codex_adapter.py` (Phase 5's comment sweep).
- **Scope — in:** `build_agy_argv` gains `--output-format json --json-schema
  <packaged, absolute>`; a packaged-schema resolver **separate from**
  `resolve_schema_path` (ADR-002.1) whose ownership flag is appended to `owned`
  on the antigravity branch; the four-case acquisition block; explicit stdout
  size cap; `extract_agy_envelope`.
- **Scope — out:** ledger schema and row model (Phase 3); health (Phase 4); prose (Phase 5).
- **Exit criterion:** `uv run pytest tests/unit/test_second_opinion_invoke.py tests/unit/test_second_opinion_adapter.py -q`
  passes with new tests covering **all six** paths — case 1 (unparseable), case 2
  (exit 0, `status != SUCCESS`), case 3 valid, case 3 invalid → `failed` with no
  `response` fall-through, case 4 (absent → extractor), case 4 with missing /
  non-`str` `response`; **plus** an oversized-envelope cap test, a temp-schema
  **leak** test (`owned` cleanup ran), a schema-resolution-failure test asserting
  the **no-schema argv** is used and the call still proceeds, and the golden argv
  test updated. Plus one `INTEGRATION=1` live call asserting a schema-shaped
  payload from a cwd inside `.worktrees/`.
- **Risk:** medium — the only phase changing an external contract.
- **Rollback:** revert to end of Phase 1 (tier fix stays live).

### Phase 3 — Ledger `duration_s` (both surfaces)
- **depends_on:** `[2]`
- **parallel_group:** `serial-ledger`
- **merge_hazards:** `second_opinion_invoke.py` (**Phases 1, 2, 4**) — named as a
  phase collision for parity with every other phase's hazard field.
  *Consumer note (not a phase hazard):* the `codex_ledger.py` row model is read by
  health aggregation and the disposition path, and the shipped JSON Schema is a
  **published contract**.
- **Scope — in:** `SecondOpinionRecord.duration_s: float | None = None`;
  `templates/schemas/second-opinion-ledger.schema.json` — add to `properties` as
  `{"type": ["number", "null"]}`, **not** to `required`; `emit` signature;
  invoker wall-clock emitting a genuine `float`; population on per-invocation rows
  only.
- **Scope — out:** aggregation formulas (unchanged).
- **Exit criterion:** `uv run pytest tests/unit/test_codex_ledger.py tests/unit/test_second_opinion_ledger.py -q`
  passes, **and** all 112 pre-existing rows plus a new row validate against
  **both** validators (Pydantic *and* the shipped JSON Schema) — the
  Pydantic-only half is what let the `stage`-enum incident through — **and** a
  test asserts a row is actually written on each of the seven status branches
  with the field populated, so a strict-mode `ValidationError` swallowed by
  `_emit_row` cannot silently drop it.
- **Risk:** medium
- **Rollback:** revert to end of Phase 2, **accepting mixed-shape history** — rows
  already carrying `duration_s` are rejected by both validators after a revert, so
  the field is append-only in practice. Ship the schema half before the writer
  half so the schema is forward-compatible on its own.

### Phase 4 — Python-owned health budget advisory
- **depends_on:** `[3]`
- **parallel_group:** `serial-health`
- **merge_hazards:** `second_opinion_invoke.py` (Phases 1–3); `health.md.j2` →
  **six-gate ratchet**.
- **Scope — in:** `duration_s` added to `invoke()`'s returned JSON; the threshold
  comparison and advisory emission in Python; `health.md.j2` relays it.
- **Scope — out:** making health *fail* on latency; `readiness.py` (it does not
  own this smoke).
- **Exit criterion:** a unit test on the Python threshold function at, over and
  under the boundary; `uv run pytest tests/unit/test_render_configure_health_second_opinion.py tests/structural/ -q`
  passes with baseline deltas attributed in `work-docs/BASELINE-DELTA-P7.md` and
  synthesize snapshots regenerated.
- **Risk:** medium
- **Rollback:** revert to end of Phase 3.

### Phase 5 — Correct the schema claim (ADR-006)
- **depends_on:** `[2, 4]` — the graph, not prose, carries the ordering that keeps
  two ratchet-tripping phases out of one review.
- **parallel_group:** `serial-prose`
- **merge_hazards:** `second_opinion_antigravity.md.j2` (**shared with Phase 1**);
  `second-opinion-gate/SKILL.md.j2`; `codex_adapter.py` docstring (Phase 2) →
  **six-gate ratchet**.
- **Scope — in:** all **seven** assertion sites of ADR-006, including
  `second_opinion_oracle.py:6`; project `CLAUDE.md`; `.claude/memory/wiki.md`.
- **Scope — out:** behavioural change (all of it is Phase 2); the oracle's path
  sanitisation, which must survive the premise correction unchanged.
- **Exit criterion:** `rg -n "no --output-schema|NO .--output-schema|has no output schema|no CLI-level schema" src/ CLAUDE.md .claude/memory/`
  returns **zero hits** — corrected prose is written so it does not match the
  pattern, making the check machine-decidable rather than a judgment. The scan
  roots include `.claude/memory/` because SC 7 covers the memory site and the
  first draft's roots (`src/ CLAUDE.md`) did not reach it.
  `uv run pytest tests/unit/test_second_opinion_no_stale_names.py tests/structural/ -q`
  passes **with baseline deltas attributed in `work-docs/BASELINE-DELTA-P7.md`,
  synthesize snapshots regenerated, and the command-registry check run** — the
  same clause as Phase 4, because the same gates fire.
- **Risk:** low
- **Rollback:** revert to end of Phase 4.

### Phase 6 — This repo's own harness
- **depends_on:** `[1, 3, 4, 5]`
- **parallel_group:** `serial-selfhost`
- **merge_hazards:** `.claude/harness.yaml` + every re-rendered `.claude/` artifact.
- **Scope — in:** set `second_opinion.antigravity.model: "Gemini 3.6 Flash (High)"`; re-render.
- **Scope — out:** other harness axes.
- **Exit criterion:** a live `hm second_opinion_invoke --model antigravity` on a
  **real ≥30 KB review prompt** returns `status: invoked` with **≥1 finding in
  ≤60 s**, measured from process start to process exit. A green `/hm:health` is a
  **supporting, not sufficient**, signal — this PLAN exists because green health
  coexisted with 100 % real-call failure.
- **Risk:** low
- **Rollback:** revert the one config line and re-render.

## 🧪 Testing Strategy

**Unit** — golden argv with the new flags; the six payload paths of ADR-002;
oversized-envelope cap; temp-schema leak; schema-resolution-failure → no-schema
argv; ledger round-trip against **both** validators over the 112 legacy rows and
a new row; row-written-on-all-seven-branches; health threshold at/over/under.

**Integration (`INTEGRATION=1`)** — one live `agy` call from a cwd inside
`.worktrees/`, asserting exit 0 and a schema-shaped payload within budget. This is
the only test class that can catch a capability claim being wrong — the defect
this PLAN exists to fix — and a render-grep provably cannot.

**Manual** — run `/hm:review` on a real diff after Phase 6 and confirm an
antigravity `source:`-tagged finding reaches Step 4.

**Regression watch** — after a week, recompute per model:

```
rows where finding_ref == "n/a" AND stage != "health"
grouped by model:  (skipped + failed) / total
```

The `finding_ref == "n/a"` filter is **not optional**: per-invocation rows and
per-finding disposition rows share the file and both carry `status: "invoked"`,
so omitting it inflates the denominator and reports a systematically low loss
rate — the same corruption CLAUDE.md records from 2026-08-06 (10.3 % reported vs
20.7 % actual). Target: antigravity ≤ 5 %.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | `structured_output` absent more often than probed | medium | low | Case 4 is mandatory; Phase 2 tests the absent case |
| R2 | Schema path resolution regresses under per-task worktrees | low | high | Probed working from a worktree cwd with an absolute base-root path; Phase 2 tests from both cwds and includes a live integration call |
| R3 | Six-gate ratchet under-sized | high | medium | Now named in **Phases 1, 4 and 5**, each with the same attribution + snapshot clause. **Confirmed under-sized during Phase 1: it is SEVEN.** Any new `tests/structural/` gate must also file a row in `.claude/observability/mutation-receipts.jsonl` naming the line whose deletion turns it red (`test_new_gates_file_a_mutation_receipt`). That gate earned its keep immediately — the first version of Phase 1's fixture assertion used `"literal" in text` and survived deleting a real fixture line, because five other occurrences remained. Strengthened to per-file floor counts, re-mutated, then filed |
| R4 | Flash (High) misses findings a Pro tier would catch | medium | low | K=2 consensus, codex holds the deep slot |
| R5 | Chosen model becomes slow later | low | medium | ADR-004 duration + ADR-005 advisory |
| R6 | New ledger field invalidates old rows or new ones | medium | high | `properties` yes / `required` no; both validators tested over legacy **and** new rows; schema half ships first |
| R7 | Fail-closed case 3 discards a usable payload | medium | low | Accepted (Interview #6); `duration_s` + reason string make the frequency measurable, so it can be revisited with data |
| R8 | Case-3 fail-closed raises the `failed` count, masking the improvement | medium | medium | Regression watch counts `skipped + failed` together, so a shift between them cannot flatter the result |
| R9 | Strict-mode `ValidationError` on `duration_s` silently drops the row | low | high | Emit a genuine `float`; Phase 3 asserts a row exists on all seven branches |

## ✅ Success Criteria

- [x] `Gemini 3.1 Pro (High)` is gone from **all five shipped sites** and README, asserted by an allowlist test.
- [x] `agy` argv carries `--output-format json --json-schema <packaged, absolute>`, pinned by a golden test.
- [x] All six ADR-002 paths behave as tabled, each with a test; case 3 fails closed.
- [x] A schema-resolution failure degrades to the no-schema argv and the call still proceeds — no new `skipped` class.
- [x] Every **newly emitted per-invocation** row carries `duration_s`; disposition rows carry `null`; the 112 pre-existing rows validate against **both** Pydantic and the shipped JSON Schema.
- [x] The health advisory's threshold is a Python function with boundary tests; `health.md.j2` only relays it.
- [x] No source, template, skill, CLAUDE.md or memory site still claims agy cannot enforce output shape.
- [x] A live antigravity call on a real ≥30 KB review prompt returns ≥1 finding in ≤60 s (process start to exit).

## 📊 Execution status (2026-08-08)

| Phase | Status | Note |
|---|---|---|
| 1 — model tier, 5 sites | **DONE** | ADR-003's *rationale* refuted by its own test (sites 3–4 unreachable); literal change kept, record corrected |
| 2 — structured output + chain | **DONE** | Grew to **seven** paths: an empty-`response` case was found by Phase 6's live run, not by any unit test |
| 3 — ledger `duration_s` | **DONE** | Both validators green over the real 114 rows; ADR-007 added mid-flight |
| 4 — health advisory | **DONE** | Threshold in Python with boundary tests; template relays only |
| 5 — schema-claim correction | **DONE** | 7 sites; `rg` pattern returns zero hits |
| 6 — self-host + live check | **DONE, criterion partially met** | See below |

### Phase 6 acceptance — measured, not assumed

Three live runs, real 47 KB review prompt, `Gemini 3.6 Flash (High)`:

| Run | Elapsed | Status | Findings |
|---|---|---|---|
| 1 | 30 s | `invoked` | 0 |
| 2 | 7 s | `failed` (empty response) | — |
| 3 | 40 s | `invoked` | 2 |

**The timeout class is fixed.** No run came near the 240 s cap; the worst was 40 s
against a shipped default that took 4 m 04 s and returned zero bytes.

**The "≥1 finding" half of the criterion is not reliably met, and the criterion
was partly wrong to demand it.** Zero findings is a legitimate answer from a
reviewer; requiring one conflates liveness with verdict. What is legitimately
concerning is run 2.

**Residual: intermittent empty responses (NEW, agy-side).** agy sometimes answers
`status: SUCCESS` in ~7 s with `response: ""` and no `structured_output` —
observed 3 times across 7 large-prompt calls. The same prompt then succeeds, so it
is flakiness, not a size cliff. This change does not fix it; it makes it
**legible** (a named `failed` reason instead of "expected exactly one JSON
payload, found 0", which blamed our parser for agy's silence). **The Executive
Summary's ~2 % projection is therefore optimistic** — the timeout and parse
classes are addressed, but this third class remains and will show up in
`failed`. `duration_s` plus the per-model loss recomputation are what will size
it after a week of real use.

## 🔍 Plan Validation

**Pass 1 — `plan-validator`: MAJOR_REVISION** (3 critical, 8 warning, 3 suggestion;
`clean_categories`: risk-register, adr-rejected-alternatives, interview-rounds,
spec-alignment). Recorded as `stage_agent_ledger` run `asot-20260808-1`, pass 1.

| Critique | Resolution |
|---|---|
| Critical — literal lives in 5 sites, not 2; harness-yaml fallbacks are the fresh-install path | Verified by `rg`. ADR-003 rewritten with the site table; Phase 1 scope + allowlist exit criterion; Phase 1↔5 merge hazard declared |
| Critical — `readiness.py` does not own the smoke; advisory would become untestable prose | Verified (`0` references). ADR-005 rewritten: threshold in Python, `duration_s` added to `invoke()`'s return, `health.md.j2` relays only |
| Critical — shipped ledger JSON Schema is `additionalProperties:false` + all-required; SC 4's two clauses were mutually exclusive | Verified by file read. ADR-004 + Phase 3 now name the JSON asset, specify properties-yes/required-no, and test both validators over legacy and new rows |
| Warning — `resolve_schema_path` reads codex's key, may leak a temp file, and raises on a missing explicit path | Interview #7 → packaged schema always, degrade to no-schema argv, ownership flag wired into `owned`, leak test |
| Warning — fallback chain missing envelope-`status` and invalid-`structured_output` cases | Interview #6 → four-case decision table, case 3 fail-closed |
| Warning — regression-watch formula omitted the `finding_ref` filter | Formula written out in full with the rationale |
| Warning — bounded-read claim false of the new design | Cap re-applied explicitly against `len(proc.stdout)` + oversized-envelope test |
| Warning — Phase 5/6 `depends_on` did not carry the prose ordering | Phase 5 → `[2, 4]`; Phase 6 → `[1, 3, 4, 5]` |
| Warning — Phase 1 exit criterion was a human judgment | Replaced with an enumerated allowlist assertion + the structural suites |
| Warning — Phase 5 exit criterion omitted the ratchet clause | Given Phase 4's clause verbatim |
| Warning — Phase 6 reused green health as completion evidence | Numeric, representative criterion (≥30 KB, ≥1 finding, ≤60 s); health demoted to supporting |
| Warning — ADR-004 "every row" vs disposition rows; strict-mode silent drop | Scoped to per-invocation rows; genuine `float`; seven-branch row-written test (R9) |
| Suggestion — ADR-001 causal claim overstated | Narrowed to the measured claim; the 8-row attribution marked as inference |
| Suggestion — no `## Non-Goals` | Added |
| Suggestion — Phase 3 rollback unreachable | Stated as append-only, with schema-half-first ordering |

**Cross-model second opinion (main-loop supplied, Step 4 pre):**

| Model | Status | Findings | Dispositions |
|---|---|---|---|
| codex | invoked | 5 (1×P1 ×2, 3×P2) | 5 accepted |
| antigravity | invoked | 2 (1×P0, 1×P2) | 2 rejected |

`820bac41` (antigravity P0 — "`--sandbox` blocks a base-root schema path, every
invocation will fail") was **refuted by live probe**: an absolute base-root path
with cwd inside `.worktrees/<slug>/` returned rc = 0 in ~10 s with a valid
`structured_output`. `--json-schema` is consumed by the agy CLI's own argument
handling; `--sandbox` governs the tools exposed to the model. `a109d745`
(antigravity P2) was **rejected on the text** — the PLAN already specified a
default — while its substantive form, one layer out in the shipped JSON Schema,
is codex's `a3a17196`, accepted as critical.

**Pass 2 — `plan-validator`: NEEDS_REVISION** (all 3 criticals `resolved`; 3 new
warnings + 3 suggestions). Recorded as run `asot-20260808-1`, pass 2, terminal.
**The re-run cap is 2 — no pass 3 was run.** All six pass-2 items were verified
against the repo and applied directly:

| Pass-2 critique | Verified | Resolution |
|---|---|---|
| Phase 1's allowlist was self-contradictory (roots `src/ README.md` can never emit a `tests/` path) | yes — by inspection | Allowlist dropped; criterion is now "zero hits", with the deliberate out-of-scope sites named in prose |
| `test_interview_codex_second_opinion.py:71` asserts the old default and was in no named suite | yes — `grep` | Added to Phase 1's Scope-in and pytest invocation; the two other asserting files were already covered |
| `second_opinion_oracle.py:6` is a 7th assertion site with different wording that Phase 5's pattern missed; memory site outside the scan roots | yes — file read | ADR-006 now lists seven sites; Phase 5's pattern gained `no CLI-level schema` and its roots gained `.claude/memory/`; criterion is zero-hits |
| Phase 3's `merge_hazards` named consumers, not phases, and omitted `second_opinion_invoke.py` | yes | Phase collision named; consumer note separated |
| ADR-003's Decision line omitted `models.py:459` | yes | Decision line amended |
| Diagram/table/SC described the same set at three granularities | yes | ADR-002's table numbered 3a/3b/4a/4b; diagram gained the missing-`response` leg; "six paths" is now literal everywhere |

Pass 2 also noted the pass-1 resolution table lists 15 rows against 14 critiques
(one warning was split). Accepted as bookkeeping, not corrected — the table is a
resolution log, not a 1:1 ledger.

**Residual risk accepted by stopping at the cap:** the pass-2 items were applied
without a third validation, so the edits themselves are unvalidated. All six were
verified against the repo first (`grep`/`rg`/file read), and all are local — none
changes an ADR decision, a phase boundary, or the dependency graph.

**Outstanding for `/hm:execute`:** the `Gemini 3.1 Pro (Low)` fixtures at
`test_second_opinion_invoke.py:177,193,872` and
`tests/integration/test_antigravity_sandbox_probe.py:53` are deliberately
non-default values proving config plumbing. Do not "fix" them.
