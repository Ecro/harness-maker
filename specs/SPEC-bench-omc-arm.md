---
type: spec
task_slug: bench-omc-arm
status: approved
created: 2026-11-28
tags: [bench, eval, saga, comparison]
test_framework: pytest
interview_rounds: 0
summary: An `omc` arm in the tier 1/2 bench and the saga bench - oh-my-claudecode loaded from a pinned local checkout with `--plugin-dir`, prompted through its lightest execution mode `/oh-my-claudecode:execute`, in its own HOME, reported beside plain and hm without touching the existing arms or the published README block.
---

# SPEC — bench-omc-arm

## Intent

The DRI wants hm compared with a popular open-source harness, not only with a raw prompt.
They named oh-my-claudecode (OMC, Yeachan-Heo/oh-my-claudecode, MIT, v5.8.9) and asked for
its token-saving execution mode. OMC has no official light build (its README points to
gajae-code, which is a separate agent CLI rather than a Claude Code plugin, so it would
compare agents, not harnesses) and no eco mode any more; its lightest execution mode is
`/oh-my-claudecode:execute` (one lead agent that delegates only when the task needs it).
The DRI chose the scope on a card on 2026-11-28: saga bench (plain, hm, omc x 5) plus tier
1/2 (plain, hm, omc x 3), about $75.

## Outcomes

- `bench_light_lane.py run --arms plain,hm,omc --omc-dir <checkout>` and
  `saga_bench.py run --arms plain,hm,omc --omc-dir <checkout>` run an OMC arm next to the
  existing arms.
- `report` shows the omc arm with cost and wall-time ratios against plain (tier 1/2) and its
  trap rates beside hm (saga).
- Every existing arm's prompt, argv, environment, template and runner hash stay as they were.

## In-Scope Scenarios

- **S1 (normal, tier 1/2):** Given an OMC checkout, when the bench runs the omc arm, each
  agent call gets `--plugin-dir <checkout>`, the prompt starts with
  `/oh-my-claudecode:execute `, HOME is the cell's own directory, and the row carries
  `omc_sha` and `omc_version`.
- **S2 (normal, saga):** the same for every session of a saga run, with one HOME per run so
  OMC's own memory can carry across that run's sessions but never across runs; a resume
  session stays bare, as for every arm.
- **S3 (failure):** the omc arm without `--omc-dir`, `--omc-dir` without the omc arm, or a
  directory that is not an oh-my-claudecode plugin: refused with exit 2 before any model call.
- **S4 (edge, reports):** `report` prints an external-arm block when omc rows exist; tier
  1/2 `publish` leaves omc rows out of RESULTS.md and the README block; the saga verdict
  (hm vs plain-discipline) is unchanged by omc rows.

## Non-Goals

- Superpowers or any other harness arm (only OMC was asked for; the loader is not generic).
- Other OMC modes (autopilot, ralph, team) or OMC model-routing changes: OMC runs with its
  shipped defaults, so its subagents may use models other than `--model`.
- The scripted DRI for omc on tier 2: omc, like plain, gets one headless prompt per session.
- The replay bench (`replay.py` lives in project files, not the repo).
- Publishing omc figures into README/RESULTS.md, and recording any intent metric.
- Installing or fetching OMC: the operator supplies a checkout.

## Constraints

| Constraint | Source |
|---|---|
| pytest; unit tests mock every model call | CLAUDE.md test policy |
| No change to plain/hm/control/variant arm behaviour or their runner hashes | DRI comparison against earlier rows |
| Refuse before spend on a bad omc setup | bench convention (variant arm) |
| OMC state must not leak across cells | OMC writes `~/.omc` via `homedir()` |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: the omc arm and --omc-dir come together and are checked before spend

`omc_setup(arms, omc_dir)` returns None without the arm and the flag, `(sha, version)` for a
directory whose `.claude-plugin/plugin.json` names `oh-my-claudecode`, and raises
`OmcError` for the arm without the flag, the flag without the arm, or a directory that is
not that plugin. Both runners exit 2 on `OmcError`.

### AC-002: the omc prompt is OMC's execute mode; other prompts are unchanged

bench_light_lane `prompt_for(task, "omc", s)` is `OMC_PREFIX + prompt` on every session;
saga `prompt_for(session, "omc")` is `OMC_PREFIX + prompt` except a resume session, which
stays bare. Every other arm's prompt equals the golden rows taken from the unchanged code.

### AC-003: omc agent calls load the plugin; other argv are unchanged

The omc arm's agent argv is the shared argv plus `--plugin-dir <dir>`; every other arm's
argv is unchanged.

### AC-004: omc runs in its own HOME, keeping the config dir

The omc arm's agent env sets HOME to the cell's (saga: the run's) `home/` directory, which
holds a copy of the operator's `~/.gitconfig` when one exists, and keeps CLAUDE_CONFIG_DIR
(set to the operator's `~/.claude` when unset) so auth and transcripts stay where the bench
reads them. Other arms' env is unchanged.

### AC-005: provenance and hashes

omc rows carry `omc_sha` and `omc_version`; the runner hash includes the OMC sha only when
the omc arm is set, so every hash without it equals the unchanged code's.

### AC-006: reports

bench_light_lane `report_text` adds a per-tier external-arm block (runs, solved, $/run,
x plain, wall s, x plain) when omc rows exist and is unchanged without them; `publish_rows`
drops omc rows. The saga report lists omc as an arm and adds an hm-vs-omc trap line; the
verdict ignores omc rows.

## Verification

| Scenario | Mode | AC |
|---|---|---|
| S3 | unit | AC-001 |
| S1, S2 | unit | AC-002, AC-003, AC-004, AC-005 |
| S4 | unit | AC-006 |
| S1, S2 | manual (pilot run, ~$5) | all |

## Open Questions

none

## Refinement Decisions

- **Approval:** the DRI picked "사가 + tier 1·2 (약 $75)" on the scope card (2026-11-28) after
  the arm design (OMC execute mode, `--plugin-dir`, gajae-code excluded) was posted in the
  thread; this SPEC writes that design down. Undo: revert the PR.
- **Mode = `/oh-my-claudecode:execute`:** the README's lightest mode; autopilot adds
  ralplan/QA/validation stages, ralph and team loop or fan out. Undo: change `OMC_PREFIX`.
- **Pinned local checkout via `--plugin-dir`, not a marketplace install:** per-call,
  needs no write to the config dir shared by all cells, and the sha is recorded. Verified
  headless on 2026-11-28 (plugin listed in init, node hooks ran). Undo: minutes.
- **Own HOME per cell (per run for saga):** OMC writes global state under `homedir()/.omc`,
  which parallel cells would otherwise share; plain and hm keep the operator HOME so their
  rows stay comparable with earlier runs. The omc HOME links the operator's tool caches and
  user installs (`.cache`, `.local`, `.npm`, `.bun`, `.cargo`, `.rustup`, `.nix-profile`) so
  a cold cache does not bias omc's cost or wall time; `.config` stays out (OMC keeps
  `claude-omc` there). Undo: minutes.
- **Pinned = git checkout:** `omc_sha` is HEAD plus `-dirty` for a dirty tree; a non-git
  directory is refused. Because the sha enters the runner hash, omc starts in a fresh `--out`
  together with plain and hm (an existing plain/hm dir refuses to resume with it).
- **OMC defaults kept (model routing, hooks):** the comparison is OMC as shipped in its
  lightest mode; the row's CLI total covers every subagent model. Undo: minutes.
- **No tier-2 DRI for omc:** the scripted DRI answers hm's interview; plain gets none, and
  omc is compared on the same footing as plain. On the saga the owner simulator answers
  every arm. Undo: an arm entry in `uses_dri`.
- **Saga control not re-run:** the DRI's budget covers plain/hm/omc; the saga verdict needs
  plain-discipline and will read "insufficient" without it, so the report adds the hm-vs-omc
  line. Undo: add the arm to the run.
