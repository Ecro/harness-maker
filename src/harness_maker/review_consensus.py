"""Consensus tagging, grade computation, dispositions and the re-review decision.

This module exists because ADR-007 removed cross-lens consensus, and with it the system's only
false-positive filter. What replaced it — a solo lens vote plus an AC-cited rejection escape —
is a rule about *who spoke*, and that rule was previously stated as prose in `review.md.j2` and
applied by the model. A prose rule has no executable surface: a render-grep proves the
instruction is present, never that the tag it produces is correct, and after ADR-007 the tag is
the whole control. So the arithmetic lives here and the stage calls it.

The judgment/mechanism boundary is unchanged and deliberate: the LLM still decides whether a
finding is real and whether two reasoning chains identify the same risk. Python only counts
voices, applies the tag table, and refuses a rejection with no contract behind it.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from harness_maker import command_registry

Tag = Literal["consensus-passed", "weak-consensus", "manual-only"]
Disposition = Literal["accepted", "rejected", "duplicate", "unresolved"]

#: The four PIDA values. Shared with the cross-model gate so the rejection rate cannot silently
#: split between two producers writing two different vocabularies.
DISPOSITIONS: frozenset[str] = frozenset({"accepted", "rejected", "duplicate", "unresolved"})

#: The authority a finding may be rejected against, and the one that means "there was none".
#: `no-contract` is not an authority — it is the recorded absence of one, which is why it is
#: valid on `unresolved` and invalid on `rejected`.
NO_CONTRACT = "no-contract"

#: Severities that can move the grade or raise the human-review flag. P2/P3 never do — that is
#: the pre-change behaviour, and it is what makes a nine-lens fan-out affordable at all: the
#: low-importance half of the new axis lands at P2 and is recorded rather than blocking.
_SEVERE: frozenset[str] = frozenset({"P0", "P1"})


class ConsensusError(ValueError):
    """A malformed voice, disposition or round record.

    Loud rather than lenient. A silently-dropped voice changes a grade with no diagnostic, and
    the grade is what decides whether the review can exit.
    """


@dataclass(frozen=True)
class Voice:
    """One vote on one finding.

    ``kind`` is the whole point. Two reviewer lenses examine two different axes, so expecting
    `security` to second a `naming` finding is a category error rather than a quality bar; two
    cross-model voters examine the *same* axis on the same diff, so their agreement is real
    corroboration. The tag table below is that distinction and nothing else.
    """

    source: str
    kind: Literal["lens", "cross-model"]


def _as_voice(raw: object) -> Voice:
    if isinstance(raw, Voice):
        return raw
    if not isinstance(raw, dict):
        raise ConsensusError(f"voice must be a mapping or Voice, got {type(raw).__name__}")
    source = raw.get("source")
    kind = raw.get("kind")
    if not isinstance(source, str) or not source.strip():
        raise ConsensusError(f"voice.source must be a non-empty string, got {source!r}")
    if kind not in {"lens", "cross-model"}:
        raise ConsensusError(f"voice.kind must be 'lens' or 'cross-model', got {kind!r}")
    return Voice(source=source, kind=kind)


def tag_finding(voices: list[object], *, reasoning_diverges: bool = False) -> Tag:
    """Apply ADR-007's tag table.

    One reviewer-lens voice is sovereign: the fan-out gain consists *by definition* of findings
    exactly one category raised, so demoting them to `manual-only` would spend nine dispatches
    and discard their entire distinctive output. Cross-model voters keep K=2 — they carry no
    `suggestion`, so a solo cross-model vote would block grade A with no repair path.

    ``reasoning_diverges`` is the Step 4b judgment (same OBSERVE, different CONCLUDE), passed in
    rather than inferred here. **It cannot demote a finding a lens raised** — the table is
    monotonic in voices, so adding a second voice never produces a worse tag than the first one
    earned alone. That resolves terminal-validation critical T-01, which this PLAN had accepted as
    a risk: with the pre-change rule, lens A alone was `consensus-passed` while lens A *and* lens
    B disagreeing about the mechanism was `weak-consensus` — ungraded and unfixable. Two experts
    noticing the same defect and describing it differently is the ordinary case for an axis whose
    whole premise is that distinct categories see distinct things, so under solo-lens sovereignty
    the old rule punishes exactly the corroboration the fan-out exists to produce.

    Divergence still demotes a **cross-model-only** pair, where it is doing real work: that
    finding's pass depends entirely on the two voices agreeing, so if they do not, nothing is left
    holding it up.
    """
    parsed = [_as_voice(v) for v in voices]
    if not parsed:
        raise ConsensusError("a finding with no voices cannot be tagged")
    lens_sources = {v.source for v in parsed if v.kind == "lens"}
    model_sources = {v.source for v in parsed if v.kind == "cross-model"}

    if lens_sources:
        return "consensus-passed"
    if len(model_sources) >= 2:
        return "weak-consensus" if reasoning_diverges else "consensus-passed"
    return "manual-only"


# ── Dispositions (ADR-002) ───────────────────────────────────────────────────


def _authority_kind(authority: object) -> str:
    """`ac` | `docstring` | `no-contract` | `none` | `unknown`."""
    if authority is None:
        return "none"
    if not isinstance(authority, str) or not authority.strip():
        return "unknown"
    text = authority.strip()
    if text == NO_CONTRACT:
        return NO_CONTRACT
    if text.startswith("docstring:"):
        return "docstring"
    head = text.split()[0].upper()
    if head.startswith("AC-") and head[3:].isdigit():
        return "ac"
    return "unknown"


def validate_disposition(disposition: object, authority: object = None) -> bool:
    """Is this (disposition, authority) pair recordable?

    Only `rejected` needs an authority, and it must be an independent contract — a SPEC AC id or
    a docstring citation. `no-contract` is explicitly NOT one: a harness with no SPEC and no
    docstring has nothing to reject against, and the honest record of that is `unresolved`, which
    still counts toward the grade. Letting `no-contract` justify a rejection would turn
    self-grading into grade laundering, which is the exact thing ADR-002 exists to prevent.
    """
    if disposition not in DISPOSITIONS:
        return False
    kind = _authority_kind(authority)
    if kind == "unknown":
        return False
    if disposition == "rejected":
        return kind in {"ac", "docstring"}
    if kind == NO_CONTRACT:
        return disposition == "unresolved"
    return True


def grade_effect(severity: str, disposition: object, authority: object = None) -> dict[str, bool]:
    """Whether a finding counts toward the grade, and whether it needs a human.

    Only an **AC-cited** rejection clears the grade. A docstring-cited one still counts and sets
    `human_review_needed`: CLAUDE.md makes docstrings optional and the fixer writes them, so a
    docstring is not independent of the thing under review in the way a SPEC criterion is. That
    asymmetry is the false-positive escape ADR-007 made necessary, bounded so it cannot become a
    way to talk a P0 into an A.
    """
    severe = severity in _SEVERE
    if disposition == "duplicate":
        return {"counted": False, "human_review_needed": False}
    if disposition == "rejected":
        if _authority_kind(authority) == "ac":
            return {"counted": False, "human_review_needed": False}
        return {"counted": True, "human_review_needed": severe}
    if disposition == "unresolved":
        return {"counted": True, "human_review_needed": severe}
    return {"counted": True, "human_review_needed": False}


@dataclass(frozen=True)
class RoundRecord:
    """A round's findings with a complete disposition column, plus the errors found writing it."""

    findings: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def build_round_record(findings: list[dict[str, Any]]) -> RoundRecord:
    """Assign the disposition column, defaulting the absent case rather than dropping it.

    The producer is the round-record writer, not the fix-selection step, because fix selection
    sees only fix-eligible findings — so on an `auto_fix`-disabled run, or a round with no fix
    step, every finding would have left without one.

    A finding arriving with no disposition is recorded `unresolved` / `no-contract` and the gap
    is reported in ``errors``. That is the weakest value: it counts toward the grade and raises
    the human-review flag, so a forgotten disposition can never be mistaken for a cleared one.
    An invalid pair is downgraded the same way, for the same reason.
    """
    out: list[dict[str, Any]] = []
    errors: list[str] = []
    for i, raw in enumerate(findings):
        if not isinstance(raw, dict):
            raise ConsensusError(f"finding {i} must be a mapping, got {type(raw).__name__}")
        item = dict(raw)
        disposition = item.get("disposition")
        authority = item.get("authority")
        if disposition is None:
            errors.append(f"{item.get('id', i)}: no disposition — recorded unresolved")
            item["disposition"], item["authority"] = "unresolved", NO_CONTRACT
        elif not validate_disposition(disposition, authority):
            errors.append(
                f"{item.get('id', i)}: {disposition!r} with authority {authority!r} is not "
                "recordable — downgraded to unresolved"
            )
            item["disposition"], item["authority"] = "unresolved", NO_CONTRACT
        else:
            item["authority"] = authority
        out.append(item)
    return RoundRecord(findings=out, errors=errors)


# ── Grade ────────────────────────────────────────────────────────────────────


def compute_grade(*, p0_count: int, p1_count: int, p2_count: int = 0, p3_count: int = 0) -> str:
    """The published grade table, unchanged. P2/P3 are accepted and ignored."""
    del p2_count, p3_count
    if p0_count >= 3:
        return "F"
    if p0_count >= 1:
        return "D"
    if p1_count >= 3:
        return "C"
    if p1_count >= 1:
        return "B"
    return "A"


def grade_from_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Count the graded population, then apply the table.

    A finding is graded when it is `consensus-passed` **and** its disposition counts. Two
    independent filters, in that order: the tag decides whether it is corroborated, the
    disposition decides whether a contract excused it.
    """
    counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    human_review_needed = False
    for raw in findings:
        severity = str(raw.get("severity", ""))
        tag = raw.get("tag")
        effect = grade_effect(severity, raw.get("disposition"), raw.get("authority"))
        if effect["human_review_needed"] and tag == "consensus-passed":
            human_review_needed = True
        if tag in {"manual-only", "weak-consensus"} and severity in _SEVERE:
            human_review_needed = True
        if tag != "consensus-passed" or not effect["counted"]:
            continue
        if severity in counts:
            counts[severity] += 1
    grade = compute_grade(
        p0_count=counts["P0"],
        p1_count=counts["P1"],
        p2_count=counts["P2"],
        p3_count=counts["P3"],
    )
    return {"grade": grade, "counts": counts, "human_review_needed": human_review_needed}


# ── Re-review decision (ADR-004/005; wired by Phase 6) ───────────────────────


@dataclass(frozen=True)
class Dispatch:
    """One reviewer to re-run on a repair round."""

    agent: str
    lens: str
    reason: str


def rereview_reason(churn_ratio: float, threshold: float) -> str:
    """The comparison, verbatim, so a recorded skip is auditable without re-running anything.

    The bare `<ratio> <op> <threshold>` form is load-bearing: it is what the iteration record
    carries, and a reader checking whether a skip was correct should not have to reconstruct the
    numbers from prose.
    """
    op = ">=" if churn_ratio >= threshold else "<"
    return f"churn {churn_ratio:.2f} {op} {threshold:.2f}"


def rereview_plan(churn_ratio: float, threshold: float) -> list[Dispatch]:
    """Empty below the threshold; exactly one structured reviewer at or above it.

    One, not two, because ADR-007 made a single lens sovereign — the K=2 argument that used to
    force a second dispatch on repair rounds no longer applies. The boundary is inclusive: a
    ratio exactly at the threshold dispatches, so the configured number reads as "this much churn
    is worth re-reviewing" rather than "strictly more than this much".
    """
    reason = rereview_reason(churn_ratio, threshold)
    if churn_ratio < threshold:
        return []
    return [Dispatch(agent="code-reviewer", lens="functionality", reason=reason)]


# ── CLI ──────────────────────────────────────────────────────────────────────

_USAGE = (
    "usage: hm review_consensus <tag|grade|plan|record> …\n"
    "  tag     --file <findings.json>   stamp a `tag` on each finding from its `voices`\n"
    "  grade   --file <findings.json>   grade + counts + human_review_needed\n"
    "  plan    --churn-ratio <r> --threshold <t>\n"
    "  record  --file <findings.json>   assign the disposition column; exit 1 on any gap\n"
)


def _load(path: str) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("findings", [])
    if not isinstance(data, list):
        raise ConsensusError("expected a findings array, or an object with a `findings` key")
    return [x for x in data if isinstance(x, dict)]


def main(argv: list[str] | None = None) -> int:
    guard = command_registry.guard_or_none("review_consensus", argv)
    if guard is not None:
        return guard
    args = list(sys.argv[1:]) if argv is None else list(argv)
    if not args:
        sys.stderr.write(_USAGE)
        return 2
    verb, rest = args[0], args[1:]

    parser = argparse.ArgumentParser(prog=f"hm review_consensus {verb}", add_help=False)
    # `choices` rather than a membership test against a set literal: the command-surface gate
    # extracts the shipped subcommand set from THIS source by AST, and a `not in {...}` guard is
    # invisible to it — the registry would then claim four verbs the scan cannot corroborate.
    parser.add_argument("verb", choices=["tag", "grade", "plan", "record"])
    parser.add_argument("--file")
    parser.add_argument("--churn-ratio", type=float, dest="churn_ratio")
    parser.add_argument("--threshold", type=float)
    try:
        opts = parser.parse_args([verb, *rest])
    except SystemExit:
        sys.stderr.write(_USAGE)
        return 2

    try:
        if verb == "plan":
            if opts.churn_ratio is None or opts.threshold is None:
                sys.stderr.write("plan needs --churn-ratio and --threshold\n")
                return 2
            plan = rereview_plan(opts.churn_ratio, opts.threshold)
            payload: dict[str, Any] = {
                "dispatches": [vars(d) for d in plan],
                "reason": rereview_reason(opts.churn_ratio, opts.threshold),
            }
        else:
            if not opts.file:
                sys.stderr.write(f"{verb} needs --file\n")
                return 2
            findings = _load(opts.file)
            if verb == "tag":
                payload = {
                    "findings": [
                        {**f, "tag": tag_finding(list(f.get("voices", [])))} for f in findings
                    ]
                }
            elif verb == "grade":
                payload = grade_from_findings(findings)
            else:
                record = build_round_record(findings)
                payload = {"findings": record.findings, "errors": record.errors}
    except (ConsensusError, OSError, ValueError) as exc:
        sys.stderr.write(f"review_consensus: {exc}\n")
        return 2

    sys.stdout.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
    if verb == "record" and payload.get("errors"):
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
