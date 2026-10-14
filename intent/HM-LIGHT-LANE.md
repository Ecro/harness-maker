---
id: HM-LIGHT-LANE
title: '작은 단일 세션 작업은 가벼운 /hm: 경로로, 전체 파이프라인은 그게 필요한 작업에만'
scope:
- 'spec Step 0: trivial 스킵 옆에 lane(light|full) 분류를 둔다. LLM 이 요청과 repo 를 읽고 판정하며(regex
  금지), 근거를 Refinement Decisions 에, 값을 SPEC frontmatter 에 남긴다'
- 'execute: light 는 Phase A.5 만 건너뛴다. Phase A 테스트, A.4 false-RED screen, Phase B RED
  gate 는 결정적 oracle(INV)이라 유지한다'
- 'review: 렌즈 축은 유지하고 light 는 한 번의 패스, auto-fix 한 라운드까지, 고친 게 없으면 confirmation pass
  생략'
- '레버 1 — 단계를 새 컨텍스트로: light 의 execute 와 verify 를 stage-delegate 로 돌린다. 서브에이전트는 서브에이전트를
  부를 수 없어 review(렌즈)와 full execute(A.5)는 메인에 남는다'
- '레버 2 — 단계 본문 줄이기: review·execute 의 full 전용·드문 경로를 필요할 때 읽는 참조 파일로 옮겨, 매 호출 다시 읽히는
  본문을 줄인다'
- 레버 3 — 서브에이전트 결과를 메인에 덜 싣는다 (렌즈·validator 결과 전문 대신 판정과 경로)
- 레버 4 — hm spec_machine check --all 은 통과하면 한 줄만 출력한다
- '레버 5 — 내부용 스킬·명령을 자동 호출 목록에서 숨겨 /hm: 를 안 쓸 때의 고정 비용을 줄인다'
- spec-validator 는 light 에서도 돈다 (사용자 기본값 2026-10-14)
- 'step_sensitivity: A.5 근거에 벤치 ground-truth 팔을 반영'
- 벤치 러너(픽스처 + 숨은 테스트 + plain/hm 팔)를 repo 로 올려 지표를 다시 잰다
state: proposed
created_at: '2026-10-14T10:30:49Z'
schema_version: 1
rejected: []
depends_on: []
approval:
  content_hash: 57c786cc5a83148ce0afdaf0828915b8289462503ad397272d2a02325f95cfba
  approved_by: Ecro
  approved_at: '2026-10-14T13:31:56Z'
  approved_target: 5
revisit_when: null
observed: null
note: null
closed_at: null
statement: '/hm: 실행 비용의 약 75% 는 단계 프롬프트와 도구 출력이 메인 컨텍스트에 쌓여 매 호출 다시 읽히는 데서 나온다. spec
  Step 0 이 작은 작업(약 5개 파일 이하, 한 세션, 되돌리기 어려운 결정 없음)을 light lane 으로 보내 A.5 와 반복 리뷰를
  빼고, 단계를 새 컨텍스트로 위임하고, 단계 본문과 도구 출력을 줄이면, 벤치의 숨은 테스트 통과율을 plain 아래로 낮추지 않으면서 hm_cost_ratio_small
  이 22 → 5 이하로 내려간다'
metric_id: hm_cost_ratio_small
out_of_scope:
- 크거나 여러 세션에 걸친 작업의 게이트 변경 (full 경로의 단계는 그대로, 그 가치는 미측정). 레버 2·4·5 의 크기 절감은 full 에도
  적용된다
- Cursor/Codex 쪽 별도 측정
- '기각: A.5 를 모든 작업에서 advisory 로 — 측정되지 않은 큰 작업의 게이트까지 바꾼다'
- '기각: 리뷰 렌즈 제거 — 비용의 11% 뿐이고 13회 중 5회 수정을 냈다'
---
## Problem

2026-10-14 벤치(`work-docs/RESEARCH-hm-light-lane.md`)에서 단일 세션 과제 10종에 일반 작업은 44/45 를
통과했다. 같은 과제 5종에 /hm: 전체 경로는 13/15 를 통과하면서 비용 ×22, 시간 ×15 를 썼다. 실패 2건은 모두
execute Phase A.5 의 2라운드 캡에서 스스로 멈춘 것이었고, plain 이 내보낸 결함이 아니었다. 원인은 경로가 하나뿐이라는
데 있다: spec Step 0 의 유일한 스킵은 "단일 파일, 계약 변경 없음, 1시간 안에 되돌릴 수 있음"을 모두 요구하고, 벤치 과제는
전부 이 조건을 넘는다. 그래서 작은 작업도 spec-validator, A.4/A.5, 2-pass 리뷰 팬아웃과 confirmation pass 를 모두 탄다.

비용이 어디서 나오는지가 설계를 정한다. 정상 완료 13회를 단계별로 나누면 메인 루프가 약 85%(review 38, execute 18,
spec 15, verify 15), 서브에이전트가 약 15%(A.5 6, 리뷰 렌즈 11, spec-validator 1)다. 전체의 약 75% 는 쌓인 컨텍스트를
매 호출 다시 읽고 캐시에 쓰는 비용이다: plain 은 호출 6회에 평균 39k, /hm: 는 메인 호출 54회에 67k → 181k. 메인 carry 의
60.5% 가 단계 명령 본문(review 67.6k, execute 57.4k, spec 36.6k자)이고, heredoc 도구 입력 16.4%, Bash 출력 10.3%
(`hm spec_machine check` 실행당 13k), 서브에이전트 알림·결과 11.2% 다. 단계를 빼는 것만으로는 약 7% 만 줄어든다.

## Proposed outcome

작은 작업은 가벼운 경로를 타고 큰 작업은 지금처럼 전체 파이프라인을 탄다. 성공 예: 같은 벤치를 다시 돌렸을 때 /hm: 팔의
비용이 plain 의 5배 이하이고 숨은 테스트 통과율이 plain 이상이다. 성공이 아닌 반례: 비용은 내려갔지만 통과율이 plain 아래로
떨어진 경우, 또는 Step 0 이 여러 세션짜리 작업을 small 로 보낸 경우.

판정 규칙 (사전 등록):
- 배수 ≤ 5 이고 /hm: 통과율 ≥ plain → `met`.
- 배수 > 5 → `missed`. 비용이 제거한 단계가 아니라 다른 곳(서브에이전트 수, 항상 로드되는 컨텍스트)에 있다는 뜻이다.
- /hm: 통과율 < plain → `missed`. 제거한 단계가 무언가를 잡고 있었다는 뜻이니 해당 단계를 되돌린다.
- 벤치 러너가 repo 에 들어오지 않아 다시 잴 수 없으면 → `no_data`.

## Affected users and systems

- 사용자: 모든 렌더 하네스의 /hm: 사용자 (preset 무관). 측정은 벤치에서만.
- 시스템: `templates/stages/` 의 spec·execute·review·verify 본문, `stage-delegate` 위임 경로,
  `spec_machine.py` 의 `check --all` 출력, 렌더되는 스킬·명령의 자동 호출 노출, `step_sensitivity.py` 의 A.5 근거.
- 결정 소유자: 생성자(Ecro). 목표 배수 ×5 와 spec-validator 유지는 생성자가 2026-10-14 초안에서 정했다.

## Constraints

- 품질 하한은 낮추지 않는다: 테스트 작성, A.4 false-RED screen, Phase B RED gate, verify, 리뷰 렌즈 커버리지는 가벼운 경로에서도 그대로다.
  초안은 "A.4/A.5 생략"이라고 적었지만 A.4 는 pytest 한 번으로 끝나는 결정적 검사(INV)라 유지하고 A.5 만 뺀다 (agent 판단, 2026-10-14).
- small 판정은 LLM 이 한다 (regex 금지). 되돌리기 어려운 결정이 하나라도 있으면 전체 경로다.
- 새 harness.yaml 키를 만들지 않는다. 기존 SPEC 에 lane 이 없으면 전체 경로로 읽는다.
- 서브에이전트는 서브에이전트를 부를 수 없다. 그래서 렌즈를 부르는 review 와 A.5 를 부르는 full execute 는 메인에 남고,
  레버 1 은 light 의 execute·verify 에만 적용된다. spec 은 인터뷰가 사람과 대화해야 하므로 메인에 남는다.
- 렌즈 에이전트는 Write 도구가 없고, "결과 파일이 없음 = 렌즈가 죽음"이 커버리지 판정의 신호다. 레버 3 은 이 계약을 깨지 않는 방식으로 한다.
- 렌더는 결정적이고 Claude Code·Cursor·Codex 를 한 소스에서 렌더한다.

## Open questions

- 벤치 원자료(픽스처·숨은 테스트·러너)는 세션 스크래치에서 사라졌다. 지표를 다시 재려면 러너를 repo 로 다시 만들어야 한다.
- 레버별 절감액은 추정이다. 구현 순서: (1) lane + 레버 4·5, (2) 레버 2, (3) 레버 1·3, (4) 벤치 러너와 재측정.
- 대화형 세션에서는 A.5 의 "결정 필요"가 종료가 아니라 질문 한 번이다. 헤드리스 벤치가 A.5 의 비용을 과대평가했을 수 있다.
- 사용자 주 모델로는 재지 않았다.
