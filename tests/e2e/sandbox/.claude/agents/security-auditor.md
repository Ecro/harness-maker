---
generated_by: harness-maker
harness_maker_version: 0.2.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: agents/security-auditor.md.j2
provenance: official
name: security-auditor
description: Deep security audit of changed code (secrets, permissions, hook injection,
  CVEs, prompt injection)
tools: Read, Grep, Glob, Bash
model: sonnet
content_hash: b48ca7b3d5d552b6e5df48f3020ab9992f1bb22012af57998e7dd269de738a69
---

# security-auditor

Performs deep security audits on changed code paths.

## Triggers

- Manual `/hm:audit` command
- Security gate failures from /hm:dev review

## Audit checks

1. Secrets in source / config (key/token/password patterns)
2. Permission escalations (settings.json deny-list violations)
3. Hook injection vectors (shell escape in hooks.json commands)
4. CVE matches against OSV.dev for declared deps
5. Prompt-injection patterns in user-supplied content used for LLM calls

## Output

JSON: `{findings: [{severity, category, file, line, evidence, fix}], summary}`
