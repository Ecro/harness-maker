# Workflow execution evidence — world-intent-closed-loop

These are isolated synthetic fixtures executed by the installed Codex CLI, not the three real task trial. Native dispatch used the rendered procedure plus a fixture next skill whose unique payload digest was unknown to the prompt. The boundary implementation was real and unchanged. Feedback fixtures used canonical state and the real intent CLI. Original temporary transcripts are identified below; relevant results are preserved here. No model override was supplied.

## authorized_codex_dispatch

Original source: `/tmp/hm-codex-native-3o3ffhol/events.jsonl`; SHA-256 `f3836ade518d6f5b0634ff34954c35574fffc40af632b1b979b1854dc35c6e16`.

```json
[
  {
    "command": "/bin/bash -lc 'HM_SESSION_ID=native-smoke uv run --with \"$HOME/harness-maker/.worktrees/world-intent-closed-loop\" hm autopilot_caps boundary --root . --current research --session-id \"native-smoke\" --step-cap 20 --time-cap-min 300 --slug '\"'native-smoke'\"",
    "exit_code": 0,
    "stdout_sha256": "ab966df34888c65be93bb430dc5eece70f014dcb100ac09726da630f18bbd84f",
    "stdout": "   Building harness-maker @ file:///home/noel/harness-maker/.worktrees/world-intent-closed-loop\nwarning: `build_system.requires = [\"uv_build>=0.5\"]` is missing an upper bound on the `uv_build` version such as `<0.11`. Without bounding the `uv_build` version, the source distribution will break when a future, breaking version of `uv_build` is released.\n      Built harness-maker @ file:///home/noel/harness-maker/.worktrees/world-intent-closed-loop\nInstalled 28 packages in 64ms\n[world] /tmp/hm-codex-native-3o3ffhol is not inside a git checkout; using it as the root\n{\"proceed\": true, \"halt_kind\": null, \"reason\": \"advancing to AtomicStage.SPEC\", \"steps\": 1, \"next_stage\": \"spec\", \"pipeline_complete\": false, \"task_slug\": \"native-smoke\", \"task_slug_source\": \"flag\", \"judgment_auto_answered\": false, \"judgment_directive\": null}\n"
  },
  {
    "command": "/bin/bash -lc 'sha256sum payload.txt'",
    "exit_code": 0,
    "stdout_sha256": "422c72d13604b4204356f3226bf4c867e3e32b1030a3c4edf88b56fe61fd99bc",
    "stdout": "b6b4be01414f6a31eb6fbb4a2081e343e49e992bc25ddbdc90a8df455552afe1  payload.txt\n"
  }
]
```

Observed final response:

{"stage":"spec","task_slug":"native-smoke","digest":"b6b4be01414f6a31eb6fbb4a2081e343e49e992bc25ddbdc90a8df455552afe1"}

## step_cap_halt

Original source: `/tmp/hm-codex-native-5v5wiarq/events.jsonl`; SHA-256 `9eaa1b88b9dbbb2b977203b4fb33bd63bc47a15ffac2cb7bb466579eceb3ff62`.

```json
[
  {
    "command": "/bin/bash -lc 'HM_SESSION_ID=native-smoke uv run --with \"$HOME/harness-maker/.worktrees/world-intent-closed-loop\" hm autopilot_caps boundary --root . --current research --session-id '\"'native-smoke' --step-cap 1 --time-cap-min 300 --slug 'native-smoke'\"",
    "exit_code": 0,
    "stdout_sha256": "6abb48917f42cfc250b5d993394d7ab1eea31399c6727ad4207fbf3c2dd6c5ca",
    "stdout": "{\"proceed\": false, \"halt_kind\": \"step_cap\", \"reason\": \"step cap reached (1/1)\", \"steps\": 1, \"next_stage\": null, \"pipeline_complete\": false, \"task_slug\": \"native-smoke\", \"task_slug_source\": \"flag\", \"judgment_auto_answered\": false, \"judgment_directive\": null}\n"
  }
]
```

Observed final response:

Boundary halted with `halt_kind: step_cap` (`1/1` steps reached). Stopped without reading or executing the next skill.

## entry_authorized_measurement

Original source: `/tmp/hm-feedback-entry-9y4nz_0d/events.jsonl`; SHA-256 `0a6c04f9f80f54e2e137bfff988951840031462da33d70d66a10cfdf989edcc1`.

```json
[
  {
    "command": "/bin/bash -lc 'uv run --with $HOME/harness-maker/.worktrees/world-intent-closed-loop hm intent status --json'",
    "exit_code": 0,
    "stdout_sha256": "91844a0a102dfe4772e798d70ab4cac438c23ea58cf0d08dbcc152fa9337203c",
    "stdout_projection": {
      "state": "ok",
      "active": {
        "FIXTURE-INTENT": {
          "approval_valid": true,
          "needs_revalidation": false
        }
      },
      "metrics": {
        "latency": {
          "last": null,
          "target": 10,
          "observed_at": null,
          "gap": "unevaluable",
          "stale_definition": false,
          "reason": "never_measured",
          "how_measured": "stopwatch",
          "higher_is_better": false,
          "measure": false
        }
      },
      "conflicts": []
    }
  },
  {
    "command": "/bin/bash -lc 'uv run --with $HOME/harness-maker/.worktrees/world-intent-closed-loop hm intent migrate --json'",
    "exit_code": 0,
    "stdout_sha256": "283f668448279329f6ad803a984842605b75cac6bf15f406e16b83655073f67f",
    "stdout": "{\"changed\": [], \"retired\": []}\n"
  },
  {
    "command": "/bin/bash -lc 'uv run --with $HOME/harness-maker/.worktrees/world-intent-closed-loop hm intent metric record latency --value 7 --observed-at 2026-09-22T01:20:00Z --evidence '\"'observation.txt:1'\"",
    "exit_code": 0,
    "stdout_sha256": "b893802609ecf5544c4cea50c2faa55403b41e043474fa78d73bb4c42b9e4258",
    "stdout": "value:\n  value: 7\n  observed_at: '2026-09-22T01:20:00Z'\n  evidence: observation.txt:1\n  definition_hash: 43b3d603a9ba25f94acd47be9bf220585ee5d47525127d68a9685279618fcd61\n  metric_id: latency\nchanged: .claude/intent/metrics.yaml\n"
  },
  {
    "command": "/bin/bash -lc 'uv run --with $HOME/harness-maker/.worktrees/world-intent-closed-loop hm intent status --json'",
    "exit_code": 0,
    "stdout_sha256": "03b1435ea7d246e08b062ab22d71536da1d11adc600ce5ec51f792b7d10b47ab",
    "stdout_projection": {
      "state": "ok",
      "active": {
        "FIXTURE-INTENT": {
          "approval_valid": true,
          "needs_revalidation": false
        }
      },
      "metrics": {
        "latency": {
          "last": 7,
          "target": 10,
          "observed_at": "2026-09-22T01:20:00Z",
          "gap": "at_or_better",
          "stale_definition": false,
          "reason": "measured",
          "how_measured": "stopwatch",
          "higher_is_better": false,
          "measure": false
        }
      },
      "conflicts": []
    }
  }
]
```

Observed final response:

Recorded latency **7**; CLI readback confirms it meets target **10**.

`changed: .claude/intent/metrics.yaml`

Updated [task PLAN](/tmp/hm-feedback-entry-9y4nz_0d/work-docs/PLAN-fixture-task.md) with evidence and disposition. No active trial exists.

Next action: user assessment of the broader intent outcome before authorizing closure. Authorized work is complete; the intent remains active, and no new tasks were created.

Canonical record SHA-256 before/after:
```json
{
  "before": {
    "intent/FIXTURE-INTENT.md": "3316e552754f8842388ecfadcc87beb568ea65b5f435fd5d172ae750b609c532",
    ".claude/intent.yaml": "523ea2195b3fad417ff7c44d889c19f3cc51d6bf9f8e84131203c1ed7d7bda1c",
    ".claude/intent/metrics.yaml": "b64a3d542eeba0355514bc253e1d8c0d4e5dfd04e30c50a13c4f91e2182372ce"
  },
  "after": {
    "intent/FIXTURE-INTENT.md": "3316e552754f8842388ecfadcc87beb568ea65b5f435fd5d172ae750b609c532",
    ".claude/intent.yaml": "523ea2195b3fad417ff7c44d889c19f3cc51d6bf9f8e84131203c1ed7d7bda1c",
    ".claude/intent/metrics.yaml": "db22250ca01724a14c878eec05d2f66b84fd31f6af184e80d55ea67f3ac45a30"
  }
}
```

## closeout_declined_write

Original source: `/tmp/hm-feedback-close-ojgk2y54/events.jsonl`; SHA-256 `acbfc1b4ad66969d7094ba3ef80e8bab8417ac728fc534b9db84fe431fb4ea64`.

```json
[
  {
    "command": "/bin/bash -lc 'uv run --with \"$HOME/harness-maker/.worktrees/world-intent-closed-loop\" hm intent status --json'",
    "exit_code": 0,
    "stdout_sha256": "91844a0a102dfe4772e798d70ab4cac438c23ea58cf0d08dbcc152fa9337203c",
    "stdout_projection": {
      "state": "ok",
      "active": {
        "FIXTURE-INTENT": {
          "approval_valid": true,
          "needs_revalidation": false
        }
      },
      "metrics": {
        "latency": {
          "last": null,
          "target": 10,
          "observed_at": null,
          "gap": "unevaluable",
          "stale_definition": false,
          "reason": "never_measured",
          "how_measured": "stopwatch",
          "higher_is_better": false,
          "measure": false
        }
      },
      "conflicts": []
    }
  }
]
```

Observed final response:

Completed fixture-task close-out and updated [PLAN Feedback](/tmp/hm-feedback-close-ojgk2y54/work-docs/PLAN-fixture-task.md).

The probe reports latency 7 against target 10. Metric and intent records remain unchanged as requested; the broader intent outcome remains unverified. No trial is active. No authorized work remains.

Canonical record SHA-256 before/after:
```json
{
  "before": {
    "intent/FIXTURE-INTENT.md": "3316e552754f8842388ecfadcc87beb568ea65b5f435fd5d172ae750b609c532",
    ".claude/intent.yaml": "523ea2195b3fad417ff7c44d889c19f3cc51d6bf9f8e84131203c1ed7d7bda1c",
    ".claude/intent/metrics.yaml": "b64a3d542eeba0355514bc253e1d8c0d4e5dfd04e30c50a13c4f91e2182372ce"
  },
  "after": {
    "intent/FIXTURE-INTENT.md": "3316e552754f8842388ecfadcc87beb568ea65b5f435fd5d172ae750b609c532",
    ".claude/intent.yaml": "523ea2195b3fad417ff7c44d889c19f3cc51d6bf9f8e84131203c1ed7d7bda1c",
    ".claude/intent/metrics.yaml": "b64a3d542eeba0355514bc253e1d8c0d4e5dfd04e30c50a13c4f91e2182372ce"
  }
}
```

## material_observation_replay

Original source: `/tmp/hm-feedback-entry-9y4nz_0d/replay-events.jsonl`; SHA-256 `50e729266f597015830398a4ef69add9ec7ccf7732a35273c5c0ca89105dee44`.

```json
[
  {
    "command": "/bin/bash -lc 'uv run --with $HOME/harness-maker/.worktrees/world-intent-closed-loop hm intent status --json'",
    "exit_code": 0,
    "stdout_sha256": "03b1435ea7d246e08b062ab22d71536da1d11adc600ce5ec51f792b7d10b47ab",
    "stdout_projection": {
      "state": "ok",
      "active": {
        "FIXTURE-INTENT": {
          "approval_valid": true,
          "needs_revalidation": false
        }
      },
      "metrics": {
        "latency": {
          "last": 7,
          "target": 10,
          "observed_at": "2026-09-22T01:20:00Z",
          "gap": "at_or_better",
          "stale_definition": false,
          "reason": "measured",
          "how_measured": "stopwatch",
          "higher_is_better": false,
          "measure": false
        }
      },
      "conflicts": []
    }
  }
]
```

Observed final response:

This is a replay: CLI status confirms latency **7**, meeting the **10** target, already recorded at the same timestamp.

Reuse the existing [PLAN disposition](work-docs/PLAN-fixture-task.md). Next action: stop; you assess the broader retention outcome and decide whether to authorize intent closure. No duplicate measurement, new task, or closure was performed. No active trial applies.

Canonical record SHA-256 before/after:
```json
{
  "before": {
    "intent/FIXTURE-INTENT.md": "3316e552754f8842388ecfadcc87beb568ea65b5f435fd5d172ae750b609c532",
    ".claude/intent.yaml": "523ea2195b3fad417ff7c44d889c19f3cc51d6bf9f8e84131203c1ed7d7bda1c",
    ".claude/intent/metrics.yaml": "db22250ca01724a14c878eec05d2f66b84fd31f6af184e80d55ea67f3ac45a30"
  },
  "after": {
    "intent/FIXTURE-INTENT.md": "3316e552754f8842388ecfadcc87beb568ea65b5f435fd5d172ae750b609c532",
    ".claude/intent.yaml": "523ea2195b3fad417ff7c44d889c19f3cc51d6bf9f8e84131203c1ed7d7bda1c",
    ".claude/intent/metrics.yaml": "db22250ca01724a14c878eec05d2f66b84fd31f6af184e80d55ea67f3ac45a30"
  }
}
```

## Review behavioral evidence (2026-09-22)

The independent native Codex protocol run at
`/tmp/hm-protocol-eval-jofs1mkd` passed all seven trial and five feedback
fixtures. Inputs, exact output PLANs, invocation prompt, and transcript digest
are retained in `tests/fixtures/world_intent_protocol_observed.json`.
The oracle was authored before execution and not supplied to the acting model;
the reproducible assertions live in `test_world_intent_protocol_evidence.py`.
This is captured empirical protocol evidence, not an automatic model call or
enrollment of actual repository tasks. Source binding normalizes only trailing
EOF whitespace. The earlier run at `/tmp/hm-protocol-eval-unkcxzdg` failed the
incomplete-source collection-state assertion; clarifying that activation keeps
collection active repaired it. The failure was not discarded.

Trial cases cover start order versus arrival/completion order, repeated-slug
resume, aborted tasks, missing evidence, confirmed failure before collection
completes, denied reset, successful continuity despite task abort, noncollector
handoff, and incomplete start intervals. Feedback cases cover missing, stale,
conflicting, not-yet-measurable, and delayed terminal evidence; the closed intent
remained byte-identical. These finite observations do not prove all future agents
will comply.

### Trigger controls and their limits

Native present-trigger runs for entry, material observation, and closeout
completed the intended state-write/readback or declined-write disposition.
Paired runtime omission experiments used the same prompt with the trigger
removed. Closeout then performed no feedback work; entry and observation still
discovered the intent skill through the generated project catalog and completed
the feedback. Their negative assertions therefore FAILED. These results show
host recovery, not a causal guarantee that omission prevents all feedback.

The deterministic owning-block integration fixtures fail when each trigger is
removed, while the positive native runs establish execution beyond keyword
presence. Runtime removal is inconclusive for entry/observation necessity and
is not reported as a passing behavioral negative control. Raw logs:
`/tmp/world-trigger-{entry,observation,close}-{present,removed}.log`.

### Authorized verification exception

The user explicitly approved omitting Claude live-environment tests for this
task on 2026-09-22. Only `tests/e2e/test_plugin_live.py` (four tests) is excluded.
Previous attempts failed on Claude weekly service quota. These tests are waived,
not passed; no global test selection or service configuration is changed.

## Resolved trigger controls: isolated stage dependency interface

The next experiment fixed the interface boundary before evaluating all three
pairs: both variants may execute only the supplied stage and its explicitly
referenced transitive dependencies. Ordinary task input and prior authority are
identical within each pair; only the real rendered trigger is removed. Global
catalog recovery is outside this fixture, not removed from the product.

All six provisioned runs exited 0. Entry and observation positives performed
real metric record + status readback and recorded the resulting next decision.
Closeout positive preserved declined canonical writes and recorded its explicit
declined disposition and stop decision. Each negative left canonical records
and PLAN unchanged, so the SAME completed-feedback assertion fails without the
trigger. Both canonical hashes and actual PLAN/metrics/CLI event outputs are
retained in tests/fixtures/world_intent_triggers_observed.json.

The first isolated entry/close positives encountered PyPI DNS failure while
bootstrapping the CLI; these incomplete traces remain in
/tmp/world-isolated-{entry,close}-present.log. Tool provisioning was then fixed
identically for all six final runs to use the already installed local engine.
The runner is retained as tests/fixtures/world_intent_trigger_runner.py.txt
(run with PYTHONPATH=. uv run python <runner> <entry|observation|close>
<present|removed>). Its absolute launcher is fixture provenance, not shipped
workflow configuration; substitute the current checkout's installed launcher
when independently repeating it.

This satisfies the isolated trigger-interface control; it does not relabel the
earlier unrestricted host-recovery experiments as passing negative controls.

The first observation pair accidentally repeated the resume context. The reviewer
identified this remaining dimension of AC-001; it was not accepted as independent
observation coverage. The corrected pair explicitly places the new probe result
during ongoing work, after entry and before closeout. Both corrected runs passed
the same positive/negative behavioral assertions. Earlier duplicate-context
captures remain under superseded_duplicate_entry_context in the JSON artifact.
