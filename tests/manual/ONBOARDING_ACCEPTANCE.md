# Manual acceptance — fresh-install onboarding paths

PLAN-onboarding-interview-ux Phase 7. These rows cannot be automated: they test whether an
LLM *executes* the prose in `commands/make.md` correctly, and no fixture in this repo drives
a real slash-command invocation. Everything that a fixture CAN settle lives in
`tests/e2e/test_onboarding_paths.py`, `tests/structural/test_make_fastpath_contract.py`, and
`tests/unit/test_render_configure_health_second_opinion.py`; those run in CI and are not
repeated here.

Fill the Result and Date columns on each release that touches `commands/make.md`,
`configure.md.j2`, or `health.md.j2`. **An empty row is a row that was not run** — do not
read a blank as a pass.

## Setup

Run each scenario in a scratch git repo (`git init`), from a session where you can control
whether `codex` / `agy` resolve on `PATH`. To simulate absence without uninstalling:

```bash
env PATH="/usr/bin:/bin" claude   # or prepend a dir with no codex/agy symlink
```

## Scenarios

| # | Setup | Action | Expected | Result | Date |
|---|---|---|---|---|---|
| 1 | Neither `codex` nor `agy` on PATH | `/harness-maker:make` → "Looks right" | **Zero** extra questions. Install proceeds straight to the preview. The §4.3 summary shows the "Set for you" table and NO "Detected on this machine" block. | | |
| 2a | `codex` on PATH only | `/harness-maker:make` → "Looks right" | **Exactly one** question, about the second opinion, naming codex. §4.3 shows codex as installed, antigravity as not. | | |
| 2b | as 2a | answer: enable | `harness.yaml` `second_opinion.models == ["codex"]` | | |
| 2c | as 2a | answer: enable none | `second_opinion.models == []`, and the flag is omitted from the dispatch rather than passed empty | | |
| 3a | `agy` on PATH only | "Looks right" | one question naming antigravity | | |
| 3b | both on PATH | "Looks right" | one question offering both; enabling both yields `["codex","antigravity"]` | | |
| 4 | any | `/harness-maker:make` → "Adjust a few things" | the multi-select lists **second_opinion** and **autonomy** alongside the pre-existing dimensions | | |
| 5 | harness with `second_opinion.models: []`, `codex` installed | `/hm:health` | an advisory naming codex as installed-but-unused, pointing at `/hm:configure`. It must not fail the audit. | | |
| 6 | harness with `second_opinion.models: ["codex"]` | `/hm:health` | the positive smoke runs; **no** installed-but-disabled advisory (the two must never both appear) | | |
| 7 | `second_opinion.models: []`, neither CLI installed | `/hm:health` | silence — no advisory at all. A user without these tools is not nagged every audit. | | |
| 8 | any | rename `detect-tools` out of PATH resolution, or corrupt its output | `/harness-maker:make` and `/hm:health` both continue, treating every tool as absent. Neither errors. | | |
| 9 | any | `/hm:configure` → second opinion / autopilot / locale | each dimension is offered, shows its current value, and dispatches only its own flag | | |
| 10 | fresh install | read the post-install quick-start | it tells you to run `/hm:health` FIRST, with named success criteria, and every command it names exists | | |

## Known limitation

Rows 1-4 depend on the model following branch prose. `test_make_fastpath_contract.py` pins
the branch *structure* — that both paths exist, that the no-detection path reaches dispatch
without a question, that at most one question is defined, and that its answer flows to
`--second-opinion-models`. It cannot pin that the model takes the right branch at runtime.
That gap is why this file exists rather than being replaced by the contract test.
