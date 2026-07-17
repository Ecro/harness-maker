---
type: research
task_slug: onboarding-ux-2026-05
status: complete
created: 2026-05-11
tags: [harness-maker, research, ux, onboarding, locale, second-brain]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://clig.dev/
  - https://m1.material.io/growth-communications/onboarding.html
  - https://www.atlassian.com/software/jira/service-management/product-guide/tips-and-tricks/form-design-best-practices
  - https://learn.microsoft.com/en-us/globalization/localization/localization-overview
  - https://www.w3.org/International/geo/html-tech/tech-lang.html
  - https://w3c.github.io/wcag/understanding/language-of-page
related_docs:
  - "[[work-docs/RESEARCH-make-ux-gaps-2026-05.md]]"
  - "[[work-docs/RESEARCH-deep-interview-llm-delegation.md]]"
  - "[[work-docs/RESEARCH-user-workflow-opportunities-2026-05.md]]"
  - "[[work-docs/RESEARCH-second-brain-obsidian-2026-05.md]]"
  - "[[.claude/memory/wiki.md#deep-interview-gate]]"
  - "[[.claude/memory/wiki.md#slash-command-interview-completeness]]"
  - "[[.claude/memory/wiki.md#second-brain-project-namespace]]"
summary: "Locale-locked receipt-first onboarding: explain choices, files, backups, preservation, review time, and Second Brain"
---

# RESEARCH — onboarding UX: make/configure/Deep Interview clarity

## 🎯 Recommended Direction

Implement a **locale-locked, receipt-first progressive onboarding flow** for `/harness-maker:make`, `/hm:configure`, and all Deep Interview gates.

The product should stop treating onboarding as a sequence of bare configuration prompts. Each decision point should show: current/recommended value, why it matters, operational cost, review-time impact, reversibility, and what files or external stores will be touched. The most important UX object is a reusable **Decision Receipt** shown before and after changes: install paths, target-specific outputs, backup path, preserved user blocks, non-deleted stale target files, Second Brain vault/folder/write boundaries, and next commands. This matches CLI guidance that state-changing commands should explain the new state and support dry-run previews, while avoiding a full upfront expert wizard that overwhelms first-time users.

## 🔍 Refinement Decisions

Discovery lens: User-workflow / product opportunity, Technical architecture / implementation, Risk / compliance / security.

No `--deep` refinement interview ran. The user supplied concrete research anchors:

- Make should be much friendlier and more detailed; Deep Interview should follow the same standard.
- Locale must be respected, and Deep Interview should force it so users fully understand questions.
- The UX must explicitly explain what is installed where, what is backed up where, and what is preserved.
- Make/configure must explain trade-offs of settings, especially review time.
- Second Brain behavior must be explained in enough detail for trust.

Local capability x User artifact mapping:

| User artifact / mental model | Current harness capability | Onboarding explanation required |
|---|---|---|
| Project repo | Renders `.claude/`, optional `.cursor/`, `.codex/`, `.agents/skills/`, `AGENTS.md` | Exact output roots by target, what gets updated vs left behind |
| Existing user edits | `@hm:user:*` blocks, content hashes, KEEP/MERGE_BLOCK/REPLACE reconciliation | Which edits are preserved, which files are skipped, which files are system-managed |
| Recovery point | `backup()` creates `.backup-<timestamp>` mirroring project root for `.claude`, `.cursor`, `.codex`, `.agents` assets | Show backup path before/after render and restore hint |
| Review workflow | `reviewers.enabled`, `grade_threshold`, `mechanical_checks`, `auto_fix`, `max_review_rounds` | Explain review quality vs wall-time and build-break risk |
| Reference docs | `ref_folders` + `refdocs-search` index | Explain read-only indexing, supported globs, rebuild behavior |
| Cross-repo work | `sibling_repos` + worktree isolation | Explain extra context and extra worktree creation scope |
| Obsidian vault | `second_brain` filesystem backend, typed notes, allowlisted folders, project namespace | Explain read/write folders, note types, required frontmatter, project_id isolation, and trust boundary |
| Locale preference | `locale` stored in `harness.yaml`; templates/i18n vary by generated target | Force all interactive prose and Deep Interview prompts to the configured/requested locale |

## 🛠️ Approaches Found

### Approach A — Receipt-first progressive onboarding

| Field | Content |
|---|---|
| Approach | Keep smart defaults and quick setup, but attach a structured decision receipt to each state-changing path. |
| Assumption | Users want to move quickly, but only after they understand file writes, backups, preserved edits, and future review cost. |
| Evidence | Current `/harness-maker:make` already has smart defaults, quick/full setup, dry-run, `/hm:configure`, and Second Brain prompts, but explanations are shallow and inconsistent. CLI Guidelines recommend explaining state changes and supporting dry-run for moderate changes. Material onboarding recommends goal-specific onboarding and self-select/quickstart models depending on setup needs. Atlassian form guidance supports minimal questions, logical grouping, and timely field-level help. |
| Trade-off | More prose must be maintained and localized; summaries must be generated from actual config/render results, not hand-waved. |
| Compatibility | High. Extends `commands/make.md`, `commands/hm/configure.md.j2`, `cli.py` summary/dry-run output, and stage Deep Interview templates without changing the generator architecture. |
| Risk | Low to medium. Main risk is stale explanations unless backed by tests that grep for required UX contract fragments and, where possible, derive receipt fields from actual data. |

### Approach B — Expert full wizard

| Field | Content |
|---|---|
| Approach | Ask every configuration dimension up front with detailed explanations before first install. |
| Assumption | Maximum upfront understanding is worth the added time. |
| Evidence | The previous make UX research found many valuable interview dimensions. However, form-design guidance warns against unnecessary questions and big blocks of text; current command already has at least 12 full-setup questions. |
| Trade-off | Users understand more before install, but time-to-first-success worsens and review-time explanations become buried in a long flow. |
| Compatibility | Medium. It fits slash-command `AskUserQuestion`, but not CLI non-TTY fallback or quick onboarding. |
| Risk | Medium to high. Likely to create a lecture-like setup and increase abandonment for users who just need a safe default. |

### Approach C — Documentation-only plus verbose CLI

| Field | Content |
|---|---|
| Approach | Improve README/HOW-IT-WORKS and add verbose CLI output, leaving slash prompts mostly unchanged. |
| Assumption | Users will read docs or CLI output when confused. |
| Evidence | CLI Guidelines support useful success output, and current README explains worktree isolation, brownfield safety, targets, and prerequisites. But Material onboarding notes users may be eager to try the app without reading an instruction manual. |
| Trade-off | Least invasive implementation, but misses the moment where users make choices. |
| Compatibility | High for docs; weak for Deep Interview and locale enforcement. |
| Risk | Medium. It documents trust boundaries but does not prevent wrong choices during setup. |

Recommended: **Approach A**. It preserves quick setup while making every irreversible-looking action legible.

## ⚠️ Pitfalls

1. **Information overload disguised as helpfulness.** External UX guidance agrees on timely, minimal, logically grouped prompts. The flow should expose “why this matters” and “impact” per field, not insert long manuals before every question.

2. **Mixed-language interviews.** Current dogfood config is `locale: ko`, and memory records that English plan interview prose already caused a locale correction. Deep Interview prompts must carry an explicit “answer and ask in `{{ config.locale }}`” contract. Localization is broader than translation; Microsoft notes that locale affects formats, text length, terminology, and cultural assumptions. W3C also treats language declaration as a baseline requirement for correct text processing and accessibility.

3. **Opaque filesystem mutation.** Current `/harness-maker:make` preview says “Will install 40+ files under .claude/” even though targets may also render `.cursor/`, `.codex/`, `.agents/skills/`, and root `AGENTS.md`. Current CLI dry-run counts NEW/REPLACE by existence but does not show real reconcile decisions, backup location, or target-specific stale-file behavior. This can break trust in brownfield repos.

4. **Backup confidence without restore clarity.** `cli.py` calls `backup(target_dotclaude)` before reconcile, and tests show backups include `.cursor/` and `.agents/skills/`. The user-facing output should say the concrete `.backup-*` path and what it mirrors; otherwise the safety feature is invisible.

5. **Second Brain trust boundary ambiguity.** The implementation is filesystem-backed, uses configured vault folders as trusted zones, restricts writes to Markdown, validates required frontmatter, checks note type, and warns when `project_id` ownership is missing. Models also require writable folders to include the project id as a path segment. Onboarding currently says “Connect an Obsidian vault” but not enough about read vs write folders, namespace isolation, or what “trusted allowlist” means.

6. **Review-time surprise.** Production enables more reviewers and stricter grade gates. `grade_threshold`, `mechanical_checks`, `auto_fix`, `max_review_rounds`, enabled reviewers, and `reviewers.verbosity` all affect runtime and interaction count. The onboarding should show coarse estimates such as “fastest”, “balanced”, “slowest/highest confidence” rather than pretending all presets cost the same.

7. **Dry-run divergence.** If preview does not reuse the same reconcile path as real render, it can promise the wrong outcome. The earlier make UX research already called this out; the current `_emit_dry_run_summary()` still only compares path existence.

8. **Target removal misunderstanding.** Current make command correctly notes that dropping `cursor` or `codex` does not delete previously rendered target-specific files. This must be prominent in the receipt, because it is a surprising but safe preservation behavior.

## ❓ Open Questions

1. **Review-time model:** Should estimates be static labels (`Side=fast`, `Production=slower`) or computed from enabled reviewers, mechanical checks, `max_review_rounds`, and workflow stages?

2. **Receipt source of truth:** Should the receipt be generated by Python from `Blueprint + reconcile + answers`, then consumed by slash commands, or should slash-command prose remain the source? Recommendation for plan: Python-generated for file/backup facts; slash-command prose only for per-question explanations.

3. **Locale enforcement surface:** Should every stage template include a shared locale contract partial, or should only Deep Interview sections be patched? Recommendation for plan: shared partial or macro-equivalent text to avoid another drift.

4. **Second Brain setup depth:** Should first install only support read-only vault search, with writable folders configured later in `/hm:configure`, or should full setup expose read/write folder configuration immediately?

5. **User-facing terminology:** Should “Second Brain” stay as product language, or should the setup call it “Obsidian project memory” first and mention “Second Brain” second?

6. **Configure UX shape:** Should `/hm:configure` use one multi-select followed by receipts, or a repeated “change another setting?” loop? Multi-select is simpler; loop is better for comparing trade-offs.

## 📚 Sources

- https://clig.dev/ — CLI state-change output, dry-run guidance, stable flags, uninstall discoverability.
- https://m1.material.io/growth-communications/onboarding.html — onboarding should fit user familiarity; self-select and quickstart are valid models for configurable setup.
- https://www.atlassian.com/software/jira/service-management/product-guide/tips-and-tricks/form-design-best-practices — minimal questions, logical grouping, conversational form flow, field-level help.
- https://learn.microsoft.com/en-us/globalization/localization/localization-overview — localization affects more than translation; design for target audience and text expansion/format differences.
- https://www.w3.org/International/geo/html-tech/tech-lang.html — language support should be considered from the start; declare the language of content for text processing.
- https://w3c.github.io/wcag/understanding/language-of-page — correct language improves rendering, pronunciation, and comprehension for assistive technologies.
- Internal source: `commands/make.md` — current plugin-level make onboarding flow, smart defaults, preview, target and Second Brain prompts.
- Internal source: `src/harness_maker/templates/commands/hm/configure.md.j2` — generated configure command.
- Internal source: `src/harness_maker/cli.py` — `--dry-run`, backup call, install summary, dimension override behavior, manifest and uninstall support.
- Internal source: `src/harness_maker/reconcile.py` — KEEP/REPLACE/MERGE_BLOCK decision matrix and backup comments.
- Internal source: `src/harness_maker/second_brain.py` and `src/harness_maker/models.py` — Second Brain read/write allowlist, Markdown-only writes, note validation, project namespace rules.

## 🔗 Related Internal Docs

- [[work-docs/RESEARCH-make-ux-gaps-2026-05.md]] — prior make/configure/update UX gaps; most baseline items have since been implemented.
- [[work-docs/RESEARCH-deep-interview-llm-delegation.md]] — 3-layer Deep Interview architecture and make/plan/research applicability.
- [[work-docs/RESEARCH-user-workflow-opportunities-2026-05.md]] — user workflow opportunity lens and Second Brain direction.
- [[work-docs/RESEARCH-second-brain-obsidian-2026-05.md]] — Obsidian-backed project memory research.
- [[.claude/memory/wiki.md#deep-interview-gate]] — GCIC/CLARITI/implicit probing gate pattern.
- [[.claude/memory/wiki.md#slash-command-interview-completeness]] — slash command interview coverage must match `interview.py`.
- [[.claude/memory/wiki.md#second-brain-project-namespace]] — project_id namespace guard for writable Obsidian folders.

## Implementation Candidate Checklist For Plan

1. Add a reusable “Decision Receipt” contract:
   - current intent (`fresh install`, `update`, `configure`, `target switch`)
   - target roots touched (`.claude`, `.cursor`, `.codex`, `.agents/skills`, `AGENTS.md`)
   - file actions (`NEW`, `REPLACE`, `MERGE_BLOCK`, `KEEP`)
   - backup path and restore hint
   - preserved user blocks and skipped user-owned files
   - stale target files intentionally left in place
   - enabled reviewers/skills/workflows
   - review-time impact label
   - Second Brain read/write boundaries when enabled

2. Make `/harness-maker:make` and `/hm:configure` explanations field-level:
   - `preset`: quality/speed/default reviewer set
   - `grade_threshold`: strictness vs re-review probability
   - `mechanical_checks`: catches deterministic failures before LLM review; adds command runtime
   - `reviewers`: more coverage vs more tokens/wall time
   - `auto_fix`: less manual work vs agent edits requiring review
   - `targets`: generated roots and non-deletion semantics
   - `ref_folders`: read-only local docs search
   - `sibling_repos`: cross-repo context and worktree scope
   - `second_brain`: Obsidian vault, allowlist, project_id namespace, typed note behavior

3. Enforce locale in all interactive prompt surfaces:
   - plugin-level `commands/make.md`
   - generated `/hm:configure`
   - stage Deep Interview sections in research/spec/plan/loop
   - final validation prompts
   - fallback/error text where the user must decide

4. Upgrade dry-run from existence counts to reconcile-aware preview.

5. Add tests that lock the UX contract:
   - generated make/configure templates mention backup, preservation, target roots, review-time trade-off, Second Brain boundary, and locale
   - Deep Interview templates include configured-locale instruction
   - CLI dry-run includes reconcile action labels, not only NEW/REPLACE counts
   - Second Brain configure flow explains read/write allowlist and project_id namespace
