---
type: spec
task_slug: bench-decoy-proxy
status: approved
created: 2026-10-17
tags: [harness-maker, spec, python, bench, ci, tests]
test_framework: pytest
interview_rounds: 0
lane: light
summary: "the bench env-allowlist test's decoy proxy no longer hijacks the runner's own uv probe, so CI's quality gate (and release.yml's) can pass"
---

# SPEC: the bench test's decoy proxy stays a decoy

## 🎯 Intent

Every `ci` run on main since the bench CLI-provenance check (SPEC-bench-cli-provenance) fails
quality-gate at `tests/unit/test_bench_light_lane.py::test_arms_differ_only_by_harness_and_prefix`
(e.g. run 39009871644): `cannot import the hm arm's CLI ... Failed to fetch https://pypi.org/simple/anthropic/
... tunnel error`. The module fixture `bench_run` puts `HTTPS_PROXY=http://proxy.invalid:1` in the
runner's environment to prove the agent env forwards proxy variables. The runner's own
`check_cli_fresh` probe (`uv run --no-project --with <checkout>`, under a fresh `HOME`, so a cold uv
cache) then sends its pypi traffic to that dead proxy. It passes in the dev container only because the
container's `NO_PROXY` exempts `pypi.org` and `files.pythonhosted.org`. release.yml's quality gate runs the same suite,
so no tag can publish until this is fixed. The DRI chose "지금 릴리스" (release 0.65.0 now) on a card.

## 🧩 In-Scope Scenarios

- **S1.** Given a runner environment whose `NO_PROXY` does not exempt pypi (CI), when the `bench_run` fixture
  runs, then the CLI probe reaches pypi and every test in the module passes, and the agent's env still
  carries the decoy proxy variable the test set.

## 🚫 Non-Goals

- No change to `scripts/bench_light_lane.py`; the probe running under the agent's env is intended
  (same uv cache the agent will use).
- Making the bench test network-free.

## 🔒 Constraints

| constraint | source |
|---|---|
| Test framework: pytest | repo |
| The forwarding assertion keeps checking a proxy variable from `_AGENT_ENV` | SPEC-hm-light-lane-bench |

## ✅ Acceptance Criteria

### AC-001: the decoy proxy is forwarded but does not route the runner's https traffic
`bench_run` sets the decoy as `HTTP_PROXY` (http scheme only; pypi is https), and
`test_agent_gets_an_allowlisted_environment` asserts the agent env carries it. With `NO_PROXY` and
`no_proxy` removed from the environment, the module passes.
- oracle_source: golden. The failure is CI run 39009871644's log, reproduced locally by unsetting
  `NO_PROXY`/`no_proxy`; `HTTP_PROXY` applying only to `http://` URLs is uv's (reqwest's) documented proxy rule.

## 🧪 Verification

| AC | mode | test |
|---|---|---|
| AC-001 | unit | `tests/unit/test_bench_light_lane.py::test_agent_gets_an_allowlisted_environment` (run with `env -u NO_PROXY -u no_proxy`) |

## 🔧 Refinement Decisions

- Step 0 skip: one test file, obvious acceptance, no contract change, reversible. `lane: light`, exempt.
- `HTTP_PROXY` over a `NO_PROXY` exemption: one value changes and the test still proves a proxy
  variable reaches the agent; a `NO_PROXY=*` would also bypass the dev container's real proxy.
