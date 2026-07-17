---
type: research
task_slug: multi-repo-mgmt-2026-05
status: complete
created: 2026-05-09
tags: [harness-maker, research, product-design, multi-repo, worktree, sibling-repos]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs:
  - "[[src/harness_maker/worktree.py]]"
  - "[[src/harness_maker/gates/worktree_gate.py]]"
  - "[[models.py RefFolder — cross-repo relative path support]]"
summary: "sibling_repos 필드 + 다중 worktree create/gate 확장이 최소 침습적 해법"
---

# RESEARCH — 2개 repo가 하나의 프로젝트인 경우 harness 설계

## 시나리오 (구체화)

```
~/projects/
├── repo-a/          ← git repo 1 (예: backend)
│   └── .claude/harness.yaml  (harness는 어디에?)
├── repo-b/          ← git repo 2 (예: frontend / SDK)
└── (parent dir — git repo가 아닐 수도 있음)
```

사용자가 하나의 기능 구현 시 repo-a + repo-b 양쪽을 동시에 수정한다.
- repo-a에 worktree 생성, repo-b에도 worktree 생성
- 각각 독립적으로 commit/merge
- 상위 디렉토리에서 Claude Code를 열고 두 repo를 한 번에 제어

**현재 구현의 한계:**
- `worktree.create(workflow, base_dir)` → 단일 `base_dir` 가정, `git worktree add` 한 번만 호출
- `.claude/.hm-loop-active` 마커 → 단일 worktree path만 기록
- `worktree_gate` → 단일 active worktree 외부 write 전부 block
- harness 자체 위치: `parent/` 는 git repo가 아니므로 `git worktree add` 불가

---

## 🎯 Recommended Direction

**Approach B: `sibling_repos` 필드 + 다중 worktree create/gate 확장.**

`harness.yaml`에 `sibling_repos: [../repo-b]` 추가, `worktree.create`가 primary + 각 sibling에서 `git worktree add`를 순서대로 실행, `.hm-loop-active` 마커를 newline-separated list로 확장, `worktree_gate`가 ANY match로 판정. harness는 `repo-a`(primary)에 설치. 모델 변경 최소, 기존 단일 repo 사용자 영향 없음.

단기 우회책(Approach A)은 기능 개발 없이 즉시 쓸 수 있지만, worktree isolation이 깨지는 구조적 한계가 있다.

---

## 🛠️ Approaches Found

### A. 단기 우회책: Primary repo 하네스 + ref_folders + bash 수동 git (기능 추가 없음)

| 필드 | 내용 |
|------|------|
| Approach | `repo-a`에 harness 설치. `ref_folders: [../repo-b]`로 sibling 소스 읽기. repo-b git ops는 에이전트 bash로 수동 처리. |
| Assumption | worktree isolation 없어도 괜찮음; Claude가 repo-b 파일을 `Edit /home/.../repo-b/src/foo.ts` 로 직접 수정 |
| Evidence | `RefFolder` 모델이 이미 `../shared-architecture` 같은 상대 경로를 portable str로 저장. 존재 검증은 registration time에만. |
| Trade-off | `worktree_gate`가 `repo-b` 경로 write를 **전부 block**. 활성 loop 중에는 sibling repo 파일 수정 불가. isolation 깨거나 gate 끄거나 둘 중 하나. |
| Compatibility | 코드 변경 없음. 바로 사용 가능. |
| Risk | low (구현), **high (worktree_gate 충돌)** |

**worktree_gate 충돌 상세:**
```python
# gates/worktree_gate.py 핵심 로직 (현재)
active_wt = _read_active_worktree(project_root)  # repo-a/.claude/.hm-loop-active
if target.is_relative_to(active_wt):
    allow()
else:
    block()   # ← repo-b/src/foo.ts 는 여기서 무조건 block
```
loop 비활성화(`worktree.scope: []`) 시 gate 자체가 비활성 → worktree isolation 전부 없어짐. 절충 없음.

---

### B. `sibling_repos` + 다중 worktree create/gate 확장 ✅ 권장

| 필드 | 내용 |
|------|------|
| Approach | `harness.yaml`에 `sibling_repos: [../repo-b]`. `worktree.create`가 primary + 각 sibling에서 독립적 `git worktree add`. `.hm-loop-active` 마커를 newline-separated paths로 확장. `worktree_gate`가 active worktrees ANY match. wrapup 시 각 repo에 독립 commit. |
| Assumption | 각 sibling은 독립 git repo. parent dir은 git repo일 필요 없음. |
| Evidence | 구현 패턴: `git worktree add`는 repo-scoped라 sibling마다 호출 필요 — `subprocess.run(["git","worktree","add",...], cwd=sibling_path)` 완전 유효. 마커 확장: `_write_loop_marker`가 한 path 쓰는 것을 list로 확장하면 `worktree_gate`의 `is_relative_to` 체크를 ANY로 변경 가능. |
| Trade-off | wrapup commit: "repo-a에 commit A, repo-b에 commit B" — 순서 및 메시지 조율이 필요. 현재 wrapup은 단일 `git commit`. |
| Compatibility | 모델 변경: `HarnessConfig`에 `sibling_repos: list[str]` 추가 (default `[]`). `worktree.py` create/finalize/cleanup_all 확장. `worktree_gate` 마커 파싱 확장. 기존 단일 repo는 sibling_repos 비어있으면 동일 동작 — **기존 사용자 영향 없음.** |
| Risk | medium (구현 범위), low (아키텍처 - 기존 설계 자연 확장) |

**변경 파일 목록 (추정):**
```
src/harness_maker/models.py        ← HarnessConfig.sibling_repos 필드
src/harness_maker/worktree.py      ← create/finalize/cleanup_all 다중 repo 지원
src/harness_maker/gates/worktree_gate.py  ← ANY match 로직
src/harness_maker/interview.py     ← sibling_repos 인터뷰 질문 추가
src/harness_maker/synthesize.py    ← sibling_repos pass-through
tests/unit/test_worktree_multi.py  ← 새 테스트
```

---

### C. Parent dir을 git repo로 만들기 (git subtree / git submodule)

| 필드 | 내용 |
|------|------|
| Approach | `~/projects/`를 git repo로 만들고 `repo-a`, `repo-b`를 submodule 또는 subtree로 포함. parent에 harness 설치. `git worktree add`를 parent에서 한 번만. |
| Assumption | 사용자가 repo 구조를 재편할 의사 있음. submodule 운영 오버헤드 감수. |
| Evidence | git submodule은 nested `.git`을 지원하지만 worktree add 시 submodule worktree 동기화가 별도 필요. subtree는 히스토리 복잡성 증가. |
| Trade-off | 양쪽 repo의 git history가 뒤엉킬 위험. 각 repo를 독립적으로 push/PR하는 워크플로우와 충돌. |
| Compatibility | harness-maker 코드 변경 없음. 하지만 사용자 레포 구조 대규모 변경. |
| Risk | low (harness-maker 구현), **high (사용자 레포 구조 파괴적 변경)** |

---

## ⚠️ Pitfalls

1. **sibling worktree branch name 충돌**: `worktree.create`는 현재 branch name = worktree dir name (`execute-20260509T1234Z`). sibling에서 같은 이름으로 생성 시 "branch already exists" 오류. 해결: sibling worktree는 `{workflow}-{ts}-{repo_slug}` 형식 사용 (`-a`, `-b` suffix 등).

2. **finalize 순서**: 다중 repo 시 merge 순서가 중요. `repo-a` squash-merge 실패 시 `repo-b`는 어떻게? 현재 `_cli_finalize`는 단일 경로 기준이라 partial success 개념이 없음. 롤백 정책 결정 필요.

3. **worktree_gate 마커 파싱 하위 호환**: 마커를 newline-separated list로 바꾸면 기존 단일-path 마커 파일을 쓰는 현재 코드와 하위 호환 필요. `_read_active_worktree` → `_read_active_worktrees() -> list[Path]` 로 rename + 단일 path도 list로 파싱.

4. **wrapup commit 메시지 조율**: 현재 wrapup 스테이지는 단일 `git commit`. 2개 repo에 별개 commit이 필요할 경우, wrapup 에이전트가 "repo-a commit → repo-b commit" 순서로 2번 실행해야 함. 자동화 설계 필요.

5. **ref_folders vs sibling_repos 역할 명확화**: `ref_folders`는 read-only 문서 검색용, `sibling_repos`는 read-write 협업 repo용 — 두 개념이 겹치면 혼동. 인터뷰 질문에서 명확히 분리.

6. **`_detect_existing_worktree`의 path-based fallback**: 현재 `base.parts`에서 `.worktrees` 탐색. sibling repo의 worktree path는 primary repo 기준으로 보이지 않음 → 기존 idempotency 로직은 primary repo 워크트리만 감지. sibling worktree에서 실행 시 "no existing worktree" 판정 후 중복 생성 시도 → 충돌. 마커 기반(signal 1)에서 sibling path들도 포함하면 해결.

---

## ❓ Open Questions

`/hm:plan` 이 결정해야 할 사항:

1. **harness 설치 위치 정책**: `repo-a`(primary 지정)에만 설치? 아니면 각 repo에 독립 harness + sibling_repos cross-reference? 전자가 단순, 후자가 대칭.

2. **sibling worktree branch name prefix**: `{ts}-a` / `{ts}-b` suffix vs `{repo_slug}-{ts}` 방식. 사용자 가독성 vs collision 안전성 트레이드오프.

3. **finalize 실패 시 partial rollback**: repo-a 성공 + repo-b 실패 시 repo-a를 undo해야 하는가? 단순하게는 "실패한 쪽 preserve, 성공한 쪽은 그대로" 정책도 가능. 결정 필요.

4. **인터뷰 UX**: `sibling_repos`를 interview 질문으로 추가 시 free-text path input — validation (경로 존재 여부, git repo 여부) 수행 위치와 실패 처리.

5. **wrapup 의 multi-commit flow**: wrapup 에이전트가 각 repo별 commit message를 어떻게 생성? "하나의 논리적 변경 → 2개의 commit" 패턴에서 message를 동일하게 할지, 각 repo 맞춤으로 할지.

---

## 📚 Sources

- 내부 코드 분석:
  - `src/harness_maker/worktree.py` — 전체 구현 리뷰 (단일 repo 가정 확인)
  - `src/harness_maker/gates/worktree_gate.py` — 단일 마커 파싱 확인
  - `src/harness_maker/models.py` — `RefFolder` 상대 경로 portable str 정책

---

## 🔗 Related Internal Docs

- `[[src/harness_maker/worktree.py]]` — `create(workflow, base_dir)` 단일 repo 가정
- `[[src/harness_maker/gates/worktree_gate.py]]` — `_read_active_worktree` 단일 path 파싱
- `[[PLAN-plugin-vs-generator-2026-05]]` ADR-001 — 기존 아키텍처 기준
- `[[CLAUDE.md]]` §Worktree cleanup 정책 — prefix-match cleanup (sibling도 동일 정책 적용 필요)
