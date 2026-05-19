<!--
Two-tier template. Fill in the "Always required" section.
Expand the "Core-module changes" section ONLY if your PR touches:
  - src/harness_maker/render.py
  - src/harness_maker/reconcile.py
  - src/harness_maker/synthesize.py
  - src/harness_maker/interview.py
  - src/harness_maker/cli.py
  - Anything under src/harness_maker/templates/ that other modules render
See ADR-011 in work-docs/PLAN-oss-readiness-audit.md for the rationale.
-->

## Summary

<!-- One or two sentences. What does this PR change, and why? -->

## Always required

- [ ] Ran `uv run ruff check .` locally — clean.
- [ ] Ran `uv run ruff format --check .` locally — clean.
- [ ] Ran `uv run mypy --strict src` locally — clean.
- [ ] Ran `uv run pytest -x --tb=short` locally — green.
- [ ] CHANGELOG.md entry added (skip if change is internal-only / not user-visible).
- [ ] If this is a version bump: all **five** version files moved in lockstep (`.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`). See CLAUDE.md "버전업 정책".
- [ ] Linked issue or short rationale below.

Linked issue / rationale:

<!-- e.g., "Fixes #123" or "No issue — typo in README" -->

<details>
<summary>Core-module changes — open ONLY if this PR touches render / reconcile / synthesize / interview / cli</summary>

The 8 checkpoints from `CLAUDE.md` apply when changing core modules. Mark `OK` / `N-A` for each:

- [ ] **1. User-state preservation contract drawn** — what user-touched files could this write delete? Policy flag in place?
- [ ] **2. External-consumer parser alignment verified** — for every file we render, the reader (Claude Code, Cursor, Codex CLI, GitHub Actions, etc.) accepts the format we ship. Frontmatter only where the consumer parses it.
- [ ] **3. Settings precedence considered** — if writing under `.claude/`, `.cursor/`, or `.codex/`, the precedence chain (enterprise → team → project → user) was checked.
- [ ] **4. CLI vs slash-command boundary preserved** — CLI is flag-driven, no `AskUserQuestion`; slash commands collect intent then dispatch to flagged CLI.
- [ ] **5. Fingerprint-based auto-upgrade vs preserve branch** — `content_hash` checked before overwriting user-touched output.
- [ ] **6. Bidirectional mapper exists** — anything new written to disk has a `read` path (e.g., `answers_from_harness_yaml`).
- [ ] **7. Test determinism + environment isolation** — `freeze_time`, `Path.home()` mocking, `INTEGRATION=1` guard for external calls.
- [ ] **8. Integration-boundary smoke test added** — at least one e2e or `subprocess`-based test that exercises the user-facing surface.

</details>

## Notes for the reviewer (optional)

<!-- Anything non-obvious: an ADR you deliberately diverged from, a regression test you couldn't add, a follow-up issue you'll file. -->
