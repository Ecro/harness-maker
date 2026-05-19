# Security Policy

> **Solo-maintained project — best-effort response.** harness-maker has one maintainer. There is no SLA on disclosure timeline. Reports are read but may take days to respond. See [ADR-010 in `work-docs/PLAN-oss-readiness-audit.md`](work-docs/PLAN-oss-readiness-audit.md) for the rationale.

## Reporting a vulnerability

**Primary channel — GitHub Private Vulnerability Reporting:**

→ <https://github.com/Ecro/harness-maker/security/advisories/new>

Why this channel: encrypted, audit-logged, and the GitHub UI surfaces a "Report a vulnerability" button on the repo's Security tab. Reports remain private until a fix lands.

**Backup channel — email:**

`e839638@gmail.com` (set subject prefix `[harness-maker security]`). Use this only if you do not have a GitHub account or PVR is unavailable.

**Do not file public GitHub Issues for security reports.** Public disclosure before a fix exposes users.

## Scope

In scope (vulnerabilities here will be triaged):

- `src/harness_maker/**` — runtime code (CLI, renderer, reconcile, telemetry emitter, hooks, autoloop driver, worktree manager).
- `templates/**` — all generated harness assets (`.claude/*`, `.cursor/*`, `.codex/*`, `AGENTS.md`).
- `hooks/**` — telemetry + session-start hooks.
- `agents/**` and the rendered reviewer/executor permission policies — privilege-separation correctness.
- `.github/workflows/**` — supply-chain (action SHA pinning, PyPI Trusted Publisher subject).

Out of scope (route elsewhere):

- Vulnerabilities in third-party dependencies — file with the upstream project; if you believe a transitive dep introduces a CVE we propagate, mention it in a regular Issue with the CVE link and we'll bump the lock file.
- Example projects under `tests/e2e/sandbox/` and `tests/e2e/sandbox-plugin-test/` — these are throwaway fixtures, not production code.
- Anthropic Claude Code / Cursor / Codex platform bugs — report to those vendors directly.

## What to include in a report

- Affected version (`harness-maker --version`).
- Reproduction steps with a minimal harness.yaml or input fixture.
- Observed vs expected behavior.
- Severity assessment (CVSS optional).
- Whether you've coordinated with any other parties.

## What to expect after reporting

- **Acknowledgement.** Best-effort within 7 days. If you don't hear back in 14 days, ping via the backup channel — the primary may have been missed.
- **Triage.** The maintainer will assess severity and reproduce.
- **Fix.** For confirmed P0 (CVSS ≥ 7.0) issues, the maintainer aims to publish a patch release within 30 days. No guarantee — this is a solo project.
- **Disclosure.** Coordinated. A GitHub Security Advisory is published after the patch release.
- **Credit.** Reporters are credited in the advisory unless they request anonymity.

## P0 definition

A bug is treated as P0 (drop-everything) if any of:

1. `harness-maker:make` fails on a clean repository (`Side` or `Production` preset) on a supported Python version (3.12+).
2. Published telemetry record contradicts [`PRIVACY.md`](PRIVACY.md) (extra or undocumented field).
3. Security issue with CVSS ≥ 7.0.
4. Data-loss bug in `render` or `reconcile` (user files overwritten without provenance match).

Anything else gets normal triage.

## Past advisories

None yet. This file ships with the initial OSS launch.
