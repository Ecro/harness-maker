"""`hm change_card`: the owner's short card at SPEC approval and at wrapup land (SPEC-change-card).

Every line is read from files by code — the SPEC, its machine.yaml, the REVIEW record, the last
`hm check` verdict and the commit's `Understanding:` block — so the verified / not-verified lines
cannot be written by the model and skipped (HR-028). Labels follow the harness locale.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from harness_maker import i18n

#: The spec card's soft cap. IRRs and open questions are never trimmed, so a SPEC with many of
#: them may exceed it: approval facts outrank length.
SPEC_CAP = 1500
_ITEM_CAP = 110
_KEEP_AGENT = 3

_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "spec_title": "Change card · SPEC-{slug} (before approval)",
        "land_title": "Change card · {subject}",
        "why": "Why",
        "example": "Example",
        "criteria": "Acceptance criteria ({n})",
        "irreversible": "Irreversible",
        "agent": "Agent-decided",
        "non_goals": "Out of scope",
        "open": "Open questions",
        "full": "Full text",
        "none": "none",
        "more": "+{n} more",
        "verified": "Verified",
        "not_verified": "Not verified",
        "assumptions": "Changed assumptions",
        "unknown": "Unknown",
        "gates": "hm check gates passed: {n} ({cmds})",
        "ac_tests": "AC tests passed: {acs} ACs, {tests} tests",
        "review": "Review: {n} findings, all disposed ({doc})",
        "review_none": "Review: no findings ({doc})",
        "judged": "{id} {title}: judged by a model, no test",
        "manual": "Manual check: {row}",
        "record_missing": "no hm check record for this task: gates and {n} AC tests unconfirmed",
        "record_failed": "the last hm check did not pass: gates and {n} AC tests unconfirmed",
        "record_stale": "code changed after the last hm check: gates and {n} AC tests unconfirmed",
        "no_review": "no REVIEW record",
        "review_open": "Review not closed ({doc}): {ids}",
        "more_acs": "+{n} criteria not listed",
        "pending": "{id} {title}: no test bound",
    },
    "ko": {
        "spec_title": "변경 카드 · SPEC-{slug} (승인 전)",
        "land_title": "변경 카드 · {subject}",
        "why": "왜",
        "example": "예시",
        "criteria": "수용 기준 {n}개",
        "irreversible": "되돌리기 어려운 결정",
        "agent": "에이전트가 정한 것",
        "non_goals": "범위 밖",
        "open": "열린 질문",
        "full": "전문",
        "none": "없음",
        "more": "+{n}개 더",
        "verified": "검증함",
        "not_verified": "검증 못 함",
        "assumptions": "바뀐 가정",
        "unknown": "모르는 것",
        "gates": "hm check 게이트 {n}개 통과 ({cmds})",
        "ac_tests": "AC 테스트 통과: AC {acs}개, 테스트 {tests}개",
        "review": "리뷰 지적 {n}건, 모두 처리 ({doc})",
        "review_none": "리뷰 지적 없음 ({doc})",
        "judged": "{id} {title}: 모델 판정만, 테스트 없음",
        "manual": "수동 확인: {row}",
        "record_missing": "이 작업의 hm check 기록 없음: 게이트와 AC 테스트 {n}개 미확인",
        "record_failed": "마지막 hm check 불통과: 게이트와 AC 테스트 {n}개 미확인",
        "record_stale": "마지막 hm check 뒤 코드가 바뀜: 게이트와 AC 테스트 {n}개 미확인",
        "no_review": "REVIEW 기록 없음",
        "review_open": "리뷰가 닫히지 않음 ({doc}): {ids}",
        "more_acs": "+{n}개 기준은 목록에 없음",
        "pending": "{id} {title}: 테스트 없음",
    },
}


def label(key: str, locale: str | None, **values: object) -> str:
    table = _LABELS.get(locale or i18n.DEFAULT_LOCALE) or _LABELS[i18n.DEFAULT_LOCALE]
    text = table.get(key) or _LABELS[i18n.DEFAULT_LOCALE][key]
    return text.format(**values) if values else text


def _clip(text: str, cap: int = _ITEM_CAP) -> str:
    flat = re.sub(r"\s+", " ", text.replace("**", "")).strip()
    return flat if len(flat) <= cap else flat[: cap - 1].rstrip() + "…"


def _frontmatter(text: str) -> dict[str, Any]:
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if m is None:
        return {}
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def _items(body: str) -> list[str]:
    """Bullets (with their continuation lines) or table rows; `none` reads as no items."""
    if not body or re.fullmatch(r"(?i)none\.?", body.strip()):
        return []
    items: list[str] = []
    rows = [ln for ln in body.splitlines() if ln.strip().startswith("|")]
    if rows:
        for row in rows[1:]:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if cells and not all(set(c) <= set("-: ") for c in cells):
                items.append(" — ".join(c for c in cells if c))
        return items
    for line in body.splitlines():
        if re.match(r"\s*[-*] ", line):
            items.append(re.sub(r"^\s*[-*] ", "", line))
        elif line.strip() and items:
            items[-1] += " " + line.strip()
        elif line.strip():
            items.append(line.strip())
    return items


def _machine(root: Path, slug: str) -> dict[str, Any]:
    path = root / "specs" / f"SPEC-{slug}.machine.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _spec_md(root: Path, slug: str) -> str:
    try:
        return (root / "specs" / f"SPEC-{slug}.md").read_text(encoding="utf-8")
    except OSError:
        return ""


def _live(model: dict[str, Any]) -> list[dict[str, Any]]:
    return [a for a in model.get("ac") or [] if isinstance(a, dict) and not a.get("superseded_by")]


def _irr_lines(model: dict[str, Any]) -> list[str]:
    out = []
    for irr in model.get("irreversible_decisions") or []:
        if isinstance(irr, dict):
            decision = re.sub(r"\s+", " ", str(irr.get("decision", ""))).strip()
            out.append(f"- {irr.get('id', '?')} {decision} ({irr.get('category', '?')})")
    return out


def _example_lines(acs: list[dict[str, Any]], limit: int = 1) -> list[str]:
    out: list[str] = []
    for ac in acs:
        for row in ac.get("golden_table") or []:
            if len(out) >= limit or not isinstance(row, dict):
                break
            given = ", ".join(f"{k}={v}" for k, v in (row.get("input") or {}).items())
            want = json.dumps(row.get("expected"), ensure_ascii=False)
            out.append(_clip(f"{ac.get('id')} {ac.get('title', '')}: {given} -> {want}"))
    return out


def _capped(items: list[str], keep: int, locale: str | None) -> list[str]:
    lines = [f"- {_clip(i)}" for i in items[:keep]]
    if len(items) > keep:
        lines.append(f"- {label('more', locale, n=len(items) - keep)}")
    return lines


def spec_card(root: Path, slug: str, locale: str | None = None) -> str:
    """What the DRI approves from: the reason, examples, the IRRs and what the agent decided."""
    locale = locale or i18n.resolve_locale(root)
    md = _spec_md(root, slug)
    model = _machine(root, slug)
    acs = _live(model)
    summary = _clip(str(_frontmatter(md).get("summary") or ""), 400)
    agent = _items(_section(md, "Refinement Decisions"))
    non_goals = _items(_section(md, "Non-Goals"))
    questions = _items(_section(md, "Open Questions"))
    irr = _irr_lines(model)

    def build(titles: bool, examples: bool, goals: int, agents: int) -> str:
        lines = [label("spec_title", locale, slug=slug), f"{label('why', locale)}: {summary}"]
        if examples:
            lines += [f"{label('example', locale)}: {e}" for e in _example_lines(acs)]
        head = label("criteria", locale, n=len(acs))
        names = "; ".join(_clip(f"{a.get('id')} {a.get('title', '')}", 60) for a in acs)
        if titles and names:
            lines.append(f"{head}: {names}")
        else:
            lines.append(f"{head}: {label('more_acs', locale, n=len(acs))}" if acs else head)
        lines.append(f"{label('irreversible', locale)}:" if irr else
                     f"{label('irreversible', locale)}: {label('none', locale)}")  # fmt: skip
        lines += irr
        if agent:
            lines += [f"{label('agent', locale)}:", *_capped(agent, agents, locale)]
        if non_goals:
            shown = [_clip(g, 80) for g in non_goals[:goals]]
            if len(non_goals) > goals:
                shown.append(label("more", locale, n=len(non_goals) - goals))
            lines.append(f"{label('non_goals', locale)}: " + "; ".join(shown))
        if questions:
            lines += [f"{label('open', locale)}:", *(f"- {q.strip()}" for q in questions)]
        else:
            lines.append(f"{label('open', locale)}: {label('none', locale)}")
        lines.append(f"{label('full', locale)}: specs/SPEC-{slug}.md")
        return "\n".join(lines)

    # Trim order (SPEC Refinement Decisions): AC titles, non-goals, agent beyond 3, examples last
    # (a concrete example is what the research found helps a reader most).
    n_goals, n_agent = len(non_goals), len(agent)
    steps = [
        (True, True, n_goals, n_agent),
        (False, True, n_goals, n_agent),
        (False, True, 2, n_agent),
        (False, True, 2, _KEEP_AGENT),
        (False, True, 0, _KEEP_AGENT),
        (False, True, 0, 1),
        (False, False, 0, 1),
    ]
    card = ""
    for titles, examples, goals, agents in steps:
        card = build(titles, examples, goals, agents)
        if len(card) <= SPEC_CAP:
            break
    return card


# ── land card ─────────────────────────────────────────────────────────────────


def _digest(path: Path) -> str:
    """The same per-file value `check.snapshot` records."""
    try:
        if path.is_symlink():
            return "link:" + os.readlink(path)
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return "absent"
    except OSError as exc:
        return f"unreadable:{type(exc).__name__}"


def card_path(base: Path, slug: str) -> Path:
    """Where `wrapup_land` leaves the land card for wrapup's closing step (local, uncommitted)."""
    return base / ".claude" / "observability" / f"change-card-{slug}.txt"


def _record(root: Path, slug: str) -> tuple[str, dict[str, Any] | None]:
    """The last `hm check` verdict for this slug and this code: `ok`, `missing`, `failed` (a
    record whose overall verdict was not 0) or `stale` (code or tests changed since it ran).

    Only code and test paths are compared: wrapup edits the PLAN and memory after its gate."""
    from harness_maker import check, check_reuse

    path = check.verdict_path(root)
    if path is None:
        return "missing", None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "missing", None
    if not isinstance(data, dict) or data.get("slug") != slug:
        return "missing", None
    recorded = data.get("files")
    if not isinstance(recorded, dict):
        return "stale", None
    # Hash only code and test paths: the land path must not re-hash a whole large repo.
    paths = {p for p in (*recorded, *check._listed_files(root)) if check_reuse.never_inert(p)}
    now = {p: _digest(root / p) for p in paths}
    moved = [p for p in paths if recorded.get(p) != now[p]]
    if moved:
        return "stale", None
    line = data.get("line")
    if not (isinstance(line, dict) and line.get("exit") == 0):
        return "failed", data
    return "ok", data


def _understanding(message: str) -> list[str]:
    from harness_maker.wrapup_land import check_understanding_block

    block = check_understanding_block(message).text or ""
    return [ln[2:].strip() for ln in block.splitlines() if ln.startswith("- ")]


def _manual_rows(md: str) -> list[str]:
    """Verification rows whose Mode cell starts with `manual` (the SPEC's own mode column)."""
    lines = [ln for ln in _section(md, "Verification").splitlines() if ln.strip().startswith("|")]
    if not lines:
        return []
    header = [c.strip().lower() for c in lines[0].strip().strip("|").split("|")]
    if "mode" not in header:
        return []
    col = header.index("mode")
    rows = []
    for line in lines[1:]:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if col < len(cells) and cells[col].lower().startswith("manual"):
            rows.append(_clip(" — ".join(c for c in cells if c)))
    return rows


def land_card(root: Path, slug: str, message: str, locale: str | None = None) -> str:
    """What landed: verified and not verified at the same level, then what changed in the
    owner's model of the system. Read from `root`, the task worktree, before it is removed."""
    from harness_maker import check

    locale = locale or i18n.resolve_locale(root)
    md = _spec_md(root, slug)
    model = _machine(root, slug)
    acs = _live(model)
    subject = message.splitlines()[0].strip() if message.strip() else slug
    summary = str(_frontmatter(md).get("summary") or "")
    if not summary:
        paragraphs = [p for p in message.split("\n\n")[1:] if p.strip()]
        summary = paragraphs[0] if paragraphs else ""
    testable = [a for a in acs if a.get("type") != "judgment"]
    bound = [a for a in testable if a.get("test_ids") and not a.get("pending_test")]
    tests = sum(len(a.get("test_ids") or []) for a in bound)
    verified: list[str] = []
    unverified: list[str] = []
    state, record = _record(root, slug)
    if state == "ok" and record is not None:
        results = (record.get("gates") or {}).get("results") or []
        passed = [str(r.get("cmd")) for r in results if isinstance(r, dict) and r.get("exit") == 0]
        if passed:
            cmds = _clip(", ".join(passed), 90)
            verified.append(label("gates", locale, n=len(passed), cmds=cmds))
        if bound:
            verified.append(label("ac_tests", locale, acs=len(bound), tests=tests))
    else:
        unverified.append(label(f"record_{state}", locale, n=tests))
    for ac in testable:
        if ac not in bound:
            unverified.append(label("pending", locale, id=ac.get("id"), title=_clip(
                str(ac.get("title", "")), 60)))  # fmt: skip
    review = check.review_section(root, slug, check._harness_config(root)).body
    doc = review.get("doc")
    if doc is None:
        unverified.append(label("no_review", locale))
    elif review.get("ok") is not True:
        why = review.get("open") or review.get("without_disposition") or [review.get("reason")]
        unverified.append(label("review_open", locale, doc=doc, ids=_clip(
            ", ".join(str(w) for w in why if w), 80)))  # fmt: skip
    elif review.get("findings"):
        verified.append(label("review", locale, n=review["findings"], doc=doc))
    else:
        verified.append(label("review_none", locale, doc=doc))
    for ac in acs:
        if ac.get("type") == "judgment":
            unverified.append(label("judged", locale, id=ac.get("id"), title=_clip(
                str(ac.get("title", "")), 60)))  # fmt: skip
    unverified += [label("manual", locale, row=r) for r in _manual_rows(md)]

    bullets = _understanding(message)
    unknown = [b.split(":", 1)[1].strip() for b in bullets if b.lower().startswith("unknown:")]
    agent = [b.split(":", 1)[1].strip() for b in bullets if b.lower().startswith("agent-decided:")]
    changed = [b for b in bullets if not b.lower().startswith(("unknown:", "agent-decided:"))]

    def block(key: str, items: list[str]) -> list[str]:
        if not items:
            return [f"{label(key, locale)}: {label('none', locale)}"]
        return [f"{label(key, locale)}:", *(f"- {_clip(i)}" for i in items)]

    lines = [label("land_title", locale, subject=subject)]
    if summary:
        lines.append(f"{label('why', locale)}: {_clip(summary, 400)}")
    lines += block("verified", verified) + block("not_verified", unverified)
    lines += block("assumptions", changed) + block("unknown", unknown) + block("agent", agent)
    irr = _irr_lines(model)
    if irr:
        lines += [f"{label('irreversible', locale)}:", *irr]
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hm change_card", description="Print the owner's change card.")
    sub = p.add_subparsers(dest="cmd", required=True)
    spec = sub.add_parser("spec", help="the card shown with the SPEC approval question")
    land = sub.add_parser("land", help="the card wrapup_land puts in its receipt")
    for cmd in (spec, land):
        cmd.add_argument("--root", type=Path, default=Path("."))
        cmd.add_argument("--slug", required=True)
        cmd.add_argument("--locale", default=None, help="default: .claude/harness.yaml locale")
    land.add_argument("--message-file", type=Path, required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    from harness_maker import command_registry

    guard = command_registry.guard_or_none("change_card", argv)
    if guard is not None:
        return guard
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    if args.cmd == "spec":
        if not (root / "specs" / f"SPEC-{args.slug}.md").is_file():
            sys.stderr.write(f"hm change_card: no specs/SPEC-{args.slug}.md under {root}\n")
            return 1
        text = spec_card(root, args.slug, args.locale)
    else:
        text = land_card(root, args.slug, args.message_file.read_text(encoding="utf-8"),
                         args.locale)  # fmt: skip
    sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
