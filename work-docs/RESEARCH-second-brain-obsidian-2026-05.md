---
type: research
task_slug: second-brain-obsidian-2026-05
status: complete
created: 2026-05-11
tags: [harness-maker, research, obsidian, second-brain, mcp, refdocs, memory]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://obsidian.md/help/cli
  - https://obsidian.md/changelog/2026-02-10-desktop-v1.12.0/
  - https://github.com/coddingtonbear/obsidian-local-rest-api
  - https://github.com/cyanheads/obsidian-mcp-server
  - https://chatforest.com/reviews/obsidian-mcp-servers/
  - https://arxiv.org/abs/2604.14228
  - https://arxiv.org/abs/2507.16044
  - https://arxiv.org/abs/2505.06416
related_docs:
  - "[[RESEARCH-harness-trends-2026-05]]"
  - "[[RESEARCH-harness-gap-cot-2026-05]]"
  - "[[RESEARCH-loop-longevity-strategies]]"
  - "[[PLAN-make-ux-gaps-2026-05]]"
  - "[[PLAN-multi-repo-mgmt-2026-05]]"
summary: "Obsidian Second Brain connector is user-facing; start read-only via refdocs/vault indexing"
---

# 🎯 Recommended Direction

**Obsidian Second Brain 연결은 benchmark runner보다 우선순위가 높다.** 이유는 간단하다: 실제 사용자가 매일 체감할 수 있고, harness-maker의 기존 `ref_folders`, `refdocs-search`, `.claude/memory/*`, `memory/episodic` 구조와 직접 맞물린다.

권장 방향은 **read-only vault context connector부터 시작**이다. 즉, Obsidian vault를 "외부 장기기억/프로젝트 지식 저장소"로 읽게 하되, 첫 버전에서는 agent가 vault를 직접 수정하지 못하게 한다. 이후 write-back은 별도 plan으로 분리한다.

최소 제품 형태:

1. `harness.yaml.ref_folders`에 Obsidian vault 또는 vault 하위 폴더를 등록한다.
2. `refdocs-search`가 Obsidian Markdown 특성인 wikilink, tags, frontmatter, backlinks를 인식해 검색 결과를 더 잘 요약한다.
3. `/hm:research`, `/hm:plan`, `/hm:execute`가 repo-local memory와 Obsidian vault memory를 구분해서 로드한다.
4. 선택적으로 Obsidian CLI/MCP가 있으면 "active note", "daily note", "open in UI" 같은 richer context를 읽는다.

이 접근은 MCP 서버 설치, API key, Obsidian plugin 권한 문제를 첫 구현에서 피한다. 사용자는 vault path만 연결하면 되고, 실패해도 일반 파일 검색으로 fallback 가능하다.

# 🛠️ Approaches Found

| Field | Content |
|-------|---------|
| Approach | **A. Filesystem-first Obsidian vault as `ref_folders`** |
| Assumption | Obsidian vault는 결국 로컬 Markdown 폴더이므로, agent에게 필요한 80%는 안전한 read-only 파일 검색으로 해결된다. |
| Evidence | Obsidian은 vault를 Markdown 파일 폴더로 운영한다. harness-maker에는 이미 `RefFolder` 모델과 `refdocs-search` skill이 있다. 기존 `PLAN-make-ux-gaps-2026-05`도 `ref_folders` slash-command path를 추가했다. |
| Trade-off | Obsidian의 active file, command palette, Dataview/Bases query, backlink graph 같은 runtime context는 제한적이다. |
| Compatibility | 매우 높음. 신규 외부 dependency 없이 Python indexer와 templates만 수정하면 된다. |
| Risk | low. Read-only라 vault 손상 위험이 낮다. |

| Field | Content |
|-------|---------|
| Approach | **B. Obsidian CLI adapter** |
| Assumption | 2026년 Obsidian 1.12 CLI는 공식 경로이므로, community MCP보다 안정적인 bridge가 될 수 있다. |
| Evidence | Obsidian CLI help는 search/read/create/append/backlinks/links/tags/properties/tasks 등 agent-friendly command를 제공한다고 설명한다. 공식 changelog도 external tools integration용 CLI를 명시한다. |
| Trade-off | Obsidian 앱과 1.12 installer가 필요하다. Headless 또는 CI 환경에서는 동작성이 제한될 수 있다. |
| Compatibility | medium-high. `subprocess.run(timeout=...)` wrapper로 구현 가능하지만, user environment variance가 크다. |
| Risk | medium. CLI availability/version detection과 fallback이 필요하다. |

| Field | Content |
|-------|---------|
| Approach | **C. MCP / Local REST API integration** |
| Assumption | read/write/search/open-in-UI 같은 richer UX가 필요하면 MCP 서버가 가장 자연스럽다. |
| Evidence | Obsidian Local REST API는 authenticated HTTPS REST API로 vault search/read/patch/open/commands를 제공한다. `cyanheads/obsidian-mcp-server`는 Local REST API를 감싸 read/write/search/frontmatter/tag/section edit tools를 제공하고, folder-scoped permissions와 read-only kill switch를 제공한다. MCP ecosystem 논문들은 REST-backed MCP 서버가 일반 패턴임을 보여준다. |
| Trade-off | 설치 복잡도, API key, self-signed cert, plugin trust, write permission 위험이 있다. |
| Compatibility | medium. harness-maker는 `mcp_servers` propagation을 이미 갖고 있지만, cross-target Claude/Cursor/Codex config 차이가 있다. |
| Risk | medium-high. 첫 버전에서 write를 열면 prompt injection과 vault corruption risk가 커진다. |

# ⚠️ Pitfalls

1. **Vault write를 너무 빨리 열면 안 된다.** Obsidian vault는 개인 지식 저장소라 repo보다 복구 심리비용이 크다. 첫 버전은 read-only가 맞다.
2. **MCP 서버 생태계가 파편화돼 있다.** 2026년 4월 기준 Obsidian MCP 서버는 여러 아키텍처가 경쟁하고 공식 지원은 아니다. 특정 community server에 hard dependency를 두면 rot risk가 크다.
3. **Local REST API는 강력하지만 권한면이 넓다.** 파일 read/write/delete/command execution까지 가능하다. `OBSIDIAN_READ_ONLY`, folder scope, destructive confirmation이 없는 서버는 피해야 한다.
4. **Obsidian CLI는 공식이지만 앱 의존성이 있다.** Obsidian CLI 문서는 앱이 실행 중이어야 한다고 설명한다. 서버/CI/headless 사용자는 fallback이 필요하다.
5. **Context bloat 위험.** Second Brain 전체를 읽으면 모델 품질이 오히려 떨어진다. vault-wide dump 금지, query-first retrieval, frontmatter/tag/path filters가 필요하다.
6. **Personal/private data boundary.** vault에는 일기, 고객 정보, 비밀, API key가 섞일 수 있다. default include가 아니라 explicit folder allowlist가 필요하다.
7. **Prompt injection in notes.** Markdown note 안의 악성 지시문이 agent context로 들어올 수 있다. `refdocs-search`는 vault content를 "user reference material"로만 취급하고 instruction authority를 낮춰야 한다.

# ❓ Open Questions

1. **연결 단위**: vault 전체를 허용할지, `Projects/<repo-name>/`, `Areas/Engineering/` 같은 folder allowlist만 허용할지 결정 필요. 권장: folder allowlist only.
2. **첫 구현 target**: `ref_folders` 확장만 할지, `obsidian_vaults`라는 별도 config schema를 만들지 결정 필요. 권장: 별도 `second_brain.obsidian` schema. `ref_folders`만 쓰면 Obsidian-specific parsing을 표현하기 어렵다.
3. **쓰기 기능**: first release에서 vault write를 완전히 제외할지, `/hm:wrapup --obsidian-note`처럼 명시 opt-in append만 허용할지 결정 필요. 권장: first release read-only, write-back은 후속.
4. **Obsidian CLI/MCP 우선순위**: 공식 CLI adapter를 먼저 붙일지, MCP server config helper를 먼저 붙일지 결정 필요. 권장: filesystem-first → CLI optional → MCP optional.
5. **검색 품질**: 단순 `rg`로 충분한지, wikilink/backlink/frontmatter index를 구축할지 결정 필요. 권장: first release는 Markdown-aware lightweight index.
6. **보안 게이트**: vault에서 가져온 note를 prompt-injection scanner에 통과시킬지 결정 필요. 권장: high-risk patterns는 warning과 source demotion.

# 📚 Sources

- [Obsidian CLI Help](https://obsidian.md/help/cli) — official CLI supports automation, vault search/read/create/append, backlinks, links, properties, tasks, developer commands.
- [Obsidian 1.12.0 changelog](https://obsidian.md/changelog/2026-02-10-desktop-v1.12.0/) — official CLI added for scripting, automation, and external tool integration.
- [Obsidian Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) — authenticated local REST API for scripts/browser extensions/AI agents; supports search, commands, tags, open files, PATCH operations.
- [cyanheads/obsidian-mcp-server](https://github.com/cyanheads/obsidian-mcp-server) — MCP server over Local REST API with read/write/search/frontmatter/tag tools, folder-scoped permissions, and read-only switch.
- [ChatForest Obsidian MCP server survey](https://chatforest.com/reviews/obsidian-mcp-servers/) — surveys multiple Obsidian MCP approaches and notes lack of official MCP blessing.
- [Dive into Claude Code](https://arxiv.org/abs/2604.14228) — describes agent systems as MCP/plugins/skills/hooks plus context management and append-oriented session storage.
- [From REST to MCP](https://arxiv.org/abs/2507.16044) — finds most MCP servers are REST-backed and discusses tool exposure/repair/filtering.
- [ScaleMCP](https://arxiv.org/abs/2505.06416) — argues dynamic MCP tool retrieval/synchronization improves tool invocation at scale.

# 🔗 Related Internal Docs

- [[RESEARCH-harness-trends-2026-05]] — context engineering and user-facing reliability trend context.
- [[RESEARCH-harness-gap-cot-2026-05]] — long-term memory and episodic memory were already high-ROI candidates.
- [[RESEARCH-loop-longevity-strategies]] — context continuity and compaction issues.
- [[PLAN-make-ux-gaps-2026-05]] — `ref_folders` slash-command coverage and lifecycle UX.
- [[PLAN-multi-repo-mgmt-2026-05]] — portable relative-path convention for cross-machine paths.
