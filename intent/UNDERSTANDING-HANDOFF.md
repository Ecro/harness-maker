---
id: UNDERSTANDING-HANDOFF
title: wrapup 이해 변화 요약과 ADR 결정 주체 표시
scope:
- 'wrapup 템플릿(인라인 경로와 stage-delegate 경로 모두)의 요약 블록: 최대 5줄, 이전→이후 형식, 파일 목록·diff 재서술
  금지, 변화가 없으면 ''없음'' 한 줄'
- 요약을 터미널 최종 출력과 wrapup 커밋(squash 포함) 본문에 동일하게 남긴다
- 'execute Step 0 ADR 에 decided_by: user|agent, agent 가 결정한 ADR 을 요약에 한 줄로 노출'
- preset 무관 기본 렌더, 새 설정 키·새 파일 없음
- 출하 후 이 repo 를 재렌더한 뒤의 wrapup 10건을 사용자가 git log 로 일괄 판정
state: active
created_at: '2026-09-26T14:12:17Z'
schema_version: 1
rejected: []
depends_on: []
approval:
  content_hash: 56a194e09e0010711a2b3fe2f975766c66607b74978f5f341b6a4036b70ed001
  approved_by: Ecro
  approved_at: '2026-09-26T14:26:37Z'
  approved_target: 80
revisit_when: null
observed: null
note: null
closed_at: null
statement: '모든 렌더 하네스의 /hm:wrapup 이 최대 5줄의 이해 변화 요약(바뀐 가정·불변조건·경계의 이전→이후, 남은 미지, agent
  가 결정한 ADR)을 터미널 출력과 커밋 본문에 남기고, PLAN ADR 에 decided_by: user|agent 를 기록하면, 사용자는 diff
  를 읽지 않고 변경을 설명할 수 있고 모르는 사이 내려진 범위 밖 결정이 없어져 understanding_handoff_rate 가 미측정 →
  80% 이상이 된다'
metric_id: understanding_handoff_rate
out_of_scope:
- 학습·코칭 모드, 역량 평가, 팀·리뷰어용 인계 기능
- decided_by 누락을 verify 게이트로 차단
- 요약 품질의 자동 채점, wrapup 마다 판정 질문
- README 슬로건 변경 (met 이후 별도)
---
## Problem

생성자(1인 시니어 개발자)가 제기한 문제: AI 가 HOW 를 가져갈수록 작업은 빨라지지만, 끝났을 때
시스템에 대한 가정·불변조건·경계가 어떻게 바뀌었는지는 diff 를 직접 읽어야만 알 수 있다. 또 PLAN
ADR 에는 결정 주체가 없어서, 합의된 범위 안에서 agent 가 스스로 고른 트레이드오프와 사용자가 정한
결정을 구분할 수 없다. 이 문제 진술은 생성자의 판단이고 측정된 실패율이 아니다 — baseline 은 미측정.

## Proposed outcome

wrapup 이 끝나면 사용자는 최대 5줄의 요약만 읽고 diff 없이 변경을 설명할 수 있고, 모르는 사이
내려진 범위 밖 WHY·WHAT 결정이 없다. 성공 예: "재시도 소유권 NetworkManager → ReconnectController;
offline 복구 후 토큰 갱신 주체는 미확인; agent 결정 ADR-002". 성공이 아닌 반례: 변경 파일 목록,
diff 를 문장으로 다시 쓴 것, 가정이 바뀌었는데 '없음' 이라고 쓴 것.

판정 규칙 (사전 등록 — 발동 후 재해석하지 않는다):
- 출하 릴리스로 이 repo 를 재렌더한 뒤의 첫 wrapup 부터 10건을 표본으로, 생성자가 git log 의
  요약 블록을 보고 일괄 판정한다.
- 80% 이상 → `met`, README 에 슬로건 "Automate the work. Elevate the engineer." 추가를 별도 task 로.
- 50–79% → `missed`, 요약 형식 재설계.
- 50% 미만 → `missed`, 기능 제거 검토 (제값을 못 하는 장치는 걷어낸다).
- 재렌더 후 60일 안에 10건이 모이지 않으면 → `no_data`.

## Affected users and systems

- 사용자: 모든 렌더 하네스의 사용자 (preset 무관). 측정은 이 repo 에서만.
- 시스템: `templates/stages/wrapup.md.j2` (인라인 경로 + stage-delegate brief/receipt 경로),
  `templates/stages/execute.md.j2` Step 0 의 ADR 섹션, wrapup 커밋 메시지 생성 경로.
- 결정 소유자: 생성자. approve 와 판정 모두 생성자가 한다.

## Constraints

- 새 파일, 새 harness.yaml 키를 만들지 않는다 (제1목표: 단순함).
- 요약은 최대 5줄; 변화가 없으면 '없음' 한 줄. 시니어 대상이므로 설명이 아니라 바뀐 가정과 위험을 드러낸다.
- decided_by 누락은 게이트로 막지 않는다. 품질 하한(검증·리뷰 게이트)은 낮추지 않는다.
- 렌더는 결정적이어야 하며 Claude Code·Cursor·Codex 한 소스에서 렌더한다.
- README 는 출하된 동작과 일치해야 하므로 슬로건은 met 이후에만.

## Open questions

- LLM 이 가정 변화를 놓치고 '없음' 이라고 쓰는 false negative 는 생성자의 판정으로만 잡힌다 —
  판정 시 반례로 따로 센다.
- worktree OFF(Side 기본) 에서는 squash 가 없다 — 요약이 wrapup 커밋 본문에 들어가는 경로는 SPEC 에서 확정.
- delegated wrapup 에서 요약을 receipt 필드로 받을지, 메인 루프가 생성할지는 SPEC 에서 정한다.
- ADR 필드의 정확한 표기(`decided_by:` 줄 형식)와 기존 PLAN 과의 호환은 SPEC 에서 정한다.
