---
generated_by: harness-maker
harness_maker_version: 0.1.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/workflow_command.md.j2
provenance: official
content_hash: cd627ef098cdf050979fa895da143f0bf9e25c926960f1c66067aea49197cca0
---
# /hm:audit

> Workflow command — composes atomic stages defined in `harness.yaml`.

## Usage

```
/hm:audit <task description>
```

## Arguments

`$ARGUMENTS` — task description.

## Behavior

`harness.yaml` 의 `workflows.audit` 시퀀스를 순서대로 실행.
