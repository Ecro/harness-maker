---
type: research
task_slug: second-opinion-multi-model
status: complete
created: 2026-07-09
tags: [harness-maker, research, codex, antigravity, second-opinion, multi-model, jinja-templates]
mtime_warn_days: 7
libs_fetched: []
sources: ["local CLI: agy --help / agy help models / agy help plugin / agy help install (agy v1.1.0, installed at /home/noel/.local/bin/agy)"]
related_docs: ["[[wiki:architecture:codex-second-llm-integration]]", "[[wiki:gotcha:subagent-tools-field-hard-gates-bash-permission]]", "[[wiki:gotcha:extend-rendered-agent-json-via-shared-partial]]", "PLAN-codex-second-llm-integration", "PLAN-codex-mandatory-second-opinion", "PLAN-crossmodel-codex-gaps", "PLAN-codex-second-opinion-sandbox", "PLAN-model-routing-multi-ide"]
summary: "Generalize codex_second_opinion -> second_opinion with models:[codex,antigravity] multi-select; antigravity lacks codex's schema-enforcement + hermetic flags"
---

## 🎯 Recommended Direction

Rename `harness.yaml.codex_second_opinion` to `second_opinion` and replace the
implicit single-vendor design with `models: list[Literal["codex","antigravity"]]`
(multi-select, both can be enabled at once). Keep the existing MAIN-LOOP
orchestration pattern (ADR-002/003: the stage prompt itself runs the external
CLI with `dangerouslyDisableSandbox: true`, not a tool-restricted subagent) and
extend it to loop over `config.second_opinion.models` instead of hardcoding one
Codex call. This is a **rename + fan-out generalization** of an existing,
well-tested vertical slice — not a new subsystem. The main risk is not the
Claude Code Jinja config plumbing (that generalizes cleanly); it is that
`agy` (Antigravity CLI v1.1.0) is architecturally weaker than `codex exec` in
two load-bearing ways: **(1) no `--output-schema` flag** (Codex enforces JSON
shape at the CLI boundary; `agy` only has free-text `--print` and must be
trusted via prompt instruction + a tolerant parser), and **(2) no
`--ignore-user-config`/`--ignore-rules` equivalent** (Codex's ADR-006
"hermetic" reproducibility guarantee has no antigravity counterpart — its
output can vary by the user's local `~/.gemini` config/imported plugins).
Both are real, not cosmetic — the adapter and the `hermetic` config field
cannot simply be copy-pasted from the Codex path.

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** (primary — this is
a config-schema + Jinja-template + CLI-adapter generalization of an existing
feature) with a secondary **Risk / security** pass (external-CLI sandbox
escape, permission-allow injection, output-trust boundary). `--deep` was not
requested and the topic ("generalize codex_second_opinion to multiple models,
add antigravity") was concrete enough that the 5-question refinement rubric
was skipped per the stage's default-off policy.

## 🛠️ Approaches Found

| Approach | Assumption | Evidence | Trade-off | Compatibility | Risk |
|---|---|---|---|---|---|
| **A. Single `models: list[str]` field, shared dispatch loop** | One config axis (which vendor CLIs to invoke) generalizes cleanly to N vendors reusing one orchestration skeleton | `codex_exec_mainloop.md.j2` is already a self-contained "invoke → adapt → skip-relay" recipe gated only on `enabled`; the transport (`codex exec ...`) is the only vendor-specific line | Every per-model quirk (schema enforcement, hermetic flags, severity vocab) must be isolated behind a small per-model partial/adapter, or the shared loop leaks Codex-isms | High — matches existing "shared partial extends 3 anchors" pattern already in the codebase (`[[wiki:gotcha:extend-rendered-agent-json-via-shared-partial]]`) | Medium — schema/field renames (`codex_status`→`second_opinion_status`) are the only breaking surface |
| **B. Two independent boolean flags (`codex_second_opinion`, `antigravity_second_opinion`)** kept as siblings, no shared `models` list | Additive rather than a rename avoids touching 13 existing test files | Zero migration risk for `codex_second_opinion` consumers | Doesn't scale past 2 vendors; duplicates the entire invoke/adapt/ledger/mandatory-matrix logic per vendor (violates the CLAUDE.md "no premature abstraction" *and* "don't duplicate" tension — but here duplication is the wrong call since the shared recipe is 90% identical) | Low forward-compat — a 3rd vendor later repeats the whole exercise | Low short-term risk, high long-term maintenance cost |
| **C. Generic `second_opinion.models` + per-model adapter registry keyed by vendor, single shared ledger with a `model` field** (recommended synthesis of A) | The ledger/ADR-005 calibration record is explicitly framed as "cross-time calibration," so cross-vendor comparison (codex vs antigravity precision) is itself valuable — one ledger, not two | `CodexSecondOpinionRecord` already isolates `codex_status`/`disposition`/`stage` as closed enums; adding a `model: Literal["codex","antigravity"]` field is a strict superset, not a breaking shape change if the field is added with a default for legacy rows | Legacy ledger rows (already on disk in installed harnesses) lack the `model` field — needs a lenient reader (`model: str | None = None`, treated as `"codex"` for pre-migration rows) | Medium — filename rename (`codex-second-opinion.jsonl` → `second-opinion.jsonl`) affects `/hm:metrics` and `/hm:health` consumers; safer to add the field to the *same* filename and defer a rename | Low if filename is kept; the field addition alone is safe |

## ⚠️ Pitfalls

1. **`agy` has no `--output-schema` guarantee — Codex's central trust
   mechanism does not transfer.** Verified live: `agy --help` / `agy help
   <subcommand>` list only `--print`/`-p`, `--model`, `--sandbox`,
   `--dangerously-skip-permissions`, and a `--mode` (accept-edits|plan) flag —
   no JSON-schema enforcement flag exists. A live test
   (`echo '<json-instruction>' | agy --print --sandbox --model "Gemini 3.1 Pro
   (Low)"`) returned clean unfenced JSON when explicitly instructed, but
   nothing in the CLI *enforces* that shape the way Codex's
   `--output-schema` does. **Copying `codex_adapter.adapt_finding_list`
   verbatim for antigravity will silently break** the first time a response
   is wrapped in a ` ```json ` fence or prefixed with a sentence — the
   antigravity adapter needs a tolerant extraction pass (strip fences, then
   `json.JSONDecoder().raw_decode` scan for the first balanced object) rather
   than a bare `json.loads`.
2. **No hermetic/ignore-user-config equivalent for antigravity.** Codex's
   `hermetic: true` config field maps directly to `--ignore-user-config
   --ignore-rules` (ADR-006 reproducibility guarantee). `agy`'s flag list has
   no such option — its behavior can depend on the user's `~/.gemini`
   directory and any plugins imported via `agy plugin import`. If
   `second_opinion.hermetic` is exposed as a shared top-level field, it will
   silently no-op for antigravity (a repeat of the "absent-case = feature
   black hole" pattern already logged in this user's CLAUDE.md Learned
   Corrections 2026-06-08). Must either drop `hermetic` to a per-model
   sub-block or document explicitly that it is Codex-only and antigravity is
   non-hermetic by construction.
3. **`agy --model` takes free-text display strings with spaces/parens**
   (e.g. `"Gemini 3.1 Pro (High)"`, verified via `agy models`), not stable
   machine IDs. No `--json` output mode was found for `agy models`. A pinned
   default in `harness.yaml` is a string that could silently stop matching
   after an `agy` CLI upgrade renames a model's display label — this is the
   same class of external-parser-fragility risk flagged in CLAUDE.md
   checklist item 2 ("외부 소비자의 파서 정합성"), except here *we* are the
   caller depending on *their* unstable display string, not the reverse.
   Recommend treating the configured model string as user-editable free text
   (not a closed enum) and validating at invoke time with a friendly failure
   message rather than a Pydantic `Literal`.
4. **`agy --sandbox` semantics are unverified beyond "terminal restrictions
   enabled"** — the help text does not document a read-only filesystem
   guarantee analogous to Codex's `--sandbox read-only`. The live smoke test
   only exercised text generation (no tool/file-write prompts), so whether
   `agy --sandbox` can still write files was not established. Codex's
   `Bash(codex exec:*)` allow-rule + `--sandbox read-only` pairing is
   documented as a deliberate defense-in-depth pairing (ADR-003 in the
   codex_exec_mainloop partial) — an antigravity parity claim needs the same
   verification before the health-smoke / permission-injection tests can
   assert equivalent safety.
5. **Output-contract fan-out is a 3-anchor problem, confirmed by prior
   incident.** `[[wiki:gotcha:extend-rendered-agent-json-via-shared-partial]]`
   documents that `plan-validator`'s canonical schema block, its dispatch
   `Task()` prompt, and the shared partial must all agree on field names — a
   real P1 was caught in review when only the partial was updated. Renaming
   `codex_status`/`codex_reconciliation` to a model-keyed shape
   (`second_opinion_status: {codex: ..., antigravity: ...}`) touches this
   exact 3-anchor set again in **3 places** (`plan-validator_body.md.j2`,
   `stages/plan.md.j2` Step 4's inline dispatch prompt, and the shared
   partial) — plus the equivalent set in `stages/review.md.j2` /
   `consensus-arbiter_body.md.j2` for the review-stage voter path.
6. **`Bash` tool-availability gate applies to any new `Bash(agy:*)` allow
   rule exactly like it did for Codex.**
   `[[wiki:gotcha:subagent-tools-field-hard-gates-bash-permission]]` — a
   `permissions.allow: Bash(agy:*)` entry is inert on any agent whose
   `tools:` frontmatter omits bare `Bash`. Current architecture (ADR-002/003)
   already moved the Codex call out of the tool-restricted reviewer agents
   into the orchestrating MAIN LOOP for exactly this reason — the antigravity
   path should follow the same main-loop-owns-the-call pattern, not
   reintroduce a subagent-Bash dependency.
7. **k-of-3 consensus voter count is currently a fixed constant in prose.**
   `stages/review.md.j2` Step 3.5 and `consensus-arbiter_body.md.j2` describe
   "Codex joins Step 4 as a **third voter**" and "k-of-3 ring" as literal
   text, not a computed `3 + len(models)`. Enabling both `codex` and
   `antigravity` simultaneously means 4 voters (Claude ×2 default reviewers +
   Codex + Antigravity, or whatever the existing k-of-3 baseline actually
   is) — the consensus math/prose needs to become parametric on
   `len(config.second_opinion.models)`, not hand-edited to "k-of-4."
8. **Two unrelated `codex`-prefixed touchpoints exist in this codebase** —
   `codex_second_opinion` (this task) and a **separate** `codex -p
   cheap/deep` model-routing profile system (`codex_user_config.py`,
   ADR-008, PLAN-model-routing-multi-ide) for `/hm:loop` cost levers. A
   broad `grep -rl codex` / rename pass must not touch the latter — it has
   nothing to do with second opinions.
9. **Mandatory-matrix policy (Production=always, Side=high-diff-gated,
   `test_codex_mandatory_matrix.py`) is currently written as a single-vendor
   gate.** Whether "mandatory" should apply per-model uniformly (both
   enabled models run on every Production validation) or only to one
   designated primary model is an open architectural choice — the mandatory
   gate's cost profile changes materially once a second external CLI call
   is in the mandatory path (2x latency/cost per validation instead of 1x).
10. **Ledger filename change is a compatibility question, not just a code
    change.** `codex-second-opinion.jsonl` is read by `/hm:metrics` narrative
    logic and any already-installed harness in the wild. Renaming the file
    breaks continuity of an existing calibration record; adding a `model`
    field to the *same* file (defaulting absent-field rows to `"codex"`) is
    the lower-risk migration (see Approach C).

## ❓ Open Questions

1. **Backward compatibility surface**: keep `codex_second_opinion` as a
   permanently-supported deprecated alias key in `harness.yaml` (read-and-map
   to `second_opinion.models`), or do a hard schema-version bump (current
   `schema_version: 2` → 3) with a one-time silent migration + advisory log
   (matching the `default_model`/`recommended_model` precedent already in
   `models.py`)? This determines how much of `interview.answers_from_harness_yaml`
   needs new tolerant-fallback code.
2. **Per-model vs shared `hermetic`/`output_schema_path`/`failure_policy`
   fields**: should `second_opinion` keep these as shared top-level fields
   that only apply where the vendor supports them (silently ignored for
   antigravity — a footgun per Pitfall 2), or move to a
   `second_opinion.per_model: {codex: {...}, antigravity: {...}}` sub-block
   that makes vendor-specific applicability explicit in the schema itself?
3. **Severity vocabulary for antigravity findings**: reuse Codex's
   `critical/high/medium/low/info` request vocabulary (lets the antigravity
   adapter reuse `map_codex_severity` verbatim — simpler), or have the
   antigravity prompt ask directly for `P0..P3` (skips a translation layer
   but diverges from the existing Codex-finding JSON schema
   `.claude/schemas/codex-finding.schema.json`, which would then need a
   parallel antigravity schema or a shared schema renamed off "codex")?
4. **Does "mandatory" apply per-model or per-a-designated-primary?** (Pitfall
   9) — decides whether enabling both models in Production doubles the
   external-CLI cost on every validation by default, or whether a second
   model stays opt-in/MAY even when the harness is otherwise in mandatory
   mode.
5. **Antigravity model pin**: what default `--model` string should the
   interview/harness.yaml default ship with, given `agy models` returns
   unstable free-text display names with no machine ID (Pitfall 3)? Should
   the render step shell out to `agy models` at interview time to offer a
   live-fetched list, or ship one hardcoded default the user can freely
   edit?
6. **`agy --sandbox` write-guarantee** (Pitfall 4) needs an explicit
   verification pass (e.g., attempt a file-write prompt under `--sandbox`)
   before the health-smoke/permission-injection tests can assert parity with
   Codex's `--sandbox read-only`.
7. **Ledger rename vs field-add** (Pitfall 10 / Approach C) — does
   `/hm:metrics`'s narrative-generation code read the ledger filename
   directly in a way a rename would break for already-installed harnesses?
   (Not verified in this pass — `/hm:metrics` template wasn't inspected.)
8. **Test-suite scope**: 13 existing test files hardcode `codex_second_opinion`
   / `codex_status` naming (`test_codex_mandatory_matrix.py`,
   `test_codex_review_consensus.py`, `test_codex_plan_pida.py`,
   `test_interview_codex_second_opinion.py`, `test_models_codex_second_opinion.py`,
   `test_synthesize_roundtrip_codex.py`, `test_render_codex_partial_include.py`,
   `test_render_codex_permission_injection.py`, `test_codex_health_smoke.py`,
   `test_agent_body_partials.py` SHA baselines, plus CHANGELOG/README/CLAUDE.md
   prose). `/hm:plan` should scope this explicitly as a rename+extend pass,
   not a from-scratch feature — most of these tests likely get
   renamed/parametrized over `models` rather than deleted.

## 📚 Sources

- Live CLI probe (this session): `agy --help`, `agy help models`, `agy help
  plugin`, `agy help install`, `agy models` (model list), and two live
  `agy --print --sandbox --model "..."` invocations (one plain, one
  JSON-instructed) — Antigravity CLI v1.1.0, OAuth token present at
  `~/.gemini/antigravity-cli/antigravity-oauth-token`.
- `git log --all --grep antigravity` and `grep -r antigravity work-docs/` —
  both empty; confirmed no prior harness-maker work on this topic.
- Internal source files read in full or via targeted grep: `src/harness_maker/models.py`
  (`CodexSecondOpinionConfig`, lines ~440-491), `src/harness_maker/interview.py`
  (`_ask_codex_second_opinion`, `answers_from_harness_yaml` migration block),
  `src/harness_maker/codex_adapter.py`, `src/harness_maker/codex_ledger.py`,
  `src/harness_maker/codex_user_config.py`,
  `src/harness_maker/templates/agents/_partials/codex_exec_mainloop.md.j2`,
  `src/harness_maker/templates/agents/consensus-arbiter_body.md.j2`,
  `src/harness_maker/templates/stages/review.md.j2`,
  `src/harness_maker/templates/stages/plan.md.j2`,
  `src/harness_maker/templates/commands/hm/health.md.j2`,
  `src/harness_maker/templates/harness-yaml/Production.yaml.j2`,
  `src/harness_maker/templates/settings/Production.json.j2`,
  `tests/unit/test_codex_mandatory_matrix.py`.

## 🔗 Related Internal Docs

- `[[wiki:architecture:codex-second-llm-integration]]` — original
  PLAN-codex-second-llm-integration architecture (ADR-001..009), the
  single-vendor baseline this task generalizes.
- `[[wiki:gotcha:subagent-tools-field-hard-gates-bash-permission]]` —
  applies identically to any new `Bash(agy:*)` allow-rule.
- `[[wiki:gotcha:extend-rendered-agent-json-via-shared-partial]]` — the
  3-anchor output-contract rule that will fire again on the `codex_status`
  → model-keyed rename.
- `work-docs/PLAN-codex-second-opinion-sandbox.md` — ADR-002/003 main-loop
  sandbox-escape architecture (transport layer this task reuses).
- `work-docs/PLAN-codex-finding-schema-strict-mode.md` — origin of
  `codex-finding.schema.json` / `--output-schema` strict enforcement, useful
  context for why antigravity's lack of this flag matters.
- CLAUDE.md `## Targets 정책` § Codex dual role (ADR-009) and § Cross-model
  deepening — the prose sections that will need a rewrite pass once this
  ships (out of scope for research, in scope for `/hm:plan`'s doc-update
  checklist).
