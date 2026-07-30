"""Second-opinion finding -> reviewer-finding adapter (PLAN-crossmodel-codex-gaps ADR-001 /
Phase 4a, generalized to multi-vendor by PLAN-second-opinion-multi-model ADR-011).

Normalizes a Codex or Antigravity finding (``second-opinion-finding.schema.json`` shape) into
the reviewer-finding shape the ``/hm:review`` Step 4 consensus filter consumes, so either
vendor can be a real k-of-N voter. Two normalizations are load-bearing (both flagged by
plan-validator):
- **severity vocabulary** — the shared ``info/low/medium/high/critical`` request vocabulary
  (ADR-004) maps to reviewer ``P0..P3``, else Step 4a's "same severity tier" predicate rejects
  every second-opinion finding.
- **null location** — when ``file``/``line`` is null, set ``needs_relaxation`` so the Step 4
  filter applies the symbol/message-similarity surface-match fallback (prose half, P4b).

Codex's output is schema-enforced (``codex exec --output-schema``) so ``adapt_codex_finding``
trusts direct ``json.loads``. Antigravity (``agy``) has no equivalent CLI-level enforcement,
so ``adapt_antigravity_finding``'s payload extraction is deliberately tolerant of markdown
fences and adversarial/malformed output, and FAILS CLOSED (raises) rather than guessing among
ambiguous candidates — the caller (the rendered Bash recipe) turns that failure into a
``status: "failed"`` ledger row, never a crash of the dispatch loop.
"""

from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

from harness_maker import command_registry

# critical->P0, high->P1, medium->P2, low/info->P3 (ADR-001, validator pass-2 critical).
# Shared across both vendors (ADR-004 — antigravity reuses the Codex request vocabulary).
_SEVERITY_TO_PTIER: dict[str, str] = {
    "critical": "P0",
    "high": "P1",
    "medium": "P2",
    "low": "P3",
    "info": "P3",
}


def map_severity(severity: str) -> str:
    """Map a second-opinion severity enum value (shared vocabulary) to a reviewer P-tier."""
    key = severity.strip().lower()
    try:
        return _SEVERITY_TO_PTIER[key]
    except KeyError:
        raise ValueError(f"unknown second-opinion severity: {severity!r}") from None


def finding_id(source: str, file: str | None, line: int | None, message: str) -> str:
    """Derive the immutable identity of a finding from its ORIGINAL location + message.

    WHY this exists rather than keying on ``file:line:summary`` directly: all three move
    when a fix round edits the code, and the id is the lifecycle key, the REVIEW frozen-set
    join key, and the ledger ``finding_ref`` at once — so a shifting key would retire the
    wrong record and mis-attribute a ledger row. Computing it once at adaptation freezes
    it against every later mutation.
    """
    payload = json.dumps([source, file, line, message], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _disambiguate(adapted: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Give colliding ids a batch-scoped occurrence suffix (ADR-002 rule 4).

    A null-location finding has ``file``/``line`` both None, so its identity reduces to
    (source, message) and two such findings from one model can collide. Merging them would
    drop a lifecycle record and let one ``finding_ref`` carry two ledger rows, so the
    suffix is mandatory — but it fires ONLY on a real collision, because applying it
    unconditionally would make an id depend on its position in the batch.
    """
    seen: dict[str, int] = {}
    for finding in adapted:
        base = str(finding["id"])
        count = seen.get(base, 0) + 1
        seen[base] = count
        if count > 1:
            finding["id"] = f"{base}-{count}"
    return adapted


def adapt_codex_finding(finding: dict[str, Any]) -> dict[str, Any]:
    """Adapt one Codex finding into a reviewer-shaped finding for the Step 4 filter.

    ``needs_relaxation`` is True when ``file`` or ``line`` is null — the signal for the
    consensus filter to fall back to symbol/message-similarity for surface-match
    candidacy (Codex findings often omit a precise location).
    """
    file = finding.get("file")
    line = finding.get("line")
    message = finding.get("message", "")
    return {
        "id": finding_id("codex", file, line, message),
        "severity": map_severity(finding["severity"]),
        "file": file,
        "line": line,
        "summary": message,
        "evidence": finding.get("evidence"),
        "source": "codex",
        "needs_relaxation": file is None or line is None,
    }


def adapt_finding_list(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    """Adapt a Codex output payload (``{findings:[...]}`` or a bare list) into reviewer findings."""
    findings = payload.get("findings", []) if isinstance(payload, dict) else payload
    return _disambiguate([adapt_codex_finding(f) for f in findings])


def adapt_antigravity_finding(finding: dict[str, Any]) -> dict[str, Any]:
    """Adapt one Antigravity finding into a reviewer-shaped finding for the Step 4 filter.

    Same shape as ``adapt_codex_finding`` (ADR-004 shares the severity vocabulary and the
    reviewer-finding contract) — only ``source`` differs.
    """
    file = finding.get("file")
    line = finding.get("line")
    message = finding.get("message", "")
    return {
        "id": finding_id("antigravity", file, line, message),
        "severity": map_severity(finding["severity"]),
        "file": file,
        "line": line,
        "summary": message,
        "evidence": finding.get("evidence"),
        "source": "antigravity",
        "needs_relaxation": file is None or line is None,
    }


def adapt_antigravity_finding_list(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    """Adapt an Antigravity output payload into reviewer findings."""
    findings = payload.get("findings", []) if isinstance(payload, dict) else payload
    return _disambiguate([adapt_antigravity_finding(f) for f in findings])


_SENTINEL: Any = object()


def _strip_code_fences(text: str) -> str:
    """Drop a single leading/trailing ``` fence (with optional language tag), if present."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


# Reject oversized antigravity output before the O(n) scan — an unbounded response is a mild
# DoS vector and never a legitimate finding list (review security P3).
_MAX_ANTIGRAVITY_BYTES = 512_000


def _scan_balanced_json_values(text: str) -> list[tuple[Any, int]]:
    """Scan ``text`` for every top-level balanced JSON object/array, returning (value, start).

    ``start`` is the character index the value begins at — the caller uses it to reject a
    candidate found *inside* a truncated primary structure (i.e. one not anchored at the first
    structural opener). RecursionError from pathologically-nested input is converted to a
    ValueError so the fail-closed contract holds (review security P3).
    """
    decoder = json.JSONDecoder()
    found: list[tuple[Any, int]] = []
    idx = 0
    length = len(text)
    while idx < length:
        if text[idx] in "{[":
            try:
                obj, end = decoder.raw_decode(text, idx)
            except json.JSONDecodeError:
                idx += 1
                continue
            except RecursionError as exc:
                raise ValueError("antigravity payload nesting exceeds the parser limit") from exc
            found.append((obj, idx))
            idx = end
        else:
            idx += 1
    return found


def extract_antigravity_payload(raw: str) -> dict[str, Any] | list[Any]:
    """Fail-closed tolerant JSON extraction for Antigravity's unenforced output (ADR-011).

    Strips a single leading/trailing markdown code fence, then tries a direct parse. If that
    fails, scans for balanced JSON values. Raises ``ValueError`` unless EXACTLY ONE candidate
    exists AND it is anchored at the first structural opener — a candidate found deeper than the
    first ``{``/``[`` means the primary structure is truncated (e.g. an unterminated outer
    object whose one complete inner object would otherwise be mistaken for the payload), which
    must fail closed. An absent / ambiguous / oversized / pathologically-nested payload also
    fails closed. The caller turns any ValueError into a ``status: "failed"`` ledger row, never
    a crash of the dispatch loop.
    """
    if len(raw) > _MAX_ANTIGRAVITY_BYTES:
        raise ValueError(
            f"antigravity output {len(raw)} bytes exceeds cap {_MAX_ANTIGRAVITY_BYTES}"
        )
    stripped = _strip_code_fences(raw)
    try:
        direct = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        direct = _SENTINEL
    except RecursionError as exc:
        raise ValueError("antigravity payload nesting exceeds the parser limit") from exc
    if direct is not _SENTINEL:
        if not isinstance(direct, (dict, list)):
            raise ValueError(f"antigravity payload is not an object/array: {type(direct).__name__}")
        return direct
    candidates = [
        (v, s) for (v, s) in _scan_balanced_json_values(stripped) if isinstance(v, (dict, list))
    ]
    if len(candidates) != 1:
        raise ValueError(
            f"expected exactly one JSON payload in antigravity output, found {len(candidates)}"
        )
    value, start = candidates[0]
    first_opener = next((i for i, ch in enumerate(stripped) if ch in "{["), None)
    if first_opener is not None and start != first_opener:
        raise ValueError(
            "antigravity payload's primary JSON structure is truncated/unparseable "
            "(the sole complete value is nested inside an unparseable container)"
        )
    result: dict[str, Any] | list[Any] = value
    return result


# -- CLI -----------------------------------------------------------------------


def _parse_model_flag(rest: list[str]) -> str | None:
    """Extract an optional ``--model <name>`` / ``--model=<name>`` flag."""
    for i, arg in enumerate(rest):
        if arg == "--model" and i + 1 < len(rest):
            return rest[i + 1]
        if arg.startswith("--model="):
            return arg.split("=", 1)[1]
    return None


def stamp_ids(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    """Stamp a stable ``id`` on every finding in a merged reviewer list.

    WHY a CLI-reachable function and not prose: ``/hm:review`` Step 3.4 runs in an LLM turn,
    which cannot evaluate SHA-256 and cannot reproduce ``json.dumps``'s exact separators. Told
    to compute the hash itself it invents an id-shaped string, so the id changes every round
    and the merge-by-``id`` rule silently degrades to the ``file:line:summary`` matching it was
    written to replace. This is the invocable path that makes the instruction executable.

    A finding that already carries an ``id`` keeps it — re-deriving on post-fix values is the
    bug the whole identity contract exists to prevent.
    """
    if isinstance(payload, dict):
        findings = payload.get("findings")
        if findings is None:
            # A dict WITHOUT `findings` is a bare record, not an empty batch. Returning []
            # here would silently drop the caller's whole input.
            findings = [payload]
    else:
        findings = payload

    records = [dict(f) for f in findings if isinstance(f, dict)]
    # Ids already present are authoritative and are NEVER re-suffixed: a carried-forward
    # record keeps the id the round-2 merge joins on. `_disambiguate` cannot be reused here
    # because it renames every occurrence after the first — including the carried one — and
    # never checks its own result against ids already taken.
    taken = {str(r["id"]) for r in records if r.get("id")}
    for record in records:
        if record.get("id"):
            continue
        base = finding_id(
            str(record.get("reviewer") or record.get("source") or ""),
            record.get("file"),
            record.get("line"),
            str(record.get("summary", "")),
        )
        candidate = base
        n = 1
        while candidate in taken:
            n += 1
            candidate = f"{base}-{n}"
        taken.add(candidate)
        record["id"] = candidate
    return {"findings": records}


def main(argv: list[str] | None = None, *, stdin_text: str | None = None) -> int:
    """CLI: ``python -m harness_maker.codex_adapter adapt [--model codex|antigravity]`` — reads
    the second-opinion output JSON on stdin (the ``--output-last-message`` file for Codex, or
    agy's captured stdout for Antigravity) and writes the adapted reviewer-finding list.

    Reading from stdin/file (not an inlined shell arg) keeps untrusted content out of the
    shell, and makes the severity map + null-location flag actually deterministic rather than
    LLM-applied prose (REVIEW round 3, finding C). Default model is ``codex`` (back-compat with
    the single-vendor CLI shape)."""
    _guard = command_registry.guard_or_none("codex_adapter", argv)
    if _guard is not None:
        return _guard
    args = list(sys.argv[1:]) if argv is None else list(argv)
    if args and args[0] == "stamp-ids":
        raw = sys.stdin.read() if stdin_text is None else stdin_text
        if not raw.strip():
            sys.stderr.write("stamp-ids: stdin is empty\n")
            return 1
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            sys.stderr.write(f"stamp-ids: stdin is not valid JSON: {exc}\n")
            return 1
        sys.stdout.write(json.dumps(stamp_ids(parsed), ensure_ascii=False) + "\n")
        return 0
    if not args or args[0] != "adapt":
        sys.stderr.write(
            "usage: python -m harness_maker.codex_adapter (adapt [--model codex|antigravity] "
            "| stamp-ids) < input.json\n"
        )
        return 2
    model = _parse_model_flag(args[1:]) or "codex"
    if model not in ("codex", "antigravity"):
        sys.stderr.write(f"adapt: unknown --model {model!r} (expected codex|antigravity)\n")
        return 2
    raw = sys.stdin.read()
    if not raw.strip():
        sys.stderr.write("adapt: stdin is empty\n")
        return 1
    if model == "codex":
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            sys.stderr.write(f"adapt: stdin is not valid JSON: {exc}\n")
            return 1
        try:
            adapted = adapt_finding_list(payload)
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            sys.stderr.write(f"adapt: malformed codex finding: {exc}\n")
            return 1
    else:
        try:
            payload = extract_antigravity_payload(raw)
        except ValueError as exc:
            sys.stderr.write(f"adapt: antigravity payload extraction failed: {exc}\n")
            return 1
        try:
            adapted = adapt_antigravity_finding_list(payload)
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            sys.stderr.write(f"adapt: malformed antigravity finding: {exc}\n")
            return 1
    sys.stdout.write(json.dumps(adapted, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
