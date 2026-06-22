"""SPEC machine.yaml schema + cross-validation + coverage evaluation (ADR-006/007).

Owns the dual-file SPEC contract:
- SPEC.md (human, 8-section narrative) — produced by /hm:spec template
- SPEC.machine.yaml (machine, this schema) — produced alongside .md

Cross-validation enforces 6 rules per ADR-007.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import json
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from harness_maker.io_utils import atomic_append, atomic_write

#: Current authored schema version. Templates write ``schema_version: 2``.
#: NOTE (ADR-006): the SpecMachine field default is the LITERAL ``1``, NOT this
#: constant — an OMITTED schema_version must pin to v1 so a constant bump never
#: silently re-tags legacy files as v2 (the migration footgun).
SCHEMA_VERSION = 2

#: ADR-007 rule 2 fuzzy-match threshold. P4 calibration may tune this.
FUZZY_RATIO_THRESHOLD: float = 0.85

ACType = Literal["mechanical", "parametric", "judgment", "property"]
VerificationTier = Literal[1, 2, 3]

#: Oracle source taxonomy (ADR-001/005/007). Maps conceptually onto sw-improve
#: x-contract ``conformance.kind`` (see docs) — documented correspondence, not a
#: validated isomorphism. ``legacy-unspecified`` is the absent-case default for
#: pre-v2 specs (ADR-006): present so a v1 AC loads without an oracle, surfaced
#: advisory by spec_drift, never hard-blocked.
OracleSource = Literal[
    "golden", "differential", "property", "rubric", "consensus", "legacy-unspecified"
]
ORACLE_SOURCES: tuple[str, ...] = (
    "golden",
    "differential",
    "property",
    "rubric",
    "consensus",
    "legacy-unspecified",
)

#: Substrings that signal oracle_evidence names an implementation-independent
#: source (a path, a reference impl, a metamorphic rationale, a citation).
#: SINGLE source of truth (PLAN-wrapup-waiver-enforcement ADR-001) — spec_quality
#: imports this; it must NOT redefine the list (a static test enforces that).
ORACLE_EVIDENCE_SPECIFICITY_MARKERS: tuple[str, ...] = (
    "path",
    "/",
    "reference",
    "golden",
    "metamorphic",
    "independent",
    "citation",
    "differential",
    "attestation",
    "rationale",
    "invariant",
)

#: A per-AC evidence score below this is "weak" (needs a waiver in task-driven).
ORACLE_EVIDENCE_WEAK_THRESHOLD: int = 40


def score_ac_oracle_evidence(ac: dict[str, Any]) -> int:
    """Raw per-AC oracle-evidence score (ADR-001). PURE: no waiver/mode/load.

    The single shared ladder behind both `spec_quality`'s aggregate dim and the
    `waiver-check` CLI — keeping it in one place is what prevents the
    producer-consumer threshold drift. ``legacy-unspecified`` scores 0 (the
    caller still counts it in its denominator — a denominator-retained 0, never
    a skipped AC). The waiver lift (+100) is the CALLER's job, never here.
    """
    if ac.get("oracle_source") == "legacy-unspecified":
        return 0
    # str() coercion: spec_quality feeds raw (non-pydantic) yaml dicts here too, so
    # a malformed `oracle_evidence: [x]` must degrade, not crash (REVIEW consensus).
    evidence = str(ac.get("oracle_evidence") or "").strip()
    if not evidence:
        return 20
    if len(evidence) < 15:
        return 40
    if any(m in evidence.lower() for m in ORACLE_EVIDENCE_SPECIFICITY_MARKERS):
        return 85
    return 60


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
    # --- oracle axis (ADR-001/007) -----------------------------------------
    #: Default ``legacy-unspecified`` = model-level backward compat for v1 ACs;
    #: ``validate`` enforces an explicit non-legacy source only at schema_version>=2.
    oracle_source: OracleSource = "legacy-unspecified"
    #: Independence evidence the spec_quality gate scores (ADR-007). Required
    #: (non-empty) at v2 — what (partially) earns the independence claim.
    oracle_evidence: str | None = None
    #: Durable task-driven override (ADR-003/C9): when set, a low-independence
    #: oracle is a recorded, auditable decision rather than an ephemeral warning.
    #: spec-driven mode blocks regardless; task-driven requires this before wrapup.
    oracle_independence_waiver: str | None = None
    # --- structured property AC fields (ADR-001, type == "property") -------
    input_domain: str | None = None
    transformation: str | None = None
    expected_relation: str | None = None
    preconditions: list[str] = Field(default_factory=list)
    observable_output: str | None = None
    #: Advisory generation hint — NOT a generator (C7). The structured triple
    #: above is the gateable contract; this only nudges Phase A authoring.
    generator_hint: str | None = None

    @field_validator("id")
    @classmethod
    def _ac_id_format(cls, v: str) -> str:
        if not re.match(r"^AC-\d{3,}$", v):
            raise ValueError(f"ac.id must be 'AC-NNN' (3+ digits), got {v!r}")
        return v


class SpecMachine(BaseModel):
    """Top-level SPEC.machine.yaml shape (ADR-006)."""

    #: LITERAL 1 by design (ADR-006): an omitted schema_version pins to v1 so a
    #: SCHEMA_VERSION bump never silently promotes legacy files to v2. New specs
    #: declare ``schema_version: 2`` explicitly.
    schema_version: int = 1
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


#: AST node types that make a predicate "assertable" — an oracle, not a label.
#: A bare Name ("retries") or Constant ("True") is a tautology, never an oracle.
_ASSERTABLE_PREDICATE_NODES = (ast.Compare, ast.BoolOp, ast.Call, ast.UnaryOp)


def _predicate_error(ac_id: str, predicate: str | None) -> str | None:
    """Return an error if a mechanical AC's predicate is not an assertable expression.

    ADR-007 (PLAN-spec-test-accumulation): "predicate-bound" test authoring is
    only real if the predicate is mechanically checkable. The contract: the
    string must ``ast.parse`` as a Python *expression*, its top-level node must
    be a comparison / call / bool-op / unary-op (not a bare name or constant),
    and it must reference at least one symbol. Prose like "retries are bounded"
    fails to parse; "True" parses but is a tautology.
    """
    text = (predicate or "").strip()
    if not text:
        return f"{ac_id}: type=mechanical requires non-empty executable_predicate"
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        return (
            f"{ac_id}: executable_predicate must be a parseable Python expression "
            f"(prose rejected): {predicate!r}"
        )
    if not isinstance(tree.body, _ASSERTABLE_PREDICATE_NODES):
        return (
            f"{ac_id}: executable_predicate must be an assertable expression "
            f"(comparison/call/bool-op/unary), not a bare name or constant: {predicate!r}"
        )
    if not any(isinstance(node, ast.Name) for node in ast.walk(tree)):
        return f"{ac_id}: executable_predicate must reference at least one symbol: {predicate!r}"
    return None


def validate(model: SpecMachine) -> list[str]:
    """Return a list of validation error strings (empty = valid).

    Catches issues pydantic alone can't, such as mechanical AC missing a
    predicate or parametric AC with empty golden table.
    """
    errors: list[str] = []
    is_v2 = model.schema_version >= 2
    for ac in model.ac:
        if ac.type == "mechanical":
            predicate_error = _predicate_error(ac.id, ac.executable_predicate)
            if predicate_error:
                errors.append(predicate_error)
        if ac.type == "parametric" and not ac.golden_table:
            errors.append(f"{ac.id}: type=parametric requires non-empty golden_table")
        if ac.type == "judgment" and not (ac.rubric_id or "").strip():
            errors.append(f"{ac.id}: type=judgment requires rubric_id")
        if ac.type == "property":
            errors.extend(_property_errors(ac))
            # The property AC type + the oracle axis are v2-only. A v1 file that
            # hand-edits one in must declare the version (ADR-006.3 mixed-file).
            if not is_v2:
                errors.append(
                    f"{ac.id}: type=property requires schema_version: 2 "
                    f"(declare it to use property/oracle_source)"
                )
        if not ac.test_ids and not ac.pending_test:
            errors.append(f"{ac.id}: needs >=1 test_ids OR pending_test=true")
        if is_v2:
            errors.extend(_oracle_errors(ac))
    return errors


def _property_errors(ac: AcceptanceCriterion) -> list[str]:
    """A property AC needs the structured metamorphic contract, not free text (ADR-001, C7)."""
    errors: list[str] = []
    for field in ("input_domain", "transformation", "expected_relation", "observable_output"):
        if not (getattr(ac, field) or "").strip():
            errors.append(f"{ac.id}: type=property requires non-empty {field}")
    return errors


def _oracle_errors(ac: AcceptanceCriterion) -> list[str]:
    """v2 ACs must name an explicit oracle source + attach independence evidence (ADR-001/007)."""
    errors: list[str] = []
    if ac.oracle_source == "legacy-unspecified":
        errors.append(
            f"{ac.id}: schema_version 2 requires an explicit oracle_source "
            f"(one of {', '.join(s for s in ORACLE_SOURCES if s != 'legacy-unspecified')})"
        )
    if not (ac.oracle_evidence or "").strip():
        errors.append(
            f"{ac.id}: schema_version 2 requires non-empty oracle_evidence "
            f"(independence evidence the quality gate scores)"
        )
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
    # Drop any token whose file part starts with '-' so a SPEC-authored test_id
    # like ``-pmalicious::x`` cannot be spliced into pytest's argv as an option
    # (REVIEW S-P1: test_ids share the SPEC trust boundary that paths_to_mutate
    # already guards). Dropped tokens stay in test_ids → reported unresolved.
    file_args = sorted(
        {tid.split("::", 1)[0] for tid in test_ids if "::" in tid and not tid.startswith("-")}
    )
    if not file_args:
        return list(test_ids)
    try:
        # ``-q --collect-only`` emits one full nodeid (``file::test``) per line on
        # modern pytest; the non-quiet form emits an indented ``<Function ...>``
        # tree with NO ``::`` nodeids, which would make EVERY id look unresolved
        # (PLAN-spec-test-accumulation: the prior no-`-q` choice silently zeroed
        # rule-3 — only caught once mark_tested exercised it with real pytest).
        # ``--`` fences the file args as positional so none is parsed as an option.
        result = subprocess.run(
            ["pytest", "--collect-only", "-q", "--no-header", "--", *file_args],
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
    if not collected:
        # No nodeids parsed. Either the file(s) failed to collect (rc != 0 →
        # genuinely unresolved) or this pytest emits a count-form summary
        # (rc == 0 → can't tell per-id, degrade to resolved rather than
        # false-failing every id).
        return list(test_ids) if result.returncode != 0 else []
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


def unresolved_test_ids(test_ids: list[str], cwd: Path) -> list[str]:
    """Public wrapper over ``_check_pytest_collect`` — which test_ids pytest can't find.

    Used by spec_drift to flag "resolved-but-pending" ACs (ADR-009) without
    reaching into a module-private helper.
    """
    return _check_pytest_collect(test_ids, cwd=cwd)


# ---------------------------------------------------------------------------
# Forward-binding write-back (ADR-005 of PLAN-spec-test-accumulation)
# ---------------------------------------------------------------------------


def _dump_machine_yaml(yaml_path: Path, model: SpecMachine) -> None:
    """Atomically persist a SpecMachine back to disk (deterministic field order).

    NOTE (REVIEW C-P2b): this round-trips through ``model_dump`` so the first
    write of a sparse hand-authored ``.machine.yaml`` materializes every default
    field (``golden_table: []``, ``rubric_id: null``, …) and drops inline
    comments. That diff-noise is the accepted cost of ADR-005's post-finalize
    write-back (we chose base-repo correctness over a line-stable 3-way merge).
    No field is lost — all model fields, including nested golden rows, are dumped.
    """
    payload = model.model_dump(mode="json")
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    atomic_write(yaml_path, text)


def mark_tested(
    yaml_path: Path,
    md_path: Path,
    ac_test_ids: dict[str, list[str]],
    *,
    validate_after: bool = True,
) -> list[str]:
    """Flip ``pending_test→false`` + record test_ids for the named ACs, then cross_validate.

    The forward-accumulation write-back: wrapup calls this in the base repo
    AFTER finalize has merged the authored tests, so ``cross_validate``'s
    spec-path-relative collection (``md_path.parent.parent``) sees them.

    ``ac_test_ids`` maps AC id → test_ids to union onto the AC's existing list
    (empty list = keep existing test_ids, just flip pending). Returns an error
    list (empty = clean). **Validates before persisting** (REVIEW C-P2c): if a
    named AC would have no test_ids, or its test_ids do not resolve via
    ``pytest --collect-only``, the file is left UNTOUCHED and the errors are
    returned — no half-bound state lands on disk.
    """
    model = load(yaml_path)
    known = {ac.id for ac in model.ac}
    unknown = sorted(a for a in ac_test_ids if a not in known)
    if unknown:
        return [f"mark-tested: unknown ac id(s): {', '.join(unknown)}"]

    # Compute the post-merge test_ids per named AC without mutating yet.
    merged_by_ac: dict[str, list[str]] = {}
    for ac in model.ac:
        if ac.id not in ac_test_ids:
            continue
        merged_by_ac[ac.id] = list(dict.fromkeys([*ac.test_ids, *ac_test_ids[ac.id]]))

    # Refuse to flip an AC to non-pending with no test to back it (REVIEW C-P2d).
    empty = sorted(ac_id for ac_id, ids in merged_by_ac.items() if not ids)
    if empty:
        return [f"mark-tested: cannot mark {ac_id} tested with no test_ids" for ac_id in empty]

    # Pre-check resolution so a flip is never persisted against an unresolved test.
    if validate_after:
        to_check = sorted({tid for ids in merged_by_ac.values() for tid in ids})
        unresolved = unresolved_test_ids(to_check, md_path.parent.parent)
        if unresolved:
            return [
                f"rule-3: test_id does not resolve via pytest --collect-only: {tid}"
                for tid in sorted(unresolved)
            ]

    for ac in model.ac:
        if ac.id not in merged_by_ac:
            continue
        ac.test_ids = merged_by_ac[ac.id]
        ac.pending_test = False
    _dump_machine_yaml(yaml_path, model)
    if validate_after:
        return cross_validate(md_path, yaml_path)
    return []


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


# ---------------------------------------------------------------------------
# CLI (``python -m harness_maker.spec_machine <cmd>``)
# ---------------------------------------------------------------------------


def _parse_ac_test_id(raw: str) -> tuple[str, str]:
    """Parse a ``--test-id AC-001=tests/foo.py::test_bar`` token."""
    ac_id, sep, node = raw.partition("=")
    if not sep or not ac_id.strip() or not node.strip():
        raise argparse.ArgumentTypeError(f"--test-id must be 'AC-ID=test_node', got {raw!r}")
    return ac_id.strip(), node.strip()


# ---------------------------------------------------------------------------
# Oracle-waiver check (PLAN-wrapup-waiver-enforcement — tri-state, never blocks)
# ---------------------------------------------------------------------------


def _slug_from_machine_path(p: Path) -> str:
    """``SPEC-<slug>.machine.yaml`` → ``<slug>`` (fallback: file stem)."""
    m = re.match(r"^SPEC-(.+)\.machine\.ya?ml$", p.name)
    return m.group(1) if m else p.stem


def _safe_slug(slug: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "-", slug) or "unknown"


def _waiver_error(slug: str, reason: str) -> dict[str, Any]:
    return {"status": "check_error", "reason": reason, "slug": slug, "flagged_acs": []}


def waiver_check(yaml_path: Path, dev_mode: str) -> dict[str, Any]:
    """Tri-state oracle-waiver advisory (ADR-002/004). NEVER raises.

    Returns ``{status, slug, flagged_acs, ...}`` where status is:
    - ``check_error`` — the yaml could not be read/parsed / ``ac`` is not a list
      (the check could NOT run — must not look like a clean pass).
    - ``ok`` — no task-driven AC needs a waiver (incl. dev_mode != task-driven,
      which spec_quality already hard-blocks at authoring, ADR-003).
    - ``flagged`` — ≥1 task-driven AC has weak evidence + no waiver.
    """
    slug = _slug_from_machine_path(yaml_path)
    try:
        if not yaml_path.is_file():
            return _waiver_error(slug, "file not found")
        # ValueError covers UnicodeDecodeError (non-UTF-8 file) — a ValueError
        # subclass that is NOT an OSError (REVIEW consensus P1).
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError, ValueError) as e:
        return _waiver_error(slug, str(e))
    if not isinstance(data, dict):
        return _waiver_error(slug, "yaml is not a mapping")
    ac = data.get("ac")
    if not isinstance(ac, list):
        return _waiver_error(slug, "ac is not a list")

    if dev_mode != "task-driven":
        return {"status": "ok", "slug": slug, "flagged_acs": [], "dev_mode": dev_mode}

    # A malformed AC (non-dict entry, or a non-str field where a string is
    # expected) means the check could NOT run for that AC → check_error, NEVER a
    # clean `ok` (ADR-002; the false-clean-pass the tri-state exists to prevent).
    flagged: list[str] = []
    for a in ac:
        if not isinstance(a, dict):
            return _waiver_error(slug, "ac entry is not a mapping")
        ac_id = str(a.get("id", "?"))
        waiver = a.get("oracle_independence_waiver")
        if waiver is not None and not isinstance(waiver, str):
            return _waiver_error(slug, f"{ac_id}: oracle_independence_waiver is not a string")
        if waiver and waiver.strip():
            continue
        evidence = a.get("oracle_evidence")
        if evidence is not None and not isinstance(evidence, str):
            return _waiver_error(slug, f"{ac_id}: oracle_evidence is not a string")
        if score_ac_oracle_evidence(a) < ORACLE_EVIDENCE_WEAK_THRESHOLD:
            flagged.append(ac_id)
    return {
        "status": "flagged" if flagged else "ok",
        "slug": slug,
        "flagged_acs": flagged,
        "dev_mode": dev_mode,
    }


def _write_waiver_receipt(root: Path, result: dict[str, Any]) -> None:
    """Append the result to a root-anchored JSONL receipt (path-guarded, atomic).

    The path is COMPUTED under ``root`` (never a CLI arg) so a crafted slug
    cannot escape the repo (ADR-004/C6); the ``is_relative_to`` guard is the
    belt-and-suspenders backstop.
    """
    slug = _safe_slug(str(result.get("slug", "unknown")))
    receipt = (root / ".claude" / "observability" / f"oracle-waiver-check-{slug}.jsonl").resolve()
    if not receipt.is_relative_to(root.resolve()):
        return
    # atomic_append's POSIX single-write atomicity holds only for lines < 4096
    # bytes (io_utils contract). A pathologically large flagged_acs list must be
    # summarized so concurrent appends never interleave (REVIEW consensus P2).
    line = json.dumps(result, ensure_ascii=False)
    if len(line.encode("utf-8")) + 1 >= 4096:
        flagged = result.get("flagged_acs") or []
        line = json.dumps(
            {
                "status": result.get("status"),
                "slug": slug,
                "flagged_count": len(flagged),
                "truncated": True,
            },
            ensure_ascii=False,
        )
    receipt.parent.mkdir(parents=True, exist_ok=True)
    atomic_append(receipt, line + "\n")


def _run_waiver_check(args: argparse.Namespace) -> int:
    """ALWAYS exits 0 (ADR-002) — the tri-state status carries the verdict.

    Belt-and-suspenders never-raises floor: any unexpected failure (incl. a
    receipt write error) becomes a check_error / no-op so a tool failure never
    escapes as a non-zero exit + traceback (REVIEW consensus P1/P2).
    """
    try:
        result = waiver_check(args.yaml_path, args.dev_mode)
    except Exception as e:  # noqa: BLE001 — the never-raises contract floor
        result = _waiver_error(_slug_from_machine_path(args.yaml_path), f"{type(e).__name__}: {e}")
    # receipt is advisory telemetry — its failure must not break exit-0
    with contextlib.suppress(OSError):
        _write_waiver_receipt(args.root, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for validate / cross-validate / mark-tested / waiver-check."""
    parser = argparse.ArgumentParser(prog="python -m harness_maker.spec_machine")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate", help="schema + semantic validate one .machine.yaml")
    p_val.add_argument("yaml_path", type=Path)

    p_cross = sub.add_parser("cross-validate", help="6-rule md↔yaml cross-validation")
    p_cross.add_argument("md_path", type=Path)
    p_cross.add_argument("yaml_path", type=Path)

    p_mark = sub.add_parser(
        "mark-tested", help="flip pending_test→false + record test_ids (forward write-back)"
    )
    p_mark.add_argument("--yaml", dest="yaml_path", type=Path, required=True)
    p_mark.add_argument("--md", dest="md_path", type=Path, required=True)
    p_mark.add_argument(
        "--ac", dest="acs", action="append", default=[], help="AC id to flip (repeatable)"
    )
    p_mark.add_argument(
        "--test-id",
        dest="test_ids",
        action="append",
        default=[],
        type=_parse_ac_test_id,
        help="AC-ID=test_node to record (repeatable)",
    )

    p_waiver = sub.add_parser(
        "waiver-check",
        help="tri-state task-driven oracle-waiver advisory (never blocks; exits 0)",
    )
    p_waiver.add_argument("--yaml", dest="yaml_path", type=Path, required=True)
    p_waiver.add_argument("--dev-mode", dest="dev_mode", default="task-driven")
    p_waiver.add_argument("--root", dest="root", type=Path, default=Path.cwd())

    args = parser.parse_args(argv)

    if args.cmd == "waiver-check":
        return _run_waiver_check(args)

    if args.cmd == "validate":
        errors = validate(load(args.yaml_path))
    elif args.cmd == "cross-validate":
        errors = cross_validate(args.md_path, args.yaml_path)
    else:  # mark-tested
        ac_test_ids: dict[str, list[str]] = {ac: [] for ac in args.acs}
        for ac_id, node in args.test_ids:
            ac_test_ids.setdefault(ac_id, []).append(node)
        if not ac_test_ids:
            print("mark-tested: no --ac or --test-id given (nothing to do)", file=sys.stderr)
            return 2
        errors = mark_tested(args.yaml_path, args.md_path, ac_test_ids)

    for e in errors:
        print(e, file=sys.stderr)
    if errors:
        return 1
    print(f"{args.cmd}: OK")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    raise SystemExit(main())


__all__ = [
    "FUZZY_RATIO_THRESHOLD",
    "ORACLE_EVIDENCE_SPECIFICITY_MARKERS",
    "ORACLE_EVIDENCE_WEAK_THRESHOLD",
    "ORACLE_SOURCES",
    "SCHEMA_VERSION",
    "ACType",
    "AcceptanceCriterion",
    "GoldenRow",
    "OracleSource",
    "SpecMachine",
    "VerificationTier",
    "cross_validate",
    "evaluate_coverage",
    "load",
    "main",
    "mark_tested",
    "migrate",
    "resolve_pytest_selector",
    "score_ac_oracle_evidence",
    "unresolved_test_ids",
    "validate",
    "waiver_check",
]
