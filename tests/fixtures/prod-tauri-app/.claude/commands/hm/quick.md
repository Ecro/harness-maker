---
generated_by: harness-maker
harness_maker_version: 0.1.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/workflow_command.md.j2
provenance: official
content_hash: dd2b2264de7ba195d68b17bf1d8ce63be7ed656abaf100c2524b6043f5a5d596
---
# /hm:quick

> Workflow command — composes atomic stages defined in `harness.yaml`.

## Usage

```
/hm:quick <task description>
```

## Arguments

`$ARGUMENTS` — task description.

## Behavior

`harness.yaml` 의 `workflows.quick` 시퀀스를 순서대로 실행.
