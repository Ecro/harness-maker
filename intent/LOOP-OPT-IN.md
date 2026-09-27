---
id: LOOP-OPT-IN
title: /hm:loop 계열을 harness.yaml 옵트인 렌더로
scope:
- synthesize 조건부 렌더, 새 설정 키, 기존 하네스 보존 마이그레이션
state: active
created_at: '2026-09-18T11:23:50Z'
schema_version: 1
rejected: []
depends_on: []
approval:
  content_hash: 4ddb31ebd6860325fb17456bf49653e76a8ed24088724a66d95a867557645ba2
  approved_by: Ecro
  approved_at: '2026-09-27T02:15:03Z'
  approved_target: 10
revisit_when: null
observed: null
note: null
closed_at: null
statement: loop·loop-p5-batch 를 옵트인으로 바꾸고 이 repo 에서 끄면 dead_rendered_bytes 가 21.7
  → 약 9.2 로 내려간다 (2026-09-27 실측 기준, 두 파일 56,526B 제외)
metric_id: dead_rendered_bytes
out_of_scope:
- loop 본문 삭제·축소, 다른 무호출 명령
---
## Problem



## Proposed outcome



## Affected users and systems



## Constraints



## Open questions

