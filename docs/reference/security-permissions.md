# 보안 / 권한 (v1.6, REVIEW-2026-05-08 개정)

> Relocated verbatim from `CLAUDE.md` on 2026-09-30 (SPEC-top-issues-2026-09). CLAUDE.md keeps a
> short summary and a link here; this file is the recorded *why*.

## 보안 / 권한 (v1.6, REVIEW-2026-05-08 개정)

> **⚠️ 집행 현실 정정 (2026-06-02 — codex permission probe + Claude Code 공식 docs):**
> 아래 agent 별 `permissions.allow/deny` frontmatter 블록은 **Claude Code 가 집행하지
> 않는다.** subagent frontmatter 의 공식 인식 필드는 `name / description / tools /
> disallowedTools / model / permissionMode / hooks / …` 뿐 — `permissions` 는 그
> 목록에 없어 **silent ignore** 된다 (`sub-agents.md`). command 단위 allow/deny 는
> **오직 `settings.json`** (user/project/local/managed) 에서만 deny-first 로 집행된다
> (`permissions.md`). 결과:
> - read-only reviewer 의 *실제* 경계는 **`tools:` 에 Bash 부재** (도구 자체가 없음 — 이건 집행됨). frontmatter `deny` 는 의도 표기일 뿐, 보안 경계 아님.
> - `tools:` 에 Bash 가 있으면 frontmatter deny 와 무관하게 `sh`/`python`/`rm` 실행 가능. executor 의 `Write(/etc/**)`·`Edit(~/.ssh/**)` deny 도 동일하게 cosmetic — `Write`/`Edit` 도구가 있으면 경로 무관 write 가능.
> - **per-agent** command scoping 은 frontmatter 로 표현 불가. 진짜 경계는 (a) `tools:`/`disallowedTools` 도구 가감, (b) `settings.json` deny(단 session-wide — 전 agent·메인 공통이라 `python -m harness_maker …` 같은 자기 호출까지 막힘 주의), (c) agent 식별 기반 PreToolUse hook, (d) sandbox. 넷 다 `--dangerously-skip-permissions`/`bypassPermissions` 모드에선 무력화됨.
> 아래 블록은 **의도(intent) 문서**로만 유지한다. 실제 집행이 필요하면 위 (a)~(d) 로 옮길 것. 상세: [[fail:design subagent-frontmatter-permissions-not-enforced]], PLAN-spoton-codex-rm-stash-rootcause 후속.

- **Agent frontmatter `permissions:` 블록은 0.40.0 에서 전부 삭제됨** (Phase 7, ADR-002). subagent frontmatter 에 `permissions` 필드가 없어 Claude Code 가 silent-ignore 했고, 집행 0 인데 보안 경계처럼 읽혀 incoming brief 작성자를 오도했다. 진짜 경계는 `tools:` 뿐 (도구 부재 = 사용 불가). Reviewer agent 는 `tools:` 에 Bash 미포함 → `python -c`/`sh -c` 우회 자체가 불가 (이건 집행됨). Executor 는 `tools:` 에 Write/Edit/Bash 포함 → frontmatter deny 유무와 무관하게 경로 제한 없음. `.worktrees/**` 밖 write 금지는 **프롬프트 지시**이지 런타임 강제가 아니다 (executor_body.md.j2 의 "Scope — instruction, not enforcement").
- **Main-session `settings.json` deny (opt-in, default OFF — 2026-05-31):** 위 reviewer/executor *agent* deny 와 별개로, 사용자 메인 세션의 `settings.json.permissions.deny` 는 **기본 빈 리스트**다 (`rm`/`curl|sh`/`/etc`/`~/.ssh` write 미차단 — 솔로 작업 효율). 전체 destructive baseline 은 `harness.yaml.permissions.deny_dangerous: true` 로 opt-in → `["Bash(rm:*)", "Edit(/etc/**)", "Edit(~/.ssh/**)", "Edit(~/.aws/**)"]` 렌더 (0.40.0, Phase 5). **옛 리스트 `["Bash(rm:*)", "Bash(curl * | sh)", "Write(/etc/**)", "Write(~/.ssh/**)"]` 은 4개 중 3개가 죽은 문법** — `Write(<path>)` 는 file-permission check 가 Edit/Read 만 보므로 미집행, `Bash(curl * | sh)` 는 `|` 가 separator 라 subcommand 분할 후 매치 불가 (silent). `curl|sh` 탐지는 settings 규칙이 아니라 `permission_gate` PreToolUse hook 의 몫 (ADR-003). 재렌더 시 `_HARNESS_SHIPPED_DENY_LITERALS` 가 harness 가 실제 발행한 **죽은** literal 만 prune (live `Bash(rm:*)`/`Bash(curl:*)` 은 대체 hook 배선 전까지 보류 — `is_matchable_rule` 이 안전 불변식, `test_permission_syntax.py` 가 회귀 차단). **Why**: 솔로 프로젝트에서 `Bash(rm:*)` 기본 차단이 비효율적이라는 사용자 피드백. **Reviewer agents 는 `tools:` 에 Bash 부재로 rm 자체 불가** (read-only). `readiness.py` 의 `permissions_deny_present` / `deny_covers_dangerous` 두 signal 은 opt-out 시 N-A (passed=True, no penalty) — 의도된 config 선택은 finding 이 아님. 스키마: `models.PermissionsConfig.deny_dangerous` (default False), 양 `settings/*.json.j2` 가 `config.permissions.deny_dangerous` 로 분기.
- 모든 generated 파일은 frontmatter 에 `generated_by + content_hash + source_template + harness_maker_version`

> **Cursor target 의 권한 매핑** (Phase 1 검증 결과 채움):
> Cursor 의 `permissionMode`, `sandbox.json` 등가물이 위 allow/deny 정책을 어떻게 강제하는지 미정의. Phase 1 검증 fixture 로 확인 후 본 섹션 갱신.
