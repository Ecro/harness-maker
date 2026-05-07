---
generated_by: harness-maker
harness_maker_version: 0.5.7
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/refdocs-search/SKILL.md.j2
provenance: official
content_hash: fa1e04737038d31b4277566804accff7aad010641534d41a69e898c68d452073
---
# refdocs-search

> Search registered reference document folders without extracting their content
> — lossy yaml index for triage, *original* files for answers.

## Triggers

- Inside research / spec / plan / execute when the question references
  documentation outside the source tree.
- Direct prompts: "search the design docs for X", "what does the spec say".

## Behavior — two-tier search

The index is intentionally lossy (filename + title + h1/h2). Answers come from
the **original** file so PDF tables / figures / equations are never lost.

1. Read `.claude/harness.yaml` → `ref_folders:`. Empty → say so and stop.
   Read `.claude/observability/docs_index.yaml`. Missing → advise:
   `python -m harness_maker.refdocs_index build`.

2. Triage: pick top 3-5 candidates by *reasoning* over filename + title +
   headings. Don't keyword-grep the index.

3. Search candidate content by `kind`:

   | kind | tool |
   |---|---|
   | `md`, `txt` | `Bash`: `rg -n -C 2 -F '<term>' <ref_folder>/<relpath>` |
   | `pdf` | `Read(<ref_folder>/<relpath>, pages="<range>")` (multimodal) |

   PDFs >10 pages need a `pages` range (max 20/req). Skim 1-2 pages first,
   then targeted range read.

4. **DOCX is unsupported** — skipped at indexing (see `warnings:` in the
   index). Tell user to convert to PDF or markdown then rebuild.

5. Cite file path + heading (md) or page (pdf).

## Stale-index check

Glance at `generated_at`. If user mentions adding docs since, suggest a
rebuild — cheap, no LLM calls, idempotent.

## Output

Inline answer with citations. Never persist extracted content.

<!-- @hm:user:extensions -->
<!-- Project-specific search heuristics (preferred topics, alias terms, "always check this folder first" hints). Preserved across upgrades. -->
<!-- @hm:/user:extensions -->
