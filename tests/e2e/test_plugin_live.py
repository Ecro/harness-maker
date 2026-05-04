"""Live plugin e2e — run /harness-maker:make via the real claude binary.

Uses two isolation strategies:
- --setting-sources project,local (method 2): skips user-global
  ~/.claude/settings.json so no user-level prompts fire. OAuth/keychain
  auth still works — it is not read from settings.json.
- --ci flag (method 3): embedded in the prompt so the make command skips
  all AskUserQuestion calls and uses the supplied inline params directly.

These tests require the `claude` binary in PATH. `--plugin-dir` loads
harness-maker from the repo without a prior `claude /plugin install`.

Run:
    pytest tests/e2e/test_plugin_live.py -v
    LIVE=1 pytest tests/e2e/test_plugin_live.py -v   # force re-run
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _claude_available() -> bool:
    return shutil.which("claude") is not None


def _run_make(
    project: Path,
    *,
    preset: str = "Side",
    locale: str = "en",
    dev_mode: str = "task",
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    prompt = f"/harness-maker:make --ci preset={preset} locale={locale} dev_mode={dev_mode}"
    return subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--plugin-dir",
            str(REPO_ROOT),
            "--dangerously-skip-permissions",
            "--setting-sources",
            "project,local",  # skip user-global settings.json; auth still works
            "--output-format",
            "text",
            "--no-session-persistence",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fresh_project(tmp_path: Path) -> Path:
    """Minimal Python project with a git repo — matches the fresh-install path."""
    proj = tmp_path / "myproject"
    proj.mkdir()
    (proj / "pyproject.toml").write_text(
        '[project]\nname = "myproject"\nversion = "0.1.0"\nrequires-python = ">=3.12"\n',
        encoding="utf-8",
    )
    (proj / "main.py").write_text('def main() -> None:\n    print("hello")\n', encoding="utf-8")
    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@test.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@test.com",
    }
    subprocess.run(["git", "init", "-b", "main"], cwd=proj, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=proj, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed"], cwd=proj, check=True, capture_output=True, env=git_env
    )
    return proj


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _claude_available(), reason="claude binary not in PATH")
def test_make_fresh_install_creates_harness_yaml(fresh_project: Path) -> None:
    """Fresh /harness-maker:make --ci must produce .claude/harness.yaml."""
    cp = _run_make(fresh_project)
    assert cp.returncode == 0, (
        f"make returned rc={cp.returncode}\nstdout={cp.stdout[:800]}\nstderr={cp.stderr[:400]}"
    )
    assert (fresh_project / ".claude" / "harness.yaml").is_file(), (
        f"harness.yaml not found after make\nstdout={cp.stdout[:500]}"
    )


@pytest.mark.skipif(not _claude_available(), reason="claude binary not in PATH")
def test_make_fresh_install_file_count(fresh_project: Path) -> None:
    """Fresh install must produce at least 25 files under .claude/."""
    cp = _run_make(fresh_project)
    assert cp.returncode == 0, f"make failed: rc={cp.returncode} stderr={cp.stderr[:400]}"
    files = [f for f in (fresh_project / ".claude").rglob("*") if f.is_file()]
    assert len(files) >= 25, f"expected ≥25 files, got {len(files)}: {[f.name for f in files]}"


@pytest.mark.skipif(not _claude_available(), reason="claude binary not in PATH")
def test_make_production_preset(fresh_project: Path) -> None:
    """Production preset must write preset=Production into harness.yaml."""
    import yaml

    cp = _run_make(fresh_project, preset="Production", dev_mode="spec")
    assert cp.returncode == 0, f"make failed: rc={cp.returncode}"
    text = (fresh_project / ".claude" / "harness.yaml").read_text(encoding="utf-8")
    # harness.yaml is multi-document YAML (frontmatter + body); the body doc has preset.
    docs = list(yaml.safe_load_all(text))
    body = next((d for d in docs if isinstance(d, dict) and "preset" in d), None)
    assert body is not None, f"no body document with 'preset' in harness.yaml: {docs}"
    assert body.get("preset") == "Production", f"unexpected preset: {body}"


@pytest.mark.skipif(not _claude_available(), reason="claude binary not in PATH")
def test_make_no_interactive_prompts(fresh_project: Path) -> None:
    """With --ci, the session must complete without hanging on AskUserQuestion."""
    cp = _run_make(fresh_project, timeout=60)
    # AskUserQuestion hang → subprocess timeout (raises); error → rc != 0.
    assert cp.returncode == 0, (
        f"session hung or errored (rc={cp.returncode}); likely AskUserQuestion blocked\n"
        f"stderr={cp.stderr[:400]}"
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
