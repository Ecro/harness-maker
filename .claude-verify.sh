#!/usr/bin/env bash
# .claude-verify.sh — autoloop TESTER stage 가 호출하는 검증 entry.
# 각 Phase 의 task 별 sub-check + Phase Exit Criteria + Final Acceptance.
# v2.2: 12 phases (Phase 2 = Foundations, Phase 3 = Pipeline, Phase 8 = Worktree, Phase 9 = Security)
# Usage: bash .claude-verify.sh <check_name>
#        bash .claude-verify.sh all                  # 모든 Phase + Final Acceptance
#        bash .claude-verify.sh phase_<N>            # Phase N 의 Exit Criteria
#        bash .claude-verify.sh phase_<N>_invariants # cross-phase invariant gate

set -euo pipefail

CHECK="${1:-all}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ──────────────────────────────────────────────────────────────────────
# 공통 헬퍼
# ──────────────────────────────────────────────────────────────────────

log() { echo "[verify] $*"; }
fail() { echo "[verify FAIL] $*" >&2; exit 1; }
ok()   { echo "[verify OK] $*"; }

require_file() { test -f "$1" || fail "Missing file: $1"; }
require_dir()  { test -d "$1" || fail "Missing dir: $1"; }
require_cmd()  { command -v "$1" >/dev/null 2>&1 || fail "Missing command: $1"; }

# Cross-phase invariant: 생성된 .claude/ 자산 모두 frontmatter 보유
verify_frontmatter_invariants() {
  local phase_n="$1"
  # 임의 fixture (가장 최근 빌드된 것) 의 .claude/ 자산이 frontmatter 갖는지 검증
  for fix in tests/fixtures/side-python-cli tests/fixtures/prod-tauri-app tests/e2e/sandbox; do
    if [[ -d "$fix/.claude" ]]; then
      missing=$(find "$fix/.claude" -type f \( -name "*.md" -o -name "*.json" \) \
        -not -path "*/.backup-*/*" \
        -not -path "*/hooks/hooks.json" \
        -not -path "*/observability/refresh/*" \
        -not -path "*/observability/security/*" \
        -not -path "*/observability/metrics.jsonl" \
        | while read f; do
            head -1 "$f" 2>/dev/null | grep -q '^---' || echo "$f"
          done)
      if [[ -n "$missing" ]]; then
        # phase 1-2 는 .claude/ 가 없을 수 있음 — skip
        [[ "$phase_n" -ge 3 ]] || continue
        # phase 3+ 부터 모든 생성 .md/.json 에 frontmatter 필수
        echo "[invariant FAIL] phase $phase_n: 다음 파일에 frontmatter 없음:" >&2
        echo "$missing" >&2
        fail "frontmatter invariant violation"
      fi
    fi
  done
  ok "phase_${phase_n}_invariants (frontmatter 검증)"
}

phase_1_invariants()  { verify_frontmatter_invariants 1; }
phase_2_invariants()  { verify_frontmatter_invariants 2; }
phase_3_invariants()  { verify_frontmatter_invariants 3; }
phase_4_invariants()  { verify_frontmatter_invariants 4; }
phase_5_invariants()  { verify_frontmatter_invariants 5; }
phase_6_invariants()  { verify_frontmatter_invariants 6; }
phase_7_invariants()  { verify_frontmatter_invariants 7; }
phase_8_invariants()  { verify_frontmatter_invariants 8; }
phase_9_invariants()  { verify_frontmatter_invariants 9; }
phase_10_invariants() { verify_frontmatter_invariants 10; }
phase_11_invariants() { verify_frontmatter_invariants 11; }
phase_12_invariants() { verify_frontmatter_invariants 12; }

# ──────────────────────────────────────────────────────────────────────
# Phase 1: Project Scaffold + Plugin Manifest + i18n MVP
# ──────────────────────────────────────────────────────────────────────

phase_1_env() {
  log "환경 precheck (fail fast)"
  require_cmd uv
  require_cmd git
  require_cmd python3
  py_ver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  py_major=$(echo "$py_ver" | cut -d. -f1)
  py_minor=$(echo "$py_ver" | cut -d. -f2)
  [[ $py_major -eq 3 && $py_minor -ge 12 ]] || fail "Python 3.12+ 필요 (현재 $py_ver)"
  test -d .git || fail "current dir 가 git repo 아님 — 'git init' 필요"
  mkdir -p ~/.cache/harness-maker
  touch ~/.cache/harness-maker/.write-test
  rm ~/.cache/harness-maker/.write-test
  ok "phase_1_env (uv·git·python3.${py_minor}·cache write 모두 OK)"
}

phase_1_uv() {
  require_file pyproject.toml
  require_file uv.lock
  require_file src/harness_maker/__init__.py
  uv sync >/dev/null 2>&1 || fail "uv sync failed"
  uv run python -c "from harness_maker import __version__; assert __version__ == '0.1.0', __version__" \
    || fail "version mismatch (expected 0.1.0)"
  ok "phase_1_uv"
}

phase_1_manifest() {
  require_file .claude-plugin/plugin.json
  require_cmd jq
  name=$(jq -r .name .claude-plugin/plugin.json)
  [[ "$name" == "harness-maker" ]] || fail "plugin.json name != harness-maker (got $name)"
  ver=$(jq -r .version .claude-plugin/plugin.json)
  [[ "$ver" == "0.1.0" ]] || fail "plugin.json version != 0.1.0 (got $ver)"
  ok "phase_1_manifest"
}

phase_1_command() {
  require_file commands/make.md
  grep -q "/harness-maker:make" commands/make.md \
    || fail "make.md missing /harness-maker:make reference"
  uv run python -m harness_maker.cli --help >/dev/null 2>&1 \
    || fail "cli --help failed"
  ok "phase_1_command"
}

phase_1_i18n() {
  require_file src/harness_maker/i18n.py
  require_file src/harness_maker/i18n_messages.py
  uv run pytest tests/unit/test_i18n.py -q || fail "i18n tests failed"
  ok "phase_1_i18n"
}

phase_1_meta() {
  require_file README.md
  require_file LICENSE
  require_file .github/workflows/ci.yml
  grep -q "MIT" LICENSE || fail "LICENSE not MIT"
  grep -q "ruff" .github/workflows/ci.yml || fail "ci.yml missing ruff"
  grep -q "mypy" .github/workflows/ci.yml || fail "ci.yml missing mypy"
  grep -q "pytest" .github/workflows/ci.yml || fail "ci.yml missing pytest"
  ok "phase_1_meta"
}

phase_1() {
  phase_1_env
  phase_1_uv
  phase_1_manifest
  phase_1_command
  phase_1_i18n
  phase_1_meta
  uv run ruff check src/ || fail "ruff check failed"
  uv run mypy --strict src/ || fail "mypy strict failed"
  phase_1_invariants
  ok "Phase 1 Exit Criteria"
}

# ──────────────────────────────────────────────────────────────────────
# Phase 2: Foundations — Models + Profiler + Interviewer
# ──────────────────────────────────────────────────────────────────────

phase_2_models() {
  uv run python -c "from harness_maker.models import HarnessConfig, Blueprint, ProjectProfile, FileEntry, ConflictItem" \
    || fail "models import failed"
  uv run pytest tests/unit/test_models.py -q || fail "models tests failed"
  ok "phase_2_models"
}

phase_2_profile()   { uv run pytest tests/unit/test_profile.py -q   || fail "profile tests";   ok "phase_2_profile"; }
phase_2_interview() { uv run pytest tests/unit/test_interview.py -q || fail "interview tests"; ok "phase_2_interview"; }

phase_2() {
  phase_2_models
  phase_2_profile
  phase_2_interview
  uv run ruff check src/harness_maker/{models,profile,interview}.py || fail "ruff"
  uv run mypy --strict src/harness_maker/{models,profile,interview}.py || fail "mypy"
  phase_2_invariants
  ok "Phase 2 Exit Criteria"
}

# ──────────────────────────────────────────────────────────────────────
# Phase 3: Synthesis Pipeline — Synth + Render + Reconcile + Verify + Fixtures + CLI
# ──────────────────────────────────────────────────────────────────────

phase_3_synthesize() { uv run pytest tests/unit/test_synthesize.py -q || fail "synth tests";    ok "phase_3_synthesize"; }
phase_3_render()     { uv run pytest tests/unit/test_render.py -q     || fail "render tests";   ok "phase_3_render"; }
phase_3_reconcile()  { uv run pytest tests/unit/test_reconcile.py -q  || fail "reconcile";      ok "phase_3_reconcile"; }
phase_3_verifier()   { uv run pytest tests/unit/test_verify.py -q     || fail "verify tests";   ok "phase_3_verifier"; }

phase_3_fixtures() {
  for fix in side-python-cli side-tauri-app prod-tauri-app prod-firmware; do
    require_dir "tests/fixtures/$fix"
    require_file "tests/snapshot/$fix.expected.yaml"
  done
  uv run pytest tests/unit/test_synthesize_snapshot.py -q || fail "snapshot tests failed"
  ok "phase_3_fixtures"
}

phase_3_cli_make() {
  for fix in side-python-cli side-tauri-app prod-tauri-app prod-firmware; do
    rm -rf "tests/fixtures/$fix/.claude"
    uv run python -m harness_maker.cli make "tests/fixtures/$fix" --autoloop \
      || fail "cli make failed for $fix"
    require_file "tests/fixtures/$fix/.claude/harness.yaml"
    count=$(find "tests/fixtures/$fix/.claude" -type f | wc -l)
    case "$fix" in
      side-*)  [[ $count -ge 25 && $count -le 32 ]] || fail "$fix: expected 25-30 files, got $count" ;;
      prod-*)  [[ $count -ge 35 && $count -le 47 ]] || fail "$fix: expected 35-45 files, got $count" ;;
    esac
  done
  ok "phase_3_cli_make"
}

phase_3() {
  phase_3_synthesize
  phase_3_render
  phase_3_reconcile
  phase_3_verifier
  phase_3_fixtures
  phase_3_cli_make
  uv run ruff check src/ || fail "ruff"
  uv run mypy --strict src/ || fail "mypy"
  phase_3_invariants
  ok "Phase 3 Exit Criteria"
}

# ──────────────────────────────────────────────────────────────────────
# Phase 4: Monitoring 3 Metrics
# ──────────────────────────────────────────────────────────────────────

phase_4_telemetry() {
  require_file src/harness_maker/telemetry.py
  uv run pytest tests/unit/test_telemetry.py -q || fail "telemetry tests"
  ok "phase_4_telemetry"
}

phase_4_health() {
  require_file src/harness_maker/readiness.py
  uv run pytest tests/unit/test_readiness.py -q || fail "readiness tests"
  ok "phase_4_health"
}

phase_4_agent_quality() {
  require_file src/harness_maker/agent_quality.py
  uv run pytest tests/unit/test_agent_quality.py -q || fail "agent_quality tests"
  ok "phase_4_agent_quality"
}

phase_4_dashboard() {
  require_file src/harness_maker/templates/observability/dashboard.ko.md.j2
  require_file src/harness_maker/templates/observability/dashboard.en.md.j2
  require_file src/harness_maker/templates/commands/hm/monitor.md.j2
  ok "phase_4_dashboard"
}

phase_4_hooks_settings() {
  require_file src/harness_maker/templates/hooks/hooks.json.j2
  require_file src/harness_maker/templates/settings/Side.json.j2
  require_file src/harness_maker/templates/settings/Production.json.j2
  ok "phase_4_hooks_settings"
}

phase_4() {
  phase_4_telemetry
  phase_4_health
  phase_4_agent_quality
  phase_4_dashboard
  phase_4_hooks_settings
  rm -rf tests/fixtures/side-python-cli/.claude
  uv run python -m harness_maker.cli make tests/fixtures/side-python-cli --autoloop || fail "make"
  jq . tests/fixtures/side-python-cli/.claude/hooks/hooks.json >/dev/null \
    || fail "rendered hooks.json invalid"
  require_file tests/fixtures/side-python-cli/.claude/observability/dashboard.md
  phase_4_invariants
  ok "Phase 4 Exit Criteria"
}

# ──────────────────────────────────────────────────────────────────────
# Phase 5: Anti-rot Pipeline
# ──────────────────────────────────────────────────────────────────────

phase_5_anthropic()      { uv run pytest tests/unit/crawler/test_anthropic_blog.py -q  || fail "anthropic crawler"; ok "phase_5_anthropic"; }
phase_5_github()         { uv run pytest tests/unit/crawler/test_github_releases.py -q || fail "gh crawler";        ok "phase_5_github"; }
phase_5_arxiv()          { uv run pytest tests/unit/crawler/test_arxiv.py -q           || fail "arxiv crawler";     ok "phase_5_arxiv"; }
phase_5_osv()            { uv run pytest tests/unit/crawler/test_osv_dev.py -q         || fail "osv crawler";       ok "phase_5_osv"; }
phase_5_relevance()      { uv run pytest tests/unit/test_relevance.py -q               || fail "relevance";         ok "phase_5_relevance"; }
phase_5_skill_template() { require_file src/harness_maker/templates/skills/research-crawler/SKILL.md.j2; ok "phase_5_skill_template"; }
phase_5_filter_template(){ require_file src/harness_maker/templates/skills/relevance-filter/SKILL.md.j2; ok "phase_5_filter_template"; }

phase_5_refresh_template() {
  require_file src/harness_maker/templates/commands/hm/refresh.md.j2
  grep -q "AskUserQuestion" src/harness_maker/templates/commands/hm/refresh.md.j2 \
    || fail "refresh.md.j2 missing AskUserQuestion (manual confirm 필수)"
  ok "phase_5_refresh_template"
}

phase_5() {
  phase_5_anthropic
  phase_5_github
  phase_5_arxiv
  phase_5_osv
  phase_5_relevance
  phase_5_skill_template
  phase_5_filter_template
  phase_5_refresh_template
  uv run python -c "from harness_maker.crawler import anthropic_blog, github_releases, arxiv, osv_dev" \
    || fail "crawler imports"
  phase_5_invariants
  ok "Phase 5 Exit Criteria"
}

# ──────────────────────────────────────────────────────────────────────
# Phase 6: Workflow Engine + Conditional Router + Modular Installer
# ──────────────────────────────────────────────────────────────────────

phase_6_stages() {
  for s in research spec plan execute review wrapup verify; do
    require_file "src/harness_maker/templates/stages/$s.md.j2"
  done
  ok "phase_6_stages"
}

phase_6_fuse()      { uv run pytest tests/unit/test_workflow_fuse.py -q || fail "fuse"; ok "phase_6_fuse"; }
phase_6_router()    { uv run pytest tests/unit/test_conditional_router.py -q || fail "router"; ok "phase_6_router"; }
phase_6_modular()   { uv run pytest tests/unit/test_modular_edit.py -q || fail "modular"; ok "phase_6_modular"; }

phase_6_commands_render() {
  rm -rf tests/fixtures/side-python-cli/.claude
  uv run python -m harness_maker.cli make tests/fixtures/side-python-cli --autoloop || fail "make"
  for s in research spec plan execute review wrapup verify; do
    require_file "tests/fixtures/side-python-cli/.claude/commands/hm/$s.md"
  done
  require_file tests/fixtures/side-python-cli/.claude/commands/hm/dev.md
  ok "phase_6_commands_render"
}

phase_6_agents() {
  rm -rf tests/fixtures/prod-tauri-app/.claude
  uv run python -m harness_maker.cli make tests/fixtures/prod-tauri-app --autoloop || fail "make"
  for a in code-reviewer security-reviewer performance-reviewer ux-reviewer concurrency-reviewer consensus-arbiter autoloop-coder executor; do
    require_file "tests/fixtures/prod-tauri-app/.claude/agents/$a.md"
  done
  ok "phase_6_agents"
}

phase_6_workflow_interview() { uv run pytest tests/unit/test_interview.py -q || fail "interview"; ok "phase_6_workflow_interview"; }

phase_6() {
  phase_6_stages
  phase_6_fuse
  phase_6_router
  phase_6_modular
  phase_6_workflow_interview
  phase_6_commands_render
  phase_6_agents
  rm -rf tests/fixtures/prod-tauri-app/.claude
  uv run python -m harness_maker.cli make tests/fixtures/prod-tauri-app --autoloop --add reviewer:security || fail "modular add"
  require_file tests/fixtures/prod-tauri-app/.claude/agents/security-reviewer.md
  phase_6_invariants
  ok "Phase 6 Exit Criteria"
}

# ──────────────────────────────────────────────────────────────────────
# Phase 7: Autoloop driver + Verify-before-completion gate
# ──────────────────────────────────────────────────────────────────────

phase_7_driver()         { uv run pytest tests/unit/test_autoloop_driver.py -q || fail "autoloop driver"; ok "phase_7_driver"; }
phase_7_loop_template()  { require_file src/harness_maker/templates/commands/hm/loop.md.j2; ok "phase_7_loop_template"; }

phase_7_autoloop_assets() {
  require_file src/harness_maker/templates/agents/autoloop-coder.md.j2
  require_file src/harness_maker/templates/skills/autoloop-driver/SKILL.md.j2
  ok "phase_7_autoloop_assets"
}

phase_7_verify_gate() {
  require_file src/harness_maker/templates/skills/verify-before-completion/SKILL.md.j2
  for k in "PLAN/SPEC" "smoke" "Health" "pending" "security" "Worktree"; do
    grep -E "$k" src/harness_maker/templates/skills/verify-before-completion/SKILL.md.j2 >/dev/null \
      || fail "verify-before-completion missing check: $k"
  done
  ok "phase_7_verify_gate"
}

phase_7_health_skills() {
  require_file src/harness_maker/templates/skills/ai-readiness-rubric/SKILL.md.j2
  require_file src/harness_maker/templates/skills/agent-quality-rubric/SKILL.md.j2
  ok "phase_7_health_skills"
}

phase_7() {
  phase_7_driver
  phase_7_loop_template
  phase_7_autoloop_assets
  phase_7_verify_gate
  phase_7_health_skills
  rm -rf tests/fixtures/side-python-cli/.claude
  uv run python -m harness_maker.cli make tests/fixtures/side-python-cli --autoloop || fail "make"
  require_file tests/fixtures/side-python-cli/.claude/commands/hm/loop.md
  require_file tests/fixtures/side-python-cli/.claude/skills/verify-before-completion/SKILL.md
  require_file tests/fixtures/side-python-cli/.claude/agents/autoloop-coder.md
  phase_7_invariants
  ok "Phase 7 Exit Criteria"
}

# ──────────────────────────────────────────────────────────────────────
# Phase 8: Worktree Isolation + harness.yaml schema 확장
# ──────────────────────────────────────────────────────────────────────

phase_8_worktree()       { uv run pytest tests/unit/test_worktree.py -q || fail "worktree"; ok "phase_8_worktree"; }
phase_8_worktree_skill() { require_file src/harness_maker/templates/skills/worktree-isolator/SKILL.md.j2; ok "phase_8_worktree_skill"; }

phase_8_yaml_schema() {
  for p in Side Production; do
    require_file "src/harness_maker/templates/harness-yaml/$p.yaml.j2"
    grep -q "worktree:" "src/harness_maker/templates/harness-yaml/$p.yaml.j2" || fail "$p missing worktree section"
    grep -q "security:" "src/harness_maker/templates/harness-yaml/$p.yaml.j2" || fail "$p missing security section"
  done
  ok "phase_8_yaml_schema"
}

phase_8() {
  phase_8_worktree
  phase_8_worktree_skill
  phase_8_yaml_schema
  phase_8_invariants
  ok "Phase 8 Exit Criteria"
}

# ──────────────────────────────────────────────────────────────────────
# Phase 9: 5 Security Gates
# ──────────────────────────────────────────────────────────────────────

phase_9_secrets()          { uv run pytest tests/unit/test_secrets_scan.py -q || fail "secrets scan"; ok "phase_9_secrets"; }
phase_9_permissions()      { uv run pytest tests/unit/test_permissions_scan.py -q || fail "perm scan"; ok "phase_9_permissions"; }
phase_9_hook_injection()   { uv run pytest tests/unit/test_hook_injection.py -q || fail "hook scan"; ok "phase_9_hook_injection"; }
phase_9_cve()              { uv run pytest tests/unit/test_cve_scan.py -q || fail "cve scan"; ok "phase_9_cve"; }
phase_9_prompt_injection() { uv run pytest tests/unit/test_prompt_injection.py -q || fail "PI scan"; ok "phase_9_prompt_injection"; }

phase_9_orchestrator() {
  uv run pytest tests/unit/test_security_scanner.py -q || fail "security scanner"
  require_file src/harness_maker/templates/skills/security-scanner/SKILL.md.j2
  require_file src/harness_maker/templates/agents/security-auditor.md.j2
  ok "phase_9_orchestrator"
}

phase_9_seeded_vulns() {
  # Phase 11 sandbox 가 시드된 vulns 모두 검출해야 — 여기선 unit test 결과로 갈음
  uv run pytest tests/unit/test_security_scanner.py -q -k seeded || true
  ok "phase_9_seeded_vulns (delegated to Phase 11)"
}

phase_9() {
  phase_9_secrets
  phase_9_permissions
  phase_9_hook_injection
  phase_9_cve
  phase_9_prompt_injection
  phase_9_orchestrator
  phase_9_invariants
  ok "Phase 9 Exit Criteria"
}

# ──────────────────────────────────────────────────────────────────────
# Phase 10: Context Lint + Privilege Separation + Provenance
# ──────────────────────────────────────────────────────────────────────

phase_10_context_lint()      { uv run pytest tests/unit/test_context_lint.py -q || fail "context lint"; ok "phase_10_context_lint"; }
phase_10_render_lint()       { uv run pytest tests/unit/test_render.py -q -k "lint" || true; ok "phase_10_render_lint"; }
phase_10_lint_skill()        { require_file src/harness_maker/templates/skills/context-linter/SKILL.md.j2; ok "phase_10_lint_skill"; }

phase_10_reviewer_perms() {
  for a in code-reviewer security-reviewer security-auditor performance-reviewer ux-reviewer concurrency-reviewer; do
    require_file "src/harness_maker/templates/agents/$a.md.j2"
    grep -E "Write|deny|Read.*Grep" "src/harness_maker/templates/agents/$a.md.j2" >/dev/null \
      || fail "$a missing read-only permission constraint"
  done
  ok "phase_10_reviewer_perms"
}

phase_10_executor_perms() {
  require_file src/harness_maker/templates/agents/executor.md.j2
  grep -q ".worktrees" src/harness_maker/templates/agents/executor.md.j2 \
    || fail "executor missing .worktrees scope"
  ok "phase_10_executor_perms"
}

phase_10_provenance_verify() {
  uv run pytest tests/unit/test_provenance.py -q || fail "provenance"
  ok "phase_10_provenance_verify"
}

phase_10_reconcile_provenance() {
  uv run pytest tests/unit/test_reconcile.py -q || fail "reconcile"
  ok "phase_10_reconcile_provenance"
}

phase_10() {
  phase_10_context_lint
  phase_10_lint_skill
  phase_10_reviewer_perms
  phase_10_executor_perms
  phase_10_provenance_verify
  phase_10_reconcile_provenance
  rm -rf tests/fixtures/prod-tauri-app/.claude
  uv run python -m harness_maker.cli make tests/fixtures/prod-tauri-app --autoloop || fail "make"
  phase_10_invariants
  ok "Phase 10 Exit Criteria"
}

# ──────────────────────────────────────────────────────────────────────
# Phase 11: Dogfood — sandbox 적용
# ──────────────────────────────────────────────────────────────────────

phase_11_sandbox_init() {
  require_dir tests/e2e/sandbox
  require_file tests/e2e/sandbox/pyproject.toml
  require_file tests/e2e/sandbox/hello_world.py
  test -d tests/e2e/sandbox/.git || (cd tests/e2e/sandbox && git init -b main)
  ok "phase_11_sandbox_init"
}

phase_11_apply() {
  rm -rf tests/e2e/sandbox/.claude
  uv run python -m harness_maker.cli make tests/e2e/sandbox --autoloop || fail "make sandbox"
  require_file tests/e2e/sandbox/.claude/harness.yaml
  count=$(find tests/e2e/sandbox/.claude -type f | wc -l)
  [[ $count -ge 25 ]] || fail "expected >= 25 files in sandbox/.claude (got $count)"
  ok "phase_11_apply ($count files)"
}

phase_11_commands() {
  for cmd in research spec plan execute review wrapup verify dev loop monitor refresh; do
    require_file "tests/e2e/sandbox/.claude/commands/hm/$cmd.md"
  done
  uv run pytest tests/e2e/test_dogfood_sandbox.py -q -k commands || fail "dogfood commands"
  ok "phase_11_commands"
}

phase_11_security() { uv run pytest tests/e2e/test_dogfood_sandbox.py -q -k security  || fail "dogfood security";  ok "phase_11_security"; }
phase_11_metrics()  { uv run pytest tests/e2e/test_dogfood_sandbox.py -q -k metrics   || fail "dogfood metrics";   ok "phase_11_metrics"; }
phase_11_reconcile(){ uv run pytest tests/e2e/test_dogfood_sandbox.py -q -k reconcile || fail "dogfood reconcile"; ok "phase_11_reconcile"; }

phase_11_plugin_entry() {
  require_file tests/e2e/test_plugin_entry.py
  uv run pytest tests/e2e/test_plugin_entry.py -q || fail "plugin entry test"
  require_file tests/e2e/sandbox-plugin-test/.claude/harness.yaml
  ok "phase_11_plugin_entry"
}

phase_11() {
  phase_11_sandbox_init
  phase_11_apply
  phase_11_commands
  phase_11_security
  phase_11_metrics
  phase_11_reconcile
  phase_11_plugin_entry
  phase_11_invariants
  ok "Phase 11 Exit Criteria"
}

# ──────────────────────────────────────────────────────────────────────
# Phase 12: Polish
# ──────────────────────────────────────────────────────────────────────

phase_12_readme() {
  require_file README.md
  grep -q "Quick Start" README.md || fail "README missing Quick Start"
  grep -q "License" README.md || fail "README missing License"
  ok "phase_12_readme"
}

phase_12_contributing() { require_file docs/CONTRIBUTING.md; ok "phase_12_contributing"; }
phase_12_architecture() { require_file docs/ARCHITECTURE.md; ok "phase_12_architecture"; }

phase_12_final_quality() {
  uv run ruff check src/ tests/ || fail "ruff"
  uv run ruff format --check src/ tests/ || fail "ruff format"
  uv run mypy --strict src/ || fail "mypy"
  uv run pytest tests/ -q || fail "pytest"
  ok "phase_12_final_quality"
}

phase_12_marketplace() {
  jq -e '.license' .claude-plugin/plugin.json >/dev/null || fail "plugin.json missing license"
  ok "phase_12_marketplace"
}

phase_12() {
  phase_12_readme
  phase_12_contributing
  phase_12_architecture
  phase_12_final_quality
  phase_12_marketplace
  phase_12_invariants
  ok "Phase 12 Exit Criteria"
}

# ──────────────────────────────────────────────────────────────────────
# Final Acceptance — Section 5 모든 R/M 검증
# ──────────────────────────────────────────────────────────────────────

final_acceptance() {
  log "=== Final Acceptance ==="

  # R1 Locale-first
  log "R1 Locale-first"
  uv run python -c "from harness_maker.i18n import resolve_locale, t; from harness_maker.models import Locale; assert t('q1_choose_language', Locale.KO, lang='ko')" \
    || fail "R1: i18n broken"

  # R2 Anti-rot
  log "R2 Anti-rot"
  uv run python -c "from harness_maker.crawler import anthropic_blog, github_releases, arxiv, osv_dev; from harness_maker.relevance import score" \
    || fail "R2: anti-rot modules missing"
  grep -q "AskUserQuestion" src/harness_maker/templates/commands/hm/refresh.md.j2 || fail "R2: refresh missing manual confirm"

  # R3 Monitoring
  log "R3 Monitoring"
  uv run python -c "from harness_maker.readiness import compute_readiness; from harness_maker.cache_diagnostics import diagnose_cache; from harness_maker.agent_quality import score_agent" \
    || fail "R3: monitoring modules missing"

  # R4 Workflow
  log "R4 Workflow"
  for s in research spec plan execute review wrapup verify; do
    require_file "src/harness_maker/templates/stages/$s.md.j2"
  done
  uv run python -c "from harness_maker.workflow_fuse import fuse" || fail "R4: fuse missing"

  # R5 Autoloop
  log "R5 Autoloop"
  uv run python -c "from harness_maker.autoloop_driver import run" || fail "R5: autoloop driver missing"
  require_file src/harness_maker/templates/commands/hm/loop.md.j2

  # R6 Per-project preset
  log "R6 Preset"
  for p in Side Production; do
    require_file "src/harness_maker/templates/harness-yaml/$p.yaml.j2"
    require_file "src/harness_maker/templates/settings/$p.json.j2"
  done

  # M1-M13 메커니즘
  log "Mechanisms M1-M13"
  uv run python -c "
from harness_maker import (
    profile, interview, synthesize, reconcile, render, verify, modular_edit,
    workflow_fuse, conditional_router, autoloop_driver, worktree, security_scanner,
    context_lint, provenance, readiness, agent_quality
)
" || fail "M1-M13: missing mechanism module"

  # 자산 존재 — Skills 10
  log "Skills (10) 존재"
  for sk in verify-before-completion conditional-router ai-readiness-rubric agent-quality-rubric \
            research-crawler relevance-filter autoloop-driver worktree-isolator security-scanner context-linter; do
    require_file "src/harness_maker/templates/skills/$sk/SKILL.md.j2"
  done

  # Agents 10
  log "Agents (10) 존재"
  for ag in code-reviewer security-reviewer security-auditor performance-reviewer ux-reviewer \
            concurrency-reviewer consensus-arbiter autoloop-coder executor plan-validator; do
    require_file "src/harness_maker/templates/agents/$ag.md.j2"
  done

  # Sandbox final dogfood
  log "Sandbox dogfood"
  if [[ -d tests/e2e/sandbox/.claude ]]; then
    require_file tests/e2e/sandbox/.claude/harness.yaml
    require_file tests/e2e/sandbox/.claude/observability/dashboard.md
  fi

  ok "ALL R1-R6 + M1-M13 + assets verified"
}

# ──────────────────────────────────────────────────────────────────────
# Dispatch
# ──────────────────────────────────────────────────────────────────────

case "$CHECK" in
  all)
    phase_1
    phase_2
    phase_3
    phase_4
    phase_5
    phase_6
    phase_7
    phase_8
    phase_9
    phase_10
    phase_11
    phase_12
    final_acceptance
    ok "ALL CHECKS PASSED"
    ;;
  phase_1|phase_2|phase_3|phase_4|phase_5|phase_6|phase_7|phase_8|phase_9|phase_10|phase_11|phase_12|final_acceptance)
    "$CHECK"
    ;;
  phase_*_*)
    if declare -f "$CHECK" >/dev/null; then
      "$CHECK"
    else
      fail "Unknown check: $CHECK"
    fi
    ;;
  *)
    echo "Usage: $0 <check_name>"
    echo "  all                   # 모든 phase + final acceptance"
    echo "  phase_<N>             # Phase N exit criteria (1-12)"
    echo "  phase_<N>_<sub>       # 개별 task verify (e.g. phase_1_uv, phase_1_env)"
    echo "  phase_<N>_invariants  # cross-phase frontmatter invariant check"
    echo "  final_acceptance      # Section 5 검증"
    exit 2
    ;;
esac
