---
type: plan
task_slug: second-opinion-invocation-and-slug-cap
status: complete
created: 2026-07-25
tags: [harness-maker, plan, python, second-opinion, cli-contract, memory, observability]
interview_rounds: 3
adrs: 8
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Move second-opinion CLI invocation into a tested Python module; grandfather legacy memory slugs"
---

# PLAN — second-opinion-invocation-and-slug-cap

## 🎯 Executive Summary

**TL;DR** — Three live harness bugs share one root-cause class: *an external contract assumed in
prose and never executed under the conditions it actually runs in*. Fix them by moving the two
second-opinion CLI invocations out of rendered prose into a single tested Python module, and by
making the memory CLI's slug validator agree with the corpus it already wrote.

**What:**
1. **H1** — the rendered `codex exec` recipe passes `--output-schema` as a **cwd-relative** path.
   Under `worktree.feature_branch_workflow` (Production default) every `/hm:` stage runs inside
   `.worktrees/<slug>/`, which has no `.claude/schemas/`. `codex exec` exits 1 → graceful degrade
   records `status: skipped`. The codex vote is dead on the harness's normal Production path.
2. **H2** — `agy --print` takes the prompt as its **VALUE**, not as a boolean flag. The rendered
   recipe `agy --print --sandbox … < prompt_file` makes `--sandbox` the prompt and never reads
   stdin. Every antigravity vote this harness has cast was vacuous. Probed 2026-07-25: `agy` does
   **not read stdin at all** in print mode, so the recipe's whole `< file` shape is structurally
   invalid, not merely mis-ordered.
3. **H3** — `memory_md`'s slug validator rejects a large part of the corpus it already wrote.
   45/123 `failures.md` and 49/185 `wiki.md` slugs exceed the 40-char cap (max 65), and two wiki
   slugs under the cap violate the `[a-z0-9-]` character class
   (`metrics-rotation-reader-via-_metrics_io`, `adr-supersession-precedent-v0.22.3`). Failure
   entries cannot receive a `count++`, so the `count>=3` escalation cannot fire for them; wiki
   entries cannot be replaced in place.

**Why now:** all three are *silent*. H1 and H2 hide behind `status: skipped|failed`, which is also
the legitimate outcome for a missing CLI or an expired login. H3 hides behind a non-zero CLI exit
that the operator works around by inventing a new near-duplicate slug — which *lowers* the counts
the dedup step exists to raise.

**Key decisions:**
- Second-opinion invocation moves to a Python module (**ADR-001**) that owns argv construction,
  base-root and config resolution, prompt delivery, status classification, adaptation, and the
  ledger row (**ADR-002**).
- Status classification is a **seven-way** matrix over exceptions, payload acquisition, and payload
  validity, not a three-way matrix over exit codes (**ADR-008**) — under `shell=False` there is no
  exit 127, `FileNotFoundError`/`TimeoutExpired` are not the only exceptions `subprocess.run` can
  raise, and reading the payload back is its own raising region.
- `/hm:health`'s smoke calls the **same** entrypoint (**ADR-005**), with an explicit statement of
  what a base-cwd smoke does and does not prove.
- agy prompts are truncated on **UTF-8 byte length** against a reserved budget, with the invoker
  owning the output-contract envelope as its single source (**ADR-003**).
- Memory slugs already present in the tier file bypass both the length cap and the kebab-case
  character class; only **new** slugs are held to the full rule (**ADR-004**).
- Scoped `allow` rules stay, with agy's corrected to the real argv grammar (**ADR-006**).
- Un-re-rendered user harnesses are **not** detected; the CHANGELOG carries the signal
  (**ADR-007**, accepted risk with a named residual exposure).

**Estimated impact:** 1 new module (~360 lines), 4 templates rewired, 1 validator restructured,
2 settings templates, 1 ledger `Literal` + its shipped JSON enum widened, ~65 new tests, snapshot
regeneration. No user-facing `harness.yaml` change.

---

## 📚 Prior Work

- `[fail:render] recipe-relative-path-breaks-in-worktree` (count:1) — H1's failure record; names the
  fix and the prevention (check every rendered command from **inside** a worktree).
- `[fail:tooling] agy-print-flag-swallows-next-flag` (count:1) — H2's record; names the compounding
  trap that the allow-rule prefix constraint **freezes the broken command shape**.
- `[fail:tooling] memory-cli-slug-cap-blocks-legacy-count` — H3's record; enumerates the three fix
  options, of which ADR-004 takes the third.
- `[fail:design] assertion-invariant-over-named-dimension` — recorded 2026-07-25, and it has now
  fired **three times against this work**: once against the Phase 3 `--output-schema` grep (removed,
  see Phase 3), once against `test_json_schema_matches_model_fields` which compares property *names*
  and is therefore invariant over the enum values ADR-002 changes (see Phase 2), and once against a
  golden-argv assertion that cannot see prompt delivery (see ADR-008's Consequences).
- `[fail:design] producer-consumer-schema-drift-in-same-process-pipeline` — the reason ADR-003 gives
  the output-contract envelope a single owner instead of a Python copy of template prose.
- `[wiki:gotcha] codex-exec-is-noninteractive-no-approval-flag` — this is the **fourth** distinct
  cause of a silently-skipping codex second opinion in this project's history. The meta-lesson
  recorded there ("when a feature is wrapped in warn-and-proceed, add a POSITIVE smoke that the
  happy path actually runs") was implemented — and still missed H1, because the smoke ran from a
  different cwd than the recipe. ADR-005 closes that gap and states its remaining limit.
- `[fail:process] trust-crossmodel-over-own-probe` — reconfirmed here: the cross-model panel plus two
  validator passes found 21 defects in this PLAN's drafts, seven of them critical, none of which the
  author had raised.
- `[wiki:architecture] second-opinion-multi-model` — the invariants this work must preserve: K stays
  fixed at 2, per-model config sub-blocks, fail-closed antigravity parsing, graceful degrade for
  every failure mode, one `second_opinion_results` entry per enabled model.

---

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|-------|----------|----------|---------|--------|------|-------|
| 1 | Invocation architecture | Architecture | Where should the two second-opinion CLI call contracts live? | A Python invoker module / B minimal prose patch / C hybrid | **A — Python invoker module** | Removes cwd-relative path, flag arity, permission-prefix fragility, and smoke/real divergence in one change | ADR-001 |
| 2 | agy prompt ceiling | Contract | What happens when the prompt exceeds the 128 KB single-argv limit? | A truncate at 100 KB + marker / B graceful skip / C summarise first | **A — truncate + marker** | Keeps the antigravity vote alive on large diffs; validator review then hardened this into a budgeted, envelope-owning operation | ADR-003 |
| 3 | Memory slug cap | Contract | How to handle the 40-char cap against a corpus that already violates it? | A grandfather existing, validate new only / B raise cap to 80 / C both | **A — grandfather existing** | Restores `count++` and in-place wiki replacement without abandoning terseness for new slugs | ADR-004 |
| 4 | Invoker scope | Architecture | How much does the invoker own? | A invoke + status + ledger / B invoke + adapt only / C thin wrapper | **A — invoke + status + ledger** | The `skipped`/`failed` distinction is the most error-prone judgment in the path and the one thing prose cannot be tested on | ADR-002, ADR-008 |
| 5 | Stale user harnesses | Risk tolerance | How to handle harnesses already rendered with the broken recipes? | A `/hm:health` detects old shape / B fix + CHANGELOG only / C health + forced re-render | **B — fix + CHANGELOG only** | Residual exposure accepted; the asymmetry is named in ADR-007 and the CHANGELOG carries the missing signal | ADR-007 |
| 6 | allow rules after the move | Contract | Keep or drop the scoped `Bash(codex exec:*)` / `Bash(agy …:*)` rules? | A keep, fix agy order / B drop / C keep both orders | **A — keep, fix agy order** | Manual diagnosis stays one-approval; the corrected rule stops pre-approving a command shape that cannot work | ADR-006 |
| 7 | Validation depth | Risk tolerance | Both validator passes returned MAJOR_REVISION with determined-answer defects — proceed, self-certify, or split? | A fix all + third pass / B fix all, no further validation / C split H3 into its own task | **A — fix all + third pass** | Findings rose 3→4 criticals between passes; C4 (codex prompt delivery) is invisible to execute's own gates, so another pass is cheaper than discovering it at review | — |

**Post-validation revisions without an interview round.** Both validator passes returned
MAJOR_REVISION. None of the 21 critiques opened a decision with more than one defensible answer —
each is a missing branch, an unspecified mechanism, an arithmetic inconsistency, or an assertion
that cannot fail. Under the interview gate's common-ground term they were resolved by revision and
recorded in the ADR each amends. Two contract changes that *did* have real alternatives were settled
by evidence rather than by asking: the ledger `stage` enum (no Python consumer reads
`SecondOpinionRecord`, so widening breaks no strict reader — though the shipped JSON asset does need
widening too), and whether grandfathered slugs bypass the character class as well as the length cap
(`_HEADING_RE` captures the slug as `\S+`, so `_` and `.` re-parse cleanly).

**Evidence gathered before and during planning** (investigated, not asked):

- `.claude/schemas/` is matched by `.gitignore`'s `.claude/*` — verified with `git check-ignore -v`.
  The worktree therefore *cannot* contain it, and by the same rule neither can `.claude/harness.yaml`.
- `agy` help output is Go-`flag`-style; `--prompt` is documented as "Alias for `--print`", which is
  only coherent if `--print` takes a value. Probe P1 `agy --sandbox --print "Reply with exactly:
  PONG1"` → `PONG1`. Probe P2 `agy --sandbox --print --print-timeout 60s < file` → answered *about
  `--print-timeout`*, exit 0, stdin unread.
- `getconf ARG_MAX` = 2 097 152, but the binding limit is `MAX_ARG_STRLEN` = 131 072 **bytes** for a
  single argument.
- `HarnessConfig`'s `output_schema_path` validator **rejects absolute paths** (`models.py:471-472`).
- `/hm:health` has no `task-preflight` step — it always runs at base. Its codex smoke uses the same
  relative path as the recipe and passes there. This is the mechanism by which a positive smoke
  validated a path the real invocation never takes.
- `codex_ledger.main()` calls `emit(record, project_root=Path.cwd())` (`codex_ledger.py:238`).
  `skip_reason` is `Field(default=None, max_length=500)` (`:48`) and `_append_atomic_line` raises
  above 4096 bytes (`:66-70`), both under `strict=True, extra="forbid"`.
- `SecondOpinionRecord.stage` is `Literal["review", "plan"]` (`codex_ledger.py:43`). No Python module
  reads `SecondOpinionRecord`. **But** the shipped asset
  `src/harness_maker/templates/schemas/second-opinion-ledger.schema.json:21` declares
  `"stage": {"enum": ["review", "plan"]}`, and `tests/unit/test_codex_ledger.py:123-136` compares
  property **names** only — invariant over enum values.
- `_SLUG_RE` is `[a-z0-9][a-z0-9-]{0,39}` and occurs at exactly two lines (`memory_md.py:35`, `:217`);
  argparse registers `--slug` with `required=True` and no validator (`:644`, `:649`).
  `_HEADING_RE` (`:28`) captures the slug as `\S+`.
- Two live wiki slugs violate `[a-z0-9-]` while sitting **under** the 40-char cap:
  `metrics-rotation-reader-via-_metrics_io` (39 chars, underscore) and
  `adr-supersession-precedent-v0.22.3` (34 chars, dots). `failures.md` has no such case.
- The current codex recipe delivers its prompt on **stdin** and reads findings back from the
  `--output-last-message` **file**: `codex exec … --output-last-message "$out_tmp" - < "$prompt_tmp"`
  (`second_opinion_codex.md.j2:49`).
- `agy --print --sandbox` is pinned by three existing unit tests:
  `test_render_second_opinion.py`, `test_codex_health_smoke.py`, `test_render_codex_permission_injection.py`.
  Only the first matches `test_render*.py`.
- `jsonschema` is **not** a project dependency (`pyproject.toml:38-46`).
- The shared finding schema requires `["severity","message","evidence","file","line"]` per item plus
  `["findings","summary","confidence"]` at the top, with `additionalProperties: false` at both levels.
  `codex_adapter` consumes only `severity` (direct index — `KeyError` if absent), `message`, `file`,
  `line`, `evidence`.
- `io_utils.load_harness_yaml(path)` exists (`io_utils.py:90`) and is the multi-document-safe reader
  the provenance-frontmatter format requires.
- `git worktree list --porcelain`'s first entry is the main worktree; run from both the base repo and
  a linked worktree it returned `/home/noel/harness-maker` in each case.
- **Live reproduction of the vacuous-vote class during this planning session**: agy returned a payload
  keyed `title/description/recommendation`; `adapt_antigravity_finding` reads `message`
  (`codex_adapter.py:85`); the adapter accepted the payload and produced seven findings with empty
  summaries.

---

## 📐 Architecture Decision Records

### ADR-001: Second-opinion CLI invocation moves from rendered prose to a Python module
**Status:** Accepted (2026-07-25, via /hm:plan interview; amended after two plan-validator passes)
**Context:** Both second-opinion CLIs are invoked by shell commands embedded in rendered stage
prompts. That shape has now produced four distinct silent-skip bugs, none of which any test could
catch, because a prose recipe has no execution surface: render tests can only grep for its text.
**Decision:** Add `harness_maker.second_opinion_invoke`. It resolves the base repo root **and the
harness config**, builds the argv list (no shell), **delivers the prompt over the channel each CLI
actually uses**, runs it under a timeout, and returns one structured JSON result. The rendered
recipes shrink to a single `uv run … python -m harness_maker.second_opinion_invoke --model <m>
--prompt-file <f> --slug <s> --stage <stage>` call.
**Consequences:**
- ✅ The cwd-relative path (H1), the flag arity (H2), and the permission-prefix fragility all become
  unit-testable properties of a function rather than untested text.
- ✅ A future CLI-contract change is a code change with a failing test, not a silent degrade.
- ✅ The invocation stops being duplicated between the stage recipe and the health smoke.
- ⚠️ **Approval-prompt equivalence, stated narrowly.** `Bash(uv:*)` is already present in both
  settings templates (`Production.json.j2:63`, `Side.json.j2:11`) and prefix-matches `uv run …`, so
  the move introduces no new *approval prompt* and grants no capability the allow list did not
  already grant.
- ⚠️ **Sandbox-escape widening — accepted, unverified.** The recipe that instructs the model to pass
  `dangerouslyDisableSandbox: true` is now attached to a generic `uv run` prefix rather than to the
  literals `codex exec` / `agy …`. Whether that widens the *unprompted* escape surface depends on how
  Claude Code gates `dangerouslyDisableSandbox` against `permissions.allow` — behaviour this repo has
  twice found to differ from its own documentation (the 2026-06-02 and 2026-07-17 corrections in
  CLAUDE.md). No oracle in this repo settles it. Recorded as an accepted, unverified risk rather than
  asserted as equivalent.
- ⚠️ **Schema fallback is split on default-vs-explicit.** When the configured `output_schema_path` is
  the shipped default and the file is absent, the invoker materialises the packaged asset (located
  via `importlib.resources`, not a repo-relative path, so an installed wheel works) into a temp file
  and proceeds. When the path is a **non-default, explicitly configured** value and the file is
  absent, the call is `skipped` with a reason naming the path. Falling back silently in the second
  case would convert a configuration error into a successful-looking vote against the wrong schema.
**Rejected alternatives:**
- *Minimal prose patch* — leaves both invocations as untestable prose and depends on `$(cat file)`
  surviving Claude Code's Bash permission prefix matching, which is unverified.
- *Hybrid (codex prose, agy module)* — permanently splits the two models' invocation paths.
**Source:** Interview #1; amended per validator pass 1 criticals 2 and 8, pass 2 critical C4 and
suggestion S3, and the codex second opinion.

---

### ADR-002: The invoker owns status classification and the ledger row, not just the call
**Status:** Accepted (2026-07-25, via /hm:plan interview; amended after two plan-validator passes)
**Context:** The current recipes ask the LLM to decide `invoked` vs `skipped` vs `failed` and to call
`codex_ledger emit` with the right value. The antigravity recipe spends a full paragraph warning
against the specific mistake of recording a parse failure as `skipped` — a warning that exists
because the judgment is subtle and the consequence (skip-rate inflated, failure-rate zeroed) is
invisible in the telemetry it corrupts.
**Decision:** `second_opinion_invoke` classifies the outcome itself (ADR-008), writes **exactly one
ledger row per invocation** rooted at the resolved base repo root, and emits one JSON object carrying
`{model, status, findings, reason}`. The recipe relays that object into `second_opinion_results`
without re-deriving anything.
**Row contract (all six branches):** one row, `finding_ref="n/a"`, `disposition="unresolved"`,
`status` = the classified status, `skip_reason` = the branch's reason string (`None` on `invoked`).
Per-finding disposition rows remain the stage's business, not the invoker's.
**Consequences:**
- ✅ The `skipped`/`failed` boundary becomes a tested matrix instead of prose the model may skim.
- ✅ The ledger can no longer be silently skipped when a stage is under context pressure.
- ✅ Ledger rows land in the **base repo's** `.claude/observability/`, not in the per-worktree,
  gitignored copy that `task-land` deletes. `codex_ledger.main()`'s existing
  `project_root=Path.cwd()` would have written calibration data into a directory scheduled for
  destruction — the invoker passes the resolved base root explicitly.
- ⚠️ **The skip-rate denominator changes by design, and this must be said rather than claimed away.**
  Today the ledger is written *only* on the degrade path — both templates' `emit` calls sit inside
  their "Skip relay" blocks (`second_opinion_codex.md.j2:70`, `second_opinion_antigravity.md.j2:81`)
  and the invoked path emits nothing — so every existing row **is** a skip. One row per invocation
  turns it into a file of invocations. An earlier revision asserted the opposite ("keeps skip-rate
  comparable"); that was factually wrong about the current templates. `/hm:health:105` cross-refs
  "per-model skip-rate", so Phase 3 must make that prose compute a rate over invocations and
  **exclude `stage="health"` rows**, which are structurally biased toward `invoked` (base cwd,
  trivial prompt) and would otherwise dilute the number every time a user runs a health audit.
  A per-finding row on the invoked path is still rejected — it would change the denominator a second
  time, and per-finding disposition is the stage's business.
- ⚠️ `SecondOpinionRecord.stage` widens from `Literal["review","plan"]` to include `"health"`, **and
  so does the shipped `second-opinion-ledger.schema.json` enum.** The Python half alone is not
  sufficient: the harness ships that schema to describe the very JSONL it writes, and
  `test_json_schema_matches_model_fields` compares property *names* only, so a widened `Literal`
  against a stale enum passes every existing test while the schema contradicts the rows the code
  writes. **Stakes, stated accurately:** `second-opinion-ledger.schema.json` exists only under
  `src/harness_maker/templates/schemas/` and is rendered into **no** user harness — its sole consumer
  is that parity test. So this is an in-repo contract, not a shipped one; there is no downstream
  validator to reject a `health` row. The widening is still required (the parity contract is real),
  but a reader should not go looking for a rendering surface that does not exist.
- ⚠️ Largest change surface of the three scope options; the invoker takes a hard dependency on both
  `codex_adapter` and `codex_ledger`.
- ⚠️ A ledger-write failure must not fail the invocation — it stays best-effort. Because it is
  swallowed, **the reason string must be budgeted before record construction** (ADR-008), or a
  verbose CLI failure produces a `ValidationError` on `max_length=500` and no row is written for the
  branch whose entire purpose is telling the operator why the model did not run.
**Rejected alternatives:**
- *invoke + adapt only* — leaves the most error-prone judgment where it cannot be tested.
- *thin wrapper* — preserves nearly the whole bug class.
- *No ledger row for health smokes* — rejected once the `Literal` widening was shown to break no
  reader; a smoke whose purpose is detecting silent degradation should leave a trace.
- *One row per adapted finding on the invoked path* — rejected: changes the skip-rate denominator.
**Source:** Interview #4; amended per validator pass 1 warnings 4 and 7, pass 2 critical C2 and
warnings W3 and W4.

---

### ADR-003: agy prompts are truncated on a reserved UTF-8 byte budget, with the invoker owning the envelope
**Status:** Accepted (2026-07-25, via /hm:plan interview; amended after two plan-validator passes)
**Context:** `agy` does not read stdin in print mode (probe P2), so the prompt must be an argv value.
Linux caps a single argument at `MAX_ARG_STRLEN` = 131 072 **bytes**.
**Decision:**
- `LIMIT = 100_000` bytes is the budget for the **whole** argv value.
- The invoker owns a module-level `AGY_OUTPUT_CONTRACT` constant — the JSON-only output instruction.
  It is appended to **every** agy prompt, truncated or not. The truncation marker is appended only
  when truncation fires.
- `BUDGET = LIMIT - len(AGY_OUTPUT_CONTRACT.encode()) - len(marker.encode())`. Truncation fires iff
  `len(body.encode("utf-8")) > BUDGET`; when it does, the body is sliced to `BUDGET` at a UTF-8
  character boundary, retaining the head.
- The rendered antigravity partial **stops instructing the model about output shape**; it says the
  invoker appends the output contract. There is one owner of that text, so there is no producer/
  consumer pair to drift.
**Why the envelope is unconditional:** the partial's instruction is today the *only* shape signal on
the agy path (`second_opinion_antigravity.md.j2:31-34` — agy has no `--output-schema`). Phase 3
deletes it. If the invoker appended the contract only on the truncation path, every ordinary-sized
agy prompt would ship with no shape instruction at all, agy would answer in prose, the fail-closed
parser would reject it, and **every non-truncated antigravity call would classify `failed`** — the
outcome ADR-008 explicitly rejects ("the same zero votes with better telemetry"). The `--smoke`
prompt would be affected too, making `/hm:health`'s antigravity check permanently red: a
silent-degradation detector inverted into a permanent false alarm.
**Consequences:**
- ✅ The total stays within `LIMIT` for every input, so `len(result.encode()) <= LIMIT` is
  satisfiable — an earlier revision specified "truncate to 100 000 then append", which cannot satisfy
  its own `<= 100_000` criterion.
- ✅ Every agy prompt carries the output contract, so the shape signal Phase 3 removes from the
  template is never absent.
- ✅ The output contract survives truncation. Without it, head-truncation deletes the JSON-only
  instruction whenever it sits at the end of the prompt file — which the old prose permitted — so agy
  returns prose and the fail-closed parser records `failed` on exactly the largest reviews.
- ✅ Byte measurement plus boundary-safe slicing prevents both `E2BIG` on multi-byte text (a
  100 000-**character** CJK prompt is roughly 300 000 bytes) and a mid-character split.
- ✅ Single-owner envelope avoids the drift class recorded in
  `[fail:design] producer-consumer-schema-drift-in-same-process-pipeline`.
- ⚠️ A defect located only in the truncated tail is missed. A recall loss, not a correctness loss:
  K=2 consensus means a missed antigravity finding costs a vote, never introduces a wrong one.
- ⚠️ `LIMIT` is a margin below the kernel limit, not a measured optimum; it is a named constant.
**Rejected alternatives:**
- *Graceful skip on oversize* — reproduces the "silent degrade on the normal path" pattern.
- *Summarise the diff first* — an extra LLM call whose quality becomes the ceiling on the vote's.
- *Character-count truncation* — measures the wrong quantity for the limit it defends against.
- *Envelope authored in the Jinja partial and copied into Python* — a producer/consumer pair with no
  parity test.
**Source:** Interview #2; amended per validator pass 1 warning 9 and pass 2 warning W1, plus
converging codex and antigravity findings.

---

### ADR-004: Pre-existing memory slugs bypass both the length cap and the kebab-case class
**Status:** Accepted (2026-07-25, via /hm:plan interview; amended after plan-validator pass 2)
**Context:** `_SLUG_RE = [a-z0-9][a-z0-9-]{0,39}` encodes two independent rules in one pattern: a
character class and a length cap. The corpus violates both. 45/123 failure and 49/185 wiki slugs
exceed 40 characters (max 65); two wiki slugs *under* the cap violate the character class
(`metrics-rotation-reader-via-_metrics_io`, `adr-supersession-precedent-v0.22.3`). The validator was
tightened on the writer after the corpus was written, with no migration and no read-side
reconciliation, so the writer and the corpus disagree about what a valid key is and the writer wins
by refusing.
**Decision:** Split the single pattern into two, and apply them by slug provenance:

| Pattern | Applies to | Value |
|---|---|---|
| `_SLUG_SAFE_RE` | **every** slug | `[^\s\]|]+` — no whitespace, `]`, or `\|` |
| `_SLUG_NEW_RE` | **new** slugs only | `[a-z0-9][a-z0-9-]{0,39}` (unchanged) |

A slug that already appears as an entry heading in the tier file is *existing* and is checked only
against `_SLUG_SAFE_RE`. Any other slug is *new* and must satisfy `_SLUG_NEW_RE`. Validation moves
inside the lock, after the file is read. This applies to **both** `upsert-failure` and `upsert-wiki`,
which share `_upsert`.
**Why `_SLUG_SAFE_RE` is the correctness floor:** `_HEADING_RE` (`memory_md.py:28`) captures the slug
as `\S+`, so `_` and `.` re-parse cleanly and are safe to grandfather. Whitespace would truncate the
captured slug; `]` would break the `[tier:category]` bracket; `|` would collide with the
`| date | count:N` meta field. Those three are the only characters that can corrupt the file, so they
are the only ones every slug must avoid.
**Consequences:**
- ✅ `count++` and therefore the `count>=3` escalation work for the whole existing failure corpus.
- ✅ In-place replacement works for the whole existing wiki corpus — including the two
  character-class violators, which length grandfathering alone does not reach. The first revision
  would have left them permanently unwritable while a 65-character test case passed.
- ✅ New slugs stay terse and kebab-case — the rule's original intent survives intact, because
  `_SLUG_NEW_RE` is byte-identical to today's `_SLUG_RE`.
- ✅ No migration and no rewrite of existing entries; the file is the source of truth about what is
  grandfathered.
- ⚠️ `_upsert` must be restructured so validation happens after the read rather than before it.
- ⚠️ The error message must distinguish "new slug fails kebab-case/length" from "slug contains a
  file-corrupting character", or the operator learns the wrong lesson.
**Rejected alternatives:**
- *Raise the cap to 80* — does not stop new slugs from growing, and does not reach the character-class
  violators at all.
- *Grandfather length only* — leaves 2 of 185 wiki entries unwritable while every stated criterion
  passes.
- *Grandfather everything including whitespace/`]`/`|`* — those characters silently corrupt the file
  on the next `_entry_headings` scan.
**Source:** Interview #3; wiki-path coverage added per validator pass 1 warning 14; character-class
split added per pass 2 critical C1.

---

### ADR-005: The `/hm:health` smoke calls the same entrypoint as the stage recipe
**Status:** Accepted (2026-07-25, via /hm:plan interview; consequence corrected after review)
**Context:** A positive smoke check already existed for exactly this failure mode, and it did not
catch H1. `/hm:health` has no worktree preflight, so it runs at the base repo where the relative
schema path resolves, while the real recipe runs inside a worktree where it does not. The smoke was a
*copy* of the command, so it could drift from the original in the one dimension that mattered.
**Decision:** The health smoke invokes `second_opinion_invoke --smoke --stage health --slug
health-smoke`. `--smoke` uses a module-level smoke prompt, so no prompt file has to be materialised
inside a health audit, and the fixed `health-smoke` slug keeps smoke rows out of the per-task
calibration keyspace.
**Consequences:**
- ✅ The copy-divergence is gone: the smoke and the recipe cannot drift, because they are the same
  code.
- ⚠️ **A smoke pass proves less than "the real path works", and the ADR says so.** `/hm:health` still
  runs from the base repo, where `resolve_base_root` hits its identity case. The smoke validates the
  shared invocation path *from the base*; it does **not** exercise the worktree branch of base-root or
  config resolution. That branch is carried by the Phase 2 tests (cwd set to a real linked worktree,
  including one driven through `main()`) and the Phase 4 manual check. A future contributor must not
  read a green `/hm:health` as proof the Production path works — that inference is what hid H1.
- ⚠️ The smoke still costs a real network round-trip per enabled model — unchanged, and required.
**Rejected alternatives:**
- *Keep a separate smoke command* — the direct cause of the bug being fixed.
- *Give the smoke a temp-worktree cwd* — considered; deferred as scope beyond the three bugs, and the
  gap it would close is explicitly named above rather than left implicit.
**Source:** Derived from Interview #1 + #4; consequence corrected per pass 1 warning 11; smoke
arguments pinned per pass 2 suggestion S1.

---

### ADR-006: Scoped allow rules are kept, with agy's corrected to the real argv grammar
**Status:** Accepted (2026-07-25, via /hm:plan interview)
**Context:** After ADR-001 the normal path is authorised by the pre-existing `Bash(uv:*)` rule, so the
scoped `Bash(codex exec:*)` and `Bash(agy --print --sandbox:*)` rules are no longer on the hot path.
The agy rule additionally pins a command prefix that **cannot work** — it pre-approves the exact
broken invocation.
**Decision:** Keep both scoped rules for manual debugging and probing, and change the agy rule to
`Bash(agy --sandbox --print:*)`.
**Consequences:**
- ✅ Manual `codex exec` / `agy` diagnosis stays one-approval, which matters because diagnosing a
  silent skip is precisely when an operator reaches for the raw CLI.
- ✅ The permission surface stops pre-approving a command shape that is known not to work.
- ⚠️ Two rules remain that the normal path no longer uses. The templates note that they are a
  debugging affordance, not the gate on the invoker — ADR-001's second ⚠️ records what the real gate
  now is.
- ⚠️ CLAUDE.md currently *states* that the rendered command must begin with `agy --print --sandbox`.
  That sentence becomes false and must change in the same unit of work, or the next contributor will
  restore the bug from the documentation.
**Rejected alternatives:**
- *Drop the scoped rules* — makes manual diagnosis require a permission prompt per attempt.
- *Allow both flag orders* — keeps pre-approving a broken shape.
**Source:** Interview #6

---

### ADR-007: Harnesses already rendered with the broken recipes are not detected
**Status:** Accepted (2026-07-25, via /hm:plan interview — accepted risk)
**Context:** A user harness rendered before this fix carries the broken recipes. Re-rendering via
`/harness-maker:make --update` picks up the fix, but nothing prompts the user to do so.
**Decision:** Ship the fix without a detector. The CHANGELOG carries the notice.
**Consequences:**
- ✅ No new health check, no forced overwrite of user-editable command files (which would conflict
  with the user-state-preservation contract in CLAUDE.md checkpoint 1).
- ⚠️ **Named residual exposure, asymmetric between the two models.** An un-re-rendered harness's *old*
  antigravity smoke fails visibly (its adapter step cannot parse agy's prose reply), so that user has
  a signal. The *old* codex smoke runs at base, where the relative path resolves, and passes — so a
  user whose codex vote is dead sees `status: skipped`, indistinguishable from "codex is not
  installed". They receive no signal to re-render.
- ⚠️ Mitigation folded into the decision: the CHANGELOG entry states the symptom explicitly — that a
  codex second opinion reporting `skipped` was this bug rather than a local CLI problem, and that
  re-rendering is the fix.
**Rejected alternatives:**
- *`/hm:health` detects the old recipe shape* — rejected by the user as scope the fix need not carry.
- *Forced re-render at make time* — conflicts with user-state preservation.
**Source:** Interview #5

---

### ADR-008: Status is a seven-way classification over exceptions, payload acquisition, and validity
**Status:** Accepted (2026-07-25, added per validator pass 1; extended per passes 2 and 3)
**Context:** The first draft specified three outcomes keyed on the exit code. Two independent defects
make that wrong under the design it belongs to.
First, the graceful-degrade contract inherits "CLI missing ⇒ exit 127" from CLAUDE.md — but 127 is a
**shell** artifact. Under the mandated `shell=False`, `subprocess.run(["agy", …])` on a missing binary
raises `FileNotFoundError`, `timeout=N` raises `TimeoutExpired`, a non-executable binary raises
`PermissionError`, and `text=True` can raise `UnicodeDecodeError` on non-UTF-8 output from a CLI whose
output shape is unenforced. None produces an exit code. `codex` has no native timeout flag, so
`TimeoutExpired` is its only hang guard.
Second, "parsed ⇒ invoked" accepts a payload that parses as JSON but carries nothing usable —
reproduced live during this planning session.
**Decision:** Classify over six branches, in order:

| # | Condition | Status | Reason string |
|---|---|---|---|
| 1 | `FileNotFoundError` from `subprocess.run` | `skipped` | `"CLI not installed: <binary>"` |
| 2 | `subprocess.TimeoutExpired` | `skipped` | `"timeout after <N>s"` |
| 3 | Any other exception from `subprocess.run` | `skipped` | `"<ExceptionType>: <first 200 chars>"` |
| 4 | Non-zero exit | `skipped` | `"exit <code>: <last 300 chars of stderr, newlines collapsed>"` |
| 5 | Exit 0, the payload could not be **acquired** | `failed` | `"payload unreadable via <channel>: <why>"` |
| 6 | Exit 0, payload acquired but fails `validate_payload` | `failed` | `"payload did not validate: <why>"` |
| 7 | Exit 0, payload validates | `invoked` | `None` |

**The try-block for branches 1–3 wraps the CLI `subprocess.run` and nothing else** — with one
addition found during Phase 2's test-quality gate: `resolve_base_root` **also** shells out
(`git worktree list --porcelain`), and that call sits outside every branch as first drafted. A
machine without `git`, or with a non-executable one, would raise `FileNotFoundError` /
`PermissionError` straight out of `invoke` before any branch could fire — breaking the never-block
contract in the module whose whole purpose is to hold it. The resolution helpers are therefore
wrapped too, and the outcome is **`invoked`, not `skipped`**: an exception from the git probe falls
back to `cwd` and the call **proceeds**. That is the same answer `resolve_base_root` already gives
for a non-git directory — a missing `git` binary is operationally the identical situation, there is
no base root to find and `cwd` is the answer. Skipping instead would cost a git-less container
100 % of its votes with a `skipped` status, which is precisely the silent-skip-on-the-normal-path
class this PLAN exists to delete.
The `skipped` arm is scoped narrowly to the case where resolution still cannot produce a usable
configuration — concretely, `load_config` raising on a corrupt base `harness.yaml` — with reason
`"config load failed: <ExceptionType>"`. This is deliberately NOT branch 1's `"CLI not installed"`
string: a broken config and a missing `codex` are different operator actions.

> **Drafting note.** The first version of this paragraph named *both* outcomes for the *same*
> condition ("degrades to `skipped` … and proceeds against `cwd` only if that still yields a usable
> root"). Two equally literal readings gave opposite implementations, so the ADR was unimplementable
> as written and the Phase 2 test that pinned `invoked` looked like an over-pin. Caught at the Phase
> 2 test-quality gate; the test was right and this document was wrong.

Branch 5 is a separate guard around payload acquisition, which is where the two documented raising
helpers live:
`extract_antigravity_payload` raises `ValueError` by contract on any non-single-JSON output (its
docstring makes turning that into `failed` the caller's job), and the codex path `json.loads`es the
`--output-last-message` file, which the invoker creates with `mktemp` — so it **exists** but may be
empty when codex exits 0 having written nothing, giving `JSONDecodeError`.
Keeping the scopes separate is load-bearing: widening branch 1's `except FileNotFoundError` to cover
the file read would make a missing out-file report `"CLI not installed: codex"`, the single most
operator-misleading string in the table, and branch 1 would then shadow a payload failure.
An agy prose reply is the **most common** antigravity degrade, since agy has no CLI-level schema
enforcement — without branch 5 it propagates as a traceback and breaks the never-block contract.

Every reason string is truncated to **400 characters** before record construction, below
`skip_reason`'s `max_length=500` and well below the 4096-byte line cap.

**Ordering note (empirical):** `agy` prints an error and still exits 0 (probed 2026-07-25 with an
invalid `--model`). Branch 4 therefore fires rarely on the agy path; branches 5 and 6 are its
primary gates. This is a reason to keep both, not to merge them.

**`validate_payload` runs BEFORE `codex_adapter.adapt_*`, never after.** `map_severity` raises
`ValueError` on any severity outside the shared vocabulary (`codex_adapter.py:41-47`) and
`adapt_*_finding` indexes `finding["severity"]` directly (`:61`, `:91`). Adapting first would let an
out-of-vocabulary severity raise out of the invoker before the classifier could reject it cleanly —
which is the whole reason `validate_payload` requires `severity` at all.
**`validate_payload` is defined as the adapter-consumable surface, deliberately laxer than
`--output-schema`'s strict shape:** the payload must be a dict with a `findings` key whose value is a
list, and every item must be a dict carrying a `severity` in the shared enum **after the same
`.strip().lower()` normalization `map_severity` applies** (`codex_adapter.py:43` — a literal
membership test would reject `"Critical"` or `" high "`, plausible from an unenforced model, even
though the adapter would consume them) and a non-empty `message`. `additionalProperties` is **not**
enforced and the other schema-required fields (`evidence`, `file`, `line`, `summary`, `confidence`)
are **not** required. It is a hand-rolled
predicate — `jsonschema` is not a dependency and adding one to gate a graceful-degrade path would be
disproportionate.
**Why exactly that surface:** `codex_adapter.adapt_*_finding` indexes `finding["severity"]` directly
(a `KeyError` crash on absence) and reads `message` via `.get("message","")` (an empty summary on
absence). Requiring those two fields is what prevents both the crash and the vacuous-vote. Enforcing
the *full* schema instead would classify most genuine agy replies as `failed` — agy has no CLI-level
schema enforcement, so a reply omitting `evidence` is normal — which would turn H2's fix from
"silently vacuous votes" into "loudly failed votes", the same zero votes with better telemetry.
**Consequences:**
- ✅ The never-block contract holds for every way `subprocess.run` can fail, not just the two most
  obvious ones. Branch 3 is a terminal catch-all, but branches 1 and 2 stay separately named, so the
  two operator-actionable cases are still distinguishable — this is not the rejected "one bucket".
- ✅ It also holds for the **payload-acquisition** region, which branches 1–3 deliberately do not
  cover. That region was uncovered until pass 3: the per-model read channel introduced to fix the
  prompt-delivery defect is itself a place two documented helpers raise.
- ✅ A vacuous vote can no longer be recorded as a successful one.
- ✅ The `skipped`/`failed` split stays meaningful: `skipped` means the call could not run or could
  not complete, `failed` means it ran and returned something unusable.
- ✅ The budgeted reason string means branch 4's row is actually written. Unbudgeted, a verbose CLI
  failure would raise `ValidationError` on `max_length=500`, be swallowed by the best-effort wrapper,
  and leave no row for the noisiest, most diagnosable failures.
- ⚠️ A genuine reply that omits `message` is `failed`. Accepted: a finding with no message is not
  usable by the Step 4 filter, so counting it as a vote would be the vacuous-vote bug again.
- ⚠️ Every branch needs its own test. An assertion that merely checks "status is one of the legal
  values" is invariant over the dimension it claims to cover.
- ⚠️ **A golden-argv assertion cannot see prompt delivery.** argv can be perfectly correct while the
  prompt never reaches the process (see ADR-001's delivery decision and Phase 2's call-kwargs
  criterion). This is the third instance of `assertion-invariant-over-named-dimension` in this work.
**Rejected alternatives:**
- *Three-way matrix over exit codes* — wrong under `shell=False`, and accepts vacuous payloads.
- *Only `FileNotFoundError` + `TimeoutExpired` wrapped* — leaves `PermissionError`,
  `UnicodeDecodeError`, and other `OSError`s propagating as tracebacks, breaking the contract at the
  case it exists for.
- *Catch every exception into one undifferentiated `skipped`* — loses "not installed" vs "hung",
  which the operator acts on differently.
- *Full shared-schema validation* — turns most real agy replies into `failed`.
**Source:** validator pass 1 criticals 1 and 3; pass 2 critical C3 and warnings W2 and W4; codex
second opinion (`codex_adapter.py:91`).

---

## 🏗️ Technical Design

### Current state

```
stage prompt (prose) ──Bash──> codex exec … --output-schema <relative> --output-last-message F - < P
                     ──Bash──> agy --print --sandbox … < prompt_file     [--print eats --sandbox]
health prompt (prose) ─Bash──> same two commands, copied                 [cwd=base — passes]
LLM ────────────────────────> decides invoked/skipped/failed, calls codex_ledger emit
```

### Target state

```
stage prompt  ─┐
               ├── Bash ──> uv run … -m harness_maker.second_opinion_invoke
health prompt ─┘              --model {codex|antigravity} --prompt-file F --slug S --stage T
                                   │
                                   ├── resolve_base_root(cwd)   git worktree list --porcelain [0]
                                   │                            → git rev-parse --show-toplevel → cwd
                                   ├── load_config(base_root)   io_utils.load_harness_yaml
                                   ├── resolve_schema_path(...) absolute; default→packaged asset via
                                   │                            importlib.resources,
                                   │                            explicit-and-missing→skipped
                                   ├── truncate_prompt(...)     agy only; reserved UTF-8 byte budget
                                   ├── build_argv(...)          list[str], no shell
                                   ├── subprocess.run(timeout)  codex: input=<prompt>; agy: no stdin
                                   ├── read payload             codex: --output-last-message file
                                   │                            agy:   captured stdout
                                   │                            (guarded — ADR-008 branch 5)
                                   ├── validate_payload(...)    adapter-consumable surface
                                   ├── adapt_*(...)             ONLY after validation
                                   ├── classify(...)            7 branches (ADR-008)
                                   ├── codex_ledger.emit(project_root=base_root)   1 row, best-effort
                                   └── stdout: {model, status, findings, reason}
```

### Affected components

| Component | Change |
|---|---|
| `src/harness_maker/second_opinion_invoke.py` | **new** — the whole invocation contract |
| `src/harness_maker/command_registry.py` | register `second_opinion_invoke` as `ModuleSpec("flagonly")` |
| `src/harness_maker/memory_md.py` | `_upsert` restructured; `_SLUG_RE` split into safe/new patterns |
| `src/harness_maker/codex_ledger.py` | `SecondOpinionRecord.stage` gains `"health"` |
| `src/harness_maker/templates/schemas/second-opinion-ledger.schema.json` | `stage` enum gains `"health"` |
| `tests/unit/test_codex_ledger.py` | name-only parity test extended to enum values |
| `src/harness_maker/templates/agents/_partials/second_opinion_codex.md.j2` | recipe → invoker call |
| `src/harness_maker/templates/agents/_partials/second_opinion_antigravity.md.j2` | recipe → invoker call; output-contract instruction removed (ADR-003) |
| `src/harness_maker/templates/commands/hm/health.md.j2` | smoke calls the invoker |
| `src/harness_maker/templates/settings/{Production,Side}.json.j2` | agy allow rule reordered |
| `tests/unit/test_render_second_opinion.py`, `test_codex_health_smoke.py`, `test_render_codex_permission_injection.py` | assertions updated off the old agy shape |
| `tests/integration/test_antigravity_sandbox_probe.py` | argv corrected — it currently builds `["agy","--print","--sandbox",…]` with `input=prompt`, so the probe never exercised `--sandbox` |
| `tests/manual/ANTIGRAVITY_SANDBOX_PROBE.md` | documented command corrected; the re-scoped evidence noted |
| `CLAUDE.md` | the `agy --print --sandbox` prefix requirement is now false |
| `CHANGELOG.md` | carries the ADR-007 signal |

### Dependencies

No new third-party dependencies. `second_opinion_invoke` depends on `codex_adapter`, `codex_ledger`,
`io_utils.load_harness_yaml`, `models.SecondOpinionConfig`, and `importlib.resources`.

### Design decisions

- **Base-root resolution** (ADR-001) branches on whether cwd is a **linked worktree**, measured as
  `git rev-parse --git-dir != --git-common-dir`. If it is, take the first entry of
  `git worktree list --porcelain` (the main worktree by git's definition); otherwise take
  `git rev-parse --show-toplevel`. Any failure — including a missing `git` binary — falls back to
  the cwd.

  Two earlier formulations were wrong, each measured rather than reasoned:
  the **parent of `--git-common-dir`** holds only when the git dir sits inside the checkout, and
  breaks under `git init --separate-git-dir`, inside submodules, and with an external
  `GIT_COMMON_DIR`; **porcelain-first unconditionally** — this PLAN's own second draft — is wrong for
  the same layout, because under `--separate-git-dir` porcelain's first entry is the *external git
  dir*, not the checkout. Observed 2026-07-25: base checkout and separate-git-dir both report
  `--git-dir == --git-common-dir`, and only a linked worktree reports them different, so that
  equality is exactly the "am I the main worktree" test.
- **Config resolution** (ADR-001) loads `<base_root>/.claude/harness.yaml` through
  `io_utils.load_harness_yaml` — never cwd-relative. A worktree has no `.claude/` at all when the
  project gitignores it, so a cwd-relative load would either silently fall back to model defaults (a
  user's configured `antigravity.model` replaced by the default while reporting `invoked` — H2's shape
  in the config dimension) or hard-fail on every worktree call (H1's shape). A missing `harness.yaml`
  **at the base root** is a real configuration absence and uses model defaults.
- **Prompt delivery, per model** (ADR-001) — the channel each CLI actually uses, not a shared
  assumption:
  - **codex**: prompt passed as `input=<prompt text>` to `subprocess.run`, with the `-` positional in
    argv. Findings are read back from the `--output-last-message` temp file the invoker creates, not
    from stdout.
  - **agy**: prompt is the value of `--print` in argv; no stdin is used. Findings are the captured
    stdout.
  Specifying this is not optional detail: `subprocess.run(argv, capture_output=True, text=True)` with
  no `input=` gives codex an inherited stdin that hits EOF, so `codex exec … -` receives an **empty
  prompt** and returns exit 0 with an empty payload — the codex vote dead again for the identical
  reason it is dead today, with the golden-argv test still green.
- **Golden argv, stated here so the tests derive from the CLI contract rather than from the code:**
  - codex, hermetic (the default):
    `["codex", "exec", "--sandbox", "read-only", "--ignore-user-config", "--ignore-rules",
    "--output-schema", "<abs schema>", "--output-last-message", "<abs out tmp>", "-"]`
  - codex, `hermetic: false`: the same list without `--ignore-user-config --ignore-rules`.
  - agy: `["agy", "--sandbox", "--print", "<prompt text>", "--print-timeout", "240s", "--model",
    "<configured model>"]`
  **Probed 2026-07-25 (P3), because the trailing flags sit AFTER a value-consuming flag and that
  parse behaviour was an assumption — exactly the class this PLAN exists to remove.**
  `agy --sandbox --print "…" --model "definitely-not-a-real-model-xyz"` and the same with `--model`
  placed *before* `--print` produced the **identical** "invalid model selection" error, so agy does
  continue parsing after `--print`'s value and the trailing `--print-timeout` / `--model` take
  effect. P4 confirmed the configured display name works:
  `agy --sandbox --print "Reply with exactly: PONG" --model "Gemini 3.1 Pro (High)"` → `PONG`.
  Had this gone the other way, the hang guard would have vanished and the user's configured model
  would have been silently replaced by agy's default while still reporting `invoked`.
- **Schema resolution** (ADR-001) joins the config's relative `output_schema_path` onto the base root.
  Missing **default** path → materialise the packaged asset via `importlib.resources` into a temp file
  and proceed. Missing **explicitly configured** path → `skipped` with a reason naming the path.
- **No shell** (CLAUDE.md implementation patterns): argv is a `list[str]`, `shell=False`, `timeout`
  mandatory. **Timeout values are named constants: `CODEX_TIMEOUT_S = 300`, `AGY_TIMEOUT_S = 300`.**
  agy's is deliberately *above* its native `--print-timeout 240s` so the native timeout fires first
  and the graceful path stays branch 4 (agy's own non-zero exit and diagnostic) rather than branch 2
  (our wrapper's, which names the wrong cause). codex has no native timeout, so the process-level
  value is its only hang guard — an unbounded stall in a mandatory Production stage otherwise.
  CLAUDE.md's invariant "external `timeout` 래퍼 금지" was justified by allow-rule prefix matching,
  which no longer applies after ADR-001; Phase 4 amends it to say the process-level timeout is the
  outer backstop, not the forbidden shell wrapper.
- **Status classification** — ADR-008's six-branch table, with `validate_payload` as defined there.
- **Ledger** (ADR-002): exactly one row per invocation via
  `codex_ledger.emit(record, project_root=<resolved base root>)`, never `Path.cwd()`.
- **Truncation** (ADR-003) applies to the antigravity path only. Codex receives its prompt on stdin,
  which has no argv limit.
- **Grandfathering** (ADR-004): the existing-slug set is derived from `_entry_headings` inside the
  lock; `_SLUG_SAFE_RE` applies to all slugs, `_SLUG_NEW_RE` only to new ones.
- **Public names the tests pin (this list is the contract; the PLAN must not contradict it).**
  `AGY_OUTPUT_CONTRACT`, `AGY_OUTPUT_CONTRACT_EXAMPLE` (a parseable JSON example embedded verbatim in
  the contract, so the producer/consumer parity is checkable), `PROMPT_LIMIT_BYTES` (the `LIMIT`
  referred to in ADR-003), `TRUNCATION_MARKER_PREFIX`, `SMOKE_PROMPT`, `DEFAULT_ANTIGRAVITY_MODEL`,
  `CODEX_TIMEOUT_S`, `AGY_TIMEOUT_S`, exceptions `SecondOpinionSkip` and `PayloadInvalid`, and
  `invoke(..., base_root=None)`. Two earlier naming divergences (`_AGY_OUTPUT_CONTRACT`,
  `_AGY_TIMEOUT_S`) would each have cost an execute cycle on an `AttributeError` that says nothing
  about behaviour.
- **`--root` has no argparse default.** When absent, `resolve_base_root(cwd)` is used; when present it
  wins. It is a test and debug affordance — **no rendered recipe passes it**. Giving it
  `default="."` would make "explicit wins" true of every invocation and reinstate H1 in full, while
  every function-level unit test still passed.

### Data flow

`stage prompt` writes the prompt file with the Write tool (verbatim bytes — the injection defence is
unchanged) → invoker reads it → agy path truncates with reserved budget and appends the envelope →
argv + per-model delivery channel → CLI → payload read from the model's own channel (guarded) →
`validate_payload` → **then** adapter → status → one ledger row at base root → single JSON line on
stdout → stage folds `findings` into Step 4 / Step 3.5. The validate-before-adapt order is pinned in
ADR-008 and is not interchangeable.

### API changes

- **New CLI**: `python -m harness_maker.second_opinion_invoke --model {codex,antigravity}
  (--prompt-file PATH | --smoke) --slug SLUG --stage {review,plan,health} [--root PATH]`.
  `--prompt-file` is required unless `--smoke` is given, in which case a module-level smoke prompt is
  used. Exits 0 in every graceful-degrade case (the JSON carries the status); non-zero only on
  invalid arguments.
- **`SecondOpinionRecord.stage`** widens to `Literal["review","plan","health"]`, **and the shipped
  `second-opinion-ledger.schema.json` `stage` enum widens to match.** No Python consumer reads the
  model, so no strict reader breaks; the JSON asset is the contract the harness ships about its own
  JSONL and must not contradict it.
- **`second_opinion_results` shape is unchanged** — one entry per enabled model, with
  `{model, status, reconciliation}`.
- **`memory_md` CLI surface is unchanged**; only which slugs are accepted changes, strictly in the
  permissive direction for existing slugs.

---

## 📝 Implementation Plan

### Phase 1 — Memory slug grandfathering — ✅ DONE

- **depends_on:** `[]`
- **parallel_group:** `independent-fixes`
- **merge_hazards:** none — touches `memory_md.py` and its tests only
- **Scope in:** `src/harness_maker/memory_md.py`, `tests/unit/test_memory_md*.py`
- **Scope out:** the memory tier files themselves (no rewrite, no migration — ADR-004)
- **Work:**
  1. Replace `_SLUG_RE` with `_SLUG_SAFE_RE` (`[^\s\]|]+`, all slugs) and `_SLUG_NEW_RE`
     (`[a-z0-9][a-z0-9-]{0,39}`, new slugs only).
  2. Move slug validation inside `exclusive_lock`, after `_locate_block` / `_entry_headings`.
  3. A slug present in the file's existing headings is checked only against `_SLUG_SAFE_RE`.
  4. Distinct error messages for "new slug fails kebab-case/length" and "slug contains a
     file-corrupting character".
- **Exit criterion:** `uv run pytest tests/unit/test_memory_md*.py -q` passes, with each case pinning a
  discriminating value:
  - (a) a 65-character slug already in `failures.md` receives `count++` — assert the count went from
    N to N+1, not merely that the call succeeded;
  - (b) a 65-character slug already in `wiki.md` is **replaced in place** — entry count unchanged,
    body replaced (the wiki path has no `count++`, so (a) cannot cover it);
  - (c) **the real character-class violators**: `metrics-rotation-reader-via-_metrics_io` (39 chars,
    underscore) already in `wiki.md` is accepted, and the same string as a **new** slug is rejected.
    A 65-character case cannot cover this — it is a length violator, and length grandfathering alone
    leaves these two entries unwritable;
  - (d) a 65-character slug **not** in the file is rejected, message naming the length rule;
  - (e) the new-slug boundary as a **pair**: 40 characters accepted, 41 rejected;
  - (f) a slug containing whitespace, `]`, or `|` is rejected **even when it already appears in the
    file** — `_SLUG_SAFE_RE` is the correctness floor, not a style rule;
  - (g) at least one case driven through `memory_md.main([...])`, not `_upsert` directly.
- **Risk:** low
- **Rollback:** revert this phase's commit; nothing on disk is modified, so the CLI simply returns to
  current behaviour.

### Phase 2 — `second_opinion_invoke` module — ✅ DONE

- **depends_on:** `[]`
- **parallel_group:** `independent-fixes`
- **merge_hazards:** `codex_ledger.py`, its shipped schema asset, and `test_codex_ledger.py` — a
  three-file cluster no other phase touches
- **Scope in:** `src/harness_maker/second_opinion_invoke.py`, `src/harness_maker/command_registry.py`,
  `src/harness_maker/codex_ledger.py`,
  `src/harness_maker/templates/schemas/second-opinion-ledger.schema.json`,
  `tests/unit/test_codex_ledger.py`, `tests/unit/test_second_opinion_invoke.py`
- **Scope out:** templates other than the ledger schema (Phase 3), `codex_adapter` internals
- **Work:**
  1. `resolve_base_root(cwd)` — porcelain-first with the two fallbacks.
  2. `load_config(base_root)` via `io_utils.load_harness_yaml`.
  3. `resolve_schema_path(base_root, cfg)` with the default-vs-explicit split; packaged asset via
     `importlib.resources`.
  4. `truncate_prompt(text, limit_bytes)` — reserved budget, UTF-8 byte measurement, boundary-safe
     slice, head retention, `AGY_OUTPUT_CONTRACT` envelope, marker line.
  5. `build_codex_argv(...)` / `build_agy_argv(...)` matching the golden lists in the design.
  6. `validate_payload(payload)` — the adapter-consumable surface from ADR-008.
  7. `invoke(...)` — per-model delivery (`input=` for codex, argv value for agy), payload read from
     the model's own channel, `subprocess.run(..., timeout=N)` wrapped for the ADR-008 branches with a
     terminal catch-all, reason budgeted to 400 chars, one best-effort
     `codex_ledger.emit(project_root=base_root)`.
  8. `main(argv)` — argparse CLI, `--root` with **no default**, `--smoke` mutually exclusive with
     `--prompt-file`, one JSON line on stdout.
  9. Widen `SecondOpinionRecord.stage` and the shipped ledger schema `stage` enum to include
     `"health"`.
  10. Extend `test_json_schema_matches_model_fields` to compare **enum values** for every `Literal`
      field, not only property names.
  11. Register the module in `command_registry.MODULES` as `ModuleSpec("flagonly")` — flag-only, so
      guard-exempt. `test_command_surface_gate.py:74-75` fails any rendered
      `python -m harness_maker.<module>` whose module is absent from the registry, so Phase 3's
      templates would turn T-C1 red the moment they land; registering it here, with the module rather
      than with its consumers, keeps that out of the phase with the widest snapshot churn. A
      subparser spec would instead trip T-C2's guard-wiring parity check.
- **Exit criterion:** `uv run pytest tests/unit/test_second_opinion_invoke.py tests/unit/test_codex_ledger.py -q`
  passes and `mypy --strict` is clean, with tests pinning:
  - **Golden argv** — the full `list[str]` compared as a whole, against the lists written in the
    Technical Design (which were derived from the CLI contract and the probe transcript, not from the
    implementation), for codex hermetic, codex non-hermetic, and agy.
  - **Prompt delivery** — assert the recorded `subprocess.run` **call kwargs**, not only argv: the
    codex call carries the prompt bytes in `input=`; the agy call carries no `input` and the prompt is
    argv element 3. A golden-argv assertion alone is invariant over this dimension.
  - **Payload channel** — codex findings are read from the `--output-last-message` file (write a
    payload there and assert it is adapted); agy findings are read from captured stdout.
  - **Base-root resolution** in five cases: base checkout, linked worktree, `--separate-git-dir`,
    nested cwd inside a subdirectory, non-git directory.
  - **Schema path** is `is_absolute()` and exists, asserted on the constructed argv with cwd set to
    both a base checkout and a linked worktree lacking `.claude/schemas/`.
  - **Config resolution** — a non-default `antigravity.model` and `codex.hermetic` set in the base
    `harness.yaml` survive when cwd is a linked worktree with no `.claude/` at all.
  - **Schema fallback split** — missing default path proceeds with the packaged asset; missing
    explicitly-configured path yields `skipped` with the path in the reason.
  - **Truncation, under budget** — a 90 000-byte body (safely under `BUDGET`) comes back with the
    body **byte-identical**, `AGY_OUTPUT_CONTRACT` **present**, no marker, and a total `<= 100_000`.
    The earlier "99 999 bytes is byte-identical to the input" phrasing was unmeetable under an
    unconditional envelope and would have pushed the implementer into appending the contract only on
    the truncation path — killing every ordinary agy call.
  - **Truncation, over budget** — a 130 000-byte body yields a total `<= 100_000` with the marker
    **and** `AGY_OUTPUT_CONTRACT` present; a non-ASCII prompt whose character count is under the
    limit but whose byte count is over it is truncated and never splits a character.
  - **Smoke prompt** — the `--smoke` prompt on the agy path yields a payload that passes
    `validate_payload`. If it does not, `/hm:health`'s antigravity check is a permanent false alarm.
  - **Status matrix, one test per ADR-008 branch**, each pinning a discriminating value:
    `FileNotFoundError` → `skipped`/"not installed"; `TimeoutExpired` → `skipped`/"timeout";
    `PermissionError` → `skipped` carrying the exception type (branch 3); exit 3 → `skipped` carrying
    the exit code; **agy exit 0 returning prose → `failed`** (branch 5) and **codex exit 0 with an
    empty `--output-last-message` file → `failed`** (branch 5) whose reason does **not** contain
    "not installed"; exit 0 with each of a bare list, `{"answer": …}`, and a
    `title/description/recommendation` payload → `failed` (branch 6); exit 0 with a conforming
    payload → `invoked`.
  - **Validate-before-adapt** — a payload whose `severity` is outside the shared vocabulary (e.g.
    `"blocker"`) classifies `failed` rather than raising `ValueError` out of the invoker. This is the
    only criterion that distinguishes the two pipeline orders.
  - **`validate_payload` laxness** — a finding carrying `severity` and a non-empty `message` but no
    `evidence`/`file`/`line` classifies `invoked`, not `failed`; and `severity: "Critical"` (mixed
    case, surrounding space) is accepted, matching `map_severity`'s normalization. Without these the
    fix converts vacuous votes into failed votes: the same zero votes.
  - **Reason budget** — a 5 000-character stderr on branch 4 still produces a **written** ledger row
    (assert the row exists and its `skip_reason` is ≤400 chars), not a swallowed `ValidationError`.
  - **Ledger** — exactly one row per invocation; its `finding_ref` is `"n/a"` and `disposition` is
    `"unresolved"`; the written path is under the base root when cwd is a worktree; a write failure
    leaves the returned status unchanged; a `stage="health"` row is accepted by both the model and the
    shipped JSON schema.
  - **End-to-end through `main()`** — cwd inside a real linked worktree, **no `--root`**, assert the
    schema path is absolute-under-base and the ledger lands under the base root. Every other criterion
    here is function-level and would pass an argparse mis-wire that reinstates H1.
- **Risk:** medium — new subprocess surface; base-root resolution and prompt delivery are the two
  pieces that can be wrong in ways tests must deliberately reproduce rather than assume.
- **Rollback:** revert this phase's commit; nothing references the module yet.

### Phase 3 — Template rewiring — ✅ DONE

- **depends_on:** `[1, 2]`
- **parallel_group:** `serial-3`
- **merge_hazards:** both settings templates and every rendered snapshot under `tests/` — snapshot
  regeneration touches many files at once
- **Scope in:** the two `second_opinion_*` partials, `health.md.j2`, both settings templates, snapshot
  fixtures, and the **five** existing artifacts that pin the old agy shape —
  `tests/unit/test_render_second_opinion.py`, `tests/unit/test_codex_health_smoke.py`,
  `tests/unit/test_render_codex_permission_injection.py`,
  `tests/integration/test_antigravity_sandbox_probe.py`, `tests/manual/ANTIGRAVITY_SANDBOX_PROBE.md`.
  The last two are **invisible to the full-suite criterion** — the integration file is double-gated on
  `INTEGRATION` and on `agy` being present, so a default `pytest` run skips it and reports green.
  That is this repo's own `[fail:test] integration-gated-test-stale-after-behavior-flip`, so they are
  named here rather than left to the criterion.
- **Scope out:** `harness.yaml` schema (unchanged), `models.py` (unchanged)
- **Work:**
  1. Replace the raw CLI block in both `second_opinion_*.md.j2` partials with the invoker call, keeping
     the Write-tool prompt-file step and the `dangerouslyDisableSandbox` note, and noting that the
     scoped allow rules are a debugging affordance (ADR-006).
  2. Remove the output-shape instruction from the antigravity partial — the invoker owns it (ADR-003).
  3. Point the `health.md.j2` smoke at `--smoke --stage health --slug health-smoke` (ADR-005), and
     make its ledger cross-ref (`health.md.j2:105`) compute a rate over **invocations** while
     excluding `stage="health"` rows (ADR-002).
  4. Reorder the agy allow rule in both settings templates (ADR-006).
  5. Update all five existing artifacts off the old shape; regenerate snapshots. The sandbox probe's
     argv becomes `["agy", "--sandbox", "--print", <prompt>]` with no `input=`.
- **Exit criterion:** the **full** `uv run pytest` is GREEN — not a `test_render*.py` subset.
  `test_codex_health_smoke.py` asserts the exact old string and does not match that glob, so a subset
  criterion would declare this phase complete against a red tree and push the diagnosis into Phase 4.
  In addition:
  - a render-grep asserting **no** rendered artifact contains `agy --print --sandbox`;
  - a render-grep asserting no rendered artifact contains a stdin-redirected `agy` invocation;
  - a rendered `settings.json` contains `Bash(agy --sandbox --print:*)`.
  - **Not** a grep for a non-absolute `--output-schema`: under the target design that flag never
    appears in rendered output, so such a check passes unconditionally even when the Python builds a
    relative path. The absoluteness gate lives on the constructed argv in Phase 2.
- **Risk:** medium — snapshot churn is wide; a missed rendered surface is the documented
  `enumeration-tests-not-updated-with-new-rendered-artifact` failure mode.
- **Rollback:** revert to Phase 2's tip; the module is inert without the templates.

### Phase 4 — Regression fences, docs, and live verification — ✅ DONE

**Live verification result (2026-07-25, run from inside `.worktrees/second-opinion-invocation-and-slug-cap/`):**

| model | result |
|---|---|
| codex | `{"model": "codex", "status": "invoked", "findings": [], "reason": null}` |
| antigravity | `{"model": "antigravity", "status": "invoked", "findings": [], "reason": null}` |

Both ledger rows landed under the **base** repo (`/home/noel/harness-maker/.claude/observability/second-opinion.jsonl`) with `stage: "health"`, `finding_ref: "n/a"`, `disposition: "unresolved"` — one row per invocation — and **no** ledger was created inside the worktree. This is the same command, from the same directory, that produced a `skipped` codex vote and a vacuous antigravity vote before the change.

- **depends_on:** `[3]`
- **parallel_group:** `serial-4`
- **merge_hazards:** `CLAUDE.md`, `CHANGELOG.md` — both are edited by wrapup as well, so this phase
  must land before wrapup runs
- **Scope in:** `CLAUDE.md`, `CHANGELOG.md`, the producer-gate test, live smoke evidence
- **Scope out:** memory tier files (wrapup owns those)
- **Work:**
  1. Correct the CLAUDE.md sentence requiring the command to begin with `agy --print --sandbox`
     (ADR-006), and the second-opinion invariant list to name the invoker as the single path. Also:
     (a) record that the pre-fix sandbox probe ran with `--sandbox` **consumed as `--print`'s value**,
     so the ADR-012 safety evidence verified a command that never had `--sandbox` in effect — the
     corrected shape is strictly more restrictive, so no new exposure follows, but the standing
     evidence must be re-scoped rather than silently reused; (b) amend the "external `timeout` 래퍼
     금지" invariant to say the process-level timeout is the outer backstop (its allow-rule-prefix
     justification no longer applies after ADR-001).
  2. CHANGELOG entry carrying the ADR-007 signal in explicit symptom terms.
  3. Producer-gate test that fails if any template reintroduces a stdin-fed agy call or the old flag
     order.
  4. Live verification: run the invoker for both models from **inside** the task worktree and record
     the returned JSON.
- **Exit criterion — two halves, only the first gates the phase:**
  - **Blocking (automated):** full `uv run pytest` GREEN; `ruff check`; `ruff format --check`;
    `mypy --strict` clean; the producer-gate test present and demonstrated failing against a
    deliberately reverted template.
  - **Non-blocking (recorded evidence):** the invoker run from inside `.worktrees/<slug>/` for each
    enabled model, with its returned JSON recorded in the phase notes. `status: invoked` with a
    non-empty adapted payload is the expected result. **A `skipped` caused by an uninstalled CLI, an
    expired login, or a rate limit is an acceptable outcome and is recorded as such** — evidence about
    the environment, not a regression. Only a `failed`, or a `skipped` whose reason names our own
    invocation, is a regression.
- **Risk:** low for the code. The live check depends on both external CLIs being logged in; the
  two-half criterion is what keeps that dependency out of the gate.
- **Rollback:** revert to Phase 3's tip.

---

## 🧪 Testing Strategy

**Unit — memory (`test_memory_md*.py`)**
The seven cases in Phase 1's exit criterion, each pinning a discriminating value. The new-slug
boundary is tested as a **pair** (40 accepted / 41 rejected), because a single-sided assertion cannot
distinguish a cap of 40 from a cap of 80. Case (c) uses the two **real** corpus slugs rather than a
synthetic 65-character one, because a length violator cannot detect a character-class regression.

**Unit — invoker (`test_second_opinion_invoke.py`)**
Golden-argv comparison against lists derived from the CLI contract; **call-kwargs assertions for
prompt delivery**, which the golden argv structurally cannot cover; payload-channel tests per model;
five-case base-root resolution; schema-path absoluteness from two cwds; config survival from a linked
worktree; the fallback split; the truncation budget with a multi-byte case; one test per ADR-008
branch; the `validate_payload` laxness case; the reason budget; the ledger row's values, cardinality,
and location; and one end-to-end `main()` case with no `--root`.

**Render / producer gate**
A grep over every rendered artifact asserting the broken agy shapes cannot come back. This makes
*that* half of the fix durable. The schema-path half is **not** expressible as a render grep after
this change — the flag leaves rendered output entirely — so it is enforced on the constructed argv in
Phase 2 instead. Stating this explicitly matters: an earlier draft claimed the render grep as "the
mechanism that makes the fix durable" when half of it could never fail.

**Ledger contract parity**
`test_json_schema_matches_model_fields` is extended from property **names** to enum **values**. In its
current form it is invariant over exactly the dimension ADR-002 changes, so the shipped schema could
declare the harness's own rows invalid with the suite green.

**Integration**
Guarded by `INTEGRATION=1`: invoke each model end-to-end and assert a validating payload. Skipped by
default, matching the existing external-CLI test policy.

**Manual**
From inside `.worktrees/<slug>/`, run each model's invoker and record the result. This is the check
that would have caught H1 on day one, and the one the prior positive smoke structurally could not
perform — see ADR-005 for why `/hm:health` alone still cannot.

---

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Prompt never reaches codex (no `input=`) | medium | high — the codex vote dies again, golden-argv green | Per-model delivery stated in the design; Phase 2 asserts call kwargs, not just argv |
| Base-root resolution wrong in a non-standard git layout | medium | high — schema, config, and ledger all bind to the wrong directory | Porcelain-first algorithm; five-case test list |
| `--root` given an argparse default | medium | high — reinstates H1 in full with every unit test green | No default, stated in the design; end-to-end `main()` case with cwd in a worktree |
| An unhandled `subprocess.run` exception | medium | high — traceback instead of JSON, never-block contract breaks | ADR-008 branch 3 terminal catch-all; `PermissionError` test |
| An agy prose reply or an empty codex out-file raises out of the invoker | high | high — the most common agy degrade crashes the stage | ADR-008 branch 5 guards payload acquisition separately from the call; both cases pinned |
| Envelope appended only on the truncation path | medium | high — every ordinary agy call returns prose → `failed`, health smoke permanently red | Envelope unconditional (ADR-003); under-budget criterion asserts its presence |
| Adapt runs before validate | medium | high — out-of-vocabulary severity raises instead of degrading | Order pinned in ADR-008 and both diagrams; a dedicated criterion |
| Timeout value unset or below agy's native 240 s | medium | medium — wrapper reports the wrong cause, or codex stalls unbounded | Named constants, agy's above its native timeout; CLAUDE.md invariant reconciled in Phase 4 |
| `second_opinion_invoke` unregistered in `command_registry` | high | low — T-C1 red in the widest-churn phase | Registered in Phase 2 with the module, `ModuleSpec("flagonly")` |
| A schema-mismatched payload records as a successful vote | medium | high — calibration data silently corrupt | Fail-closed `validate_payload`; three wrong-shape payloads pinned to `failed` |
| `validate_payload` too strict | medium | medium — antigravity votes flip from vacuous to `failed`, still zero | Laxness defined as the adapter-consumable surface; a test pins that a missing `evidence` is `invoked` |
| In-repo ledger schema contradicts the rows written | medium | low — the parity test is the only consumer; the schema ships to no harness | Enum widened in the same phase; parity test extended to enum values |
| Skip-rate becomes non-comparable across the change boundary | high | medium — the health cross-ref reads a number that moved for unrelated reasons | Denominator change stated in ADR-002; Phase 3 rewrites the cross-ref prose and excludes health rows |
| Verbose CLI failure loses its ledger row | medium | medium — skip-rate under-counts the most diagnosable failures | Reason budgeted to 400 chars before record construction; 5 000-char stderr test |
| Config read cwd-relative | medium | high — silent wrong-model votes or universal skip | Config loaded from base root only; test with a worktree lacking `.claude/` |
| Snapshot regeneration misses a rendered surface | medium | medium — a stale artifact keeps the broken command | Producer-gate grep over *all* rendered output; Phase 3 gated on the full suite |
| Truncation drops the output contract | medium | medium — the vote dies on the largest reviews | Envelope owned by the invoker and appended after truncation; asserted present |
| `MAX_ARG_STRLEN` differs on another platform | low | medium | 100 000 bytes is a margin below the Linux value; `E2BIG` surfaces as branch 3 or 4, never a crash |
| The `agy` argv grammar changes again upstream | low | high — silent vacuous votes return | Golden-argv test, the Phase 4 live check, and the `/hm:health` smoke |
| Sandbox-escape surface widened by attaching the escape to `uv run` | unknown | unknown | Accepted and named in ADR-001; no in-repo oracle settles it |
| An un-re-rendered harness keeps the dead codex vote | high | medium | Accepted (ADR-007); CHANGELOG carries the explicit symptom-to-cause mapping |
| Grandfathered slug corrupts the tier file | low | high — silent duplicate entries | `_SLUG_SAFE_RE` applies to every slug; case (f) pins it for an existing slug |

---

## ✅ Success Criteria

- [x] A 65-character slug already present in `failures.md` receives `count++`, with the count asserted
      to increment.
- [x] A 65-character slug already present in `wiki.md` is replaced in place, entry count unchanged.
- [x] `metrics-rotation-reader-via-_metrics_io` (39 chars, underscore) is accepted as an **existing**
      wiki slug and rejected as a **new** one.
- [x] A slug containing whitespace, `]`, or `|` is rejected even when it already appears in the file.
- [x] A 40-character new slug is accepted and a 41-character one is rejected.
- [x] The codex `subprocess.run` call carries the prompt bytes in `input=`, and codex findings are read
      from the `--output-last-message` file.
- [x] The agy argv matches the golden list — `--sandbox` before `--print`, the prompt as `--print`'s
      value, `--print-timeout` and `--model` present — with no `input=`.
- [x] The codex argv's `--output-schema` is absolute and exists when cwd is a linked worktree.
- [x] A non-default `antigravity.model` in the base `harness.yaml` reaches the argv when cwd is a
      worktree with no `.claude/` directory.
- [x] A missing **default** schema path proceeds via the packaged asset; a missing **explicitly
      configured** path yields `skipped` naming the path.
- [x] A prompt over the truncation budget yields ≤100 000 bytes total, still carries
      `AGY_OUTPUT_CONTRACT` and the marker, and never splits a character; a 90 000-byte body under
      budget comes back byte-identical **with** `AGY_OUTPUT_CONTRACT` present and no marker.
- [x] The `--smoke` prompt on the agy path yields a payload that passes `validate_payload`.
- [x] All seven ADR-008 branches are pinned by their own test, including `PermissionError`, an agy
      prose reply, and a codex exit-0-with-empty-out-file whose reason does not say "not installed".
- [x] A payload whose `severity` is outside the shared vocabulary classifies `failed` rather than
      raising — the criterion that distinguishes validate-before-adapt from adapt-before-validate.
- [x] A finding with `severity` and a non-empty `message` but no `evidence` classifies `invoked`, and
      `severity: "Critical"` is accepted after normalization.
- [x] `second_opinion_invoke` is registered in `command_registry.MODULES` as `ModuleSpec("flagonly")`
      and the command-surface gate is green.
- [x] A bare list, a `{"answer": …}` dict, and a `title/description/recommendation` payload each
      classify as `failed`.
- [x] A 5 000-character stderr on a non-zero exit still produces a written ledger row.
- [x] Exactly one ledger row per invocation, `finding_ref="n/a"`, `disposition="unresolved"`, written
      under the base repo root when cwd is a worktree.
- [x] A `stage="health"` row validates against both `SecondOpinionRecord` and the shipped
      `second-opinion-ledger.schema.json`.
- [x] `main()` run with cwd inside a linked worktree and no `--root` resolves schema and ledger against
      the base root.
- [x] No rendered artifact contains `agy --print --sandbox` or a stdin-redirected `agy` call, and
      neither does `tests/integration/test_antigravity_sandbox_probe.py` nor
      `tests/manual/ANTIGRAVITY_SANDBOX_PROBE.md`.
- [x] `/hm:health`'s ledger cross-ref computes a rate over invocations and excludes `stage="health"`
      rows.
- [x] A rendered `settings.json` contains `Bash(agy --sandbox --print:*)`.
- [x] `/hm:health`'s smoke and the stage recipe invoke the same entrypoint.
- [x] The invoker run from inside `.worktrees/<slug>/` has its result recorded for both models, with an
      environment-caused `skipped` recorded as acceptable.
- [x] CLAUDE.md no longer states that the rendered command must begin with `agy --print --sandbox`.
- [x] `ruff check`, `ruff format --check`, `mypy --strict`, and the full `pytest` suite are GREEN.

---

## 🔍 Plan Validation

**Pass 1 — `plan-validator`: MAJOR_REVISION** (3 critical, 11 warning, 3 suggestion), with a
cross-model second opinion injected from both enabled models. Both ran successfully: `codex` returned
8 findings and `antigravity` returned 7 — the latter being the **first non-vacuous antigravity vote
this harness has produced**, since every prior one was cast through the broken invocation this PLAN
fixes.

**Pass 2 — `plan-validator`: MAJOR_REVISION** (4 critical, 6 warning, 3 suggestion). Of pass 1's 17
critiques, 10 were verified RESOLVED, 5 RESOLVED_WITH_RESIDUAL, 2 PARTIALLY_RESOLVED — no regressions,
but four new criticals surfaced in the newly-specified detail.

| Pass | # | Critique | Sev | Resolution |
|---|---|---|---|---|
| 1 | 1 | Status matrix has no branch for a missing CLI or a timeout under `shell=False` | crit | **ADR-008** added |
| 1 | 2 | Config load path unspecified | crit | Design bullet "Config resolution" + worktree test |
| 1 | 3 | `exit 0 + parsed → invoked` records vacuous votes | crit | ADR-008 branch 5 + three wrong-shape payloads |
| 1 | 4 | `--stage health` violates the ledger `stage` `Literal` | warn | `Literal` widened (pass 2 extended this to the shipped enum) |
| 1 | 5 | argv criterion pins order but not the safety-carrying flags | warn | Golden-argv assertion |
| 1 | 6 | Phase 4 exit criterion contradicts its own Risk cell | warn | Split blocking / recorded-evidence |
| 1 | 7 | Ledger destination undesigned | warn | `project_root=<base root>` + location assertion |
| 1 | 8 | Packaged-schema fallback masks a mis-configured explicit path | warn | Default-vs-explicit split |
| 1 | 9 | Truncation undefined on envelope / UTF-8 / retained region | warn | ADR-003 rewritten (pass 2 fixed its arithmetic) |
| 1 | 10 | Phase 3's `--output-schema` grep is invariant over its dimension | warn | Removed, reason stated inline |
| 1 | 11 | ADR-005 overclaims what a base-cwd smoke proves | warn | Consequence rewritten |
| 1 | 12 | `--git-common-dir` parent wrong for separate-git-dir / submodules | warn | Porcelain-first + five cases |
| 1 | 13 | "grants no new capability" asserted, not evidenced | warn | Split into narrow claim + accepted unverified risk |
| 1 | 14 | Wiki tier in the problem statement but in no criterion | warn | Wiki cases added (pass 2 extended to the character class) |
| 1 | 15 | `--root` relationship undefined | sugg | Precedence stated (pass 2: no argparse default) |
| 1 | 16 | Phase 1 tests at the `_upsert` layer only | sugg | Case (g) through `main()` |
| 1 | 17 | `parallel_group` shared by chained phases | sugg | `serial-3` / `serial-4` |
| 2 | C1 | ADR-004's character-class rule contradicts Phase 1's work item; two real wiki slugs under the cap stay unwritable | crit | `_SLUG_SAFE_RE` / `_SLUG_NEW_RE` split; Phase 1 case (c) uses the two real slugs |
| 2 | C2 | Shipped ledger JSON enum not widened; parity test compares names only | crit | Enum widened; parity test extended to enum values; both in Phase 2 scope |
| 2 | C3 | Five-branch matrix not exhaustive (`PermissionError`, `UnicodeDecodeError`, other `OSError`) | crit | ADR-008 branch 3 terminal catch-all, branches 1–2 still named |
| 2 | C4 | codex prompt delivery (stdin) and payload readback (`--output-last-message` file) unspecified; golden argv cannot see it | crit | Per-model delivery in the design; Phase 2 asserts call kwargs and payload channel |
| 2 | W1 | Truncation arithmetic unsatisfiable; envelope source undefined | warn | Reserved budget; `AGY_OUTPUT_CONTRACT` owned by the invoker |
| 2 | W2 | `validate_payload` mechanism and strictness undefined; full schema would fail real agy replies | warn | Defined as the adapter-consumable surface; laxness pinned by its own test |
| 2 | W3 | Ledger row cardinality and required column values undefined | warn | One row per invocation; sentinel values pinned in ADR-002 and asserted |
| 2 | W4 | Branch-4 reason unbounded vs `max_length=500` → row silently dropped | warn | 400-char budget; 5 000-char stderr test |
| 2 | W5 | Phase 3's test subset excludes a test its own change breaks | warn | Three test files added to scope; criterion widened to the full suite |
| 2 | W6 | Every Phase 2 criterion is function-level; an argparse mis-wire passes all | warn | End-to-end `main()` case with no `--root` |
| 2 | S1 | Health smoke has no `--prompt-file` / `--slug` value | sugg | `--smoke` flag; `--slug health-smoke` |
| 2 | S2 | Golden argv has no stated provenance | sugg | Both lists written verbatim in the Technical Design |
| 2 | S3 | Affected-components paths omit `src/harness_maker/` | sugg | Prefixed; packaged asset located via `importlib.resources` |

**Second-opinion reconciliation.** Of codex's 8 findings, **8 were accepted** (three raised to critical
by the validator). Of antigravity's 7, **4 were accepted or merged** and **3 were refuted against
line-level evidence**, each refutation upheld by the pass-2 validator against the source: the claimed
missing `uv` allow rule (`Bash(uv:*)` is present at `Production.json.j2:63` and `Side.json.j2:11`), a
claimed parser-layer slug cap (`--slug` is registered with no validator at `memory_md.py:644`/`:649`),
and a claimed lint path consuming `_SLUG_RE` (exactly two occurrences, `:35` and `:217`). One
antigravity finding was a **duplicate** of a codex finding reached independently — the tail-truncation
defect — which raises confidence in that finding rather than its count.

**Pass 3 — `plan-validator`: MAJOR_REVISION** (2 critical, 6 warning, 2 suggestion). Of pass 2's 13
critiques, **9 verified RESOLVED and 4 PARTIALLY** — no regressions. Both new criticals are direct
consequences of pass-2 fixes, which the validator states explicitly: the invoker-owned envelope
(W1's fix) had no application condition, and the per-model read channel (C4's fix) opened a raising
region no branch covered.

| # | Critique | Sev | Resolution |
|---|---|---|---|
| CR-1 | Envelope has no application condition; Phase 2's "99 999 byte-identical" criterion forces it onto the truncation path only, so every ordinary agy call ships with no shape signal → `failed`, health smoke permanently red | crit | Envelope made **unconditional**; truncation trigger moved onto `BUDGET`; under-budget criterion restated as "body byte-identical + envelope present + total ≤ LIMIT" at 90 000 bytes; `--smoke` payload criterion added |
| CR-2 | No branch covers payload **acquisition** — agy prose (`ValueError` by contract) and an empty codex out-file (`JSONDecodeError`) fall outside all six | crit | ADR-008 branch 5 added; branches 1–3 scoped to `subprocess.run` only; both cases pinned, with the reason forbidden from saying "not installed" |
| W-1 | Pipeline order stated two ways; adapt-before-validate lets an out-of-vocabulary severity raise | warn | Validate-before-adapt pinned in ADR-008 and both diagrams; a criterion that distinguishes them |
| W-2 | `timeout=N` has no value; for agy it collides with the native `--print-timeout 240s` invariant | warn | Named constants (300 s each), agy's above its native timeout; CLAUDE.md invariant reconciled in Phase 4 |
| W-3 | agy golden argv's trailing flags after a value-consuming flag were unprobed | warn | **REFUTED by probe P3/P4** — `--model` after the prompt value produces the identical error to `--model` before `--print`, so parsing continues; the configured display name returns `PONG`. Transcript recorded in the Technical Design |
| W-4 | `command_registry.MODULES` missing → T-C1 red the moment Phase 3 lands | warn | Registered in Phase 2 as `ModuleSpec("flagonly")`; added to Affected components |
| W-5 | Two more artifacts pin the retired argv and are invisible to the full-suite criterion (integration file is double-gated) | warn | Both added to Phase 3 scope; the re-scoped sandbox evidence recorded in Phase 4 |
| W-6 | ADR-002's skip-rate-comparability claim is inverted — today the ledger holds only skip/fail rows | warn | Consequence rewritten to state the denominator changes by design; Phase 3 rewrites the health cross-ref and excludes `stage="health"` rows |
| S-1 | `validate_payload`'s severity check stricter than `map_severity`'s normalization | sugg | Membership tested after `.strip().lower()`; criterion added |
| S-2 | The ledger schema ships to no harness, so ADR-002's stated stakes were wrong | sugg | Reworded to the in-repo parity contract; the matching Risks row downgraded |

**New evidence gathered during pass 3 (probes P3/P4, recorded so the next reader need not re-derive):**
`agy` continues flag parsing after `--print`'s value; `agy` prints errors and still **exits 0**, so
branch 4 rarely fires on the agy path and branches 5–6 are its primary gates; the configured
`"Gemini 3.1 Pro (High)"` is accepted. Out of scope but recorded: `agy models` now returns stable
machine IDs (`gemini-3.1-pro-high`, …), which contradicts the CLAUDE.md rationale for
`antigravity.model` being free-text display names.

**Stopping rule.** Planning ends here. Three passes moved criticals 3 → 4 → 2, with each round's
criticals arising from the previous round's fixes rather than from unaddressed material. Every pass-3
item is resolved above; the two suggestions are one-line changes already applied. Residual risk is
carried by `/hm:execute`'s A.5 test-review gate and by `/hm:review`'s own cross-model panel, which is
the mechanism this task restores.
