"""Estimate verifier discrimination from the ledgers this harness already writes (F3).

*Verify, Repair, Repeat, Stop* (arXiv 2607.17641) reports that whether an iterative loop stops
at the right moment is governed by the **verifier's discrimination** and the **decision margin**,
not by how large the estimation error is in absolute terms. This harness computes neither, while
running a fixed round cap and a `k-of-2` consensus that both presuppose a verifier good enough to
trust. The labels needed to start estimating already exist in
``.claude/observability/second-opinion.jsonl`` — this module is the reader, not new telemetry.

**What can honestly be computed here, and what cannot.**

The PIDA gate labels each disputed cross-model finding `accepted` / `rejected` / `duplicate` /
`unresolved` after running targeted `pytest` / `ruff` / `mypy` at the paths the finding names.
That makes the label *oracle-informed*, which is more than a self-report — but it is not ground
truth about the code:

- ``rejected`` — the oracle contradicted the claim. Informative: a proposer false positive.
- ``unresolved`` — **no oracle was available**. This is the number VRR-Stop's argument is about,
  and the one nothing in this repository has ever surfaced: the share of disputes the verifier
  could not decide. A high value means the loop's stopping decisions rest on a verifier that is
  abstaining, which no round cap can compensate for.
- ``accepted`` — the oracle was consistent with the claim. **This does NOT establish that the
  finding was a real defect**, so an "accept rate" is not a true-positive rate and is not
  reported as one. Reading it that way is the same conflation this module exists to avoid.
- ``duplicate`` — a bookkeeping outcome; it says nothing about either party.

A true false-acceptance rate needs labelled ground truth (a fixture corpus with known defects).
That corpus does not exist here, so ``false_acceptance_rate`` is deliberately absent rather than
approximated — an approximation would be indistinguishable from the real thing at the call site.

**Invocation health** is reported per model with the denominator CLAUDE.md fixes:
``(skipped + failed) / total`` over **call rows only**, excluding ``stage: "health"``.
Two row kinds share this file — ``finding_ref == "n/a"`` is one row per invocation, anything
else is one row per finding disposition — so counting them together inflates the denominator by
the number of findings. Measured 2026-08-06: an aggregate that dropped ``failed`` reported 10.3%
where the truth was 20.7%, and the per-model split was 2.4% against 37.8%.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness_maker import command_registry, ledger_exclusions
from harness_maker.stage_agent_ledger import DISPATCH_SENTINELS

DEFAULT_LEDGER = Path(".claude/observability/second-opinion.jsonl")
DEFAULT_REVIEW_GLOB = "review-*.jsonl"
DEFAULT_AGENT_GLOB = "stage-agents*.jsonl"

#: The exclusions filename and its schema live in ``ledger_exclusions`` — this module used to
#: declare its own copy alongside a comment documenting the RETIRED ``{"<run-id>": "<why>"}``
#: map as authoritative, while SPEC and PLAN both pointed readers here as "the only exclusion
#: reader". Someone routed here would have written the map form, which the second-opinion
#: ledger's rows (no ``run_id`` field at all) can never match — silently. Two names for one
#: file, one of them describing a schema that no longer holds, is worse than no comment.

#: Below this many episodes a 0% release rate is small-sample noise, not a property of the gate.
_DEGENERATE_MIN_EPISODES = 5
DEFAULT_OBSERVABILITY = Path(".claude/observability")

#: Rows from the health smoke are structurally biased toward `invoked` — it runs in the base
#: repo on a trivial prompt — so including them makes every model look healthier than it is.
_EXCLUDED_STAGES = frozenset({"health"})

#: The sentinel that marks a row as an INVOCATION record rather than a per-finding disposition.
_CALL_ROW = "n/a"

DISPOSITIONS = ("accepted", "rejected", "duplicate", "unresolved")


@dataclass(frozen=True)
class ModelStats:
    """Per-model view. Absent fields are absent because they are not computable, not zero."""

    model: str
    calls: int
    invoked: int
    skipped: int
    failed: int
    dispositions: dict[str, int] = field(default_factory=dict)

    @property
    def loss_rate(self) -> float | None:
        """(skipped + failed) / calls — the share of invocations that produced no usable voice.

        ``failed`` is inside the numerator on purpose: the CLI ran, but Step 4 could not eat the
        payload, so that model had no voice in the round. From the consensus filter's point of
        view that is identical to a skip, and separating them lets a healthy model dilute a
        broken one.
        """
        return (self.skipped + self.failed) / self.calls if self.calls else None

    @property
    def judged(self) -> int:
        return sum(self.dispositions.get(d, 0) for d in DISPOSITIONS)

    @property
    def unresolved_rate(self) -> float | None:
        """Share of disputed findings the verifier could not decide — VRR-Stop's quantity.

        None when nothing was judged: with no disputes there is no evidence about the verifier,
        and reporting 0.0 would read as "the verifier decided everything".
        """
        if not self.judged:
            return None
        return self.dispositions.get("unresolved", 0) / self.judged

    @property
    def refutation_rate(self) -> float | None:
        """Share of judged findings the oracle contradicted. Not a verifier error rate.

        It mixes two causes that this ledger cannot separate: a proposer that claims defects
        that are not there, and an oracle that is too weak to confirm ones that are.
        """
        if not self.judged:
            return None
        return self.dispositions.get("rejected", 0) / self.judged


def read_rows(path: Path) -> list[dict[str, Any]]:
    """Parse the ledger, skipping unparseable lines rather than aborting the whole read.

    An append-only JSONL written by concurrent sessions can carry a torn line; refusing to
    report anything because of one is worse than reporting the rest.
    """
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def load_exclusions(observability_dir: Path) -> list[ledger_exclusions.Exclusion]:
    """Delegates to the ONE reader (ADR-007). Kept as a name so call sites read the same.

    The body used to live here and returned a run-id map, which the second-opinion ledger
    could not use at all — its rows have no `run_id` field. Loudness and the deliberate
    fail-open are documented at `ledger_exclusions.load`, which owns them; this must stay a
    delegation, not a copy, or the two ledgers drift apart one branch at a time.
    """
    return ledger_exclusions.load(observability_dir)


def agent_rounds(observability_dir: Path) -> dict[str, Any]:
    """Per-cap round behaviour for the reviewer and validator gates (F4's real question here).

    Each `(agent, slug, run_id)` is one gate episode; the verdicts ordered by pass number are
    its round sequence. Two things are worth separating, and a single "pass rate" hides both:

    - **released** — the episode reached a clean verdict. The cap paid for itself.
    - **bound** — the last pass was still unclean, so the cap stopped the loop rather than the
      loop converging. A cap that is *always* bound is not a budget; it is a formality, and
      raising it is the wrong response until you know whether the verifier ever accepts.
    """
    exclusions = load_exclusions(observability_dir)
    conflicts: list[dict[str, Any]] = []
    episodes: dict[tuple[str, str, str, str], dict[int, str]] = {}
    for path in sorted(observability_dir.glob(DEFAULT_AGENT_GLOB)):
        for row in read_rows(path):
            run_id = str(row.get("run_id"))
            if ledger_exclusions.is_excluded(row, exclusions):
                continue
            # All FOUR fields. `stage_agent_ledger.check_run_coherence` states the rule and
            # the reason: `run_id` is chosen by the model and nothing enforces uniqueness, so
            # an id reused across stages merged independent episodes and produced fabricated
            # rates. Keying on three re-introduced exactly that.
            key = (
                str(row.get("agent")),
                str(row.get("stage")),
                str(row.get("slug")),
                run_id,
            )
            attempt = row.get("pass_or_attempt")
            if not isinstance(attempt, int):
                continue
            verdict = str(row.get("verdict"))
            seen = episodes.setdefault(key, {})
            if attempt in seen and seen[attempt] != verdict:
                # Append-only with no retract verb: a second row for the same
                # (agent, stage, slug, run, pass) is a CONFLICT, not an update. Silently
                # letting the later one win would rewrite a recorded FAIL into a PASS and move
                # historical release rates. First write wins; the conflict is surfaced.
                conflicts.append(
                    {"key": list(key), "pass": attempt, "kept": seen[attempt], "ignored": verdict}
                )
                continue
            seen[attempt] = verdict

    clean = {"PASS", "APPROVED", "NO_REVISION"}
    out: dict[str, Any] = {}
    for agent in sorted({k[0] for k in episodes}):
        mine = {k: v for k, v in episodes.items() if k[0] == agent}
        released = bound = never_dispatched = 0
        multi = 0
        for verdicts in mine.values():
            order = [verdicts[p] for p in sorted(verdicts)]
            if len(order) > 1:
                multi += 1
            # Classify on the last NON-sentinel verdict. Using `order[-1]` alone dropped a
            # whole episode from the denominator when only its LAST pass failed to launch —
            # `PASS` then `dispatch-failed` read as "never dispatched", silently deflating the
            # sample. An episode is only truly never-dispatched when every pass is a sentinel.
            real = [v for v in order if v not in DISPATCH_SENTINELS]
            if not real:
                # The agent never ran, so the episode says nothing about the verifier. Counting
                # it as `bound` blames verifier strictness for a launch failure — and with ≥5
                # of them the zero-release warning would fire over episodes that produced no
                # findings at all. `stage_agent_ledger` excludes these from its own rate.
                never_dispatched += 1
            elif real[-1] in clean:
                released += 1
            else:
                bound += 1
        judged_episodes = released + bound
        out[agent] = {
            "episodes": len(mine),
            "multi_pass_episodes": multi,
            "released": released,
            "bound_by_the_cap": bound,
            "never_dispatched": never_dispatched,
            "release_rate": released / judged_episodes if judged_episodes else None,
        }
    degenerate = [
        name
        for name, s in out.items()
        if (s["released"] + s["bound_by_the_cap"]) >= _DEGENERATE_MIN_EPISODES
        and s["release_rate"] == 0.0
    ]
    return {
        "agents": out,
        "conflicting_rows": conflicts,
        "degenerate_gates": degenerate,
        # Kept under its historical name and shape for compatibility with its one reader.
        # It is LOSSY by construction: a slug entry and a stage entry sharing a value
        # collapse to one line, and the `key` that distinguished them is gone. `exclusions`
        # below is the honest record — this field is the compatible one.
        "excluded_run_ids": {e.value: e.reason for e in exclusions},
        "exclusions": [{"key": e.key, "value": e.value, "reason": e.reason} for e in exclusions],
        "note": (
            "`bound_by_the_cap` counts episodes whose final pass was still unclean. A "
            "release_rate of 0 is NOT by itself evidence about the verifier: it is equally "
            "consistent with an unreachable threshold and with an input population that "
            "genuinely fails every time. Measured here, plan-validator's was the second — its "
            "blocking findings were source-verified and held. Raising the cap answers neither."
        ),
    }


def analyse(rows: list[dict[str, Any]]) -> dict[str, ModelStats]:
    """Split the two row kinds, then aggregate each per model."""
    eligible = [r for r in rows if r.get("stage") not in _EXCLUDED_STAGES]
    models = sorted({str(r.get("model", "unknown")) for r in eligible})

    out: dict[str, ModelStats] = {}
    for model in models:
        mine = [r for r in eligible if str(r.get("model", "unknown")) == model]
        calls = [r for r in mine if r.get("finding_ref", _CALL_ROW) == _CALL_ROW]
        findings = [r for r in mine if r.get("finding_ref", _CALL_ROW) != _CALL_ROW]
        status = Counter(str(r.get("status")) for r in calls)
        out[model] = ModelStats(
            model=model,
            calls=len(calls),
            invoked=status.get("invoked", 0),
            skipped=status.get("skipped", 0),
            failed=status.get("failed", 0),
            dispositions=dict(Counter(str(r.get("disposition")) for r in findings)),
        )
    return out


def to_payload(
    stats: dict[str, ModelStats],
    exclusions: Sequence[ledger_exclusions.Exclusion] = (),
    *,
    dropped_n: int = 0,
) -> dict[str, Any]:
    """JSON view. `false_acceptance_rate` is absent by design — see the module docstring.

    ``exclusions``/``dropped_n`` are published because this report started filtering rows for
    the first time. Before ADR-007 the filter keyed on ``run_id``, which second-opinion rows
    do not have, so it was a guaranteed no-op; now one line in a gitignored file can remove a
    whole stage from the denominator and the payload would still read clean. A suppression
    control whose output does not say what it suppressed is the same silent bias the
    exclusions mechanism exists to remove, one function away.
    """
    return {
        "exclusions": {
            "applied": [{"key": e.key, "value": e.value, "reason": e.reason} for e in exclusions],
            "rows_dropped": dropped_n,
        },
        "models": {
            name: {
                "calls": s.calls,
                "invoked": s.invoked,
                "skipped": s.skipped,
                "failed": s.failed,
                "loss_rate": s.loss_rate,
                "judged": s.judged,
                "dispositions": {d: s.dispositions.get(d, 0) for d in DISPOSITIONS},
                "unresolved_rate": s.unresolved_rate,
                "refutation_rate": s.refutation_rate,
            }
            for name, s in stats.items()
        },
        "not_computable": {
            "false_acceptance_rate": (
                "needs labelled ground truth (a corpus of known defects); an `accepted` "
                "disposition means the oracle did not contradict the claim, not that the "
                "finding was real"
            ),
            "false_rejection_rate": (
                "same reason, and `rejected` additionally conflates a wrong claim with an "
                "oracle too weak to confirm a right one"
            ),
        },
    }


def marginal_gain(observability_dir: Path) -> dict[str, Any]:
    """Round-to-round marginal gain, the input a stopping rule would need (F4).

    ``consensus_passed_n`` per round is the gain that round produced. A *sign test* — stop when
    the gain stops being positive — is what VRR-Stop proposes in place of a fixed cap, and it
    needs only the SIGN to be identifiable, not the magnitude.

    So this reports the transition signs **and the counterexamples**: rounds whose gain was zero
    and whose successor was productive. Each of those is a finding a first-zero stop would have
    missed, and they are the only evidence that can refute the rule. Reporting the trend without
    them would make the rule look free.
    """
    exclusions = load_exclusions(observability_dir)
    per_slug: dict[str, dict[int, int]] = {}
    for path in sorted(observability_dir.glob(DEFAULT_REVIEW_GLOB)):
        for row in read_rows(path):
            if ledger_exclusions.is_excluded(row, exclusions):
                continue
            slug = str(row.get("slug"))
            rnd = row.get("round")
            if not isinstance(rnd, int):
                continue
            gain = row.get("consensus_passed_n") or 0
            # A slug+round can repeat when /hm:review is re-invoked; keep the largest, which is
            # the most favourable reading for the stopping rule under test.
            per_slug.setdefault(slug, {})[rnd] = max(per_slug.get(slug, {}).get(rnd, 0), int(gain))

    multi = {s: v for s, v in per_slug.items() if len(v) > 1}
    increase = flat = decrease = 0
    revivals: list[dict[str, Any]] = []
    for slug, gains in multi.items():
        rounds = sorted(gains)
        for a, b in zip(rounds, rounds[1:], strict=False):
            if gains[b] > gains[a]:
                increase += 1
            elif gains[b] == gains[a]:
                flat += 1
            else:
                decrease += 1
            if gains[a] == 0 and gains[b] > 0:
                revivals.append({"slug": slug, "zero_round": a, "next_round": b, "gain": gains[b]})

    transitions = increase + flat + decrease
    return {
        "slugs_with_multiple_rounds": len(multi),
        "transitions": transitions,
        "increase": increase,
        "flat": flat,
        "decrease": decrease,
        "revivals": revivals,
        "findings_a_first_zero_stop_would_miss": sum(int(r["gain"]) for r in revivals),
        "note": (
            "A sign test needs the sign to be identifiable. With this few transitions one "
            "counterexample moves the estimated miss rate across most of its range, so the "
            "sign is not identified and no cap is changed on this evidence. For the reviewer "
            "and validator caps use `agents`, which reads stage-agents.jsonl — an earlier "
            "draft of this field claimed those caps emitted nothing, which was false and had "
            "never been checked."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``hm verifier_discrimination report|rounds``."""
    guard = command_registry.guard_or_none("verifier_discrimination", argv)
    if guard is not None:
        return guard
    args = list(sys.argv[1:]) if argv is None else list(argv)
    # Spelled as an explicit per-verb comparison, not a set membership test: the T-C2 parity
    # gate source-scans manual-dispatch modules for `args[0] != "<verb>"` / `== "<verb>"`, and a
    # set literal hides both verbs from it — the registry then claims subcommands the scan
    # cannot find, which is the drift the gate exists to catch.
    if not args or (args[0] != "report" and args[0] != "rounds" and args[0] != "agents"):
        sys.stderr.write(
            "usage: hm verifier_discrimination report [--ledger <path>]\n"
            "       hm verifier_discrimination rounds [--observability-dir <path>]\n"
            "       hm verifier_discrimination agents [--observability-dir <path>]\n"
        )
        return 2

    if args[0] == "agents":
        aparser = argparse.ArgumentParser(prog="hm verifier_discrimination agents", add_help=False)
        aparser.add_argument("--observability-dir", type=Path, default=DEFAULT_OBSERVABILITY)
        try:
            aopts = aparser.parse_args(args[1:])
        except SystemExit:
            return 2
        payload = agent_rounds(aopts.observability_dir)
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        for name in payload["degenerate_gates"]:
            stats = payload["agents"][name]
            sys.stderr.write(
                f"[zero-release gate] {name}: 0 of "
                f"{stats['released'] + stats['bound_by_the_cap']} judged episodes reached a "
                "clean verdict. This has TWO readings and the ledger cannot tell them apart: "
                "the clean threshold is unreachable, or every input genuinely failed. They call "
                "for opposite responses, so read the episodes' recorded critiques and ask "
                "whether the blocking findings were verified against source — do not re-tune "
                "the threshold on this number alone.\n"
            )
        return 0 if payload["agents"] else 1

    if args[0] == "rounds":
        rparser = argparse.ArgumentParser(prog="hm verifier_discrimination rounds", add_help=False)
        rparser.add_argument("--observability-dir", type=Path, default=DEFAULT_OBSERVABILITY)
        try:
            ropts = rparser.parse_args(args[1:])
        except SystemExit:
            return 2
        payload = marginal_gain(ropts.observability_dir)
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return 0 if payload["transitions"] else 1

    parser = argparse.ArgumentParser(prog="hm verifier_discrimination report", add_help=False)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    try:
        opts = parser.parse_args(args[1:])
    except SystemExit:
        return 2

    rows = read_rows(opts.ledger)
    # The exclusions file says these rows "must not enter ANY aggregate"; honouring it only in
    # `agents` made that false for `report`, which is where the loss-rate lives.
    exclusions = load_exclusions(opts.ledger.parent)
    total = len(rows)
    if exclusions:
        rows = [r for r in rows if not ledger_exclusions.is_excluded(r, exclusions)]
    dropped = total - len(rows)
    if not rows:
        if total:
            # An intact, full ledger emptied by an over-broad predicate is a CONFIGURATION
            # problem, and the absence-of-evidence line points the operator at the wrong
            # file. Naming the exclusions file is the difference between a five-minute fix
            # and an investigation of a ledger that turns out to be fine.
            sys.stderr.write(
                f"verifier_discrimination: all {total} row(s) at {opts.ledger} were excluded "
                f"by {ledger_exclusions.EXCLUSIONS_FILE} — nothing left to report. The ledger "
                "is intact; the exclusion set is too broad.\n"
            )
        else:
            sys.stderr.write(
                f"verifier_discrimination: no rows at {opts.ledger} — nothing to report. "
                "This is not a clean bill of health; it is an absence of evidence.\n"
            )
        return 1
    payload = to_payload(analyse(rows), exclusions, dropped_n=dropped)
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
