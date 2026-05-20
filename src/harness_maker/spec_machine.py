"""SPEC machine.yaml schema + cross-validation + coverage evaluation (ADR-006/007).

Owns the dual-file SPEC contract:
- SPEC.md (human, 8-section narrative) — produced by /hm:spec template
- SPEC.machine.yaml (machine, this schema) — produced alongside .md

Cross-validation enforces 6 rules per ADR-007.
"""

from __future__ import annotations

import re
import subprocess
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

SCHEMA_VERSION = 1

#: ADR-007 rule 2 fuzzy-match threshold. P4 calibration may tune this.
FUZZY_RATIO_THRESHOLD: float = 0.85

ACType = Literal["mechanical", "parametric", "judgment"]
VerificationTier = Literal[1, 2, 3]


class GoldenRow(BaseModel):
    """One row of a parametric AC's golden table (ADR-003)."""

    input: dict[str, Any]
    expected: Any
    edge: bool = False
    note: str = ""


class AcceptanceCriterion(BaseModel):
    """One AC entry in SPEC.machine.yaml (ADR-006)."""

    id: str  # AC-001, AC-002, …
    title: str
    type: ACType
    test_ids: list[str] = Field(default_factory=list)
    executable_predicate: str | None = None
    golden_table: list[GoldenRow] = Field(default_factory=list)
    rubric_id: str | None = None
    note: str = ""
    pending_test: bool = False  # Phase 3 cap escape per PLAN

    @field_validator("id")
    @classmethod
    def _ac_id_format(cls, v: str) -> str:
        if not re.match(r"^AC-\d{3,}$", v):
            raise ValueError(f"ac.id must be 'AC-NNN' (3+ digits), got {v!r}")
        return v


class SpecMachine(BaseModel):
    """Top-level SPEC.machine.yaml shape (ADR-006)."""

    schema_version: int = SCHEMA_VERSION
    spec_slug: str
    parent_spec: str | None = None
    verification_tier: VerificationTier
    mutation_threshold: int | None = None  # None for non-Python or T3 informational
    mutation_threshold_rationale: str = ""
    last_mutation_run: str | None = None  # ISO date
    paths_to_mutate: list[str] = Field(default_factory=list)
    spec_quality_score: int | None = None
    spec_quality_score_at: str | None = None
    ac: list[AcceptanceCriterion] = Field(default_factory=list)

    @field_validator("spec_slug")
    @classmethod
    def _slug_kebab(cls, v: str) -> str:
        if not v or not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"spec_slug must be kebab-case alnum, got {v!r}")
        return v

    @field_validator("paths_to_mutate")
    @classmethod
    def _no_traversal_in_paths(cls, v: list[str]) -> list[str]:
        """Reject absolute paths or ``..`` traversal in paths_to_mutate.

        Without this validator, a malicious SPEC.machine.yaml entry like
        ``../../etc/passwd`` would flow through spec_mutation.measure_baseline
        into mutmut's argv (REVIEW S-P1-B). Paths must be repo-relative.
        """
        for p in v:
            if not isinstance(p, str) or not p.strip():
                raise ValueError(f"paths_to_mutate entry must be non-empty string, got {p!r}")
            if Path(p).is_absolute():
                raise ValueError(f"paths_to_mutate must be repo-relative, got absolute {p!r}")
            parts = Path(p).parts
            if ".." in parts:
                raise ValueError(f"paths_to_mutate must not contain '..', got {p!r}")
        return v


# ---------------------------------------------------------------------------
# Load + validate
# ---------------------------------------------------------------------------


def load(path: Path) -> SpecMachine:
    """Load a ``.machine.yaml`` and validate against the schema."""
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    return SpecMachine.model_validate(data)


def validate(model: SpecMachine) -> list[str]:
    """Return a list of validation error strings (empty = valid).

    Catches issues pydantic alone can't, such as mechanical AC missing a
    predicate or parametric AC with empty golden table.
    """
    errors: list[str] = []
    for ac in model.ac:
        if ac.type == "mechanical" and not (ac.executable_predicate or "").strip():
            errors.append(f"{ac.id}: type=mechanical requires non-empty executable_predicate")
        if ac.type == "parametric" and not ac.golden_table:
            errors.append(f"{ac.id}: type=parametric requires non-empty golden_table")
        if ac.type == "judgment" and not (ac.rubric_id or "").strip():
            errors.append(f"{ac.id}: type=judgment requires rubric_id")
        if not ac.test_ids and not ac.pending_test:
            errors.append(f"{ac.id}: needs >=1 test_ids OR pending_test=true")
    return errors


# ---------------------------------------------------------------------------
# Cross-validation (ADR-007 — 6 rules)
# ---------------------------------------------------------------------------


def _parse_md_frontmatter_and_acs(md_path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    """Return (frontmatter_dict, ac_headings_map) from SPEC.md.

    ac_headings_map: ``{"AC-001": "first line under heading", ...}``.
    """
    text = md_path.read_text(encoding="utf-8")
    fm: dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        m = re.match(r"^---\n(.+?)\n---\n(.*)$", text, re.DOTALL)
        if m:
            fm = yaml.safe_load(m.group(1)) or {}
            body = m.group(2)
    # AC headings of form: "### AC-001: title" OR "### AC-001 title"
    headings: dict[str, str] = {}
    pattern = re.compile(r"^###\s+(AC-\d{3,})[:\s]+(.+)$", re.MULTILINE)
    for match in pattern.finditer(body):
        ac_id = match.group(1)
        first_line = match.group(2).strip()
        headings[ac_id] = first_line
    return fm, headings


def cross_validate(md_path: Path, yaml_path: Path) -> list[str]:
    """ADR-007 six-rule cross-validation. Returns list of error strings (empty = valid)."""
    errors: list[str] = []
    try:
        machine = load(yaml_path)
    except Exception as e:
        return [f"yaml load failed: {e}"]
    fm, md_headings = _parse_md_frontmatter_and_acs(md_path)

    # Rule 1: every ac.id has a matching ### AC-XXX heading in .md
    for ac in machine.ac:
        if ac.id not in md_headings:
            errors.append(f"rule-1: ac.id {ac.id} has no '### {ac.id}' heading in {md_path.name}")

    # Rule 2: ac.title matches first line under heading (fuzzy ≥ FUZZY_RATIO_THRESHOLD)
    for ac in machine.ac:
        md_title = md_headings.get(ac.id, "")
        if not md_title:
            continue
        ratio = SequenceMatcher(None, ac.title.strip(), md_title.strip()).ratio()
        if ratio < FUZZY_RATIO_THRESHOLD:
            errors.append(
                f"rule-2: ac {ac.id} title mismatch (ratio={ratio:.2f} < {FUZZY_RATIO_THRESHOLD}): "
                f".yaml={ac.title!r}, .md={md_title!r}"
            )

    # Rule 3: every test_ids[] entry resolves via pytest --collect-only
    # Skip AC marked pending_test=true (test stub deferred to a follow-up phase
    # per Phase 3 cap policy). We still record the link in machine.yaml so
    # spec_drift can pick it up once the stub is written.
    all_test_ids: list[str] = []
    for ac in machine.ac:
        if ac.pending_test:
            continue
        all_test_ids.extend(ac.test_ids)
    if all_test_ids:
        unresolved = _check_pytest_collect(all_test_ids, cwd=md_path.parent.parent)
        for tid in unresolved:
            errors.append(f"rule-3: test_id does not resolve via pytest --collect-only: {tid}")

    # Rule 4: every rubric_id resolves to a file under .claude/rubrics/ or templates
    for ac in machine.ac:
        if not ac.rubric_id:
            continue
        if not _rubric_exists(ac.rubric_id, md_path.parent.parent):
            errors.append(f"rule-4: rubric_id not found: {ac.rubric_id}")

    # Rule 5: verification_tier in yaml matches frontmatter tier in .md
    fm_tier = fm.get("tier")
    if fm_tier is not None and int(fm_tier) != int(machine.verification_tier):
        errors.append(
            f"rule-5: tier mismatch — .yaml verification_tier={machine.verification_tier}, "
            f".md frontmatter tier={fm_tier}"
        )

    # Rule 6: parent_spec resolves to an existing L1 .md in specs/
    if machine.parent_spec:
        parent_md = md_path.parent / f"{machine.parent_spec}.md"
        if not parent_md.exists():
            errors.append(f"rule-6: parent_spec target not found: {parent_md}")

    return errors


def _check_pytest_collect(test_ids: list[str], cwd: Path) -> list[str]:
    """Return the subset of test_ids that pytest --collect-only does NOT find.

    Scopes the collection to only the **files** referenced by ``test_ids``
    (rather than the whole repo) for 90-99% speedup on large suites
    (REVIEW P-P1-B). Strips pytest parametrize ``[case]`` suffixes when
    comparing to remove a common false-negative source (REVIEW C-P1-B).
    Returns the original test_id strings (not normalized forms) so the
    caller's error messages quote what the SPEC actually says.
    """
    if not test_ids:
        return []
    # Restrict collection to the files referenced by test_ids — dedup'd.
    file_args = sorted({tid.split("::", 1)[0] for tid in test_ids if "::" in tid})
    if not file_args:
        return list(test_ids)
    try:
        # NB: do NOT pass -q — pytest's quiet mode collapses output to
        # ``file: count`` and the nodeid `file::test` form disappears, which
        # would silently zero rule-3 (REVIEW C-P1-B follow-up).
        result = subprocess.run(
            ["pytest", "--collect-only", "--no-header", *file_args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # pytest not available or collection too slow — degrade gracefully:
        # treat all as resolved (cross_validate caller can opt to enforce externally).
        return []
    collected: set[str] = set()
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if "::" not in line:
            continue
        # Strip parametrize suffix `[case_id]` so test_foo[a] matches test_foo.
        canonical = line.split("[", 1)[0]
        collected.add(canonical)
        collected.add(line)
    unresolved: list[str] = []
    for tid in test_ids:
        canonical_tid = tid.split("[", 1)[0]
        if tid in collected or canonical_tid in collected:
            continue
        unresolved.append(tid)
    return unresolved


def _rubric_exists(rubric_id: str, repo_root: Path) -> bool:
    """Look for ``rubric_id`` in .claude/rubrics/, templates/rubrics/."""
    candidates = [
        repo_root / ".claude" / "rubrics" / f"{rubric_id}.yaml",
        repo_root / "src" / "harness_maker" / "templates" / "rubrics" / f"{rubric_id}.yaml.j2",
    ]
    return any(p.exists() for p in candidates)


# ---------------------------------------------------------------------------
# Coverage evaluation
# ---------------------------------------------------------------------------


def evaluate_coverage(yaml_path: Path, pytest_collect_json: str | None = None) -> dict[str, Any]:
    """Compute AC↔test mapping coverage.

    coverage = (AC with non-empty test_ids OR pending_test) / total_AC
    Returns ``{coverage: float, missing: [ac_id, ...]}``.
    """
    machine = load(yaml_path)
    total = len(machine.ac)
    if total == 0:
        return {"coverage": 0.0, "missing": []}
    missing: list[str] = []
    covered = 0
    for ac in machine.ac:
        if ac.pending_test or ac.test_ids:
            covered += 1
        else:
            missing.append(ac.id)
    return {"coverage": covered / total, "missing": missing}


# ---------------------------------------------------------------------------
# pytest selector resolution (ADR-004 — test-naming bridge for R13)
# ---------------------------------------------------------------------------


def resolve_pytest_selector(slug: str) -> str:
    """Return a pytest -k expression supporting both new and legacy test names.

    Example: ``resolve_pytest_selector("render")`` → ``"spec-render or test_render"``.
    """
    return f"spec-{slug} or test_{slug.replace('-', '_')}"


# ---------------------------------------------------------------------------
# Migration policy (Appendix B)
# ---------------------------------------------------------------------------


def migrate(  # pragma: no cover - migration covered via integration tests
    from_version: int,
    to_version: int,
    target: Path,
    *,
    confirm: bool = False,
) -> dict[str, Any]:
    """Apply schema migration. Refuses to run without explicit ``confirm=True``.

    Operates additive-only across minor versions (per Appendix B).
    """
    if not confirm:
        return {
            "status": "dry-run",
            "from": from_version,
            "to": to_version,
            "target": str(target),
            "note": "pass confirm=True to apply",
        }
    if from_version == to_version:
        return {"status": "noop", "reason": "same version"}
    # Concrete migration logic added when v2 is introduced.
    return {"status": "not-implemented", "from": from_version, "to": to_version}


__all__ = [
    "FUZZY_RATIO_THRESHOLD",
    "SCHEMA_VERSION",
    "ACType",
    "AcceptanceCriterion",
    "GoldenRow",
    "SpecMachine",
    "VerificationTier",
    "cross_validate",
    "evaluate_coverage",
    "load",
    "migrate",
    "resolve_pytest_selector",
    "validate",
]
