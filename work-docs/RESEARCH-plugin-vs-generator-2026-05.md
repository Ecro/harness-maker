---
type: research
task_slug: plugin-vs-generator-2026-05
status: complete
created: 2026-05-09
tags: [harness-maker, architecture, plugin, generator, design-rationale]
mtime_warn_days: 30
libs_fetched: []
sources: []
related_docs: []
summary: "Generator 패턴이 필수인 이유: 5개의 binding constraint (personalization, user-block, dual-IDE schema, preset, fingerprint)"
---

# 🎯 Recommended Direction

**현재 generator 패턴이 올바른 선택이다.** 단, "plugin이면 update가 일원화"라는 장점 하나는 실제로 있다. 미래에 "hash-match 자동 재렌더" 기능으로 마찰을 줄이는 것이 실현 가능한 개선이다.

## 긴 버전 (왜)

harness-maker는 *이미 plugin이다* — `.claude-plugin/plugin.json` + `.cursor-plugin/plugin.json` 양쪽에 manifest가 있다. 질문의 핵심은 "왜 plugin이 agent/skill/command를 직접 serve 하지 않고, user 프로젝트로 복사본을 생성하는 방식으로 작동하는가?"이다.

그 답은 5개의 **binding constraint** 로 설명된다.

---

# 🛠️ Approaches Found

## Approach A: 현재 — Generator (Python renders into user's project)

| Field | Content |
|-------|---------|
| Approach | Generator: Python renders `.j2` templates → user's `.claude/` (현재) |
| Assumption | 각 프로젝트는 고유한 context를 갖고, 그것을 agent/skill 프롬프트에 주입해야 함 |
| Evidence | `code-reviewer.md.j2` → `{% for d in config.project.domains %}`; `failures.en.md.j2` vs `failures.ko.md.j2`; `Production.json.j2` vs `Side.json.j2`; `cursor/hooks.json.j2` vs `hooks/hooks.json.j2` |
| Trade-off | update friction: harness-maker 업그레이드 후 `/hm:make` 재실행 필요 |
| Compatibility | 완전 호환 (현재 설계) |
| Risk | low |

### 5개의 binding constraint 분석

**[C1] Template injection — plugin 시스템에 templating hook이 없다**

Claude Code plugin system은 plugin 설치 시점에 사용자 변수를 주입하는 메커니즘을 제공하지 않는다. `config.project.domains`, `locale`, `preset`, `reviewers.enabled` 등은 프로젝트마다 다르다. 이것들을 agent 프롬프트에 반영하려면 *렌더 타임*에 Jinja2로 처리해야 한다.

```
code-reviewer.md.j2:
  {% for d in config.project.domains %}
  {% include "agents/_standards/" + d + ".md.j2" ignore missing %}
  {% endfor %}
```

Python project에 `python` domain을 등록하면, code-reviewer가 Python 특화 하드룰을 갖는다. 정적 plugin으로는 이게 불가능하다.

**[C2] User customization blocks — 사용자 편집이 upgrade를 견뎌야 한다**

```
<!-- @hm:user:extensions -->
<!-- Project-specific reviewer rules. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
```

`block_merge.py`는 이 marker를 기준으로 사용자가 추가한 내용을 re-render 시 보존한다. plugin-resident 파일이라면 사용자가 편집할 수 없고 (편집해도 `/plugin update`에 덮어씌워짐), 이 customization 메커니즘 자체가 불가능하다.

**[C3] Dual-IDE target — hooks schema가 IDE마다 다르다**

```
# Claude Code reads:  .claude/hooks/hooks.json
# schema: PascalCase event keys, nested {hooks: [], matcher:}

# Cursor reads:       .cursor/hooks.json  
# schema: lowercase camelCase, version: 1, flat {matcher, command}
```

이것은 empirically 검증된 사실 (`tests/cursor-compat/results-2026-05-08.md`). 단일 정적 파일로 양쪽을 만족시킬 수 없다. generator만이 두 개의 다른 template에서 두 개의 다른 파일을 렌더할 수 있다.

**[C4] Preset — settings.json / agent permissions이 preset마다 다르다**

`Production.json.j2`와 `Side.json.j2`는 다른 permissions를 렌더한다. Side preset은 reviewer가 더 적고 worktree scope도 다르다. 정적 plugin은 하나의 configuration만 ship할 수 있다.

**[C5] Fingerprint-based safe upgrade — content_hash가 파일 소유권을 추적한다**

`reconcile.py`의 decision matrix:
```
existing hash matches our recompute  → REPLACE (safe overwrite)
existing hash mismatches + markers   → MERGE_BLOCK (사용자 편집 보존)
existing hash mismatches otherwise   → KEEP (사용자 파일, 건드리지 않음)
```

이 메커니즘은 파일이 user 프로젝트에 있고 우리의 `content_hash` frontmatter를 갖고 있어야 작동한다. plugin-resident 파일은 항상 "fresh version"이므로 이 fingerprinting이 의미 없어진다.

---

## Approach B: Pure Static Plugin (live agents/skills from plugin dir)

| Field | Content |
|-------|---------|
| Approach | plugin이 `.claude/agents/`, `.claude/skills/` 를 직접 serve |
| Assumption | 모든 프로젝트에 동일한 agent 설정으로 충분함 |
| Evidence | Claude Code plugin spec은 `agents/`, `skills/`, `commands/` 디렉토리를 plugin manifest에서 참조 가능 |
| Trade-off | personalization 없음, user customization 불가, dual-IDE 불가, one update step |
| Compatibility | 현재 설계와 근본적으로 충돌 |
| Risk | high (harness-maker의 core value prop을 제거) |

**Genuine advantage**: `/plugin update` 한 번으로 agent 프롬프트까지 업데이트된다. 현재는 `uv upgrade harness-maker` + `/hm:make` 두 단계 필요.

**Why this doesn't work for harness-maker**:
- code-reviewer에 Python domain standards를 넣어줄 방법 없음
- user가 agent에 자기 규칙 추가했는데 update가 날려버림
- Cursor는 `.cursor/hooks.json`, Claude Code는 `.claude/hooks/hooks.json` — 둘 다 커버 불가

---

## Approach C: Hybrid — thin wrapper in user project, base in plugin

| Field | Content |
|-------|---------|
| Approach | 사용자 프로젝트에는 얇은 wrapper만 (include/delegate), base는 plugin에서 live serve |
| Assumption | Claude Code agent 파일에 include/import 메커니즘이 있음 |
| Evidence | **없음.** Claude Code agent 파일은 standalone markdown; cross-file include 없음 |
| Trade-off | 이론적으로 update friction 해결 + personalization 유지 가능 |
| Compatibility | 불가 — IDE에 해당 feature 없음 |
| Risk | high (존재하지 않는 기능에 의존) |

현재로서는 실현 불가. Claude Code agent system이 include directive를 지원하면 재검토 가능.

---

# ⚠️ Pitfalls

**P1: "plugin update = 모든 것이 업데이트"는 착각이다**

plugin이 ship하는 것은 `/harness-maker:make` 명령 자체다. 이 명령이 더 새로운 template을 갖고 있어도, 이전에 렌더된 `.claude/agents/code-reviewer.md`는 업데이트되지 않는다. 사용자가 `/hm:make`를 다시 실행해야 한다. 이것은 generator 패턴의 고유한 마찰이며, pure plugin도 이 문제를 *다른 방식*으로 갖고 있다 (plugin update = 모든 사용자 편집 내용 소실).

**P2: Cursor hooks schema 통일 시도 → hooks 무음 실패**

2026-05-08 kairos 0.5.7 forensic에서 확인. `.cursor/hooks.json`을 Claude Code 스키마(PascalCase)로 렌더했을 때 Cursor가 hook을 fire하지 않았다. 스키마 통일 시도하지 말 것.

**P3: settings.json을 YAML frontmatter와 함께 렌더 → Claude Code가 permissions 무시**

0.3.1에서 발견. Claude Code는 `settings.json`을 pure JSON으로 기대한다. frontmatter prefix(`---\n...---\n`)가 붙으면 전체 permissions 설정이 무시된다.

---

# ❓ Open Questions

이 연구는 현재 설계의 rationale 파악을 목적으로 한 것이므로, 추가 plan이 필요한 open question은 하나다:

1. **Update friction 개선 가능한가?** — `/hm:make --update`가 content_hash가 일치하는 파일만 자동 재렌더 (= 사용자 편집 없는 파일)하도록 하면, "업그레이드 후 `/hm:make` 재실행"의 마찰을 `/hm:make --update`로 줄일 수 있다. 현재 `--reinterview` flag는 비슷하지만 인터뷰를 강제한다. "silent re-render, hash-match only"가 빠진 기능.

---

# 📚 Sources

- `src/harness_maker/render.py` — `content_hash`, `frontmatter` 생성 로직
- `src/harness_maker/reconcile.py` — KEEP/REPLACE/MERGE_BLOCK decision matrix
- `src/harness_maker/block_merge.py` — `<!-- @hm:user:* -->` marker 보존 로직
- `src/harness_maker/templates/cursor/hooks.json.j2` — Cursor hooks schema + 스키마 분기 근거 주석
- `src/harness_maker/templates/agents/code-reviewer.md.j2` — domain injection `{% for d in config.project.domains %}`
- `src/harness_maker/synthesize.py` — blueprint 생성, full inventory install 정책
- `.claude-plugin/plugin.json` — harness-maker가 이미 plugin임을 확인
- `tests/cursor-compat/results-2026-05-08.md` — hooks schema empirical verification

---

# 🔗 Related Internal Docs

- `CLAUDE.md §Plugin 구조` — dual plugin manifest 정책
- `CLAUDE.md §보안/권한` — reviewer agent permission allow/deny 정책
- `CLAUDE.md §Targets 정책` — Cursor native discovery scope + dual-render 설계
- `CLAUDE.md §버전업 정책` — 4파일 동시 수정 이유 (plugin.json × 2)
