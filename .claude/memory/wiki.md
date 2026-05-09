---
generated_by: harness-maker
harness_maker_version: 0.7.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: memory/wiki.ko.md.j2
provenance: official
---
# Wiki Index — Production preset

> 프로젝트별 패턴 / 컨벤션 인덱스. wrapup 스테이지가 자동 추가합니다.
>
> **검색:** `rg -F "[wiki:" .claude/memory/wiki.md`
>
> **형식:**
> ```
> ## [wiki:<category>] <slug> | <YYYY-MM-DD>
> <패턴 설명: 언제 쓰는지, 왜 이 방법인지 한 단락>
> ```
> - `category`: pattern / convention / gotcha / architecture / tooling / api / other
> - slug 는 kebab-case. 동일 패턴 업데이트 시 헤딩 날짜만 갱신 (중복 섹션 금지)

---

## [wiki:convention] how-it-works-grade-table | 2026-05-09
`/hm:review` grade table: A=P0:0,P1:0 / B=P0:0,P1:1-2 / C=P0:0,P1≥3 / D=P0:1-2 / F=P0≥3. The field is `grade_threshold` (default A), not `max_grade_threshold`. P2/weak-consensus/manual-only findings do NOT lower the grade — only `consensus-passed` P0/P1 count.

## [wiki:gotcha] docs-grade-table-wrong-3x | 2026-05-09
When documenting the review grade table, all boundary values were wrong on first attempt: thresholds were offset (A included P1≤2, B included P1≤5, etc). Root cause: grade table was reconstructed from memory instead of reading `review.md` source. Fix: always read the skill source file before documenting grade logic.

## [wiki:architecture] generator-not-runtime-config | 2026-05-09
harness-maker must stay a generator (Jinja2 pre-render), not a pure plugin that reads harness.yaml at runtime. Three file categories are irreducible: (1) hooks.json — IDE-specific schemas (PascalCase vs lowercase camelCase) consumed pre-LLM, no plugin-system injection hook; (2) settings.json — permission sandbox established before LLM runs, cannot be self-set; (3) CLAUDE.md — technically injectable but would break the `<!-- @hm:user:* -->` block-merge contract and content_hash KEEP/REPLACE/MERGE_BLOCK reconciliation that lets user customizations survive upgrades. Agents/skills/commands could be runtime-configured but the complexity delta is not eliminated since the three infra files still need rendering. See ADR-001 in PLAN-plugin-vs-generator-2026-05.

## [wiki:gotcha] worktree-snapshot-harness-path | 2026-05-09
`test_synthesize_snapshot.py` compares `body_sha256` of rendered files. The `ai-readiness.md.j2` template embeds `{{ harness_maker_src_path }}` which resolves to `_HARNESS_MAKER_PKG_ROOT = str(Path(__file__).parent.parent.parent)` — an absolute path. When pytest runs from a worktree (`.worktrees/execute-*/`) the path differs from the main repo, producing a different hash. All 8 snapshot tests fail in the worktree but pass on the main repo. Always run snapshot tests from the main repo directory to verify. The pre-existing failures in the worktree are NOT regressions — they disappear on `finalize stage-only` when changes land on the main branch.
