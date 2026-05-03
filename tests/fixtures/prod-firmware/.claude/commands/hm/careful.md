---
generated_by: harness-maker
harness_maker_version: 0.1.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/workflow_command.md.j2
provenance: official
content_hash: ae76b394423abb862a78b91a2d9188e723a3eab14c43fc6f125f814fac8c8d6a
---
# /hm:careful

> Workflow command — composes atomic stages defined in `harness.yaml`.

## Usage

```
/hm:careful <task description>
```

## Arguments

`$ARGUMENTS` — task description.

## Behavior

`harness.yaml` 의 `workflows.careful` 시퀀스를 순서대로 실행.
