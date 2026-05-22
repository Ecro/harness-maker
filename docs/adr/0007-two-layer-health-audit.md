# ADR-0007: Two-layer health audit (supersedes ADR-0006)

- **Status**: accepted (supersedes [ADR-0006](0006-three-layer-health-audit.md))
- **Date**: 2026-05-22
- **Source PLAN**: `work-docs/PLAN-hm-health-crawl-removal.md` (interview Rounds 1 + 2; 4 ADRs locked)
- **Source RESEARCH**: `work-docs/RESEARCH-hm-health-crawl-removal.md`

## Context

ADR-0006 (2026-05-17) consolidated three audits into `/hm:health` with a
3-layer dashboard: **structural**, **external_risks**, **personalization**.
The `external_risks` layer combined:

- 4-source crawler (`anthropic_blog`, `github_releases`, `arxiv`, `osv_dev`)
  via the `research-crawler` skill
- LLM relevance filter + adaptive threshold via the `relevance-filter` skill
- Stale-asset detection (`detect_stale_assets`)
- `harness-maker health-finalize` CLI bridge

Five days later, a 2026-05-22 production run surfaced the cost-to-signal
problem: 12 items presented to the user, 1 accepted (already known —
"Introducing Claude Opus 4.7" was already pinned as the recommended model),
11 rejected. 91% noise. The per-item AskUserQuestion contract (ADR-001 hard
rule) made the noise *interruptive* rather than *passive*. The user
recognized the wedge and asked for an honest evaluation.

`/hm:research` surfaced three options (full demolition vs soft-deprecate
vs replace-with-/hm:trends). The user chose full demolition.

## Decision

**Collapse `/hm:health` to a 2-layer audit: `structural` + `personalization`.**
Remove the entire `external_risks` layer including crawler modules, the
relevance-filter, the stale-asset code, the `health-finalize` CLI subcommand,
and the corresponding skill templates.

OSV CVE detection (the only `external_risks` source with rare-but-critical
value) survives via the independent `secscan/dependency_cves.py` channel
consumed by `/hm:verify`. The `crawler/osv_dev.py` module and its tests
are preserved; the other three crawler modules and the relevance/stale-asset
code are deleted.

## Consequences

- ✅ `/hm:health` no longer wastes user time on speculative pushes from
  blog / release-note / arxiv channels. The slash command runs structural
  scoring + Claude-judged personalization, full stop.
- ✅ Code surface shrinks ~800 LOC net (4 source modules + 2 skill templates
  + 6 test files deleted; verify Check 4 + CLI subcommand + dashboard section
  removed).
- ✅ Audit trail intact: ADR-0006 retains its decision body and now points
  forward to this ADR via the `Status: superseded by` field. First
  supersession precedent in this repo (ADR-0006 itself only `amended`
  ADR-0002; never reversed it).
- ⚠️ **Accepted risk #1 — patch-version bump for CLI subcommand removal**:
  shipping as 0.22.3 (patch), not 0.23.0 (minor). Evidence supporting:
  `health-finalize` was introduced in 0.13.0 as an internal CLI bridge
  between the Python structural step and the Claude-driven external_risks
  + personalization steps; no public README/AGENTS.md documentation
  mentions the subcommand; the only call site is the `/hm:health` slash
  template which auto-updates via `/hm:make --update`; in 9 months in
  production, no scripted external user surfaced. The
  surface is internal-to-the-plugin even though removal looks BREAKING.
- ⚠️ **Accepted risk #2 — dashboard schema change for in-flight users**:
  existing users' `dashboard.md` files retain a stale `## External risks`
  section until the next `/hm:health` run regenerates them. The parser
  silently drops the unknown section (no breakage). Documented in
  CHANGELOG.
- ⚠️ **Accepted risk #3 — orphan on-disk artifacts**: existing user disks
  may carry `.claude/observability/health/raw-*.jsonl`,
  `.claude/observability/health/decisions.jsonl`, and the orphan tmp file
  `.claude/observability/.health-external-risks.tmp.json`. All are
  gitignored on user side and harmless to leave. CHANGELOG offers an
  optional one-line cleanup command.
- ⚠️ **Accepted risk #4 — stale-asset code removed alongside crawler**:
  `StaleAsset`, `detect_stale_assets`, `build_proposal_lines`,
  `update_last_reviewed_at` (relevance.py:200-435) had zero production
  caller; only `tests/unit/test_relevance_stale.py` and a docstring
  reference in `add_domain.py:52`. Deletion is consistent with ADR-0006's
  bundling of stale-asset into `external_risks`. If a future feature wants
  `last_reviewed_at` introspection, it must be re-implemented; the
  `last_reviewed_at` *writer* side in `add_domain.py` is preserved as
  passive provenance metadata.

## Rejected alternatives

- **A — Soft-deprecate behind `harness.yaml.health.external_risks.enabled: false` flag.**
  Rejected because dead code rots: tests, mypy strictness, and reviewer
  cycles continue to pay maintenance cost for a never-fired branch. The
  cumulative risk exceeds the cost of a one-shot deletion.

- **B — Preserve only `osv_dev` crawler in the external_risks layer.**
  Rejected because OSV CVE detection already lives in
  `secscan/dependency_cves.py` (consumed by `/hm:verify`); keeping a
  parallel path inside `/hm:health` is redundant infrastructure with no
  signal upside. The dashboard's "External risks" section becomes a
  single-source rendition of what `/hm:verify` already gates.

- **C — Replace external_risks with an opt-in `/hm:trends` command.**
  Deferred (not rejected outright). If a real user request surfaces for a
  "what's new this week" sweep, this becomes a follow-up plan. As of
  2026-05-22 no such request exists; the user's explicit guidance was
  that research belongs in `/hm:research`, not pushed by a health audit.

- **D — In-place amend of ADR-0006 (no new ADR).**
  Rejected because the decision is *reversed*, not *refined*. Repo
  convention for refinements is `amended by` (ADR-0006 amends ADR-0002);
  for reversals, supersession with a paired forward-link keeps history
  clean. First supersession in this repo — sets the precedent.

## Migration

Existing users running 0.22.3 the first time should:

1. Run `/hm:health` once — produces a fresh 2-layer `dashboard.md` (the
   old `## External risks` section is silently dropped by the parser; new
   render writes only Structural + Personalization).
2. (Optional, gitignored anyway) clean up orphan artifacts:
   ```bash
   rm -rf .claude/observability/health/raw-*.jsonl \
          .claude/observability/health/decisions.jsonl \
          .claude/observability/.health-external-risks.tmp.json
   ```
   These files belong to the deleted external_risks pipeline and are
   harmless to leave; clean only if disk hygiene matters.

`/hm:verify` shrinks from 6 checks to 5 (Check 4 was the
`external_risks_pending` gate; subsequent IDs renumber 5→4 and 6→5).
CI pipelines that key off check IDs must update; CI pipelines that key
off check names are unaffected.

## Cross-references

- [ADR-0006](0006-three-layer-health-audit.md) — the decision being reversed.
- [ADR-0002](0002-three-layer-ai-readiness-rubric.md) — unchanged; the
  3-layer ai-readiness *rubric* (structural layer's internal model) is
  different from the 3-layer *health audit* and survives.
- [ADR-0011](0011-personalization-rubric-locked-v0.md) — unchanged;
  personalization layer rubric (L1/L2/L3 weights) preserved verbatim.
- `work-docs/PLAN-hm-health-crawl-removal.md` — full execution plan.
- `work-docs/RESEARCH-hm-health-crawl-removal.md` — research notes.
