# Block-merge spec (Layer 3 reconcile)

> 사용자 수정 보존 + 템플릿 업데이트 모두 받는 reconcile 모드. v1 제약: flat blocks, `.md` 파일 only.

*Last reviewed against code: 2026-05-07 (0.5.x). Block-merge markers (`@hm:user:*`) 는 현재 `.md` 파일에서만 동작. `.cursor/rules/*.mdc` 는 frontmatter 제약으로 별도 처리.*

## Marker 구문

마크다운 HTML comment 로 표현 — 마크다운 렌더에서 보이지 않고, 텍스트 에디터에서만 보임.

```markdown
<!-- @hm:block:<id> -->
{template-owned content}
<!-- @hm:/block:<id> -->

<!-- @hm:user:<id> -->
{user-owned content}
<!-- @hm:/user:<id> -->
```

- `<id>` — `[a-z][a-z0-9-]{0,30}` 영문 소문자/숫자/하이픈
- 같은 파일 내 `<id>` 중복 금지
- `<!-- @hm:/block:<id> -->` 의 `<id>` 는 여는 태그와 정확히 일치해야 함 (drift 감지)
- 중첩 금지 (v1) — `block` 안에 또 `block` 또는 `user` 넣지 말 것

## 소유권 의미론

| 블록 종류 | 소유자 | 업데이트 시 동작 |
|---|---|---|
| `block:<id>` | harness-maker template | 무조건 REPLACE + frontmatter hash 와 mismatch 면 경고 (사용자가 편집했음을 알림) |
| `user:<id>` | 프로젝트 사용자 | 무조건 KEEP (NEW 의 초기 placeholder 무시) |
| 마커 밖 free-floating | template (default) | REPLACE — 마커 안 두른 라인은 template 소유로 간주 |

**제약**: 사용자가 `block:` 내부 또는 마커 밖 편집 시 업데이트에서 잃음. 변경하고 싶으면 `user:` 블록 안으로 옮기거나 PR 보내기. `block:` 마커는 선택 사항 — drift 경고용으로만 의미. 단순 보존은 `user:` 만 두르면 충분.

## Reconcile 결정 트리

파일별로:

```
1. Frontmatter 없음 → KEEP (legacy/user file)
2. Frontmatter 있고 `content_hash == sha256(body)` (수정 안 됨)
   → REPLACE (whole-file overwrite, 마커 유무 무관)
3. Frontmatter 있고 hash mismatch (사용자 편집 있음)
   3a. NEW template 에 마커 + OLD body 에도 마커 + OLD 가 정상 파싱
       → MERGE_BLOCK (블록 단위 병합)
   3b. NEW + OLD 모두 마커, 그러나 OLD 파싱 실패 (사용자가 마커 문법 깨뜨림)
       → KEEP whole-file (이유: hash-mismatch-malformed-markers)
       → 사용자 편집 보존 우선; REPLACE 로 떨어뜨려 silent loss 방지
   3c. 그 외 (어느 한쪽이라도 마커 없음)
       → KEEP whole-file (legacy fallback)
```

## MERGE_BLOCK 알고리즘

OLD = 디스크 현재 파일 (사용자 편집 가능), NEW = 새 템플릿 렌더 결과.

1. NEW 를 기반으로 시작 (template 의 새 구조 + 새 placeholder 들)
2. OLD 를 마커 파싱 → `user:<id>` 블록의 content 들을 dict 로 모음
3. NEW 를 walk 하며 각 `user:<id>` 블록에 대해:
   - OLD dict 에 같은 `id` 있으면 → 그 content 로 NEW 의 user block 내용 교체 (KEEP)
   - 없으면 → NEW 그대로 (initial placeholder)
4. OLD 에만 있는 `user:<id>` (NEW 에서 사라진 id) → 파일 끝에 quarantine 추가:
   ```markdown
   <!-- @hm:user:_orphans -->
   <!-- 이전 버전 user 블록인데 새 템플릿에 동명 id 없음. 수동 정리 필요. -->
   ## (orphan) <id>
   {original content}
   <!-- @hm:/user:_orphans -->
   ```
5. OLD 의 `block:<id>` 내용이 frontmatter `blocks.<id>` hash 와 mismatch 면 → 경고 (사용자가 template-owned block 편집함). REPLACE 는 진행.

마커 밖 free-floating 라인은 별도 처리 안 함 — NEW 의 마커 밖 내용 그대로 사용 (REPLACE).

## Frontmatter 확장 (v1.5+)

v1 은 `content_hash` (whole-body) 만 씀. v1.5 에서 추가 예정:

```yaml
content_hash: <whole-body-sha256>
blocks:
  procedure: <hash>
  inputs: <hash>
  outputs: <hash>
```

`blocks` 는 `block:<id>` 마커 종류만 (user 블록은 사용자 소유라 hash 필요 없음). 현재 `block_merge.detect_drift()` 함수는 v1.5 도입 대비로 export 만 되어 있고, 어디서도 호출하지 않음.

## CLI 출력 (v1)

```
harness applied to /home/noel/kairos/.claude (46 files)
  KEEP: 2 file(s) preserved as-is (no markers — won't receive new template content)
  MERGE_BLOCK: stages/review.md — preserved 3 user block(s): procedure-extras, extra-quality-checks, extensions
```

v1.5 에서 추가 예정:
- `block:<id>` drift 경고 ("user edited inside template-owned block")
- malformed marker 경고 ("KEEP due to user-introduced syntax error")

## 마이그레이션 / 호환성

- 마커 없는 legacy 파일 (0.1.x, 0.2.x 출력) → 기존 KEEP/REPLACE 로 처리. 새 마커 없는 정체.
- legacy 파일을 한 번이라도 REPLACE 받으면 (= 사용자 수정 안 한 경우) → 새 템플릿 (마커 포함) 으로 갱신 → 다음부터 MERGE_BLOCK 가능.
- 사용자가 legacy 수정 파일을 의도적으로 marker 모드로 옮기려면 → `--force` 플래그로 whole-file 덮어쓰기 후 user block 에 자기 추가분 다시 붙이기.

## v1 범위 외 (후속)

- 중첩 블록
- JSON/YAML 마커 (key-level merge)
- 사용자 `user:` 블록 안에서도 일부 자동 갱신 (예: 도메인 표준 패치)
- 3-way merge with `git merge-file` (사용자가 `block:` 안 편집한 경우 보존)
