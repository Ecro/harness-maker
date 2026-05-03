---
generated_by: harness-maker
harness_maker_version: 0.1.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/workflow_command.md.j2
provenance: official
content_hash: 2cd5ce03f3cab94629f33d715466e3759c47c9c68e37aebe6f5a6e176688dd8e
---
# /hm:dev

> Workflow command — composes atomic stages defined in `harness.yaml`.

## Usage

```
/hm:dev <task description>
```

## Arguments

`$ARGUMENTS` — task description.

## Behavior

`harness.yaml` 의 `workflows.dev` 시퀀스를 순서대로 실행.
