---
type: research
task_slug: user-workflow-opportunities-2026-05
status: complete
created: 2026-05-11
tags: [harness-maker, research, product-discovery, user-workflows, mcp, persistent-memory]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://code.claude.com/docs/en/mcp
  - https://linear.app/changelog/2026-02-26-deeplink-to-ai-coding-tools
  - https://obsidian.md/help/cli
  - https://obsidian.md/changelog/2026-02-10-desktop-v1.12.0/
  - https://github.com/coddingtonbear/obsidian-local-rest-api
  - https://github.com/cyanheads/obsidian-mcp-server
  - https://playwright.dev/docs/getting-started-mcp
  - https://docs.github.com/en/copilot/concepts/agents/cloud-agent/mcp-and-cloud-agent
  - https://arxiv.org/abs/2603.23802
  - https://arxiv.org/abs/2602.20478
  - https://arxiv.org/abs/2604.14228
  - https://arxiv.org/abs/2507.16044
related_docs:
  - "[[RESEARCH-second-brain-obsidian-2026-05]]"
  - "[[RESEARCH-harness-trends-2026-05]]"
  - "[[RESEARCH-harness-gap-cot-2026-05]]"
  - "[[PLAN-make-ux-gaps-2026-05]]"
  - "[[PLAN-multi-repo-mgmt-2026-05]]"
summary: "User-facing opportunities: second brain, issue-context intake, browser/debug evidence loop"
---

# 🎯 Recommended Direction

새 discovery 방식으로 다시 보면, harness-maker의 다음 high-impact 방향은 **benchmark runner나 meta-harness보다 유저가 매번 복붙하는 외부 context를 자동으로 안전하게 가져오는 것**이다.

Top 3 권장:

1. **Second Brain / Persistent Memory Connector** — Obsidian/Markdown vault, Notion, project docs를 read-only long-term context로 연결한다. 가장 큰 반복 pain은 "매 세션마다 다시 설명"이다.
2. **Issue Context Intake** — Linear/GitHub/Jira issue를 `/hm:plan` 또는 `/hm:loop` 입력으로 구조화한다. 유저가 description/comments/links/screenshots를 복붙하지 않게 한다.
3. **Evidence Loop for Debugging** — browser/devtools/Sentry/log context를 verify/review 단계로 끌어와 "코드를 고쳤다"가 아니라 "실제 UI/production evidence로 확인했다"로 바꾼다.

이 세 가지는 모두 실제 유저 workflow에 붙어 있고, harness-maker의 기존 기능과 정합성이 높다. 반대로 full MCP marketplace aggregator나 write-heavy automation은 범위와 보안 리스크가 커서 후순위다.

# 🔍 Refinement Decisions

이번 재조사는 사용자의 지적을 반영해 방법을 바꿨다.

- 기존 방식: arXiv / benchmark / agent-harness architecture 중심.
- 새 방식: user artifact scan → repeated pain query → MCP/community prototype scan → local capability matrix.
- 판단 기준: 실제 사용자가 매일 겪는가, 복붙/재설명 시간을 줄이는가, 기존 harness-maker 구조에 낮은 위험으로 붙는가.

# 🛠️ Approaches Found

## 10개 후보 풀

| # | Opportunity | User artifact / pain | Evidence signal | harness-maker fit | Rank |
|---|-------------|----------------------|-----------------|-------------------|------|
| 1 | Obsidian / Markdown Second Brain | 프로젝트 맥락, 결정, 개인 지식이 vault에 있음 | Obsidian CLI 공식화, Local REST API, MCP 서버 다수 | `ref_folders`, `refdocs-search`, memory와 직접 연결 | Top 3 |
| 2 | Persistent memory across agents | Claude/Cursor/Codex가 세션마다 잊음 | persistent memory 제품/프로토타입 급증, Codified Context 논문 | `.claude/memory`, `memory/episodic`, wrapup와 연결 | Top 3에 1번과 병합 |
| 3 | Linear/GitHub/Jira issue intake | issue description/comments/links/screenshots 복붙 | Linear이 coding tool deeplink와 prompt templates 출시 | `/hm:plan`, `/hm:loop` 입력 normalization에 적합 | Top 3 |
| 4 | Browser/devtools verification loop | UI bug 확인, console/network/debug 반복 | Playwright MCP, Chrome DevTools MCP, Claude docs examples | `/hm:verify`, UX reviewer, e2e evidence로 연결 | Top 3 |
| 5 | Sentry/Statsig/monitoring intake | production error context 복붙 | Claude Code MCP docs가 Sentry/Statsig 예시를 직접 제시 | security/verify/review evidence source | Top 3에 4번과 병합 |
| 6 | MCP profile/safety manager | MCP 많아질수록 tool bloat와 prompt injection 위험 | Claude docs warns third-party MCP risk; MCP usage/action tools 급증 | `context_linter`, security scanner, `mcp_servers` already exist | High, enabling layer |
| 7 | Notion/Google Drive knowledge connector | docs/spec/meeting notes가 SaaS에 있음 | MCP ecosystem top servers include Notion/GDrive/Slack | harder auth; read-only source plugin later | Medium |
| 8 | Slack decision miner | decisions live in threads | MCP top-server lists and Claude docs cite Slack/Figma/email workflow | useful but privacy/auth heavy | Medium |
| 9 | Design artifact intake | Figma/Miro screenshots/specs | Claude docs: update template from Figma designs posted in Slack | likely useful for frontend users | Medium |
| 10 | Authenticated web fetch / browser-session bridge | Notion/Docs links behind login fail | community prototypes route through logged-in browser sessions | powerful but security-sensitive | Defer |

## Top 3 상세

| Field | Content |
|-------|---------|
| Approach | **A. Second Brain / Persistent Memory Connector** |
| Assumption | 유저가 agent에게 반복해서 설명하는 내용은 이미 Obsidian, Markdown docs, Notion, wiki, `CLAUDE.md`류 파일에 있다. |
| Evidence | Obsidian 1.12 CLI는 search/read/append/backlinks/tags/tasks 등 agent-friendly commands를 공식 제공한다. Local REST API와 Obsidian MCP 서버는 vault read/write/search/patch/open을 제공한다. Codified Context 논문은 hot-memory + cold-memory docs가 세션 간 일관성을 유지한다고 보고한다. |
| Trade-off | vault 전체를 context로 넣으면 bloat와 prompt injection risk가 생긴다. first release는 folder allowlist + read-only + query-first retrieval이어야 한다. |
| Compatibility | 매우 높음. `RefFolder`, `refdocs_index`, `refdocs-search`, `.claude/memory`, `memory/episodic`가 이미 있다. |
| Risk | low-to-medium. read-only로 시작하면 안전하지만, write-back은 별도 설계가 필요하다. |

| Field | Content |
|-------|---------|
| Approach | **B. Issue Context Intake** |
| Assumption | 코딩 task의 시작점은 점점 "로컬 prompt"가 아니라 Linear/GitHub/Jira issue가 된다. 좋은 harness는 issue context를 structured plan seed로 바꿔야 한다. |
| Evidence | Linear은 2026-02에 issue에서 Claude Code, Codex, Cursor 등으로 직접 launch하는 기능과 customizable prompt template을 출시했고, description/comments/updates/linked references/images를 prompt context로 넣는다. Claude Code MCP docs도 issue tracker에서 feature 구현과 PR 생성을 예시로 든다. |
| Trade-off | 각 tracker API/auth/MCP가 다르다. first release는 connector 구현보다 "copied issue markdown / URL / JSON → normalized work item"이 더 안전하다. |
| Compatibility | 높음. `/hm:plan` deep interview, `/hm:loop` feature mode, `work-docs/PLAN-*` frontmatter와 잘 맞는다. |
| Risk | medium. comments가 spec과 충돌할 때 질문해야 하며, tracker content prompt injection을 낮은 authority로 취급해야 한다. |

| Field | Content |
|-------|---------|
| Approach | **C. Evidence Loop for Debugging** |
| Assumption | 유저에게 중요한 것은 "agent가 코드를 바꿈"보다 console/network/Sentry/UI evidence로 실제 문제가 해결됐는지 확인하는 것이다. |
| Evidence | Claude Code MCP docs는 monitoring data, databases, Figma/Slack, Gmail workflows를 MCP use case로 든다. Playwright MCP는 structured accessibility snapshots, console messages, network monitoring/mocking을 제공한다. GitHub Copilot docs도 MCP를 external context/data source connector로 설명한다. MCP tool usage 논문은 software development가 MCP tool/downloads의 대부분이라고 보고한다. |
| Trade-off | browser/Sentry access는 credentials와 private data를 다룬다. default enable이 아니라 per-task opt-in + read-only evidence capture가 필요하다. |
| Compatibility | medium-high. `hm-verify`, UX reviewer, security scanner, mechanical checks에 evidence attachments를 붙일 수 있다. |
| Risk | medium. browser/profile automation과 monitoring tokens는 보안 사고로 이어질 수 있다. |

# ⚠️ Pitfalls

1. **Connector-first로 가면 위험하다.** MCP 서버를 많이 붙이는 것보다 "무엇을, 언제, 어떤 authority로 context에 넣을지"가 먼저다.
2. **Write 권한은 후순위다.** Obsidian/Notion/Slack/Linear write는 유용하지만, first release는 read-only 또는 draft-only가 맞다.
3. **Prompt injection surface가 넓어진다.** issue comments, Slack threads, vault notes, web pages는 모두 untrusted reference material이다. system/developer instruction처럼 취급하면 안 된다.
4. **MCP tool bloat.** MCP 서버가 늘면 tool descriptors와 tool choice noise가 커진다. `context_linter`가 MCP count만 경고하는 수준을 넘어 profile-based enable/disable이 필요하다.
5. **Auth setup fatigue.** 유저-facing 기능은 OAuth/API key/plugin install이 많을수록 adoption이 떨어진다. Markdown/filesystem/CLI fallback이 중요하다.
6. **Private data boundary.** personal vault, Slack, Drive에는 repo와 무관한 민감 정보가 있다. folder/channel/project allowlist가 default여야 한다.
7. **Browser automation overreach.** 실제 Chrome profile 제어는 session lock/corruption/privacy risk가 있다. Playwright-style isolated browser나 read-only logs부터 시작해야 한다.

# ❓ Open Questions

1. **우선 구현할 product slice**: Second Brain read-only connector를 먼저 할지, issue intake를 먼저 할지 결정 필요. 추천: Second Brain first, because repo already has `ref_folders` and memory code.
2. **Config shape**: `second_brain:` 별도 schema를 둘지, `ref_folders`에 type field를 추가할지 결정 필요. 추천: `second_brain.obsidian` + internally compiles to refdocs.
3. **Issue intake source**: first release가 Linear/GitHub API를 직접 붙일지, copied issue markdown/JSON parser만 제공할지 결정 필요. 추천: parser first, connector later.
4. **Evidence loop scope**: Playwright/browser evidence와 Sentry evidence 중 어느 것을 먼저 할지 결정 필요. 추천: Playwright MCP guidance + verify evidence contract first; Sentry connector is auth-heavy.
5. **MCP safety profile**: `mcp_servers`에 read/write/destructive/trusted metadata를 추가할지 결정 필요. 추천: add metadata before adding more connector helpers.
6. **Authority model**: external artifacts를 PLAN/RESEARCH에 어떻게 표시할지 결정 필요. 추천: "External Reference (untrusted)" section with citation/path and prompt-injection warnings.

# 📚 Sources

- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp) — MCP connects Claude Code to issue trackers, monitoring dashboards, databases, designs, Slack, Gmail; docs warn to trust third-party MCP servers carefully.
- [Linear deeplink to AI coding tools](https://linear.app/changelog/2026-02-26-deeplink-to-ai-coding-tools) — Linear launches Claude Code/Codex/Cursor deeplinks with issue ID, context, comments, linked references, images, and customizable prompt templates.
- [Obsidian CLI](https://obsidian.md/help/cli) — official CLI supports search/read/create/append/backlinks/links/tags/properties/tasks.
- [Obsidian 1.12.0 changelog](https://obsidian.md/changelog/2026-02-10-desktop-v1.12.0/) — CLI added for scripting, automation, external tool integration.
- [Obsidian Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) — local authenticated REST API for vault search/read/write/patch/open/commands.
- [cyanheads/obsidian-mcp-server](https://github.com/cyanheads/obsidian-mcp-server) — MCP wrapper with read/write/search/frontmatter/tag tools, folder scopes, read-only kill switch.
- [Playwright MCP](https://playwright.dev/docs/getting-started-mcp) — browser automation via structured accessibility snapshots, screenshots, console messages, network monitoring/mocking.
- [GitHub Copilot MCP docs](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/mcp-and-cloud-agent) — MCP as standard context/data-source connector for coding agents.
- [How are AI agents used? Evidence from 177,000 MCP tools](https://arxiv.org/abs/2603.23802) — software development dominates MCP tools/downloads; action tools rose sharply.
- [Codified Context](https://arxiv.org/abs/2602.20478) — persistent hot/cold context prevents repeated mistakes and maintains cross-session consistency.
- [Dive into Claude Code](https://arxiv.org/abs/2604.14228) — Claude Code system context includes MCP, plugins, skills, hooks, compaction, worktree isolation, append-oriented session storage.
- [From REST to MCP](https://arxiv.org/abs/2507.16044) — most MCP servers are REST-backed; filtering/regrouping reduces tool complexity.

# 🔗 Related Internal Docs

- [[RESEARCH-second-brain-obsidian-2026-05]] — detailed Obsidian connector research.
- [[RESEARCH-harness-trends-2026-05]] — earlier benchmark/harness-centered research; useful but not user-workflow-first.
- [[RESEARCH-harness-gap-cot-2026-05]] — long-term memory and context reliability prior work.
- [[PLAN-make-ux-gaps-2026-05]] — existing `ref_folders`, lifecycle, `vault_member` detection.
- [[PLAN-multi-repo-mgmt-2026-05]] — relative path portability convention reused for external folders.
