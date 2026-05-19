# Contributing to harness-maker

> **Status:** harness-maker is solo-maintained and experimental. PRs and issues are welcome, but there is no service-level agreement on triage time. Treat this as "send PRs at your own risk" — your contribution may sit unreviewed for weeks. Filing an issue first to discuss approach is usually faster than sending a large PR cold. See [ADR-002 in `work-docs/PLAN-oss-readiness-audit.md`](work-docs/PLAN-oss-readiness-audit.md) for the rationale.

## Quick start

1. Read [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) for the deep guide (repo layout, where code lives, test conventions).
2. Run the standard local checks before opening a PR:
   ```bash
   uv sync --frozen
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy --strict src
   uv run pytest -x --tb=short
   ```
3. Open a PR; the `ci` workflow runs the same checks automatically.

## What counts as a good PR

- **Typo / doc fix** — open it. Short message + the change.
- **Bug fix** — link the issue (or describe the bug if none), add a regression test, and ensure all local checks pass.
- **New feature** — file an issue first. A "hey, I'm thinking of doing X — does that match the project direction?" thread saves you and the maintainer time.
- **Refactor** — only when it makes a *specific upcoming change easier*. Refactors without a destination get rejected.

## Stability surface

Some surfaces are frozen across 0.x releases — breaking them needs an ADR and a major version bump. See the [`## Stability`](README.md#stability) section in the README for the current frozen set. If your change touches one of those surfaces, mention it in the PR description.

## Version-bump rule

If your PR ships a user-visible change, **five files** must move version together — see CLAUDE.md "버전업 정책" / "versioning policy". Missing one breaks `/plugin update` for Claude Code, Cursor Marketplace, and Codex CLI simultaneously.

## Telemetry & privacy

harness-maker writes local-only telemetry. See [`PRIVACY.md`](PRIVACY.md) before adding new fields. A test (`tests/unit/test_privacy_doc_schema.py`) fails any PR that adds a telemetry field without documenting it.

## Legal

No DCO sign-off, no CLA. By opening a PR you license your contribution under the project's [MIT License](LICENSE).

## Code of Conduct

See [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). This project uses a solo-maintainer adaptation of Contributor Covenant 2.1 — enforcement is best-effort.
