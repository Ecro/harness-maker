"""Project profiler — derives stack/scale/lifecycle/dotclaude/spec_only/vault signals."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from harness_maker.models import (
    Confidence,
    ProjectProfile,
    ToolchainCommands,
    ToolchainConfig,
)

logger = logging.getLogger(__name__)

SCALE_SMALL_MAX = 50
SCALE_MEDIUM_MAX = 500

IGNORE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    ".worktrees",
    "dist",
    "build",
    "target",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

# Concrete-filename manifests — checked with simple `exists()`. csharp / haskell
# use glob patterns and live in STACK_GLOB_MANIFESTS below.
STACK_MANIFESTS: dict[str, list[str]] = {
    "python": ["pyproject.toml", "requirements.txt", "setup.py"],
    "node": ["package.json"],
    "rust": ["Cargo.toml"],
    "cmake": ["CMakeLists.txt"],
    "go": ["go.mod"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
    "kotlin": ["build.gradle.kts"],
    "swift": ["Package.swift"],
    "dart": ["pubspec.yaml"],
    "ruby": ["Gemfile"],
    "php": ["composer.json"],
    "elixir": ["mix.exs"],
    "scala": ["build.sbt"],
    "c-cpp": ["CMakeLists.txt", "Makefile", "meson.build"],
    "zig": ["build.zig"],
}

# Glob-pattern manifests — matched via Path.glob at the repo root.
STACK_GLOB_MANIFESTS: dict[str, list[str]] = {
    "csharp": ["*.csproj", "*.sln"],
    "haskell": ["package.yaml", "*.cabal", "stack.yaml"],
}

# Dependency names that flag well-known frameworks per stack. Matched
# case-insensitively against dep keys; presence-only — versions ignored.
_PY_FRAMEWORKS: tuple[str, ...] = (
    "fastapi",
    "django",
    "flask",
    "streamlit",
    "jupyter",
    "zephyr-python",
    "pytest",
    "httpx",
    "pydantic",
)
_NODE_FRAMEWORKS: tuple[str, ...] = (
    "react",
    "vue",
    "svelte",
    "next",
    "remix",
    "astro",
    "express",
    "nestjs",
    "fastify",
    "vite",
)
_RUST_FRAMEWORKS: tuple[str, ...] = (
    "tauri",
    "axum",
    "tokio",
    "bevy",
    "actix-web",
)


def profile(project_dir: Path, cache_dir: Path | None = None) -> ProjectProfile:
    """Inspect ``project_dir`` and return a ProjectProfile of detected signals.

    Phase 2 wired the detection_cache — a fresh cached result short-circuits
    the live filesystem scan. ``cache_dir`` is forwarded so tests can isolate
    from the shared ``~/.cache/harness-maker/`` location.
    """
    # Lazy import — detection_cache imports STACK_MANIFESTS from this module.
    from harness_maker import detection_cache

    cached = detection_cache.load_or_run(project_dir, cache_dir=cache_dir)
    if cached is not None:
        return cached

    # (a) stack
    stack: list[str] = []
    for stack_name, manifests in STACK_MANIFESTS.items():
        if any((project_dir / m).exists() for m in manifests):
            stack.append(stack_name)
    for stack_name, patterns in STACK_GLOB_MANIFESTS.items():
        if any(_glob_match_root(project_dir, p) for p in patterns):
            stack.append(stack_name)
    if not stack:
        stack = ["unknown"]

    # (b) scale — count files excluding ignore dirs
    file_count = _count_tracked_files(project_dir)
    if file_count < SCALE_SMALL_MAX:
        scale = "small"
    elif file_count <= SCALE_MEDIUM_MAX:
        scale = "medium"
    else:
        scale = "large"

    # (c) lifecycle — git commit count last 30 days
    lifecycle = _detect_lifecycle(project_dir)

    # (d) existing_dotclaude
    existing_dotclaude = (project_dir / ".claude").is_dir()

    # (e) spec_only — TECH_SPEC.md exists + ≤5 files (assumed scaffolding only)
    spec_only = (project_dir / "TECH_SPEC.md").exists() and file_count <= 5

    # (f) vault_member
    vault_member = (project_dir / ".claude" / "obsidian.json").exists()

    detected_checks = _detect_mechanical_checks(project_dir)

    # Phase 3 enrichments — order matters: framework detection peeks at the
    # manifests so stack must already be resolved.
    frameworks = _detect_frameworks(project_dir, stack)
    package_manager = _detect_package_manager(project_dir, stack)
    ci_provider = _detect_ci_provider(project_dir)

    detection_confidence = _build_detection_confidence(
        stack=stack,
        frameworks=frameworks,
        package_manager=package_manager,
        ci_provider=ci_provider,
    )

    result = ProjectProfile(
        stack=stack,
        scale=scale,
        lifecycle=lifecycle,
        existing_dotclaude=existing_dotclaude,
        spec_only=spec_only,
        vault_member=vault_member,
        detected_checks=detected_checks,
        frameworks=frameworks,
        package_manager=package_manager,
        ci_provider=ci_provider,
        # Phase 5 owns foreign-AI-config detection; intentionally empty here so
        # downstream consumers don't double-detect or race ordering.
        foreign_ai_configs=[],
        detection_confidence=detection_confidence,
    )

    detection_cache.write(result, project_dir, cache_dir=cache_dir)
    return result


def _glob_match_root(project_dir: Path, pattern: str) -> bool:
    """Return True iff at least one file at the repo root matches ``pattern``."""
    try:
        return next(project_dir.glob(pattern), None) is not None
    except OSError:
        return False


def detect_toolchains(project_dir: Path) -> list[ToolchainConfig]:
    """Toolchain groups for `harness.yaml.toolchains`, seeded at make time (ADR-007).

    Detection supplies **stack identity and package-manager choice only**; the command
    templates come from the static table below. Reusing `_detect_mechanical_checks`' strings
    was the obvious design and it is wrong: every command it emits is repo-wide with no path
    argument (`uv run ruff check .`, `cargo test`, `{runner} run {key}`). Under the oracle's
    `{path}` contract a template without the placeholder runs once per gather and its output
    is emitted UNLABELLED — so a harness seeded that way yields zero per-finding evidence, for
    Python as much as for Node, while the coverage warning stays silent because the command
    set is non-empty and the paths are covered.

    Node uses `npx --no-install <bin>`, never `<runner> <bin>`. `_detect_mechanical_checks`
    falls back to `npm` when neither a pnpm nor a yarn lockfile is present — the most common
    Node repo — and `npm vitest run x` is not a valid command (npm exposes no such subcommand;
    binaries need `npx` / `npm exec --`). It would exit non-zero without ever parsing the
    subject and, because it carries `{path}`, be emitted id-labelled: fabricated evidence, the
    exact shape the extension gate exists to remove. `--no-install` additionally stops a
    missing package from being fetched from the network mid-review.

    Each Node role is gated on its tool appearing in `devDependencies`. Seeding already parses
    `package.json`, so this is nearly free and converts a guess into a fact: a repo on `jest`
    or `biome` gets **no entry for that role** rather than a wrong command. An absent role
    routes to `no_oracle` with a visible reason — honest degradation; a wrong command is not.
    """
    groups: list[ToolchainConfig] = []

    # Python roles are gated on EVIDENCE, exactly as the Node roles are. Seeding on
    # `pyproject.toml` presence alone is the false positive `_detect_mechanical_checks`'
    # own docstring already records as measured harm: "psf/requests reality-check showed
    # `uv run ruff check .` emitted on a repo that uses neither uv nor configures ruff".
    # On a poetry/pip/hatch repo an ungated `uv run …` yields FileNotFoundError or a sync
    # error at non-zero exit — which the verifier rubric correctly reads as an ABSENT
    # oracle, so every finding degrades to `unresolved` while the coverage warning stays
    # silent, because labelled blocks ARE being produced. They just contain no evidence.
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            py_content = pyproject.read_text(encoding="utf-8")
        except OSError:
            py_content = ""
        # `uv run` only makes sense when the project is actually uv-managed.
        uses_uv = (project_dir / "uv.lock").exists() or "[tool.uv]" in py_content
        prefix = "uv run " if uses_uv else ""
        py_commands = ToolchainCommands(
            test=f"{prefix}pytest -q {{path}}"
            if ("[tool.pytest.ini_options]" in py_content or "[tool.pytest." in py_content)
            else None,
            lint=f"{prefix}ruff check {{path}}"
            if ("[tool.ruff]" in py_content or "[tool.ruff." in py_content)
            else None,
            types=f"{prefix}mypy {{path}}" if "[tool.mypy]" in py_content else None,
        )
        if py_commands.declared():
            groups.append(
                ToolchainConfig(name="python", extensions=[".py", ".pyi"], commands=py_commands)
            )

    pkgjson = project_dir / "package.json"
    if pkgjson.exists():
        try:
            data = json.loads(pkgjson.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        # devDependencies ONLY, matching the documented policy. Unioning production
        # `dependencies` made a runtime package named `typescript` / `eslint` / `vitest`
        # read as an explicitly configured development check and seed a command for it.
        dev = data.get("devDependencies", {}) if isinstance(data, dict) else {}
        present = set(dev) if isinstance(dev, dict) else set()
        commands = ToolchainCommands(
            test="npx --no-install vitest run {path}" if "vitest" in present else None,
            lint="npx --no-install eslint {path}" if "eslint" in present else None,
            types="npx --no-install tsc --noEmit" if "typescript" in present else None,
        )
        if commands.declared():
            groups.append(
                ToolchainConfig(
                    name="node",
                    extensions=[".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"],
                    commands=commands,
                )
            )

    if (project_dir / "Cargo.toml").exists():
        # cargo takes a name filter, not a path, so these are legitimately repo-wide. A Rust
        # project therefore gets unlabelled project-wide context and no per-finding evidence —
        # a stated limitation, not a defect. The alternative is a fabricated `cargo test
        # <path>`, which is the bug under repair. The AC-011 warning fires on this shape
        # precisely because its trigger is an output property, not a config property.
        groups.append(
            ToolchainConfig(
                name="rust",
                extensions=[".rs"],
                commands=ToolchainCommands(test="cargo test", lint="cargo clippy"),
            )
        )

    return groups


def toolchains_key_present(project_dir: Path) -> bool:
    """Whether `harness.yaml` carries a `toolchains` key at all, however malformed.

    `answers_from_harness_yaml` cannot answer this: it drops an unusable value and returns the
    field's default, so "the user wrote something we could not parse" and "the user wrote
    nothing" arrive identically. That collapse is what let seeding overwrite a hand-edited
    block — the user-state destruction CLAUDE.md checkpoint 1 exists to prevent, and it also
    defeated the oracle's fail-closed-on-unusable contract across a single re-render.
    """
    path = project_dir / ".claude" / "harness.yaml"
    if not path.exists():
        return False
    try:
        from harness_maker.io_utils import load_harness_yaml

        return "toolchains" in load_harness_yaml(path)
    except Exception:  # noqa: BLE001 — an unreadable file is not evidence of absence
        return True


def seed_toolchains(existing: list[ToolchainConfig], project_dir: Path) -> list[ToolchainConfig]:
    """Fill-if-empty (ADR-007). A user-authored value is never touched — valid OR not.

    Matches CLAUDE.md checkpoint 1 (default = preserve user state) and how
    `reviewers.mechanical_checks` already survives re-render. Detection yielding nothing leaves
    the key absent rather than writing an empty list, so the absent-case default (ADR-006)
    stays distinguishable from a deliberate empty one.

    An empty `existing` is NOT sufficient evidence of absence, which is why the key-presence
    probe is here: a malformed block parses to `[]` on the way in, so seeding over it would
    replace the user's text with detected defaults and silently resume running checks they
    never configured.
    """
    if existing or toolchains_key_present(project_dir):
        return list(existing)
    return detect_toolchains(project_dir)


def _detect_mechanical_checks(project_dir: Path) -> list[str]:
    """Detect runnable checks per ADR-007 (manifest-explicit OR command-pattern whitelist).

    Conservative policy — emit only commands that the manifest signals are
    actually configured (not just dependency-listed) OR commands tied to a
    standard target where presence of the manifest proves the toolchain.
    The prior version's bare `"mypy" in content` / `"pytest" in content`
    string-match produced false positives (e.g. psf/requests reality-check
    showed `uv run ruff check .` emitted on a repo that uses neither uv
    nor configures ruff — only dep-listed pytest at all). v0.22.0 replaces
    that with strict-block matching + per-stack whitelists.
    """
    checks: list[str] = []

    # Python — manifest-explicit only ([tool.X] blocks, not dep mentions).
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
        except OSError:
            content = ""
        if "[tool.ruff]" in content or "[tool.ruff." in content:
            checks.append("uv run ruff check .")
        if "[tool.mypy]" in content:
            checks.append("uv run mypy .")
        if "[tool.pytest.ini_options]" in content or "[tool.pytest." in content:
            checks.append("uv run pytest --tb=short -q")

    # Rust — Cargo standard whitelist (presence of Cargo.toml proves the commands work).
    if (project_dir / "Cargo.toml").exists():
        checks.extend(["cargo test", "cargo clippy", "cargo fmt --check"])

    # Node — package.json scripts whitelist, runner picked by lockfile.
    pkgjson = project_dir / "package.json"
    if pkgjson.exists():
        try:
            data = json.loads(pkgjson.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
        if (project_dir / "pnpm-lock.yaml").exists():
            runner = "pnpm"
        elif (project_dir / "yarn.lock").exists():
            runner = "yarn"
        else:
            runner = "npm"
        for key in ("test", "lint", "check", "typecheck", "format", "build"):
            if isinstance(scripts, dict) and key in scripts:
                checks.append(f"{runner} run {key}")

    # Makefile — target whitelist.
    makefile = project_dir / "Makefile"
    if makefile.exists():
        try:
            content = makefile.read_text(encoding="utf-8")
        except OSError:
            content = ""
        for line in content.splitlines():
            line_stripped = line.strip()
            for target in ("test", "lint", "check", "typecheck", "format", "build"):
                if line_stripped.startswith(f"{target}:"):
                    checks.append(f"make {target}")
                    break

    # Deduplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for c in checks:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out[:6]


def _count_tracked_files(project_dir: Path) -> int:
    """Count tracked files via git ls-files if non-zero; otherwise os.walk excluding IGNORE_DIRS."""
    if (project_dir / ".git").exists():
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        else:
            tracked = len(result.stdout.splitlines())
            if tracked > 0:
                return tracked
            # git ls-files returned 0 → either fixture inside a parent repo with no
            # tracked files in this subtree, or empty repo. Fall through to os.walk.
    count = 0
    for root, dirs, files in os.walk(project_dir):  # noqa: B007
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        count += len(files)
    return count


def _detect_lifecycle(project_dir: Path) -> str:
    """3-tier classifier per ADR-006.

    Buckets: active (>=10 commits/30d) | maintenance (1-9/30d) | dormant (0/30d).
    Replaces the prior 4-tier algorithm which conflated "no .git", "git error",
    and "zero recent commits" under "experiment" — too vague for user-facing
    output (reality-check showed BurntSushi/ripgrep mis-classified). The label
    "experiment" was removed entirely in v0.22.0. Missing .git or subprocess
    failure now degrade to "dormant" (the most conservative bucket — same
    downstream SIDE-preset routing as the old "experiment" label, but with
    honest semantics).
    """
    if not (project_dir / ".git").exists():
        return "dormant"
    try:
        result = subprocess.run(
            ["git", "log", "--since=30.days.ago", "--oneline"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return "dormant"
    commit_count = len(result.stdout.splitlines())
    if commit_count == 0:
        return "dormant"
    if commit_count < 10:
        return "maintenance"
    return "active"


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 — framework / package_manager / ci_provider detection
# ─────────────────────────────────────────────────────────────────────────────


def _detect_frameworks(project_dir: Path, stack: list[str]) -> list[str]:
    """Parse manifests of detected stacks and collect known framework dep names.

    Result is de-duplicated while preserving first-seen order — Python deps
    are scanned before Node, Node before Rust, matching the package_manager
    precedence so audit consumers see a stable ordering.
    """
    found: list[str] = []

    def _add(name: str) -> None:
        if name not in found:
            found.append(name)

    if "python" in stack:
        for dep in _read_python_deps(project_dir):
            low = dep.lower()
            for fw in _PY_FRAMEWORKS:
                if low == fw or low.startswith(f"{fw}["):
                    _add(fw)
    if "node" in stack:
        for dep in _read_node_deps(project_dir):
            low = dep.lower()
            for fw in _NODE_FRAMEWORKS:
                # npm scoped packages: `@nestjs/core`, `@remix-run/node` carry
                # the framework identity in the scope segment. Require the
                # leading `@` so unscoped lookalikes (e.g. `nestjs-helper`)
                # never false-positive.
                if low == fw or low.startswith(f"@{fw}/") or low.startswith(f"@{fw}-"):
                    _add(fw)
    if "rust" in stack:
        for dep in _read_rust_deps(project_dir):
            low = dep.lower()
            for fw in _RUST_FRAMEWORKS:
                if low == fw:
                    _add(fw)

    return found


def _read_python_deps(project_dir: Path) -> list[str]:
    """Extract dep names (no version specifiers) from pyproject.toml.

    Reads PEP 621 ``[project.dependencies]`` (list) and the Poetry-flavoured
    ``[tool.poetry.dependencies]`` (table). Names normalized: lowercased,
    extras-stripped, version-stripped.
    """
    pyproject = project_dir / "pyproject.toml"
    if not pyproject.exists():
        return []
    try:
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        logger.debug("profile: pyproject.toml unreadable: %s", exc)
        return []

    deps: list[str] = []

    project_table = data.get("project")
    if isinstance(project_table, dict):
        for raw in project_table.get("dependencies", []) or []:
            if isinstance(raw, str):
                deps.append(_strip_dep_spec(raw))

    tool = data.get("tool")
    if isinstance(tool, dict):
        poetry = tool.get("poetry")
        if isinstance(poetry, dict):
            poetry_deps = poetry.get("dependencies")
            if isinstance(poetry_deps, dict):
                for key in poetry_deps:
                    if isinstance(key, str) and key.lower() != "python":
                        deps.append(_strip_dep_spec(key))

    return deps


def _strip_dep_spec(raw: str) -> str:
    """Return the bare dep name from a PEP 508-ish dependency string."""
    # Split off any extras / version specifiers / environment markers.
    name = raw.strip()
    for sep in ("[", ";", " ", "=", "<", ">", "!", "~"):
        idx = name.find(sep)
        if idx != -1:
            name = name[:idx]
    return name.strip()


def _read_node_deps(project_dir: Path) -> list[str]:
    """Read dep keys from package.json (dependencies + devDependencies)."""
    pkg = project_dir / "package.json"
    if not pkg.exists():
        return []
    try:
        with pkg.open("r", encoding="utf-8") as f:
            data: Any = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("profile: package.json unreadable: %s", exc)
        return []
    if not isinstance(data, dict):
        return []
    out: list[str] = []
    for section in ("dependencies", "devDependencies"):
        block = data.get(section)
        if isinstance(block, dict):
            out.extend(str(k) for k in block)
    return out


def _read_rust_deps(project_dir: Path) -> list[str]:
    """Read dep keys from Cargo.toml `[dependencies]` table."""
    cargo = project_dir / "Cargo.toml"
    if not cargo.exists():
        return []
    try:
        with cargo.open("rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        logger.debug("profile: Cargo.toml unreadable: %s", exc)
        return []
    deps_section = data.get("dependencies")
    if isinstance(deps_section, dict):
        return [str(k) for k in deps_section]
    return []


def _detect_package_manager(project_dir: Path, stack: list[str]) -> str:
    """Pick a lockfile-backed package manager. Single string per PLAN.

    Monorepo precedence: python > node > rust > other. For each chosen stack,
    pick the most specific lockfile first (e.g. node: bun > pnpm > yarn > npm).
    """
    # The order of stack-probes defines the cross-stack tie-break.
    if "python" in stack:
        pm = _python_package_manager(project_dir)
        if pm:
            return pm
    if "node" in stack:
        pm = _node_package_manager(project_dir)
        if pm:
            return pm
    if "rust" in stack:
        pm = _rust_package_manager(project_dir)
        if pm:
            return pm
    return ""


def _python_package_manager(project_dir: Path) -> str:
    if (project_dir / "uv.lock").exists():
        return "uv"
    if (project_dir / "poetry.lock").exists():
        return "poetry"
    if (project_dir / "Pipfile.lock").exists():
        return "pipenv"
    if (project_dir / "requirements.txt").exists():
        return "pip"
    # ADR-007 manifest-fallback exception (lower-stakes documentation hint):
    # pyproject.toml without a lockfile still narrows down the package manager
    # by header inspection. requests/fastify reality-check failed without this.
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
        except OSError:
            content = ""
        if "[tool.uv]" in content or "[tool.uv." in content:
            return "uv"
        if "[tool.poetry]" in content or "[tool.poetry." in content:
            return "poetry"
        return "pip"
    return ""


def _node_package_manager(project_dir: Path) -> str:
    # Bun 1.1+ uses bun.lock (TOML text format) alongside the legacy
    # bun.lockb binary form. Accept either as a bun signal.
    if (project_dir / "bun.lockb").exists() or (project_dir / "bun.lock").exists():
        return "bun"
    if (project_dir / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (project_dir / "yarn.lock").exists():
        return "yarn"
    if (project_dir / "package-lock.json").exists():
        return "npm"
    # ADR-007 manifest-fallback exception: package.json without lockfile
    # narrows to npm as the default tooling.
    if (project_dir / "package.json").exists():
        return "npm"
    return ""


def _rust_package_manager(project_dir: Path) -> str:
    if (project_dir / "Cargo.lock").exists():
        return "cargo"
    return ""


def _detect_ci_provider(project_dir: Path) -> str:
    """Pick the first CI provider whose signature file/dir exists."""
    gh_workflows = project_dir / ".github" / "workflows"
    if gh_workflows.is_dir():
        for entry in gh_workflows.iterdir():
            if entry.is_file() and entry.suffix in {".yml", ".yaml"}:
                return "github-actions"
    if (project_dir / ".gitlab-ci.yml").exists():
        return "gitlab-ci"
    if (project_dir / ".circleci" / "config.yml").exists():
        return "circleci"
    if (project_dir / "Jenkinsfile").exists():
        return "jenkins"
    if (project_dir / ".travis.yml").exists():
        return "travis"
    return ""


def _build_detection_confidence(
    *,
    stack: list[str],
    frameworks: list[str],
    package_manager: str,
    ci_provider: str,
) -> dict[str, Confidence]:
    """Per-detection HIGH/LOW heuristic per ADR-007.

    HIGH = explicit manifest / lockfile / dotfile match; LOW = nothing
    detected. MEDIUM is reserved for genuinely inferred signals (e.g. dep
    name mapping to opinion) — Phase 3 does presence-only so frameworks
    are HIGH on any match.
    """
    stack_conf = Confidence.HIGH if stack and stack != ["unknown"] else Confidence.LOW
    fw_conf = Confidence.HIGH if frameworks else Confidence.LOW
    pm_conf = Confidence.HIGH if package_manager else Confidence.LOW
    ci_conf = Confidence.HIGH if ci_provider else Confidence.LOW

    return {
        "stack": stack_conf,
        "frameworks": fw_conf,
        "package_manager": pm_conf,
        "ci_provider": ci_conf,
    }
