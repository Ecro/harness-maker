---
type: research
task_slug: hm-health-crawl-removal
status: complete
created: 2026-05-22
tags: [harness-maker, research, hm-health, deprecation, refactor, adr-0006]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs:
  - "[[adr-0006-three-layer-health-audit]]"
  - "[[PLAN-health-consolidation]]"
  - "[[REVIEW-health-plugin-bugs-2026-05-17]]"
summary: "Scrap external_risks crawl layer; /hm:health collapses to 2-layer (structural + personalization)."
---

# 🎯 Recommended Direction

**Drop the external_risks crawl layer entirely.** `/hm:health` becomes a 2-layer audit (structural + personalization). The 4-source crawl (anthropic_blog / github_releases / arxiv / osv_dev) + LLM relevance filter + adaptive threshold + per-item AskUserQuestion fired 12 items in the 2026-05-22 run, of which the user accepted 1 (Opus 4.7 — already pinned) and rejected the rest. Cost-to-signal is wrong by ~10×. CVE detection — the only crawl source with rare-but-critical value — is already covered by `secscan/dependency_cves.py` via `/hm:verify`, so removing the crawl does not regress security posture.

# 🔍 Refinement Decisions

User asked for an honest evaluation of the crawl layer's user-facing value. Three options surfaced:
- **A** — keep `osv_dev` only, drop blog / releases / arxiv.
- **B** — batch the per-item AskUserQuestion into one multi-select.
- **C** — scrap the entire `external_risks` layer.

User selected **C**. Rationale: OSV CVE coverage already lives in `secscan/dependency_cves.py` (consumed by `/hm:verify`), so option A is redundant with an existing channel. Options A/B preserve the "audit theater" without restoring real signal. C is the only choice that pays the demolition cost once and stops the noise permanently.

Discovery lens: **Internal architecture** (codebase impact mapping only — no external research needed for a removal task).

# 🛠️ Approaches Found

## Approach 1 — Full demolition + 2-layer rewrite (recommended, matches user's option C)

| Field | Content |
|-------|---------|
| Approach | Delete crawl + relevance + stale-asset code paths; rewrite `/hm:health` template to 2-layer; amend ADR-006. |
| Assumption | No downstream feature depends on `external_risks` data shape. OSV CVE detection survives in `secscan/dependency_cves.py`. |
| Evidence | Codebase grep: only `memory_retrieve.py` imports `WORD_RE` from `relevance.py`. `crawler/osv_dev.py` is consumed by `secscan/dependency_cves.py` (separate `/hm:verify` flow). Dashboard's `external_risks` section has no other readers. |
| Trade-off | Loses the "we crawled and flagged 0 CVEs today" reassurance — but `/hm:verify` already gives that signal. Loses arxiv research-paper push — minor (research belongs to `/hm:research` anyway). |
| Compatibility | BREAKING for downstream consumers of `dashboard.md` schema (the `External risks` section disappears). No known external consumer (we don't publish dashboard.md as an API). |
| Risk | medium — touches CLI, template, observability, ADR, spec, version sync. Reversible via git revert if a hidden consumer surfaces. |

## Approach 2 — Soft-deprecate behind a flag (rejected)

| Field | Content |
|-------|---------|
| Approach | Add `harness.yaml.health.external_risks.enabled: false` default; keep code but skip execution. |
| Assumption | Some users may still want the crawl with custom relevance scoring. |
| Evidence | No such user has surfaced; the layer fired ~2× in production telemetry (decisions.jsonl shows 28 historical samples across all sessions, mostly rejects). |
| Trade-off | Pays code-maintenance cost (tests, mypy, ruff) for dead-code branches; users still see the toggle in `harness.yaml` and wonder what it does. |
| Compatibility | Backwards-compatible. |
| Risk | high (cumulative) — dead-code branches rot; the relevance + crawler modules accumulate test failures over time. |

## Approach 3 — Replace with manual `/hm:trends` slash command (deferred)

| Field | Content |
|-------|---------|
| Approach | Move blog + arxiv to an opt-in `/hm:trends` command that user runs intentionally when curious. |
| Assumption | User would benefit from an explicit "show me anything new this week" lookup. |
| Evidence | No user request for this; if needed, can be added later as a separate task. |
| Trade-off | Defers nothing useful — `/hm:research` with a Phase 0.75 user-workflow lens already covers the use case. |
| Compatibility | Independent — adds a new command without disturbing existing flow. |
| Risk | low. |

**Verdict:** Do Approach 1 now. Approach 3 stays on the shelf as a follow-up if a real user surfaces the need.

# ⚠️ Pitfalls

1. **`secscan/dependency_cves.py` regression**: it imports `from harness_maker.crawler import osv_dev`. If `osv_dev.py` is deleted by mistake or `crawler/__init__.py` re-exports break, `/hm:verify` silently loses CVE detection. **Mitigation**: keep `osv_dev.py`; run `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py` after demolition.

2. **`memory_retrieve.py` imports `WORD_RE`**: deleting `relevance.py` outright kills the memory retrieve helper. **Mitigation**: either (a) move `WORD_RE` to `memory_retrieve.py` (its only consumer), or (b) keep `relevance.py` as a stub module exporting just `WORD_RE`. Prefer (a).

3. **ADR-006 amendment vs supersede**: ADR-006 explicitly mandates 3 layers. We're going to 2. ADR convention in this repo is `amends` (see ADR-006's relationship to ADR-002). Likely write ADR-007 that supersedes ADR-006 to keep the audit trail clean — but plan stage should decide.

4. **5-file version sync (CLAUDE.md "버전업 정책")**: removing a published dashboard section is BREAKING for any external dashboard consumer. Bump 0.22.2 → 0.23.0 (next minor, not patch — there is no major bump policy below 1.0 in this repo, but minor-bump BREAKING entries are precedented). Confirm in plan.

5. **Migration artifacts on existing user disks**:
   - `.claude/observability/health/raw-*.jsonl` — orphan data; harmless, leave on disk.
   - `.claude/observability/health/decisions.jsonl` — adaptive-threshold history; orphan; harmless.
   - `.claude/observability/.health-external-risks.tmp.json` — no longer created; safe to ignore.
   - Document one-line cleanup hint in CHANGELOG (user can `rm -rf .claude/observability/health/raw-*.jsonl` if they want).

6. **Test sandbox bloat**: `tests/e2e/sandbox-plugin-test/` has many `.backup-*` snapshots referencing the old skills. These are gitignored backups, not source — do NOT chase them. Only update the active `tests/e2e/sandbox-plugin-test/.claude/...` files.

7. **CLI surface decision**: `health-finalize` subcommand exists because the 3-layer flow split work between Python (structural) and Claude (external_risks + personalization). With 2 layers, personalization is still Claude-judged, so `health-finalize` may still be needed — or we can fold it back into `health` with a `--finalize` flag. Plan decides.

8. **`add_domain.py:52` orphan reference**: docstring mentions `detect_stale_assets` parsing the `last_reviewed_at` field it writes. After demolition, the writer becomes orphan. Either delete the writer or keep the metadata as a passive provenance field. Plan decides.

# ❓ Open Questions

The plan stage must lock these down via formal interview:

1. **ADR strategy**: amend ADR-006 in place, or write ADR-007 superseding it? (Repo convention favors supersession for "decision reversed" — amend for "decision refined".)
2. **Version bump**: 0.23.0 (BREAKING dashboard schema) confirmed? Or 0.22.3 (treat removal as bug fix)?
3. **`health-finalize` subcommand**: keep separate, or fold back into `health`?
4. **`WORD_RE` relocation**: move to `memory_retrieve.py` (single consumer) or keep `relevance.py` as a stub?
5. **`add_domain.py` `last_reviewed_at` writer**: delete or keep as orphan metadata?
6. **Migration messaging**: silent removal, or one-time CHANGELOG note + `/hm:health` first-run banner ("the external_risks layer was removed in 0.23.0 — see CHANGELOG")?
7. **Decisions.jsonl deletion**: leave on disk forever, or `/hm:health` first-run prompt to delete?

# 📚 Sources

(Internal research only — no external citations.)

# 🔗 Related Internal Docs

- [[adr-0006-three-layer-health-audit]] — the decision being reversed (`docs/adr/0006-three-layer-health-audit.md`).
- [[PLAN-health-consolidation]] — original consolidation plan that created the 3-layer model.
- [[REVIEW-health-plugin-bugs-2026-05-17]] — recent health plugin bug review.
- [[SPEC-tpl-health-md]] — `specs/SPEC-tpl-health-md.md` + `.machine.yaml` need amendment.
- `src/harness_maker/templates/commands/hm/health.md.j2` — slash command template (Step 2 deletion).
- `src/harness_maker/observability/dashboard.py` — `external_risks` section rendering removal.
- `src/harness_maker/cli.py` — `health` + `health-finalize` subcommands.
- `src/harness_maker/crawler/` — `anthropic_blog.py`, `arxiv.py`, `github_releases.py`, `__init__.py` (trim) — delete; keep `osv_dev.py`.
- `src/harness_maker/relevance.py` — delete (after `WORD_RE` relocation).
- `src/harness_maker/templates/skills/research-crawler/` + `relevance-filter/` — delete templates + rendered copies.
- `src/harness_maker/models.py` — `CrawlItem` likely kept (used by `osv_dev` + `secscan`); confirm in plan.
