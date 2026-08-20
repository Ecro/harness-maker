---
type: delta
task_slug: ai-work-boundaries
status: informational
created: 2026-08-20
sources: ["~/spoton/work-docs/실험기록6-리포접근.md", "~/spoton/work-docs/실험기록7-리포접근-루프.md", "~/spoton/work-docs/실험기록5-성긴계약.md"]
related_docs: ["[[RESEARCH-ai-work-boundaries]]", "[[PLAN-ai-work-boundaries]]"]
summary: "Three experiments finished after RESEARCH-ai-work-boundaries was written. One retires the evidence behind G8, one validates the oracle-widening rule that landed at review.md.j2:833, one narrows G1's scope."
---

# DELTA — ai-work-boundaries, experiments finished after 2026-08-19

`RESEARCH-ai-work-boundaries.md` audited this repo against
`~/spoton/work-docs/SYNTHESIS-ai-work-boundaries.md` on 2026-08-19. Three experiments in that
study finished **after** that date. None of them opens a new gap; they change the *basis* of
two existing ones and independently confirm a rule that landed here on its own.

**This document adds no work items.** It is evidence maintenance for G1 and G8, plus one
genuinely new gap (§4) that neither audit listed.

---

## 1. G8's evidence has been retired — the "4/4 regression" was an artifact of file-only review

G8 currently reads: *"all 4/4 reproduced 'regressions' were tests pinning unreachable states."*

That was the state of the finding on 08-19. It has since collapsed one step further.

```
관측 (실험 1)   4회 독립 실행이 정확히 같은 4개 테스트를 깼다        파일-only 조건
1차 정정        그 4개는 도달 불가능한 상태를 고정한 테스트였다      ← G8 이 인용한 지점
2차 정정        그 지적(D03) 자체가 오탐 판정. 발견빈도 7/10 상위권
3차 정정        리포를 열고 루프를 다시 돌리니 10라운드에서 0회
```

**E8** (2026-08-20): 실험 1 의 루프를 리뷰어·수정자 **둘 다 `src/` 를 읽는 조건**으로 재실행.
대상·오라클·라운드 수 동일, 프롬프트는 문단 하나만 교체.

```
                        실험 1 (파일만)      E8 (src/ 열림)
완료 라운드                  15                  10
RED 라운드                12 / 15            6 / 10
그 4개 테스트 등장         4 개 전부           0 개
```

한 루프는 3라운드 연속 GREEN 이다(실험 1 의 같은 루프는 5라운드 전부 RED).

**G8 에 대한 함의**: "기존 테스트가 도달 불가능한 상태를 고정하는지 research 가 확인해야 한다"
는 규칙 자체는 유효하다. 다만 **그 규칙을 정당화하던 사례는 더 이상 그 사례가 아니다** —
근본 원인은 테스트가 아니라 **리뷰어에게 호출자를 안 보여준 것**이었다.

G8 을 계획한다면 근거를 이렇게 바꾸는 것이 정확하다.

```
전  "4/4 회귀가 전부 도달 불가 상태를 고정한 테스트였다"
후  "파일-only 리뷰가 만든 오탐이 수정자에게 그대로 전달돼 회귀처럼 보였다.
     리포를 열면 지적도 회귀도 사라진다. research 의 도달성 확인은 여전히 값이 있지만,
     이 사례는 그 근거가 아니다."
```

### 뒷받침 — E7 (리뷰 단독, 같은 대상)

```
                 지적   고유 결함   진짜   오탐    정밀도   재현율
파일만             61      14        10     4      71%     77%
src/ 열림          30       7         7     0     100%     54%
```

오탐 4건(발견빈도 8·7·7·5)이 **전부** 사라졌다. 넷 다 호출자·초기화·스레드를 봐야 아는 주장이었다.
대신 **파일만으로는 원리적으로 못 찾는 진짜 결함 3건**이 새로 나왔고, 셋 다 증거가 diff 밖이었다
(호출 순서 / 헤더 상수 / 저전력 진입 경로). 정밀도와 재현율을 맞바꾼다.

그리고 합의의 방향이 뒤집힌다.

```
파일-only 에서 가장 많이 발견된 것들   →  오탐 (8, 7, 7, 5회)
리포 열린 조건에서 가장 많이 발견된 것 →  진짜 (10/10)
```

`review.md.j2` 의 solo-lens vote(ADR-007)와 escalate 지침은 이 방향과 일치한다.
**추가 작업 없음.**

---

## 2. `review.md.j2:833-842` 의 oracle-widening 규칙이 독립적으로 실측 확인됐다

이 블록은 08-19 감사 목록에 없었고, E8 은 그것을 모르는 상태에서 같은 현상을 관측했다.

E8 의 한 루프가 R1 부터 끝까지 **빌드 실패**였다.

```
src/swing_capture.c:167: undefined reference to `power_sampling_active'

수정자가 넣은 코드:
  const bool full_rate = power_sampling_active() && !power_resume_pending();
```

`power.h:44` 에 **실재하는 함수**이고, E7 이 찾은 결함(저전력 구간의 샘플레이트 오라벨)을
**실제로 고치는 코드**다. 유닛 테스트가 대상 모듈만 링크해서 깨졌다.

> 리뷰 범위를 diff 밖으로 넓히면 수정도 diff 밖 API 를 쓴다.
> 테스트 범위가 따라가지 않으면 **정당한 수정이 빨간불**이 된다.

`review.md.j2:833` 의 *"a fix reaching a symbol or module the file did not depend on before is
checked by a target missing that dependency — the build breaks on a missing symbol, not on a
wrong fix"* 와 정확히 같은 사건이다. **그 규칙이 옳다는 외부 관측 1건으로 기록한다.**

부수 관찰: 이 실패는 오라클 집계에서 `n_failed = 0` 으로 잡혔다 — 실패 케이스가 0인데
green 이 아니었다. `reverted — build/link error:` 와 `caused build failure` 를 나눈 것이
바로 이 오분류를 막는다. **이미 landed 이므로 작업 없음.**

⚠️ **한계**: R1 에서 한 번 일어나 이후 라운드로 이어졌다. **사실상 독립 관측 1건**이다.
"흔하다" 는 말은 이 데이터로 못 한다.

---

## 3. G1 의 범위를 좁힐 수 있다 — 자유 슬롯 전부가 아니라 **관례가 없는** 슬롯

G1 은 *"deliberately unspecified"* 섹션을 PLAN 에 요구한다. 근거는 47라운드에서 움직인 유일한
동작이 계약이 안 정한 그것이었다는 1:1 대응이다. 그 근거는 유효하다.

**E4** (성긴 계약 두 번째 과제): 비슷한 크기를 19 AC 가 아니라 **8 AC 로만** 덮고,
자유 영역 8개를 **구현 전에** 등록한 뒤 쟀다.

```
독립 4구현 (claude 3 + codex 1)  →  전부 8/8 통과, 쌍별 차등 400 시나리오 전부 0/400
                                     (54줄 vs 138줄인데 관측 동작 동일)
루프 3개 × 5라운드               →  AC 전부 유지, 차등 0/400. 자유 영역 이동 0
```

하네스 고장이 아니다 — 자유 영역 선택을 하나씩 뒤집으면 95/400, 400/400, 369/400 으로 전부 잡는다.

**그런데 관례가 약한 자리에서는 갈린다.** 같은 실험 안의 대조:

```
관례 강함 (TTL 경계 · LRU 갱신 · len 의미)  →  4구현 전부 일치, 차등 0/400
관례 약함 (타입 오류를 무엇으로 던지나)      →  4구현이 3가지 답
```

**함의**: 계약이 비워둔 자리라고 전부 흔들리는 것이 아니다. 관례가 강하면 서로 다른 회사의
모델도 같은 답을 고른다. 흔들리는 것은 **관례도 없는 자리**다.

> G1 의 "deliberately unspecified" 목록에 자유 슬롯을 전부 적으면 대부분이 죽은 항목이 된다.
> 적을 값이 있는 것은 **사람도 의견이 갈리는 슬롯**이다. 그리고 그 판별은 사후에 공짜다 —
> `review_churn oscillation` 이 이미 잡는다.
>
> 실행 가능한 형태: PLAN 에 빈 섹션을 요구하기보다, **oscillation 이 한 번 잡힌 슬롯을
> 그 섹션에 자동으로 적재**한다. G3(detected `spec_gap` 이 SPEC 으로 안 돌아감)과 같은 배선이다.

이건 제안이지 요구가 아니다. G1 의 A/B/C 안을 고를 때 참고 자료로만 쓰면 된다.

---

## 4. 새 간극 — execute 에 "테스트가 깨지면 도달성부터"가 없다

G8 은 이 규칙을 **research** 단계에 놓는다(기존 테스트가 무엇을 고정하는지 미리 읽기).
**수리 시점의 역방향 진단은 어디에도 없다.**

`execute.md.j2` Phase D.5 `Newly-reachable window` 는 *"수리가 새로 열어젖힌 입력"* 에 테스트를
요구한다 — 올바른 규칙이고 유지해야 한다. 그 역이 없다:

```
테스트가 빨개졌을 때, 그 테스트가 고정하는 상태가 프로덕션에서 도달 가능한가?
```

`grep -in 'unreachable|test is wrong' stages/execute.md.j2` → 0 hits.

이 진단이 없으면 D.5 는 *"수리 후 무엇이 새로 도달 가능한가"* 만 보고,
*"애초에 이 빨간불이 도달 가능한 것에 대한 것인가"* 는 아무도 안 본다.
실험 1 의 15라운드가 이 구멍에서 나왔다.

제안 형태 (D.5 **앞**):

```
Phase D.4 — 파손 테스트 분류 (수리 전에)
  (a) 프로덕션이 도달하는 상태를 고정  → 코드를 고친다
  (b) 도달 불가능한 상태를 고정        → 테스트를 고친다
  (c) 테스트 하네스 범위 부족          → review.md.j2:833 의 oracle-widening 으로
  (b) 주장에는 호출자 경로를 명시해야 한다 — 파일 안에서는 증명되지 않는다.
```

우선순위는 **중간**. G1/G2 보다 낮고, 근거 사례가 한 과제에서 나왔다.

---

## 5. 이 문서의 한계

- **판정자가 실험자 본인이다.** 진짜/오탐 판정 3벌(14 · 11 · 39건)을 전부 한 사람이 했고
  기준도 그 사람이 정했다. 정답 키는 판정 확정 후에 열었다(순서는 세션 트랜스크립트에 남음).
  **다른 사람이 같은 항목을 판정해 방향이 재현되어야 인용 가능하다.**
- E7 은 복합 레버다 — src/ 마운트 · Read/Grep 허용 · permission-mode 를 함께 켰고 분리하지 않았다.
- E7·E8 은 **codex 로 재현 불가**였다. `codex-linux-sandbox` 바이너리가 설치에 없어 셸 도구가
  이 환경에서 작동하지 않는다. claude 단일 모델 결과다.
- E8 완료 라운드 10개(계획 15개). 두 루프가 R4 리뷰 900초 타임아웃으로 멈췄다 — 내용 실패가
  아니라 실험자가 건 상한이다. 재시도 금지 원칙대로 늘리지 않았다.
- 이 연구에서 결론은 **17번 뒤집혔고 방향은 항상 덜 극적인 쪽**이었다. 위 수치들도 같은
  방향으로 더 깎일 수 있다.
