---
type: research
task_slug: auto-feedback-2026-05
status: complete
created: 2026-05-23
tags: [harness-maker, research, telemetry, privacy, feedback-loop, github-issues]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://github.blog/changelog/2026-04-22-github-cli-opt-out-usage-telemetry/
  - https://github.com/cli/cli/issues/13263
  - https://news.ycombinator.com/item?id=47862331
  - https://docs.github.com/en/github-cli/github-cli/github-cli-telemetry
  - https://www.theregister.com/2026/04/22/github_opts_all_cli_users/
  - https://groundy.com/articles/github-cli-v2910-turns-on-default-telemetry-what-gh-collects-and-how-to-opt-out/
related_docs:
  - PRIVACY.md
  - work-docs/PLAN-oss-readiness-audit.md
  - .github/ISSUE_TEMPLATE/bug.yml
  - src/harness_maker/telemetry.py
  - src/harness_maker/review_telemetry.py
  - tests/unit/test_no_network.py
summary: "Recommend Approach D — interview-opt-in (default off) + per-/hm:* tail footer with one-line gh command (no new slash command, preserves no-network contract for the 99% of users who never toggle it on)"
---

# Auto-Feedback for harness-maker — Research

## 🎯 Recommended Direction

**Approach D — Maintainer-dogfooding opt-in: `feedback.enabled: false` (default), togglable only via interview; when on, every `/hm:*` command tail prints a one-line draft footer with the exact `gh issue create --web --body-file <path>` command. No new slash command.**

The user (sole maintainer) narrowed Approach C with four decisions:
1. **Default OFF** — for every other user, `PRIVACY.md` "Nothing is transmitted" stays literally true and zero code path changes their experience.
2. **Interview is the only toggle surface** — no CLI flag, no env var, no settings.json key. Single source of truth, no surface drift.
3. **No `/hm:feedback` slash command** — the entire UX collapses into the tail footer of existing `/hm:*` commands. One fewer thing to render, document, and version.
4. **Used only during the maintainer's own dogfooding** — accept that draft volume will be tiny (one user) and that the heuristic doesn't need to scale.

Why this fits cleanly: when off, the feature is a 0-cost dead branch (gated at the dispatcher template); when on, it adds a 1-line footer to the maintainer's own session, no inline `AskUserQuestion`, no flow interruption. The maintainer then runs the printed `gh` command in their own terminal — `gh issue create --web` opens a browser pre-filled with the body; the maintainer clicks Submit. We never call HTTP; PRIVACY.md and `tests/unit/test_no_network.py` stay unmodified.

This direction is informational; `/hm:plan` locks in the binding decision (trigger rubric, footer format, draft schema, PRIVACY.md amendment scope).

## 🔍 Refinement Decisions

- Discovery lens: **User-workflow / product opportunity** + **Risk / compliance / security** (both binding; the technical-architecture lens is secondary — the bug.yml template, telemetry.py redaction primitives, and `gh` are all present already).
- No `--deep` interview ran (user's topic was concrete enough to dive in).
- **User-narrowed scope (2026-05-23 mid-research):** Approach D selected — opt-in default-off, interview-only toggle, no separate `/hm:feedback` slash command, maintainer-dogfooding use case. Approaches A/B/C kept for reference but D is the locked direction.

## 🛠️ Approaches Found

### Approach A — Local-only feedback artifact (zero-network)

| Field | Content |
|---|---|
| Approach | Detect harness-self issues from telemetry; render a local `.claude/observability/feedback-{slug}.md` with the bug.yml fields pre-filled; print a prompt with `gh issue create --body-file <path>` and a browser URL fallback. User submits manually. |
| Assumption | Users tolerate one extra step (copy-paste or one-command) to ship feedback. |
| Evidence | Our existing `.github/ISSUE_TEMPLATE/bug.yml` already enforces structured fields (version, IDE, OS, repro). `telemetry.py:_SECRET_PATTERNS` + `_ALLOWED_TOOL_INPUT_KEYS` (whitelist projection, 256-char cap) prove we can produce safe summaries. `PRIVACY.md` line 1: "Nothing is transmitted off your machine by this tool." |
| Trade-off | Friction — the value of "auto" is diluted if the user must manually act every time. Mitigated by `gh issue create --body-file` being one command, not copy-paste. |
| Compatibility | 100% with `ADR-004`, `ADR-005`, `tests/unit/test_no_network.py`, `PRIVACY.md`. No schema changes needed. |
| Risk | low |

### Approach B — Opt-in auto-submission via gh CLI / GitHub MCP

| Field | Content |
|---|---|
| Approach | New axis `feedback.auto_submit: never \| review-first \| auto` (default `never`). When user opts in, post-command hook detects issues, sanitizes via three layers (whitelist → second LLM pass classifying "harness-self vs user-code" → user confirm), then submits via local `gh` CLI (auth already on user machine) or a configured GitHub MCP server. |
| Assumption | A multi-layer sanitization pipeline can reliably keep customer data out, AND users will trust an opt-in flag they configured themselves. |
| Evidence | GitHub CLI itself shipped opt-out (not opt-in) telemetry in v2.91.0 (April 2026) and was [criticized on Hacker News](https://news.ycombinator.com/item?id=47862331) and [The Register](https://www.theregister.com/2026/04/22/github_opts_all_cli_users/) for documentation gaps on redaction. Filed issue [cli/cli#13263](https://github.com/cli/cli/issues/13263) demands "expand telemetry documentation to include sufficient information for informed policy decisions." Even an industry incumbent shipping opt-out drew immediate backlash. |
| Trade-off | (a) Privacy surface expands materially — every PR touching telemetry has to argue "this can't leak customer code"; (b) `PRIVACY.md` ("Nothing is transmitted") must be rewritten; (c) `tests/unit/test_no_network.py` (ADR-005 positive obligation) must be amended to whitelist the new code path — a known-fragile pattern (whitelist tests rot); (d) LLM-based sanitization is probabilistic — second pass can hallucinate "this looks safe" on subtle PII. |
| Compatibility | Breaks `ADR-004` ("PRIVACY.md only; no opt-out env var" was a deliberate choice — adding `auto_submit` re-opens the same drift surface). Breaks `tests/unit/test_no_network.py` unless carved out. |
| Risk | high |

### Approach C — Hybrid: auto local draft + explicit `/hm:feedback`

| Field | Content |
|---|---|
| Approach | Tail of every `/hm:*` command runs cheap heuristics over local telemetry (slow command, repeated retries, hook errors, agent dispatch failures) → if a candidate harness-self issue found, writes a draft to `.claude/observability/feedback/{YYYY-MM-DD-slug}.md` with the bug.yml fields pre-filled and a `## Redaction notes` block. Drafts queue silently — no UI noise. New `/hm:feedback` slash command lists pending drafts; user picks one, reviews it (LLM-rendered diff highlighting any field that looks like a file path / identifier / domain artifact), and either deletes or runs `gh issue create --web` (browser opens with body pre-filled; **user clicks Submit, not us**). |
| Assumption | Splitting "intelligence" from "transport" lets us automate the hard part (deciding what to report) while keeping the easy part (clicking Submit) explicit and reviewable. |
| Evidence | `gh issue create --web` is the exact pattern `gh` itself uses for safety-critical submissions — body pre-filled, server-side preview, manual submit. Local telemetry already captures enough signal: `metrics-YYYY-MM-DD.jsonl` (tool durations, error rates), `review-YYYY-MM-DD.jsonl` (build-break counts, auto-fix reverts), `silent-intent-miss-{slug}.jsonl` (gate misclassifications). The bug.yml template is structured exactly for this fill-in pattern. |
| Trade-off | Two surfaces to maintain (draft generator + review/submit command). Heuristics for "this is a harness-self issue" need iteration — initial false-positive rate will be uncomfortable until the rubric is tuned. |
| Compatibility | 100% with `PRIVACY.md`, `ADR-004`, `ADR-005`, `tests/unit/test_no_network.py` during normal operation (draft generation is local-only file IO). The `/hm:feedback` command itself shells out to user-installed `gh` — not our process making the HTTPS call. |
| Risk | low-to-medium (medium only on the heuristic-tuning side; zero on privacy). |

### Approach D — Maintainer-dogfooding opt-in (recommended) ✅

| Field | Content |
|---|---|
| Approach | New `harness.yaml.feedback.enabled: bool` (default `false`), togglable **only** via interview. When `false`, every code path is dead — dispatcher templates wrap the tail block in `{% if feedback_enabled %}`. When `true`, each `/hm:*` command tail runs cheap heuristics over local telemetry, writes a draft to `.claude/observability/feedback/{YYYY-MM-DD-slug}.md`, and prints a one-line footer like: `📝 feedback draft saved → .claude/observability/feedback/2026-05-23-slow-research.md (run: gh issue create --web --body-file <path>)`. No `AskUserQuestion`, no new slash command, no HTTP. Maintainer manually runs the printed command when they want to submit. |
| Assumption | Single-maintainer dogfooding doesn't need scale, queue management, dedup pressure, or a curated review UX — a printed path + one shell command is enough. The maintainer is also the one who will tune the trigger rubric, so initial false-positives are a self-correcting loop. |
| Evidence | Pattern parallels `git stash` — silent local artifact + later explicit recall. The dispatcher template already conditionally renders sections per `harness.yaml` axes (e.g., second_brain, model routing, presets) — adding one more `{% if feedback_enabled %}` block is the established pattern, not a new architecture. `gh issue create --web --body-file` is documented and stable. |
| Trade-off | (a) Other users get no benefit (acceptable — maintainer is the only one expected to need this initially; if patterns prove out, broadening is a separate decision); (b) Footer adds one line to every command tail when on — minor visual noise that only the maintainer sees; (c) Heuristic tuning is a long tail (mitigated by being maintainer-only — broken heuristics affect only the person who can fix them). |
| Compatibility | When `enabled: false` (the global default): bit-identical to today — `PRIVACY.md`, `ADR-004`, `ADR-005`, `tests/unit/test_no_network.py` all stay literally unchanged with no carve-outs. When `enabled: true`: still only local file IO + a printed shell command; no socket call from our process. |
| Risk | low |

## ⚠️ Pitfalls

1. **Opt-out default-on telemetry is a freshly-burned industry pattern.** GitHub CLI v2.91.0 (April 2026) shipped exactly this and faced sustained backlash for opaque redaction. [The Register](https://www.theregister.com/2026/04/22/github_opts_all_cli_users/) and [Hacker News thread](https://news.ycombinator.com/item?id=47862331) both fixated on "what gets sent" lacking precision. If we ship opt-out, we walk into the same trap one month later — worse, because we explicitly committed in `PRIVACY.md` ("Nothing is transmitted") not to.
2. **LLM-based redaction is probabilistic.** Even with `_SECRET_PATTERNS` (sk-/ghp_/AKIA/Bearer) plus a second LLM-pass "is this safe?" classifier, the failure mode is silent: the bad payload looks fine to the classifier and ships. The only fully-safe gate is "human reads the final body before clicking Submit" (Approach C).
3. **Customer data is broader than secrets.** Repo names, file paths, function names, error messages with paths, even hook output — all are "customer data" the user said never to leak. Whitelist projection (already in `telemetry.py`) catches *known* fields; novel fields added later (e.g., a new hook handler dumping more context) silently bypass. Mitigation: AST-walk drift test for any new telemetry field (PR check), same pattern PRIVACY.md uses.
4. **Submission frequency creates noise.** "Every `/hm:*` command end" runs many times per session. Even if drafts are silent, the *generation* burns tokens. Mitigation: rate-limit (`once per slug per day`) + dedupe by heuristic-key.
5. **Heuristic for "harness-self vs user-code" issue.** A slow build is the user's code; a slow `/hm:research` is ours. Mis-classification produces wrong issue title ("harness-maker is slow" when it's the user's monorepo). Mitigation: rubric inspects only our own code paths (agent dispatch, hook stop time, plan-validator latency), never user build/test results.
6. **GitHub MCP server lock-in.** If "via MCP" means a hosted server, we'd add a third-party trust boundary that PRIVACY.md cannot promise. `gh` CLI (local binary, user's existing auth) is the safer transport — same outcome, no new vendor.
7. **Existing `tests/unit/test_no_network.py` is a positive obligation, not a soft warning.** It monkey-patches `socket.socket` to raise. Approach B requires either carving out a whitelist (whitelist rot) or moving the network call to a separate process (process boundary is essentially Approach C anyway).

## ❓ Open Questions

User-resolved (locked in by user mid-research, no further interview needed):
- ~~Default off vs on~~ → **off** (opt-in).
- ~~Toggle surface~~ → **interview only** (no CLI flag, no env var).
- ~~Separate `/hm:feedback` slash command~~ → **no** (tail footer only).
- ~~MCP server vs gh CLI~~ → **gh CLI** (no third-party trust boundary).

Still blocking `/hm:plan`:

1. **Trigger rubric.** Which local telemetry signals justify a draft? Concrete candidates: (a) hook errors in `.claude/observability/metrics-*.jsonl`, (b) any command exceeding p95 wall-time from recent history, (c) repeated retry events, (d) `silent-intent-miss-*.jsonl` rows, (e) `review-*.jsonl` rows with `build_break_count > 0`. Each needs a false-positive estimate. Likely start with (a) + (d) + (e) — the three already labeled "harness-self" in their schemas — and skip (b)/(c) until needed.
2. **Footer format.** One line vs short block? Quiet mode (only when draft created) vs always (with "no drafts today" reassurance)? Recommend: silent when nothing to report, one line when a draft is created.
3. **Dedup / rate-limit.** If two `/hm:*` commands in the same session both detect the same hook error, do we write two drafts or one? Recommend: hash by `(trigger_signal_id, slug)`; if matching draft already exists today, skip silently.
4. **Heuristic accuracy for "harness-self vs user-code."** Trigger rubric (1) inherently filters to our own code paths (we own all the schemas in the candidate list). But e.g. an LLM call failing inside `/hm:research` could be either our agent dispatch bug or a user's wonky API key. Recommend the draft body explicitly tags `confidence: low|medium|high` and the maintainer eyeballs `low` ones before submitting.
5. **PRIVACY.md amendment scope.** When `enabled: false` (everyone except maintainer), `PRIVACY.md` stays literally true verbatim — no edit needed. But the *code* for feedback drafts ships in the package even when off. Recommend adding one paragraph: "harness-maker contains an opt-in feedback module (`feedback.enabled` in `harness.yaml`, default `false`); when off, it is a dead code branch and emits zero file or network IO." This pre-empts a future PR-reviewer or HN poster catching the diff and accusing weasel-wording.
6. **AST-walk drift test extension.** `tests/unit/test_privacy_doc_schema.py` enforces telemetry schema ↔ doc sync. Should the same test cover the feedback-draft schema? Recommend yes — even though only the maintainer uses it, the draft fields are user-facing on GitHub when submitted, so schema drift is a real risk.
7. **Interview wording.** Phrasing matters here — the question that turns this on should explicitly say "maintainer dogfooding only; non-maintainers should keep this off." Otherwise other users will flip it on out of curiosity and end up either ignoring tail footers or accidentally submitting issues they don't understand.

## 📚 Sources

- [GitHub CLI: Opt-out usage telemetry (Changelog, April 22 2026)](https://github.blog/changelog/2026-04-22-github-cli-opt-out-usage-telemetry/) — opt-out default-on rollout that drew industry backlash one month before this research.
- [The Register: GitHub CLI begins collecting client-side user telemetry](https://www.theregister.com/2026/04/22/github_opts_all_cli_users/) — Critical coverage of the default-on choice.
- [Hacker News discussion #47862331](https://news.ycombinator.com/item?id=47862331) — community criticism centered on redaction-clarity gaps.
- [cli/cli#13263 — Expand telemetry documentation](https://github.com/cli/cli/issues/13263) — formal demand for documentation precision that we should pre-empt.
- [GitHub CLI telemetry docs](https://docs.github.com/en/github-cli/github-cli/github-cli-telemetry) — `GH_TELEMETRY=false` / `DO_NOT_TRACK=true` / `gh config set telemetry disabled` envelope.
- [Groundy: GitHub CLI v2.91.0 turns on default telemetry](https://groundy.com/articles/github-cli-v2910-turns-on-default-telemetry-what-gh-collects-and-how-to-opt-out/) — exact fields collected (good comparator for our payload size).

## 🔗 Related Internal Docs

- [[PRIVACY.md]] — "Nothing is transmitted off your machine by this tool" + 4-file schema (`metrics`, `adaptive/overrides`, `review-`, `silent-intent-miss-`). Approach C preserves this verbatim.
- [[PLAN-oss-readiness-audit]] — ADR-004 ("PRIVACY.md only; no opt-out env var") and ADR-005 ("no-network positive obligation"). Both ADRs were deliberate; Approach B would re-litigate them.
- [[telemetry.py]] — existing redaction primitives (`_ALLOWED_TOOL_INPUT_KEYS`, `_SECRET_PATTERNS`, 256-char cap, atomic write). Reusable for Approach C draft generator.
- [[review_telemetry.py]] — per-`/hm:review` JSONL pipeline. Same pattern reusable.
- [[test_no_network.py]] — monkeypatches `socket.socket` to raise. Approach C passes unmodified; Approach B requires carve-out.
- [[bug.yml]] (`.github/ISSUE_TEMPLATE/bug.yml`) — already-structured fields. Draft generator pre-fills these exactly.
- [[feedback_domain_content_ownership]] (memory) — domain content owner = user. Same principle: harness-maker authors *the issue template + the redaction rubric*; user authors *the decision to submit*.
- [[wiki:fresh-install-health-baseline]] — `/hm:health` Layer 1 already classifies harness-self issues (the same rubric reusable as the draft generator's heuristic).
