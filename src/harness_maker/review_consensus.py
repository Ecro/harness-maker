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
from harness_maker.codex_ledger import DISPOSITION_VALUES
from harness_maker.io_utils import atomic_write

Tag = Literal["consensus-passed", "weak-consensus", "manual-only"]

#: The closed tag vocabulary. `grade_from_findings` checks membership rather than testing for
#: one value, so an ABSENT tag is distinguishable from `manual-only` — the distinction the
#: fail-open defect turned on.
_TAGS: frozenset[str] = frozenset({"consensus-passed", "weak-consensus", "manual-only"})
Disposition = Literal["accepted", "rejected", "duplicate", "unresolved"]

#: The four PIDA values, IMPORTED from the ledger rather than restated. The previous comment
#: claimed this was "shared with the cross-model gate so the rejection rate cannot silently split
#: between two producers" while being a third independent literal — a comment asserting a single
#: source of truth is what stops the next reader from checking whether there is one.
DISPOSITIONS: frozenset[str] = DISPOSITION_VALUES

#: The authority a finding may be rejected against, and the one that means "there was none".
#: `no-contract` is not an authority — it is the recorded absence of one, which is why it is
#: valid on `unresolved` and invalid on `rejected`.
NO_CONTRACT = "no-contract"

#: The closed severity vocabulary. Checked by membership, so an off-vocabulary value ("critical",
#: "p0", "P0 (blocker)") is DISTINGUISHABLE from a low one rather than falling through the count
#: silently — measured 2026-08-16: three `consensus-passed` findings at `severity: "critical"`
#: graded `A` with zero errors and exit 0, which is the same fail-open that the `tag` column had,
#: one field over and on the field that actually moves the letter.
_SEVERITIES: tuple[str, ...] = ("P0", "P1", "P2", "P3")

#: Severities that can move the grade or raise the human-review flag. P2/P3 never do — that is
#: the pre-change behaviour, and it is what makes a nine-lens fan-out affordable at all: the
#: low-importance half of the axis lands at P2 and is recorded rather than blocking.
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
    `security` to second a `consistency` finding is a category error rather than a quality bar; two
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
    exactly one category raised, so demoting them to `manual-only` would spend every dispatch
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
        # `manual-only`, not a raise. The stage PRODUCES voice-less findings by design: Step 4d
        # tells the model to leave an `unresolved` cross-model finding's voices out of the array,
        # while Step 4e requires every finding to carry a disposition — so it must stay in the
        # file. Raising made one such entry abort the whole batch with exit 2 and no output,
        # which then fed an untagged file straight into `grade`. `manual-only` is also the tag
        # the skill already specifies for that class, so this is the documented outcome rather
        # than a new leniency.
        return "manual-only"
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


def grade_effect(
    severity: str,
    disposition: object,
    authority: object = None,
    *,
    authority_verified: bool = False,
) -> dict[str, bool]:
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
        # An AC citation clears the grade only once `record --spec` VERIFIED that the id exists.
        # Shape alone is not a contract — `AC-999` parses exactly like `AC-004` — and the check
        # has to survive `grade` being run on its own.
        if _authority_kind(authority) == "ac" and authority_verified:
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
        if item.get("hm_downgraded"):
            # Re-report a gap this verb already papered over. `record` writes the downgrade and
            # THEN exits 1, so a second run read `unresolved`/`no-contract`, found it valid, and
            # exited 0 with an empty error list — the cheapest response to a red exit code turned
            # the instruction green with the gap intact.
            errors.append(
                f"{item.get('id', i)}: still carries a downgraded disposition from an earlier "
                "round — the original disposition was never supplied"
            )
            out.append(item)
            continue
        if disposition is None:
            errors.append(f"{item.get('id', i)}: no disposition — recorded unresolved")
            item["disposition"], item["authority"] = "unresolved", NO_CONTRACT
            item["hm_downgraded"] = True
        elif not validate_disposition(disposition, authority):
            errors.append(
                f"{item.get('id', i)}: {disposition!r} with authority {authority!r} is not "
                "recordable — downgraded to unresolved"
            )
            item["disposition"], item["authority"] = "unresolved", NO_CONTRACT
            item["hm_downgraded"] = True
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

    **An untagged finding is an ERROR, never a skip.** This used to `continue` past a finding
    whose `tag` key was absent, which made the whole function fail OPEN: the stage runs `tag`,
    `record` and `grade` against one temp path, the first two print to stdout, and if their
    output is not merged back then `grade` sees an array with no `tag` on anything — every
    finding skipped, counts all zero, grade `A`, `human_review_needed` false. Measured on
    2026-08-16: three consensus-passed P0s graded `A`. That is the exact defect this module was
    written to make impossible, reintroduced one layer up, so the absent case is now reported
    and the caller is expected to exit non-zero on it.
    """
    counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    human_review_needed = False
    errors: list[str] = []
    for i, raw in enumerate(findings):
        severity = str(raw.get("severity", ""))
        tag = raw.get("tag")
        if severity not in _SEVERITIES:
            # Fail CLOSED on the field that decides the letter. The previous `if severity in
            # counts` guard incremented nothing for an off-vocabulary value, so the finding was
            # graded as if it did not exist — while the untagged branch's message claimed it was
            # "counted as severe".
            errors.append(
                f"{raw.get('id', i)}: severity is {severity!r}, not one of "
                f"{list(_SEVERITIES)} — counted as P0"
            )
            counts["P0"] += 1
            human_review_needed = True
            continue
        if tag not in _TAGS:
            # Fail CLOSED: an unknown tag counts at its own severity and raises the flag, so a
            # lost tag column can only ever make the grade worse than the truth.
            errors.append(
                f"{raw.get('id', i)}: tag is {tag!r}, not one of {sorted(_TAGS)} — counted as "
                f"{severity}. Did the `tag` verb's output get written back to this file?"
            )
            counts[severity] += 1
            human_review_needed = True
            continue
        effect = grade_effect(
            severity,
            raw.get("disposition"),
            raw.get("authority"),
            authority_verified=bool(raw.get("authority_verified", False)),
        )
        if effect["human_review_needed"] and tag == "consensus-passed":
            human_review_needed = True
        if tag in {"manual-only", "weak-consensus"} and severity in _SEVERE:
            human_review_needed = True
        if tag != "consensus-passed" or not effect["counted"]:
            continue
        counts[severity] += 1
    grade = compute_grade(
        p0_count=counts["P0"],
        p1_count=counts["P1"],
        p2_count=counts["P2"],
        p3_count=counts["P3"],
    )
    return {
        "grade": grade,
        "counts": counts,
        "human_review_needed": human_review_needed,
        "errors": errors,
    }


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
    "  tag     --file <f> [--out <f>]  stamp a `tag` on each finding from its `voices`\n"
    "  record  --file <f> [--out <f>] [--spec <machine.yaml>]  disposition column + AC\n"
    "                                   citation verification; exit 1 on any gap\n"
    "  grade   --file <f>              grade + counts + human_review_needed (read-only)\n"
    "  plan    --churn-ratio <r> --threshold <t>\n"
    "\n"
    "  --out defaults to --file: `tag` and `record` rewrite the file IN PLACE, so the three\n"
    "  verbs chain over one path without the caller having to merge stdout back by hand.\n"
    "  --spec turns AC-cited rejections into VERIFIED ones, stamping `authority_verified` so the\n"
    "  verdict survives into the file `grade` reads; without it none can clear the grade.\n"
)


def _known_ac_ids(spec_path: str | None) -> tuple[frozenset[str] | None, list[str]]:
    """AC ids the machine SPEC actually declares, or None when no SPEC was supplied.

    Only an AC-cited rejection clears a finding from the grade, and `_authority_kind` can only
    check the SHAPE of the citation — `AC-999` parses exactly like `AC-004`. Measured
    2026-08-16: a P0 rejected against `AC-999`, an id in no SPEC, came back
    `{counted: false, human_review_needed: false}`. Citing a contract that does not exist is
    typing a string, not citing a contract, and ADR-002's whole claim is that clearing a P0
    requires an INDEPENDENT one.
    """
    if not spec_path:
        return None, []
    import yaml

    try:
        raw = yaml.safe_load(Path(spec_path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        # DEGRADE, do not abort. Raising made the whole verb exit 2 with no payload on every
        # harness that has no machine SPEC — a first-class `dev_mode` — so the review's sole
        # grade producer was unrunnable there and the gate had no letter to branch on. Worse, the
        # `known is None` branch below exists precisely for the absent case and was unreachable
        # from the only call site that ships. `None` is already the fail-closed value: nothing
        # can be verified, so no AC-cited rejection clears.
        return None, [f"machine SPEC {spec_path!r} unreadable ({type(exc).__name__}): {exc}"]
    if not isinstance(raw, dict) or not isinstance(raw.get("ac"), list):
        return None, [f"machine SPEC {spec_path!r} has no `ac` list — no AC citation can clear"]
    acs = raw["ac"]
    return (
        frozenset(
            str(a["id"]) for a in acs if isinstance(a, dict) and isinstance(a.get("id"), str)
        ),
        [],
    )


def _verify_ac_citations(findings: list[dict[str, Any]], known: frozenset[str] | None) -> list[str]:
    """Stamp `authority_verified` on every rejection, and report the ones that fail.

    The verdict is RECORDED, not recomputed by whoever happens to ask. `grade` used to do this
    itself and then discard the result: it downgraded an unverifiable `AC-999` in memory, counted
    the finding, printed the error and exited — leaving the file, the disposition ledger and the
    REVIEW report all still saying `rejected` / `AC-999`. The documented remedy ("fix the listed
    entries and re-run") could not terminate, because nothing the CLI did changed the file.

    Recording it also makes the check ORDER-INDEPENDENT. `grade` clears a rejection only when the
    finding carries `authority_verified: true`, so running `grade` on its own — with `record`
    never having verified anything — cannot launder a P0 through an AC id that exists nowhere.

    Fail-closed both ways: with no usable SPEC (`known is None`) nothing can be verified, so
    nothing clears; with one, an id outside it becomes `unresolved` / `no-contract`, which counts
    toward the grade and raises the human-review flag.
    """
    errors: list[str] = []
    for i, f in enumerate(findings):
        if f.get("disposition") != "rejected":
            f.pop("authority_verified", None)
            continue
        authority = f.get("authority")
        if _authority_kind(authority) != "ac":
            # A docstring citation is valid but never clears the grade, so there is no id to check.
            f["authority_verified"] = False
            continue
        ident = str(authority).split()[0].upper()
        if known is None:
            errors.append(
                f"{f.get('id', i)}: rejected against {ident} but no usable machine SPEC was "
                "given, so the citation cannot be verified — recorded unresolved"
            )
        elif ident not in known:
            errors.append(
                f"{f.get('id', i)}: rejected against {ident}, which the machine SPEC does not "
                "declare — recorded unresolved"
            )
        else:
            f["authority_verified"] = True
            continue
        f["disposition"], f["authority"] = "unresolved", NO_CONTRACT
        f["authority_verified"] = False
    return errors


def _load(path: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """The findings list, plus the envelope it arrived in (None for a bare array).

    Returning the envelope is not a convenience: `_write_findings` rewrites this same path, so
    dropping the sibling keys of a `{"findings": [...], "round": 2, "run_id": "x"}` payload would
    destroy them on the first `tag`.

    A dict **without** a `findings` key raises. It used to `.get("findings", [])` — which, once
    the write-back landed, meant `tag --file <any JSON object>` silently replaced that file's
    contents with `[]` at exit 0, and a subsequent `grade` returned `A` over the wreckage.
    Measured 2026-08-16 against a settings-shaped file. `codex_adapter.stamp_ids` already refuses
    exactly this ("a bare record, not an empty batch"); this is the same refusal, and the path is
    model-substituted out of template prose, so leniency here is destruction.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    envelope: dict[str, Any] | None = None
    if isinstance(data, dict):
        if "findings" not in data:
            raise ConsensusError(
                f"{path}: JSON object has no `findings` key — refusing to treat it as an empty "
                "batch, because this verb rewrites the file it reads"
            )
        envelope = {k: v for k, v in data.items() if k != "findings"}
        data = data["findings"]
    if not isinstance(data, list):
        raise ConsensusError("expected a findings array, or an object with a `findings` key")
    for i, x in enumerate(data):
        # Loud, not lenient — matching `build_round_record`. Dropping a malformed entry made a
        # finding vanish before the disposition column was assigned, which satisfies AC-006's
        # completeness invariant trivially by not existing.
        if not isinstance(x, dict):
            raise ConsensusError(f"finding {i} must be a mapping, got {type(x).__name__}")
    return list(data), envelope


def _write_findings(
    path: str, findings: list[dict[str, Any]], envelope: dict[str, Any] | None = None
) -> None:
    """Persist the enriched column so the NEXT verb can read it.

    `tag` and `record` used to print to stdout only, while the rendered stage passed one temp
    path to all three verbs — so `grade` re-read the original array and saw no `tag` on anything.
    Writing in place is what makes the documented `tag → record → grade` chain actually chain.
    """
    payload: object = findings if envelope is None else {**envelope, "findings": findings}
    atomic_write(Path(path), json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


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
    parser.add_argument(
        "--out",
        help="where to write the enriched findings; defaults to --file (in-place)",
    )
    parser.add_argument(
        "--spec",
        help="machine SPEC whose `ac` ids an AC-cited rejection must name to clear the grade",
    )
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
            findings, envelope = _load(opts.file)
            if verb == "tag":
                tagged = [
                    {
                        **f,
                        "tag": tag_finding(
                            list(f.get("voices", [])),
                            reasoning_diverges=bool(f.get("reasoning_diverges", False)),
                        ),
                    }
                    for f in findings
                ]
                payload = {"findings": tagged}
                _write_findings(opts.out or opts.file, tagged, envelope)
            elif verb == "grade":
                payload = grade_from_findings(findings)
            else:
                known, spec_errors = _known_ac_ids(opts.spec)
                record = build_round_record(findings)
                ac_errors = _verify_ac_citations(record.findings, known)
                payload = {
                    "findings": record.findings,
                    "errors": spec_errors + ac_errors + record.errors,
                }
                _write_findings(opts.out or opts.file, record.findings, envelope)
    except (ConsensusError, OSError, ValueError) as exc:
        sys.stderr.write(f"review_consensus: {exc}\n")
        return 2

    sys.stdout.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
    if verb in {"record", "grade"} and payload.get("errors"):
        # `grade` exits 1 on any error too, because its errors are exactly the cases where the
        # printed letter is not trustworthy — a lost tag column, or a rejection citing an AC that
        # cannot be verified. A silent zero exit next to a cheerful "A" is the shape of the
        # defect this whole change is repairing.
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
