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
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from harness_maker import command_registry
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
    # --- judgment AC binding (PLAN-judgment-ac-binding, type == "judgment") --
    #: The independent rubric-reviewer's verdict (ADR-001/006). null = unjudged.
    judgment_verdict: Literal["pass", "fail"] | None = None
    judged_at: str | None = None  # ISO date the verdict was recorded
    #: Criterion-keyed, locator-cited rationale (ADR-006). Non-empty when judged.
    judgment_evidence: str | None = None
    #: Repo-relative paths the rubric judges — the hashed subject (ADR-004/007).
    #: Required non-empty for a v2 judgment AC (validate); ``..``/absolute rejected.
    judgment_subject_paths: list[str] = Field(default_factory=list)
    #: Canonical SHA-256 over the subject at judge time; the gate re-checks it (ADR-003/004).
    judgment_subject_hash: str | None = None

    @field_validator("id")
    @classmethod
    def _ac_id_format(cls, v: str) -> str:
        if not re.match(r"^AC-\d{3,}$", v):
            raise ValueError(f"ac.id must be 'AC-NNN' (3+ digits), got {v!r}")
        return v

    @field_validator("judgment_subject_paths")
    @classmethod
    def _no_traversal_in_subject(cls, v: list[str]) -> list[str]:
        """Reject absolute / ``..`` subject paths (ADR-004 — same trust boundary as paths)."""
        for p in v:
            if not isinstance(p, str) or not p.strip():
                raise ValueError(
                    f"judgment_subject_paths entry must be non-empty string, got {p!r}"
                )
            if Path(p).is_absolute():
                raise ValueError(
                    f"judgment_subject_paths must be repo-relative, got absolute {p!r}"
                )
            if ".." in Path(p).parts:
                raise ValueError(f"judgment_subject_paths must not contain '..', got {p!r}")
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
    #: Test command mutmut runs per mutant. Absent → mutmut's default, which is the WHOLE test
    #: suite; on any repo whose suite is slower than wall_budget/mutant_count that guarantees a
    #: timeout and an all-zero report (measured here: one mutant exhausted the 600 s cap). Scope
    #: it to the tests that cover `paths_to_mutate`. Optional, so existing SPECs keep parsing —
    #: but a T1/T2 SPEC without it is very unlikely to produce a measurement.
    mutation_runner: str | None = None

    @field_validator("mutation_runner")
    @classmethod
    def _runner_is_a_test_command(cls, value: str | None) -> str | None:
        """This string is EXECUTED, so it is validated where it enters, not where it runs.

        mutmut hands `--runner` to `subprocess.Popen(cmd, shell=True)` on Windows and to
        `shlex.split(cmd)` elsewhere — once per mutant. The value arrives from a repo YAML
        that a `git pull`, a contributor, or a planning model can write, and it never appears
        in the operator's Bash approval prompt: the approved string is the benign
        `uv run … hm spec_mutation gate …` wrapper.

        **What this does and does not buy** — corrected in round 2, because the first version
        of this docstring claimed the allowlist stopped a *hostile* field and it does not.
        `python -c "__import__('os').system('…')"` contains no banned character, `shlex.split`s
        cleanly, and its head is `python`; `uv run --with <pkg> …` installs and runs arbitrary
        code. Against a hostile repo YAML the check is worth nothing.

        What it does buy: it blocks an accidental value (`bash foo.sh`, a typo'd path) and it
        blocks metacharacter chaining on the Windows `shell=True` branch. **Treat a repo YAML
        as trusted input** — a repo hostile enough to plant this can also plant `conftest.py`.
        Saying otherwise is the cosmetic-control-read-as-a-boundary class this repo records.
        """
        if value is None:
            return value
        forbidden = set(";|&$><`\n\r")
        hit = forbidden & set(value)
        if hit:
            msg = f"mutation_runner may not contain shell metacharacters {sorted(hit)}"
            raise ValueError(msg)
        try:
            tokens = shlex.split(value)
        except ValueError as exc:
            msg = f"mutation_runner is not a parseable command: {exc}"
            raise ValueError(msg) from exc
        if not tokens:
            msg = "mutation_runner is empty"
            raise ValueError(msg)
        allowed = {"pytest", "python", "python3", "uv"}
        head = Path(tokens[0]).name
        if head not in allowed:
            msg = f"mutation_runner must start with one of {sorted(allowed)}, got {head!r}"
            raise ValueError(msg)
        return value

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
        if ac.type == "judgment":
            if not (ac.rubric_id or "").strip():
                errors.append(f"{ac.id}: type=judgment requires rubric_id")
            # ADR-007: non-empty subject paths at v2 — else the omission default
            # silently exempts the AC from the find-unjudged gate forever.
            if is_v2 and not ac.judgment_subject_paths:
                errors.append(
                    f"{ac.id}: type=judgment requires non-empty judgment_subject_paths "
                    f"(schema_version: 2)"
                )
        if ac.type == "property":
            errors.extend(_property_errors(ac))
            # The property AC type + the oracle axis are v2-only. A v1 file that
            # hand-edits one in must declare the version (ADR-006.3 mixed-file).
            if not is_v2:
                errors.append(
                    f"{ac.id}: type=property requires schema_version: 2 "
                    f"(declare it to use property/oracle_source)"
                )
        # judgment ACs bind via a recorded verdict, not test_ids/pending_test (ADR-001).
        if ac.type != "judgment" and not ac.test_ids and not ac.pending_test:
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
# Non-mechanical AC forward-binding (PLAN-nonmechanical-ac-binding)
# ---------------------------------------------------------------------------

#: AC types that have a deterministic pytest node and so can be forward-bound by
#: `mark_tested` (everything but `judgment`, which is LLM-rubric-evaluated).
_PYTEST_BINDABLE_TYPES: frozenset[str] = frozenset({"mechanical", "property", "parametric"})


class GoldenTableError(Exception):
    """A parametric AC's golden_table could not be loaded (ADR-006).

    Carries ``yaml_path`` + ``ac_id`` + a cause so the consuming-project test
    author gets a loud, local, actionable failure at collection time instead of
    a raw pydantic/KeyError trace.
    """

    def __init__(self, yaml_path: Path, ac_id: str, cause: str) -> None:
        self.yaml_path = yaml_path
        self.ac_id = ac_id
        self.cause = cause
        super().__init__(f"golden_table[{ac_id}] in {yaml_path}: {cause}")


def select_pytest_bindable(
    model: SpecMachine, *, pending_only: bool = False
) -> list[AcceptanceCriterion]:
    """Return the ACs that have a deterministic pytest node (all but ``judgment``).

    Drives BOTH the wrapup write-back set and the ADR-005 enforcement scan. The
    name reflects the real predicate — "has a pytest-bindable test" — which
    INCLUDES ``mechanical`` (so the write-back set is one list, not two).
    """
    return [
        ac
        for ac in model.ac
        if ac.type in _PYTEST_BINDABLE_TYPES and (not pending_only or ac.pending_test)
    ]


def load_golden_table(yaml_path: Path, ac_id: str) -> list[GoldenRow]:
    """Load a parametric AC's golden_table as the SSOT for its parametrize test (ADR-003).

    Raises ``GoldenTableError`` (never a raw KeyError/ValidationError) for: a
    nonexistent/malformed yaml, an unknown ac_id, a non-parametric AC, or an
    absent/empty golden_table. Data-loading ONLY — the test author writes the
    oracle body around these rows (ADR-003 rejects a universal ``f(**input)``
    recipe).
    """
    try:
        model = load(yaml_path)
    except FileNotFoundError as e:
        raise GoldenTableError(yaml_path, ac_id, f"yaml not found: {e}") from e
    except Exception as e:  # noqa: BLE001 — wrap any load failure into actionable GoldenTableError (ADR-006)
        raise GoldenTableError(yaml_path, ac_id, f"yaml load failed: {e}") from e
    ac = next((a for a in model.ac if a.id == ac_id), None)
    if ac is None:
        raise GoldenTableError(yaml_path, ac_id, "unknown ac id")
    if ac.type != "parametric":
        raise GoldenTableError(yaml_path, ac_id, f"ac is type={ac.type!r}, not parametric")
    if not ac.golden_table:
        raise GoldenTableError(yaml_path, ac_id, "golden_table is absent or empty")
    return list(ac.golden_table)


def _ac_convention_prefix(ac_id: str) -> str:
    """The test-function prefix execute Phase A authors for an AC (``AC-001`` → ``test_ac_001``)."""
    return "test_" + ac_id.lower().replace("-", "_")


class BindingGateUnavailableError(Exception):
    """pytest could not adjudicate the binding state — fail-closed signal (ADR-005).

    Raised (only when there IS pending work to adjudicate) when the repo-wide
    ``pytest --collect-only`` was unavailable, timed out, or exited with a
    collection ERROR. The Production caller converts this into a FAIL — an
    unknown binding state is never a clean pass (the false-PASS the k-of-3
    review caught: collapsing "ran cleanly" / "errored" / "unavailable" into one
    boolean silently green-lit a missed binding).
    """


def _pytest_collect_nodeids(cwd: Path) -> tuple[list[str], bool]:
    """Return ``(collected_nodeids, ran_cleanly)`` from a repo-wide ``--collect-only``.

    ``ran_cleanly`` is False when pytest is unavailable/timed out, exited with a
    collection error (rc not in {0, 5} — 5 is pytest's "no tests collected", a
    legitimately-empty clean run), OR ran clean over a non-empty suite whose output
    yielded no parseable node id. All three are "could not adjudicate"; the caller
    fails closed on False.

    ``-o addopts=`` is load-bearing, not tidiness. ``--collect-only`` prints node
    ids at exactly verbosity -1; the project's own ``addopts`` composes with the
    ``-q`` below, so an ``addopts = "-q"`` (this repo's own, and a common default)
    lands on -2, where pytest prints PER-FILE COUNTS instead —
    ``tests/e2e/foo.py: 2``, not one ``file::test`` per line. Nothing in that form
    contains ``"::"``, so the parse silently yielded [] and the Production
    ``find-unbound`` gate reported OK for every AC it was ever asked about. It had
    never once fired. Resetting addopts pins the verbosity this parse assumes.

    Accepted cost: a project whose addopts carries a collection-affecting flag
    (``--import-mode``, a required ``-p``) loses it here and may collect-error.
    That surfaces as rc != 0 → fail-closed → a LOUD gate failure, which is the
    safe direction; the silent one is what this replaces.
    """
    try:
        result = subprocess.run(
            ["pytest", "-o", "addopts=", "--collect-only", "-q", "--no-header"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return [], False
    if result.returncode not in (0, 5):  # 5 = no-tests-collected (clean empty)
        return [], False
    nodeids = [ln.strip() for ln in result.stdout.splitlines() if "::" in ln]
    # rc 0 means pytest collected SOMETHING (rc 5 is the empty-suite code), so an
    # empty parse here is OUR failure to read the output, never a true empty suite.
    # Calling that "no collectable test" is precisely the false PASS above.
    if result.returncode == 0 and not nodeids:
        return [], False
    return nodeids, True


def _collectable_ac_tests(model: SpecMachine, cwd: Path) -> tuple[set[str], bool]:
    """``(ac_ids_whose_test_collects, ran_cleanly)`` — by recorded ``test_ids`` OR convention.

    The union (ADR-005, 2nd-pass-validator fix): a missed write-back leaves
    ``pending_test=true`` with EITHER an empty ``test_ids`` (caught by the
    convention name) OR a pre-populated ``test_ids`` authored at the declared
    node (caught by the recorded id) — both must be discoverable. ``ran_cleanly``
    is threaded up so the caller can fail closed when pytest could not adjudicate.
    """
    nodeids, ran = _pytest_collect_nodeids(cwd)
    if not ran:
        return set(), False
    canonical = {nid.split("[", 1)[0] for nid in nodeids} | set(nodeids)
    func_names = {nid.split("::")[-1].split("[", 1)[0] for nid in nodeids}
    collectable: set[str] = set()
    for ac in model.ac:
        recorded_hit = any(
            tid in canonical or tid.split("[", 1)[0] in canonical for tid in ac.test_ids
        )
        prefix = _ac_convention_prefix(ac.id)
        # Boundary match: `test_ac_001` matches itself and `test_ac_001_adder`,
        # NOT `test_ac_0012` (mixed-width AC ids — AC-001 vs AC-0012 collision).
        convention_hit = any(fn == prefix or fn.startswith(prefix + "_") for fn in func_names)
        if recorded_hit or convention_hit:
            collectable.add(ac.id)
    return collectable, True


def find_unbound_closed_type_acs(yaml_path: Path, cwd: Path) -> list[str]:
    """Return closed-type AC ids that are a MISSED write-back (ADR-005).

    A miss = a pytest-bindable AC that is still ``pending_test`` AND whose test
    COLLECTS (convention-named or recorded). An AC with no collectable test is
    genuine future-PLAN work and is safe-skipped (CLAUDE.md absent-case). Raises
    ``load``'s error on a malformed/absent yaml, and ``BindingGateUnavailableError``
    when there IS pending work but pytest could not adjudicate it — so the
    Production caller fails closed (never a false PASS by missing inputs).
    """
    model = load(yaml_path)  # raises on malformed → caller fails closed
    pending = {ac.id for ac in select_pytest_bindable(model, pending_only=True)}
    if not pending:
        return []  # nothing to adjudicate → pytest never invoked → genuinely clean
    collectable, ran = _collectable_ac_tests(model, cwd)
    if not ran:
        raise BindingGateUnavailableError(
            f"pytest collect did not run cleanly for {yaml_path} — "
            "binding state unknown (fail-closed)"
        )
    return sorted(pending & collectable)


# ---------------------------------------------------------------------------
# Judgment AC binding (PLAN-judgment-ac-binding) — independent rubric verdict
# ---------------------------------------------------------------------------

#: Per-file byte cap for the canonical subject hash (ADR-004). A path exceeding it
#: resolves to the SAME unbound disposition as missing/unreadable, NEVER a skip.
_SUBJECT_FILE_SIZE_CAP = 5 * 1024 * 1024


class SubjectHashError(Exception):
    """A judgment AC's subject could not be canonically hashed (ADR-004).

    Raised on a missing/unreadable path, a symlink escaping the repo root, or a
    file over the size cap. The gate treats this as **unbound** (never a skip).
    """


def select_judgment(model: SpecMachine, *, unbound_only: bool = False) -> list[AcceptanceCriterion]:
    """The judgment ACs (parallel to ``select_pytest_bindable``).

    ``unbound_only`` keeps ACs whose verdict is not ``pass`` (null or ``fail``).
    """
    return [
        ac
        for ac in model.ac
        if ac.type == "judgment" and (not unbound_only or ac.judgment_verdict != "pass")
    ]


def _iter_subject_files(rel: str, root: Path) -> list[tuple[str, Path]]:
    """Expand one subject path to ``(manifest_name, file)`` tuples.

    A directory expands via ``os.walk(followlinks=False)`` — symlinked SUBDIRS are
    NOT descended (so no symlink-dir escape and no symlink cycle, REVIEW security
    P1). Every yielded file is resolved and **rejected (SubjectHashError) if it
    escapes ``root``** — this catches a symlinked file inside the tree too. The
    manifest name is the DECLARED (walked) repo-relative path, not the symlink
    target (rename-sensitive on the declared location, REVIEW Codex P2). A missing
    path raises (the gate then treats the AC as unbound, never a silent skip).
    """
    base = (root / rel).resolve()
    root_resolved = root.resolve()
    if not base.exists():
        raise SubjectHashError(f"subject path not found: {rel}")
    if not base.is_relative_to(root_resolved):
        raise SubjectHashError(f"subject path escapes repo root (symlink?): {rel}")
    out: list[tuple[str, Path]] = []
    if base.is_dir():
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            dirnames.sort()
            for fn in sorted(filenames):
                f = Path(dirpath) / fn
                rf = f.resolve()
                if not rf.is_relative_to(root_resolved):
                    raise SubjectHashError(f"subject file escapes repo root (symlink?): {f}")
                if rf.is_file():
                    out.append((str(f.relative_to(root_resolved)), rf))
    else:
        out.append((str(base.relative_to(root_resolved)), base))
    return out


#: Caps for the canonical subject hash (ADR-004 — bound the gate's per-run cost on
#: an untrusted, possibly-huge subject path; exceeding either = unbound, never a skip).
_SUBJECT_TOTAL_FILES_CAP = 5000
_SUBJECT_TOTAL_BYTES_CAP = 200 * 1024 * 1024
#: Cap on a `--evidence-file` read (REVIEW security P2 — it lands verbatim in the YAML).
_EVIDENCE_FILE_CAP = 64 * 1024


def compute_subject_hash(subject_paths: list[str], root: Path) -> str:
    """Canonical SHA-256 over the subject (ADR-004).

    Manifest = sorted ``(declared_relative_name, sha256(file_bytes))`` tuples,
    de-duped by name — NAMES included (a rename changes the hash), order- and
    declaration-multiset-independent. A missing/unreadable path, a symlink escaping
    the repo, an empty subject (zero files), or a per-file / total size/count cap
    breach raises ``SubjectHashError`` (the caller treats it as unbound — never a
    silent skip).
    """
    by_name: dict[str, str] = {}
    total_bytes = 0
    for rel in subject_paths:
        for name, f in _iter_subject_files(rel, root):
            if name in by_name:
                continue  # de-dup overlapping declarations (REVIEW correctness P2)
            try:
                size = f.stat().st_size
                if size > _SUBJECT_FILE_SIZE_CAP:
                    raise SubjectHashError(f"subject file over size cap ({rel}): {name}")
                total_bytes += size
                if (
                    len(by_name) >= _SUBJECT_TOTAL_FILES_CAP
                    or total_bytes > _SUBJECT_TOTAL_BYTES_CAP
                ):
                    raise SubjectHashError(f"subject total size/count cap exceeded at {name}")
                by_name[name] = hashlib.sha256(f.read_bytes()).hexdigest()
            except OSError as e:
                raise SubjectHashError(f"subject file unreadable ({rel}): {e}") from e
    if not by_name:
        raise SubjectHashError("subject expanded to zero files (empty/emptied subject)")
    manifest = "\n".join(f"{name}\0{digest}" for name, digest in sorted(by_name.items()))
    return hashlib.sha256(manifest.encode("utf-8")).hexdigest()


def mark_judged(
    yaml_path: Path,
    ac_id: str,
    verdict: str,
    evidence: str,
    *,
    cwd: Path,
) -> list[str]:
    """Record an independent rubric-reviewer's verdict (ADR-005). Pure storage, NO LLM call.

    Validates the AC is type=judgment, the verdict is exactly ``pass``/``fail``, and
    the evidence is non-empty; computes the canonical subject hash; stores
    verdict/evidence/judged_at/hash. Returns an error list (empty = clean); the
    file is left UNTOUCHED on any error.
    """
    if verdict not in ("pass", "fail"):
        return [f"mark-judged: verdict must be exactly 'pass' or 'fail', got {verdict!r}"]
    if not evidence.strip():
        return ["mark-judged: judgment_evidence must be non-empty (criterion-keyed, ADR-006)"]
    model = load(yaml_path)
    ac = next((a for a in model.ac if a.id == ac_id), None)
    if ac is None:
        return [f"mark-judged: unknown ac id: {ac_id}"]
    if ac.type != "judgment":
        return [f"mark-judged: {ac_id} is type={ac.type!r}, not judgment"]
    try:
        subject_hash = compute_subject_hash(ac.judgment_subject_paths, cwd)
    except SubjectHashError as e:
        return [f"mark-judged: {e}"]
    ac.judgment_verdict = verdict  # type: ignore[assignment]
    ac.judgment_evidence = evidence.strip()
    ac.judged_at = datetime.now(UTC).date().isoformat()
    ac.judgment_subject_hash = subject_hash
    _dump_machine_yaml(yaml_path, model)
    return []


def _judgment_in_scope(ac: AcceptanceCriterion, cwd: Path) -> bool:
    """Is this judgment AC in-scope for the gate (must be bound), vs genuine future work?

    In-scope iff it has NO declared paths (misconfigured — validate rejects it, but the
    gate must block, not skip) OR **ANY** declared path exists on disk (REVIEW correctness
    P1: a partially-built multi-path subject must be gated, not skipped behind an absent
    sibling). Only a fully-absent subject (every path not yet written) is future-PLAN.
    """
    if not ac.judgment_subject_paths:
        return True  # misconfigured → block, never silently exempt (absent-case guard)
    return any((cwd / p).exists() for p in ac.judgment_subject_paths)


def find_unjudged(yaml_path: Path, cwd: Path) -> list[str]:
    """Judgment ACs that are a MISSED binding in Production (ADR-003).

    A miss = an IN-SCOPE judgment AC (see `_judgment_in_scope`) that is NOT bound: no
    ``pass`` verdict, a recorded ``fail``, a `pass` whose recomputed hash != the stored
    hash (STALE), or an unhashable subject (a partially-present multi-path subject raises
    in `compute_subject_hash` → unbound). A fully-absent subject = future-PLAN = safe-skip.
    Raises on a malformed yaml so the Production caller fails closed.
    """
    model = load(yaml_path)  # raises on malformed → caller fails closed
    misses: list[str] = []
    for ac in select_judgment(model):
        if not _judgment_in_scope(ac, cwd):
            continue  # future-PLAN: no subject path on disk yet
        if ac.judgment_verdict != "pass":
            misses.append(ac.id)
            continue
        # pass recorded — confirm it is not stale (hash must match the live subject).
        try:
            current = compute_subject_hash(ac.judgment_subject_paths, cwd)
        except SubjectHashError:
            misses.append(ac.id)  # unhashable / partially-present = unbound (fail-closed)
            continue
        if current != ac.judgment_subject_hash:
            misses.append(ac.id)  # stale pass
    return sorted(misses)


def stale_judgment_verdicts(yaml_path: Path, cwd: Path) -> list[str]:
    """Recorded-`pass` judgment ACs whose subject hash drifted (advisory health signal)."""
    model = load(yaml_path)
    stale: list[str] = []
    for ac in select_judgment(model):
        if ac.judgment_verdict != "pass" or not _judgment_in_scope(ac, cwd):
            continue
        try:
            current = compute_subject_hash(ac.judgment_subject_paths, cwd)
        except SubjectHashError:
            stale.append(ac.id)
            continue
        if current != ac.judgment_subject_hash:
            stale.append(ac.id)
    return sorted(stale)


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


def _run_find_unbound(args: argparse.Namespace) -> int:
    """Production gate (ADR-005): exit non-zero on a missed binding OR fail-closed error.

    Absent machine.yaml = nothing to check = exit 0 (mirrors Step 3.5's skip). A
    malformed/unreadable machine.yaml, or a genuine missed binding, = exit 1 — the
    binding state is either bad or unknown, neither of which is a clean pass.
    """
    if not args.yaml_path.exists():
        print("find-unbound: no machine SPEC — nothing to check", file=sys.stderr)
        return 0
    try:
        misses = find_unbound_closed_type_acs(args.yaml_path, args.root)
    except Exception as e:  # noqa: BLE001 — fail-closed: unknown state is not a pass
        print(f"find-unbound: FAIL (fail-closed) — {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if misses:
        print(
            "find-unbound: FAIL — closed-type AC(s) authored but never bound "
            f"(re-run mark-tested): {', '.join(misses)}",
            file=sys.stderr,
        )
        return 1
    print("find-unbound: OK — no missed binding")
    return 0


def _run_mark_judged(args: argparse.Namespace) -> int:
    """Record an independent rubric verdict (ADR-005). Pure storage, no LLM call."""
    evidence = args.evidence
    if evidence is None and args.evidence_file is not None:
        ev_path = Path(args.evidence_file)
        try:
            if ev_path.stat().st_size > _EVIDENCE_FILE_CAP:
                print("mark-judged: --evidence-file exceeds 64 KiB cap", file=sys.stderr)
                return 1
            evidence = ev_path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"mark-judged: cannot read --evidence-file: {e}", file=sys.stderr)
            return 1
    errors = mark_judged(args.yaml_path, args.ac_id, args.verdict, evidence or "", cwd=args.root)
    for err in errors:
        print(err, file=sys.stderr)
    if errors:
        return 1
    print(f"mark-judged: OK — {args.ac_id} verdict={args.verdict}")
    return 0


def _run_find_unjudged(args: argparse.Namespace) -> int:
    """Production gate (ADR-003): exit 1 on a not-pass/stale/unhashable judgment AC, fail-closed."""
    if not args.yaml_path.exists():
        print("find-unjudged: no machine SPEC — nothing to check", file=sys.stderr)
        return 0
    try:
        misses = find_unjudged(args.yaml_path, args.root)
    except Exception as e:  # noqa: BLE001 — fail-closed: unknown state is not a pass
        print(f"find-unjudged: FAIL (fail-closed) — {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if misses:
        print(
            "find-unjudged: FAIL — judgment AC(s) not bound (no current pass verdict; "
            f"re-judge via the judgment-reviewer): {', '.join(misses)}",
            file=sys.stderr,
        )
        return 1
    print("find-unjudged: OK — no unbound judgment AC")
    return 0


#: `cross_validate` returns flat strings tagged `rule-N:`. Attribution is by that prefix,
#: and anything untagged (today: the early `yaml load failed` return) lands in
#: `unattributed` rather than being dropped — a per-rule view that silently discards an
#: error would report six clean rules over a yaml that never loaded.
_RULE_IDS = ("rule-1", "rule-2", "rule-3", "rule-4", "rule-5", "rule-6")


def _attribute_cross_errors(errors: list[str]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {r: [] for r in _RULE_IDS}
    buckets["unattributed"] = []
    for e in errors:
        rule = next((r for r in _RULE_IDS if e.startswith(f"{r}:")), "unattributed")
        buckets[rule].append(e)
    return buckets


def _run_check_all(args: argparse.Namespace) -> int:
    """Steps 4 and 4.5 of the spec stage in one call — three round-trips become one.

    Orchestration only ([ADR-003](work-docs/PLAN-workflow-step-audit.md)): every verdict
    comes from `validate` / `cross_validate` / `evaluate_spec` unchanged, so this cannot
    drift from the subcommands it replaces.
    """
    from harness_maker.spec_quality import evaluate_spec

    payload: dict[str, Any] = {
        "yaml_path": str(args.yaml_path),
        "md_path": str(args.md_path),
        "dev_mode": args.dev_mode,
    }

    try:
        validate_errors = validate(load(args.yaml_path))
    except Exception as e:  # noqa: BLE001 — an unloadable yaml is a reportable verdict
        validate_errors = [f"yaml load failed: {type(e).__name__}: {e}"]
    payload["validate"] = {"ok": not validate_errors, "errors": validate_errors}

    cross_errors = cross_validate(args.md_path, args.yaml_path)
    payload["cross_validate"] = {
        "ok": not cross_errors,
        "errors": cross_errors,
        "by_rule": _attribute_cross_errors(cross_errors),
    }

    try:
        quality = evaluate_spec(
            args.md_path.read_text(encoding="utf-8"),
            args.dev_mode,
            machine_yaml=args.yaml_path.read_text(encoding="utf-8")
            if args.yaml_path.exists()
            else None,
        )
    except Exception as e:  # noqa: BLE001 — scoring must not mask the two gates above
        payload["quality"] = {"error": f"{type(e).__name__}: {e}"}
        quality_blocked = False
    else:
        payload["quality"] = {
            "overall": quality.overall,
            "scores": quality.scores,
            "weak_dimensions": quality.weak_dimensions,
            "blocked": quality.blocked,
            "dev_mode": quality.dev_mode,
        }
        quality_blocked = quality.blocked

    failed = bool(validate_errors) or bool(cross_errors) or quality_blocked
    payload["ok"] = not failed
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for validate / cross-validate / mark-tested / waiver-check / find-unbound."""
    _guard = command_registry.guard_or_none("spec_machine", argv)
    if _guard is not None:
        return _guard
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

    p_unbound = sub.add_parser(
        "find-unbound",
        help="list closed-type ACs that are a missed binding (Production gate; fail-closed)",
    )
    p_unbound.add_argument("--yaml", dest="yaml_path", type=Path, required=True)
    p_unbound.add_argument("--root", dest="root", type=Path, default=Path.cwd())

    p_judge = sub.add_parser(
        "mark-judged", help="record an independent rubric verdict (pure storage, no LLM call)"
    )
    p_judge.add_argument("--yaml", dest="yaml_path", type=Path, required=True)
    p_judge.add_argument("--ac", dest="ac_id", required=True)
    p_judge.add_argument("--verdict", required=True, help="exactly 'pass' or 'fail'")
    p_judge.add_argument("--evidence", default=None, help="criterion-keyed rationale")
    p_judge.add_argument("--evidence-file", dest="evidence_file", default=None)
    p_judge.add_argument("--root", dest="root", type=Path, default=Path.cwd())

    p_unjudged = sub.add_parser(
        "find-unjudged",
        help="list judgment ACs not bound by a current pass verdict (Production gate; fail-closed)",
    )
    p_unjudged.add_argument("--yaml", dest="yaml_path", type=Path, required=True)
    p_unjudged.add_argument("--root", dest="root", type=Path, default=Path.cwd())

    p_check = sub.add_parser(
        "check",
        help="validate + cross-validate + quality score in ONE call (spec Step 4/4.5)",
    )
    p_check.add_argument("--all", dest="all_", action="store_true", required=True)
    p_check.add_argument("--yaml", dest="yaml_path", type=Path, required=True)
    p_check.add_argument("--md", dest="md_path", type=Path, required=True)
    p_check.add_argument("--dev-mode", dest="dev_mode", default="task-driven")

    args = parser.parse_args(argv)

    if args.cmd == "check":
        return _run_check_all(args)

    if args.cmd == "waiver-check":
        return _run_waiver_check(args)

    if args.cmd == "find-unbound":
        return _run_find_unbound(args)

    if args.cmd == "mark-judged":
        return _run_mark_judged(args)

    if args.cmd == "find-unjudged":
        return _run_find_unjudged(args)

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
    "BindingGateUnavailableError",
    "GoldenRow",
    "GoldenTableError",
    "SubjectHashError",
    "OracleSource",
    "SpecMachine",
    "VerificationTier",
    "compute_subject_hash",
    "cross_validate",
    "evaluate_coverage",
    "find_unbound_closed_type_acs",
    "find_unjudged",
    "load",
    "load_golden_table",
    "main",
    "mark_judged",
    "mark_tested",
    "migrate",
    "resolve_pytest_selector",
    "score_ac_oracle_evidence",
    "select_judgment",
    "select_pytest_bindable",
    "stale_judgment_verdicts",
    "unresolved_test_ids",
    "validate",
    "waiver_check",
]
