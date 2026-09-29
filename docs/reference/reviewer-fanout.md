# 리뷰어 팬아웃은 언어 조건부다 — 기록만, 라우팅은 안 한다

> Relocated verbatim from `CLAUDE.md` on 2026-09-30 (SPEC-top-issues-2026-09). CLAUDE.md keeps a
> short summary and a link here; this file is the recorded *why*.

## 리뷰어 팬아웃은 언어 조건부다 — 기록만, 라우팅은 안 한다

`/hm:review` 의 7렌즈는 Production 에서 언어와 무관하게 강제된다. `Ecro/harness-bench` 의
`docs/STUDY-ko.md` 는 같은 예산 대비 **Python 코드베이스에서 재현율 +52%**, **C 펌웨어에서는
이득 없음** (팬아웃 43% vs 단일 리뷰어 50%) 을 관측했다. 겹치는 렌즈는 예산만 쓴다.

**그래서 바꾸지 않았다.** 언어별로 렌즈를 줄이려면 어느 렌즈가 어느 언어에서 겹치는지에 대한
데이터가 필요한데 우리에겐 없고, 근거 없는 라우팅은 mandatory-lens 가 승인을 막는 구조와 정면
충돌한다 (`lens_coverage` 의 `blocks_approval`). 침묵이 "검토 안 한 구멍" 으로 읽히는 걸 막으려고
적어둔다 — 이건 미검토가 아니라 **의도적 보류**다.

> **철회 (2026-09-08, PLAN-token-efficiency-autopilot-ux-speed ADR-003).** 이 자리에는
> "소비 프로젝트가 C/펌웨어 위주라면 `reviewers.enabled` 를 직접 줄이는 것이 사용자 선택으로
> 열려 있다" 가 있었다. **그런 레버는 없다.** `conditional_router.lens_dispatch(preset)` 는
> `enabled` 를 인자로 받지 않고 읽지도 않는다 — 렌즈 집합은 preset 에서만 파생되므로
> `enabled` 를 둘로 줄여도 렌더된 `/hm:review` 는 여전히 네 에이전트를 디스패치한다.
> `reviewers.enabled` 가 실제로 하는 일은 `/harness-maker:make --add/--remove` 가 기록하는
> **기본 활성화 목록**이고 (`synthesize.py` 는 preset 과 무관하게 전 인벤토리를 설치한다),
> 팬아웃 비용에는 영향이 없다. 위 문단의 "바꾸지 않았다" 는 그대로 유효하다 — 바뀐 것은
> 존재하지 않는 우회로를 사용자에게 권하지 않는다는 것뿐이다. 언어별 라우팅을 실제로 원하면
> 그건 `conditional_router` 변경이고, 근거 데이터가 없어 보류 상태다.
