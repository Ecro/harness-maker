# Release checklist — harness-maker

Step-by-step runbook for shipping a new version of `harness-maker` to TestPyPI and PyPI via the
`.github/workflows/release.yml` Trusted Publishing workflow.

> Audience: maintainers cutting a release. Audit trail for everyone else.

---

## Phase 0 — one-time prerequisites (done by maintainer outside CI)

Performed once when the package is first published. Re-verify the values periodically.

### 0.1 PyPI / TestPyPI accounts

- [ ] PyPI account exists with **2FA enabled** (https://pypi.org/account/login/)
- [ ] TestPyPI account exists with **2FA enabled** (https://test.pypi.org/account/login/)

### 0.2 GitHub environments

Create two environments under `Settings → Environments` in the `Ecro/harness-maker` repository:

| Environment | Optional protections |
|-------------|---------------------|
| `testpypi`  | none required |
| `pypi`      | **Required reviewers** recommended — guards against accidental publish |

### 0.3 Trusted Publishers (Pending)

PyPI's "Pending Publisher" model registers the publisher before the project exists; the first
successful workflow run creates the project automatically.

**On TestPyPI** (https://test.pypi.org/manage/account/publishing/, add pending publisher):

| Field              | Value              |
|--------------------|--------------------|
| PyPI Project Name  | `harness-maker`    |
| Owner              | `Ecro`             |
| Repository name    | `harness-maker`    |
| Workflow name      | `release.yml`      |
| Environment name   | `testpypi`         |

**On PyPI** (https://pypi.org/manage/account/publishing/, add pending publisher):

| Field              | Value              |
|--------------------|--------------------|
| PyPI Project Name  | `harness-maker`    |
| Owner              | `Ecro`             |
| Repository name    | `harness-maker`    |
| Workflow name      | `release.yml`      |
| Environment name   | `pypi`             |

> The `Workflow name` field is the filename only (`release.yml`), not the path.

### 0.4 Verification

- [ ] `test.pypi.org/manage/account/publishing/` lists `harness-maker` under pending publishers.
- [ ] `pypi.org/manage/account/publishing/` lists `harness-maker` under pending publishers.
- [ ] `github.com/Ecro/harness-maker/settings/environments` shows both `testpypi` and `pypi`.

---

## Phase 1 — preflight (per release, locally)

Run from `main` after the version-bump commit is merged.

```bash
# 5-file version sync — every file must match
grep -H 'version\|__version__' \
    pyproject.toml \
    src/harness_maker/__init__.py \
    .claude-plugin/plugin.json \
    .cursor-plugin/plugin.json \
    .codex-plugin/plugin.json

# Full check suite
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src
uv run pytest -q

# Artifact regression test
uv run pytest tests/unit/test_package_artifacts.py -v

# End-to-end smoke (build + venv install + CLI exercise)
uv run python scripts/release_smoke.py
```

All commands must exit 0. If `release_smoke.py` fails, stop — `release.yml` will hit the same
failure inside CI and waste time.

---

## Phase 2 — tag and push

```bash
# Replace 0.14.0 with the actual version you are releasing
VERSION=0.14.0
git tag -a "v${VERSION}" -m "v${VERSION}"
git push origin "v${VERSION}"
```

The `v*` tag push triggers `.github/workflows/release.yml`. Watch the run at
`https://github.com/Ecro/harness-maker/actions`.

---

## Phase 3 — observe the workflow

The workflow has five jobs that run in sequence:

1. **`quality-gate`** — ruff/mypy/pytest defense-in-depth for the tag event.
2. **`build`** — `uv build` writes `dist/*.whl` + `dist/*.tar.gz` and uploads them as a workflow artifact.
3. **`publish-testpypi`** (environment: `testpypi`) — `uv publish --trusted-publishing always` to TestPyPI, then installs the published package from `test.pypi.org` and runs `harness-maker --help`.
4. **`publish-pypi`** (environment: `pypi`, `needs: publish-testpypi`) — same OIDC publish to production PyPI.
5. **`github-release`** — creates the GitHub Release with `dist/*` assets and notes extracted from `CHANGELOG.md`.

If `pypi` has a required reviewer, the workflow pauses between TestPyPI smoke and PyPI publish for
manual approval.

---

## Phase 4 — post-release verification

```bash
# PyPI page exists with the right files
open https://pypi.org/project/harness-maker/  # macOS  (or use any browser)

# Production install smoke from a clean machine
uv tool uninstall harness-maker || true
uv tool install harness-maker
harness-maker --version
harness-maker --help

# GitHub Release exists with dist/* attached
gh release view "v${VERSION}"
```

- [ ] `pypi.org/project/harness-maker/` shows the new version.
- [ ] `uv tool install harness-maker` succeeds.
- [ ] `harness-maker --version` prints the released version.
- [ ] GitHub Release page has wheel + sdist attached and release notes from CHANGELOG.

---

## Phase 5 — yank and re-issue (only if a bad release ships)

PyPI does not support replacing a file for the same version. When a defective version lands:

1. **Yank** the release on PyPI (Project → Manage → Releases → click version → "Yank release").
   Confirm at `https://pypi.org/project/harness-maker/`; the version is hidden from
   `pip install harness-maker` resolution but stays in the index history.
2. **Fix forward**: bump the patch version (e.g. `0.14.0 → 0.14.1`) per the 5-file version sync
   policy in CLAUDE.md §버전업 정책.
3. **Re-run** Phases 1 and 2 with the new version.
4. Document the yank reason in `CHANGELOG.md` under the yanked version line.

The yanked version number is never reused (ADR-009).

---

## Trusted Publisher subject — quick reference

If the workflow fails with "untrusted publisher", verify all five fields match exactly between
PyPI/TestPyPI registration and the GitHub Actions OIDC token:

| Field          | Value (TestPyPI)         | Value (PyPI)              |
|----------------|--------------------------|---------------------------|
| Project name   | `harness-maker`          | `harness-maker`           |
| Owner          | `Ecro`                   | `Ecro`                    |
| Repo name      | `harness-maker`          | `harness-maker`           |
| Workflow name  | `release.yml`            | `release.yml`             |
| Environment    | `testpypi`               | `pypi`                    |

Each publish job in `release.yml` echoes its expected subject before running `uv publish` — check
the `Show Trusted Publisher subject (for audit)` step in the run logs for the actual values.
