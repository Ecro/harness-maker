"""Renderer (Task 3.2) — render Blueprint FileEntries to disk with deterministic output.

Determinism contract (per amendment §C):
- Jinja2 env: StrictUndefined, no autoescape, keep_trailing_newline=True.
- Body: normalize CRLF→LF, exactly one trailing LF, UTF-8 bytes.
- Frontmatter: YAML, sort_keys=False (insertion order), allow_unicode=True.
- settings.json: JSON, sort_keys=True (cross-edit determinism).
- content_hash: sha256 of the normalized body bytes; injected into frontmatter.
- freeze_time: when set, generated_at is fixed (used in tests + CI).

hooks.json (Phase 4 F1 amendment §E):
- Claude Code hooks.json must be pure JSON (jq-parseable) — no YAML frontmatter prefix.
- The cross-phase frontmatter invariant gate explicitly excludes `*/hooks/hooks.json`,
  so we render hooks.json as pure JSON via `_render_pure_json` (no symlink, no sidecar).
- Provenance is sacrificed for hooks.json (acceptable since it's small + reproducible).

Render manifest (ADR-005, Phase 0):
- Every blueprint file render appends one JSON line to
  ``<target_dir>/.hm-render-manifest.jsonl`` ({path, content_hash, timestamp}).
  The reconcile orphan-sweep uses this manifest as the authoritative
  ours-vs-theirs registry for files that lack provenance frontmatter (.sh,
  .json, .toml). Duplicates are intentionally not collapsed — re-renders
  accumulate so historical hashes remain matchable.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from harness_maker import __version__, template_globals
from harness_maker.block_merge import MergeReport
from harness_maker.block_merge import merge as block_merge
from harness_maker.io_utils import RETIRED_TOP_LEVEL_KEYS, atomic_append, atomic_write
from harness_maker.models import Blueprint, FileEntry

# Module constants — templates ship inside the harness_maker package so they're
# present in both editable installs (src/harness_maker/templates/) and wheel
# installs (importable as package data).
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
DEFAULT_FREEZE_TIME = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

# Append-only audit log consulted by the reconcile orphan-sweep (ADR-005).
# Lives inside the rendered ``.claude/`` directory so it travels with the
# harness and can be inspected/git-ignored alongside other internal state
# files (e.g. ``.hm-loop-*``).
RENDER_MANIFEST_NAME = ".hm-render-manifest.jsonl"
RENDER_MANIFEST_COMPACT_LINE_THRESHOLD = 2000


def _make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
        undefined=StrictUndefined,
        autoescape=False,
    )
    return template_globals.install(env)


def _normalize_body(text: str) -> bytes:
    """Normalize body to LF + single trailing LF, UTF-8 bytes."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        text += "\n"
    while text.endswith("\n\n"):
        text = text[:-1]
    return text.encode("utf-8")


def _format_frontmatter(fm: dict[str, Any]) -> str:
    """YAML frontmatter — sort_keys=False for stable insertion order."""
    body = yaml.safe_dump(
        fm,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    return "---\n" + body + "---\n"


def _format_settings_json(data: dict[str, Any]) -> bytes:
    """settings.json — sort_keys=True for cross-edit determinism."""
    raw = json.dumps(
        data,
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
        separators=(",", ": "),
    )
    return (raw + "\n").encode("utf-8")


def _build_provenance(
    fe: FileEntry,
    freeze_time: datetime | None,
) -> dict[str, Any]:
    ts = (freeze_time or DEFAULT_FREEZE_TIME).isoformat()
    return {
        "generated_by": "harness-maker",
        "harness_maker_version": __version__,
        "generated_at": ts,
        "source_template": fe.template,
        "provenance": "official",
        **fe.frontmatter,
    }


def _assert_portable_install_ref(ref: str | None) -> None:
    """Render-time guard (ADR-005 of PLAN-portable-hook-paths).

    The install ref baked into every hook command MUST NOT be, or start a path
    segment under, the render-machine home. A home-prefixed ref means
    ``synthesize._portablize_ref`` failed to substitute ``$HOME`` and a machine-
    specific absolute path would be committed — re-igniting the team flip-flop
    this work removed. A ``$HOME``-substituted ref, a non-home system install
    (``/opt/...``), and a PyPI name all pass. No-op when the context carries no
    ref (non-hook renders). This is the substitution-correctness invariant, not a
    general portability claim — it holds identically in real render and under the
    regen/conftest monkeypatch (both pin the already-``$HOME`` form).
    """
    if ref is None:
        return
    home = str(Path.home())
    if ref == home or ref.startswith(home + os.sep):
        msg = (
            f"non-portable install ref leaked into a rendered hook: {ref!r} is under "
            f"the render-machine home {home!r}. synthesize._portablize_ref should have "
            f"replaced the home prefix with $HOME."
        )
        raise ValueError(msg)


def _render_settings_json(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,  # noqa: ARG001 — kept for dispatch signature parity
) -> Path:
    """Render settings.json as pure JSON, shallow-merging with any existing on disk.

    Claude Code expects ``settings.json`` to be parseable as plain JSON, so we
    cannot prepend YAML frontmatter (it'd break the file). We also need to
    coexist with Claude Code-managed top-level keys like ``enabledPlugins`` —
    written when the user runs ``/plugin install`` — so we shallow-merge:
      * existing top-level keys NOT in our template are preserved
      * keys present in both — our template's value wins (it's the source of
        truth for permissions/preset)

    v1 limitation — the merge is **shallow**: nested customizations under a
    key our template owns (e.g. user-added entries in ``permissions.allow``)
    are lost on re-render. Workaround: keep custom permissions in
    ``.claude/settings.local.json`` (Claude Code merges that automatically).
    """
    _assert_portable_install_ref(fe.context.get("harness_maker_src_path"))
    template = env.get_template(fe.template)
    rendered = template.render(**fe.context)
    try:
        new_data: dict[str, Any] = json.loads(rendered)
    except json.JSONDecodeError as e:
        msg = f"Template {fe.template} rendered invalid JSON for {fe.path}: {e}"
        raise ValueError(msg) from e
    if not isinstance(new_data, dict):
        msg = f"Template {fe.template} must render a JSON object (got {type(new_data).__name__})"
        raise ValueError(msg)
    out = resolve_output_path(target_dir, fe.path)
    merged = _shallow_merge_existing_json(out, new_data, dry_run=dry_run)
    body_bytes = _format_settings_json(merged)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    if not dry_run:
        atomic_write(out, body_bytes)
    return out


# Keys harness-maker has ever written to settings.json.  When a key is
# removed from the template it must be actively dropped on the next render —
# simple {**existing, **new_data} would leave it behind forever.
# NOTE: "env" is intentionally absent — users may set their own env vars.
_SETTINGS_KEYS_OWNED_BY_HARNESS: frozenset[str] = frozenset(
    {
        "statusLine",  # written by <=0.3.x; template no longer emits it
        "preset",
        "permissions",
        # Claude Code reads project hooks ONLY from settings files — a plain
        # project's `.claude/hooks/hooks.json` is never loaded (hooks.md's
        # location table; that path is valid for a PLUGIN bundle only).
        # Confirmed by controlled experiment 2026-07-17: the same commands fired
        # from settings.json and not from `.claude/hooks/hooks.json`.
        # Owned, but DEEP-merged — see `_shallow_merge_existing_json`.
        "hooks",
    }
)

# Permission sub-keys whose lists are unioned (template entries first, then
# user-added entries). This preserves rules the user added themselves — via
# /hm:health Layer 1 acceptance or by hand — across re-renders. A naive replace
# would wipe them and silently downgrade the project's posture.
_PERMISSIONS_LIST_KEYS: tuple[str, ...] = ("allow", "deny", "ask")

# Every `permissions.deny` literal a harness-maker settings template has ever
# rendered. APPEND-ONLY — never recycle an entry, and never add a literal the
# templates did not ship (an entry here is unconditionally deleted from the
# user's disk).
#
# Why this exists: the union above cannot tell a rule harness-maker rendered in
# 0.12 from one the user typed, so our own history accreted forever. That is how
# projects still carry `Write(/etc/**)` — dead syntax that warns at startup —
# long after the template stopped shipping it. Dropping these before the union
# rebuilds `deny` from `deny_dangerous` policy each render instead.
#
# An entry here is deleted from the user's settings.json unconditionally, so
# membership is governed by TWO invariants, both enforced by tests:
#
#   1. We shipped it — `git log -S` finds it in templates/settings/ history.
#      (ADR-004 listed nine literals from memory; four had never been in a
#      settings template at all — they reach disk via /hm:health Layer 1
#      acceptance or by hand. Pruning those would have deleted user content.)
#   2. It provably enforces NOTHING — `permission_syntax.is_matchable_rule` is
#      False for it.
#
# Invariant 2 is what makes this safe, and invariant 1 cannot substitute for it:
# git history proves we shipped a string, NOT that the user did not also author
# it. For dead syntax that distinction costs nothing — deleting a rule that
# never fired removes zero protection and clears the startup warning it caused.
# For a LIVE rule it is the difference between tidying and silent data loss.
#
# Hence `Bash(rm:*)` and `Bash(curl:*)` are deliberately absent even though we
# shipped both: they are live, `deny_dangerous` defaults to False so the template
# does not re-add them, and `permission_gate`'s PreToolUse hook — their intended
# replacement — is not wired yet. A user who health-accepted `Bash(rm:*)` keeps it.
_HARNESS_SHIPPED_DENY_LITERALS: frozenset[str] = frozenset(
    {
        # `|` is a command separator, so this never matches. Fails silently.
        "Bash(curl * | sh)",
        # The file-permission check consults Edit/Read only. Warns at startup.
        "Write(/etc/**)",
        "Write(~/.ssh/**)",
    }
)

# Every `permissions.allow` literal a settings template once rendered and has since
# STOPPED rendering, mapped to the one-line reason the user is shown when it is
# removed from their disk. APPEND-ONLY, same as the deny set.
#
# ⚠️ These are LIVE rules — `is_matchable_rule` is True for both — so the deny set's
# "provably enforces nothing" proof is NOT available here and must not be faked. The
# safety argument is a different one, resting on the DIRECTION of the failure:
#
#   * Wrongly pruning a deny rule silently removes protection. Unrecoverable in the
#     sense that nothing tells the user it happened.
#   * Wrongly pruning an allow rule makes Claude Code *ask* before running the
#     command. The failure direction is toward the prompt, which is the safe side,
#     and it is self-announcing rather than silent.
#
# ⚠️ The "it only costs a prompt" half of that is INTERACTIVE-ONLY (REVIEW round 1,
# 3 of 4 voters). In headless `claude -p` there is no prompt to answer, so the call
# fails instead of asking; under `--dangerously-skip-permissions` / bypassPermissions
# the prune is a no-op. Neither mode offers "don't ask again". What survives in every
# mode is the weaker but sufficient half: a pruned allow rule never removes
# protection, and never fails silently.
#
# That asymmetry is why an allow prune can be unconditional where a deny prune of a
# live rule cannot. It is a risk ACCEPTANCE (the user may have typed the literal
# themselves and now gets prompts), not a proof — and it is bought with a real
# benefit: without it, 0.43.0's retirement of the blanket `Bash(uv:*)` applies to
# new installs only, and every existing project keeps an arbitrary-command grant
# forever. Membership is bounded by three test-enforced invariants:
#
#   1. We shipped it — `git log -S` finds it in templates/settings/ history.
#   2. We no longer ship it — absent from every current rendered settings.json.
#      (Pruning something still shipped is pure churn; the union re-adds it.)
#   3. The prune never leaves a harness with LESS than a fresh install.
#
# ⚠️ Invariant 3 is STRUCTURAL, not test-enforced, and calling it the third bound was
# an overstatement (REVIEW round 3, two independent voters). The union builds from
# `(*new_list, *existing_list)` while the prune filters only `existing_list`, so every
# rule the current template renders survives BY CONSTRUCTION — no test of it can fail,
# and it therefore constrains nothing about which entries may join the tables above.
# The bounds that actually bite are 1 and 2 plus the near-miss tests. Invariant 3 is
# still worth stating because it is what caps the blast radius, but it is a property of
# the merge's shape, not evidence about the prune set.
#
# ⚠️ Invariant 3 is one-directional ON PURPOSE. An earlier draft claimed the upgraded
# list becomes byte-IDENTICAL to a fresh install's, and that is false in the field
# (REVIEW round 1): the `uv run --with <src_path> …` rule embeds the plugin's VERSION
# directory, so each `/plugin update` renders a new variant and unions the previous
# one in forever. That is a real accretion bug, tracked separately — but it leaves the
# user with MORE rules than a fresh install, never fewer, so it does not touch the
# safety property this invariant exists to establish. Do not re-strengthen the claim
# to equality without first pruning that version-pinned family.
#
# Invariant 3 is deliberately NOT "every harness-emitted command stays covered" —
# that is false and must stay false. `uv run python -c "<arbitrary python>"` is
# emitted by two templates and was covered only by the blanket grant; pre-approving
# it again would re-open exactly the arbitrary-execution hole 0.43.0 closed. Those
# prompt now, for new and upgraded installs alike.
_HARNESS_SHIPPED_ALLOW_LITERALS: dict[str, str] = {
    # `uv run <anything>` executes its argument, so this pre-approved every command.
    "Bash(uv:*)": "blanket arbitrary-command grant, retired in 0.43.0 for scoped `uv run` rules",
    # `agy --print --sandbox X` consumes `--sandbox` as the prompt VALUE, so this
    # pre-approved the un-sandboxed spelling. Reordered to `--sandbox --print`.
    "Bash(agy --print --sandbox:*)": "flag order that silently disabled agy's sandbox; "
    "replaced by `Bash(agy --sandbox --print:*)`",
}

# Retired allow rules whose text EMBEDS the resolved install path, so no exact literal
# can ever match what is on a user's disk. Each entry is (pattern, user-facing reason).
#
# ⚠️ A regex prune is strictly more dangerous than a literal one and needs its own
# justification, so this list stays tiny and every pattern must be a shape the RENDERER
# provably generates end-to-end — anchored at both ends, with the wildcard confined to
# the interpolated slot. A prefix or substring pattern is never acceptable here (the
# same rule the hook-retire set states).
#
# Why it had to exist: REVIEW round 2 found that tightening the module rule from
# `harness_maker*` to `harness_maker.*` reached NEW INSTALLS ONLY. The old text carries
# the user's own `harness_maker_src_path`, so the literal set could not name it, the
# union preserved it, and an upgraded harness kept BOTH rules — leaving
# `python -m harness_maker_evil` pre-approved by the stale one while a fresh install
# denied it. That is the very "fix reaches new installs only" gap this whole change
# exists to close, reintroduced one layer down.
_HARNESS_SHIPPED_ALLOW_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        # The 0.43.0 spelling. Two things keep this off user content:
        #   * `harness_maker\*` cannot match the current `harness_maker.*` form —
        #     the character before `*` differs.
        #   * the `--with` slot is NOT a free `.+`. It must name harness-maker
        #     itself, which is the only thing `synthesize._compute_install_ref`
        #     ever emits there ($HOME-substituted plugin cache path, a non-home
        #     absolute install, or the bare PyPI name). A free `.+` deleted
        #     `--with requests`, `--with .` and `--with /path/to/my/fork` — rules
        #     only a USER can have written (REVIEW round 3, two models agreeing).
        re.compile(r"^Bash\(uv run --with [^ ]*harness[-_]maker[^ ]* python -m harness_maker\*\)$"),
        "unbounded module prefix — also matched `python -m harness_maker_evil`; "
        "replaced by the `python -m harness_maker.*` form",
    ),
    (
        # Retired when the `hm` console script landed (PLAN-workflow-step-audit
        # ADR-018): every rendered call site moved from `python -m harness_maker.<mod>`
        # to `hm <mod>`, so the scoped second-opinion grant is now spelled
        # `hm second_opinion_invoke:*`. Without this entry the long form accretes on
        # every upgraded harness — a stale grant nobody re-approves and nobody removes.
        # The `--with` slot carries the same must-name-harness-maker guard as above, so
        # a user-written `--with /path/to/my/fork` rule is never pruned.
        re.compile(
            r"^Bash\(uv run --with [^ ]*harness[-_]maker[^ ]* "
            r"python -m harness_maker\.second_opinion_invoke:\*\)$"
        ),
        "long-form module invocation — replaced by the `hm second_opinion_invoke:*` "
        "form when the `hm` console script landed",
    ),
)


def _retired_allow_reason(item: str) -> str | None:
    """Why `item` is being dropped from `allow`, or None when it is not ours."""
    literal = _HARNESS_SHIPPED_ALLOW_LITERALS.get(item)
    if literal is not None:
        return literal
    for pattern, reason in _HARNESS_SHIPPED_ALLOW_PATTERNS:
        if pattern.match(item):
            return reason
    return None


def _is_harness_shipped(key: str, item: Any) -> bool:  # noqa: ANN401 — JSON is heterogeneous
    """Whether `item` is history this harness rendered into `key` and no longer does.

    The `isinstance` guard is load-bearing, not defensive noise: a malformed entry may
    be a dict or list, and `unhashable in frozenset` raises TypeError — which used to
    abort the whole render on one hand-edited settings.json.

    `ask` is absent from both tables on purpose: no settings template has ever rendered
    an `ask` entry, so every string there is the user's by construction.
    """
    if not isinstance(item, str):
        return False
    if key == "deny":
        return item in _HARNESS_SHIPPED_DENY_LITERALS
    if key == "allow":
        return _retired_allow_reason(item) is not None
    return False


def _announce_allow_prune(pruned: list[str], *, dry_run: bool) -> None:
    """Tell the user which allow rules vanished — the prompt they get next is otherwise
    an unexplained regression, and the remedy is only obvious if they know why.

    ``dry_run`` is defensive, NOT a fix for a reachable bug. `cli.py`'s ``--dry-run``
    branch returns at its ``typer.Exit(0)`` before the only ``render()`` call site, so no
    shipped command reaches the merge with ``dry_run=True`` today; only a direct API
    caller does. Two rounds of review split on this, and I first "settled" it by running
    ``render(dry_run=True)`` — which answers whether the *API* path prints, not whether
    the *CLI* reaches it. Tracing `cli.py` is what actually settles it. The parameter
    stays so that wiring a preview through `render()` later cannot silently start
    announcing deletions that never happened.
    """
    import typer

    verb = "would drop" if dry_run else "dropped"
    tail = "" if dry_run else " — commands they covered now require approval"
    typer.echo(
        f"NOTE: {verb} {len(pruned)} harness-shipped `permissions.allow` rule(s) from "
        f"settings.json{tail}:",
        err=True,
    )
    for literal in pruned:
        typer.echo(f"  - {literal} — {_retired_allow_reason(literal)}", err=True)
    typer.echo(
        "  Re-adding one of these to settings.json will NOT stick — the next re-render "
        "drops it again. If you need the access, add a SCOPED rule instead "
        "(e.g. `Bash(uv run ruff check:*)`), which is never pruned. In headless "
        "`claude -p` an affected call fails rather than prompting.",
        err=True,
    )


def _merge_permissions(
    existing_perms: dict[str, Any],
    new_perms: dict[str, Any],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Deep-merge permissions: union list sub-keys; template wins on scalars.

    Why list union (not "template wins"): users add to ``permissions.deny``
    via /hm:health Layer 1 acceptance + manual edits. The template ships a
    minimal baseline; user additions are project-specific guardrails. A
    naive replace wipes them on every re-render, which silently downgrades
    the project's security posture. List union preserves both.

    Template entries come first (preserving the template's intended order),
    then any user-added entries that aren't already in the template list
    are appended. Non-string entries in either list are dropped (malformed).
    """
    out: dict[str, Any] = dict(new_perms)
    for key in _PERMISSIONS_LIST_KEYS:
        new_list = new_perms.get(key, [])
        existing_list = existing_perms.get(key, [])
        if not isinstance(new_list, list) or not isinstance(existing_list, list):
            continue
        # Skip emitting the sub-key when neither side provided it. Without this
        # guard, the second render adds `"ask": []` (since new_perms.get default
        # was substituted into out via dict(new_perms)? No — actually the bug
        # is that we always set out[key] = [] when both sides empty, which adds
        # a key that wasn't present in either input. Idempotency requires not
        # creating phantom keys. (Phase 4 byte-identical regression guard.)
        if (
            not new_list
            and not existing_list
            and key not in new_perms
            and key not in existing_perms
        ):
            continue
        # Drop our own accreted history before the union, so the list is rebuilt
        # from the current template rather than accumulating every rule we ever
        # shipped. `_is_harness_shipped` owns the exact-vs-pattern decision and the
        # non-string guard; a near-miss like "Bash(rm:*) # my note" is the user's
        # content, not our history.
        if key in ("allow", "deny"):
            # Only rules the current template does NOT re-add actually disappear;
            # report those, so the notice never names a rule that is still there.
            # dict.fromkeys keeps on-disk order while collapsing a repeated entry,
            # which would otherwise inflate the count and print the same line twice.
            dropped = list(
                dict.fromkeys(
                    i for i in existing_list if _is_harness_shipped(key, i) and i not in new_list
                )
            )
            existing_list = [i for i in existing_list if not _is_harness_shipped(key, i)]
            if dropped and key == "allow":
                _announce_allow_prune(dropped, dry_run=dry_run)
        seen: set[str] = set()
        merged_list: list[str] = []
        for item in (*new_list, *existing_list):
            if isinstance(item, str) and item not in seen:
                merged_list.append(item)
                seen.add(item)
        out[key] = merged_list
    return out


def _shallow_merge_existing_json(
    out: Path,
    new_data: dict[str, Any],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Merge top-level keys: existing's unique keys + new_data (template wins).

    Previously-owned harness-maker keys absent from new_data are removed so
    stale keys don't linger after a template drops them.

    Two nested keys have a documented deep-merge:

    * ``permissions`` — list sub-keys (allow/deny/ask) union via
      ``_merge_permissions`` so user-added deny patterns survive re-render.
    * ``hooks`` — per-event union via ``_merge_hooks_json`` (nested/Claude
      schema) so user-authored hooks survive while retired harness hooks are
      dropped. A shallow replace here would wipe every user hook on re-render.
    """
    existing: dict[str, Any] = {}
    if out.exists():
        try:
            text = out.read_text(encoding="utf-8")
        except OSError:
            text = ""
        if text:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                existing = parsed
    merged = {**existing, **new_data}
    new_perms = new_data.get("permissions")
    existing_perms = existing.get("permissions")
    if isinstance(new_perms, dict) and isinstance(existing_perms, dict):
        merged["permissions"] = _merge_permissions(existing_perms, new_perms, dry_run=dry_run)
    new_hooks = new_data.get("hooks")
    existing_hooks = existing.get("hooks")
    if isinstance(new_hooks, dict) and isinstance(existing_hooks, dict):
        merged["hooks"] = _merge_hooks_json(
            {"hooks": existing_hooks},
            {"hooks": new_hooks},
            schema="nested",
        )["hooks"]
    for key in _SETTINGS_KEYS_OWNED_BY_HARNESS:
        if key not in new_data:
            merged.pop(key, None)
    return merged


def _is_settings_json(fe: FileEntry) -> bool:
    return fe.path.name == "settings.json"


def _is_hooks_json(fe: FileEntry) -> bool:
    return str(fe.path).endswith("hooks.json")


def resolve_output_path(target_dir: Path, fe_path: Path) -> Path:
    """Resolve where a FileEntry should be written/read.

    `target_dir` 는 보통 `<project>/.claude` (CLI dispatch). `.cursor/`,
    `.codex/`, `.agents/`, `AGENTS.md` 는 `.claude/` 의 sibling 이라
    `target_dir.parent` 기준으로 resolve.

    그 외 자산은 기존대로 ``target_dir / fe_path``. reconcile.py 도 동일
    helper 사용 — 같은 path 에 read/write/backup 이 일관.
    """
    path_str = str(fe_path)
    if (
        path_str.startswith(".cursor/")
        or path_str.startswith(".codex/")
        or path_str.startswith(".agents/")
        or path_str == "AGENTS.md"
    ):
        return target_dir.parent / fe_path
    return target_dir / fe_path


def _is_cursor_mdc(fe: FileEntry) -> bool:
    """Cursor rules — ``.cursor/rules/*.mdc``. Plain markdown + Cursor frontmatter
    (``description``, ``globs``, ``alwaysApply``). 우리 ``content_hash`` 등 메타는
    Phase 1 A1.frontmatter 검증 결과 따라 추후 sidecar 분리 가능 — 현재는 jinja
    template 이 frontmatter 자체를 만들어내므로 ``_render_pure_text`` 로 처리.
    """
    return str(fe.path).startswith(".cursor/rules/") and fe.path.suffix == ".mdc"


def _is_cursor_command(fe: FileEntry) -> bool:
    """Cursor slash commands — ``.cursor/commands/*.md``.

    **Currently dead code** — no template feeds ``.cursor/commands/`` because
    Cursor 2.4+ reads ``.claude/commands/hm/*.md`` natively (verified
    empirically via kairos 0.5.7 forensic on 2026-05-08; see
    ``tests/cursor-compat/results-2026-05-08.md``). Kept as a reserved
    dispatch in case a future Cursor release regresses the single-source
    contract — adding a ``templates/cursor/commands/`` directory would be
    sufficient to reactivate it. Until that happens, the dispatch evaluates
    to False on every FileEntry produced by synthesize.
    """
    return str(fe.path).startswith(".cursor/commands/") and fe.path.suffix == ".md"


def _is_cursor_mcp_json(fe: FileEntry) -> bool:
    """Cursor MCP config — ``.cursor/mcp.json`` (pure JSON, no frontmatter)."""
    return str(fe.path) == ".cursor/mcp.json"


def _is_schemas_json(fe: FileEntry) -> bool:
    """Schema files under ``.claude/schemas/*.json`` — pure JSON, frontmatter-prohibited.

    The external consumer is ``codex exec --output-schema`` (PLAN-codex-second-llm-integration
    ADR-008), which expects a JSON Schema document. ``fe.path`` inside ``.claude/``
    uses paths relative to the target dir, so the prefix is ``schemas/`` (no
    leading dot, no ``.claude/`` prefix — see ``resolve_output_path``).
    """
    return str(fe.path).startswith("schemas/") and fe.path.suffix == ".json"


def _is_codex_hooks_json(fe: FileEntry) -> bool:
    """Codex hooks — ``.codex/hooks.json`` (pure JSON, PascalCase Codex schema)."""
    return str(fe.path) == ".codex/hooks.json"


def _is_codex_config_toml(fe: FileEntry) -> bool:
    """Codex main config — ``.codex/config.toml`` (pure TOML, no frontmatter)."""
    return str(fe.path) == ".codex/config.toml"


def _is_codex_agent_toml(fe: FileEntry) -> bool:
    """Codex agent definition — ``.codex/agents/<name>.toml`` (pure TOML)."""
    return str(fe.path).startswith(".codex/agents/") and fe.path.suffix == ".toml"


def _is_agents_md(fe: FileEntry) -> bool:
    """AGENTS.md at project root — pure text with HTML-comment metadata."""
    return str(fe.path) == "AGENTS.md"


def _render_pure_toml(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,  # noqa: ARG001 — kept for dispatch signature parity
    merge_with_existing: bool = False,
    merge_reports: dict[Path, MergeReport] | None = None,
) -> Path:
    """Render pure TOML (no frontmatter prefix), validated via tomllib.loads().

    Used for ``.codex/config.toml`` and ``.codex/agents/<name>.toml``.
    Raises ``ValueError`` (with template name) if the rendered output is not
    valid TOML — mirrors ``_render_pure_json`` error contract.

    When ``merge_with_existing`` is True (Phase 2 v0.23.1, ADR-004/007), and an
    existing file on disk carries ``# @hm:user:<id>`` / ``# @hm:/user:<id>`` markers,
    ``block_merge`` is invoked with ``HASH_COMMENT`` style to preserve user-block content.
    The merged result must still parse as valid TOML — if a user's content
    between markers breaks TOML syntax, the merge raises ``ValueError`` rather
    than silently writing invalid TOML; backup remains the recovery path.
    """
    from harness_maker.block_merge import MarkerStyle, has_markers

    template = env.get_template(fe.template)
    rendered = template.render(**fe.context)
    try:
        tomllib.loads(rendered)
    except tomllib.TOMLDecodeError as e:
        msg = f"Template {fe.template} rendered invalid TOML for {fe.path}: {e}"
        raise ValueError(msg) from e

    body_text = _normalize_body(rendered).decode("utf-8")
    out = resolve_output_path(target_dir, fe.path)

    if merge_with_existing and out.exists():
        try:
            existing_text = out.read_text(encoding="utf-8")
        except OSError as exc:
            import typer

            typer.echo(
                f"WARN: could not read existing {fe.path} ({exc}); "
                f"falling back to template overwrite. Backup is the recovery path.",
                err=True,
            )
        else:
            if has_markers(existing_text, MarkerStyle.HASH_COMMENT) and has_markers(
                body_text, MarkerStyle.HASH_COMMENT
            ):
                merged, report = block_merge(existing_text, body_text, MarkerStyle.HASH_COMMENT)
                # Verify merged result still parses as valid TOML — user content
                # inside markers can be arbitrary; if it breaks the TOML, fall
                # back to template overwrite + WARN (user data still in backup).
                try:
                    tomllib.loads(merged)
                except tomllib.TOMLDecodeError as exc:
                    import typer

                    typer.echo(
                        f"WARN: merged {fe.path} is invalid TOML ({exc}); "
                        f"falling back to template overwrite. Backup is the recovery path.",
                        err=True,
                    )
                else:
                    body_text = merged
                    if merge_reports is not None:
                        merge_reports[fe.path] = report

    body_bytes = body_text.encode("utf-8") if isinstance(body_text, str) else body_text
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    if not dry_run:
        atomic_write(out, body_bytes)
    return out


def _render_agents_md(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,
    merge_reports: dict[Path, MergeReport] | None = None,
) -> Path:
    """Render AGENTS.md as pure text with a leading HTML-comment metadata line.

    AGENTS.md has no YAML frontmatter (Codex would display it as literal text).
    Provenance is stored in ``<!-- harness-maker: content_hash=... version=... -->``.
    Block-merge markers (``<!-- @hm:user:* -->``) work unchanged because Codex
    ignores HTML comments.

    When ``merge_reports`` is provided the existing file's user blocks are
    preserved into the freshly rendered template — same contract as the YAML
    frontmatter path in ``_render_text_file``.
    """
    template = env.get_template(fe.template)
    rendered = template.render(**fe.context)
    body_text = rendered

    # Block-merge: splice OLD user blocks into fresh template body.
    if merge_reports is not None:
        out_path = resolve_output_path(target_dir, fe.path)
        if out_path.exists():
            try:
                existing = out_path.read_text(encoding="utf-8")
                old_body = _strip_agents_md_metadata(existing)
                merged, report = block_merge(old_body, rendered)
                body_text = merged
                merge_reports[fe.path] = report
            except Exception:  # noqa: BLE001 — fall back to plain replace
                pass

    body_bytes = _normalize_body(body_text)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    ts = freeze_time.isoformat() if freeze_time else datetime.now(UTC).isoformat()
    metadata = (
        f"<!-- harness-maker: content_hash={body_hash}"
        f" version={__version__} generated_at={ts} -->\n"
    )
    final_bytes = metadata.encode("utf-8") + body_bytes
    out = resolve_output_path(target_dir, fe.path)
    if not dry_run:
        atomic_write(out, final_bytes)
    return out


def _render_pure_text(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,  # noqa: ARG001 — kept for dispatch signature parity
) -> Path:
    """Render template body verbatim, no provenance frontmatter.

    Used for files whose external consumer rejects a YAML preamble:

    - ``.sh`` wrappers under ``.claude/lib/`` — bash interprets ``---`` as
      a command
    - ``.cursor/rules/*.mdc`` — Cursor frontmatter parser may strict-reject
      our ``content_hash`` / ``generated_by`` keys (Phase 1 A1.frontmatter
      검증 결과에 따라 sidecar 메타 분리 가능)
    - ``.cursor/commands/*.md`` — Cursor slash commands are plain markdown

    Provenance is sacrificed because these files are small, reproducible
    from the template, and re-rendered every time the user runs
    ``/harness-maker:make``. Reconcile of ``.cursor/`` 자산은 Phase 2.4 에서
    별도 정책 (sidecar 또는 항상 REPLACE).
    """
    template = env.get_template(fe.template)
    rendered = template.render(**fe.context)
    body_bytes = _normalize_body(rendered)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    out = resolve_output_path(target_dir, fe.path)
    if not dry_run:
        atomic_write(out, body_bytes)
    return out


def _is_pure_text(fe: FileEntry) -> bool:
    """Files rendered without a YAML provenance prefix (interpreter would
    choke on it). Currently shell wrappers under ``.claude/lib/``.
    """
    return str(fe.path).endswith(".sh")


def _render_pure_json(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,  # noqa: ARG001 — kept for dispatch signature parity
) -> Path:
    """Render pure JSON (no frontmatter prefix).

    Used for files whose external consumer expects pure JSON:

    - ``.claude/hooks/hooks.json`` — jq-parseable, Claude Code spec
    - ``.cursor/mcp.json`` — Cursor MCP config

    Provenance is intentionally omitted; both are small, reproducible from the
    template, and re-rendered every time. Frontmatter invariant gate explicitly
    excludes them.
    """
    # A FRESH render (no existing file to merge) routes .cursor/hooks.json and
    # .codex/hooks.json here — NOT through _render_hooks_json_merged — so the
    # ADR-005 leak-check guard must fire here too, else 2 of 3 IDE hook surfaces
    # bypass it on the common path. No-op for non-hook pure JSON (.cursor/mcp.json,
    # schemas) — those contexts carry no `harness_maker_src_path`.
    _assert_portable_install_ref(fe.context.get("harness_maker_src_path"))
    template = env.get_template(fe.template)
    rendered = template.render(**fe.context)
    try:
        data: dict[str, Any] = json.loads(rendered)
    except json.JSONDecodeError as e:
        msg = f"Template {fe.template} rendered invalid JSON for {fe.path}: {e}"
        raise ValueError(msg) from e
    if not isinstance(data, dict):
        msg = f"Template {fe.template} must render a JSON object (got {type(data).__name__})"
        raise ValueError(msg)
    body_bytes = _format_settings_json(data)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    out = resolve_output_path(target_dir, fe.path)
    if not dry_run:
        atomic_write(out, body_bytes)
    return out


def _render_json_file(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,
) -> Path:
    """settings.json — JSON body wrapped in YAML provenance frontmatter."""
    return _render_settings_json(
        fe,
        env,
        target_dir,
        dry_run=dry_run,
        freeze_time=freeze_time,
    )


# ──────────────────────────────────────────────────────────────────────────────
# hooks.json in-place 3-way merge (Phase 1+3, ADR-003/006)
# ──────────────────────────────────────────────────────────────────────────────


# Matches any harness-maker-managed hook command by its `python -m
# harness_maker.<invocation>` suffix, regardless of the `uv run --with <path>`
# prefix. The prefix is volatile: it changes on every `/plugin update` (cache
# version bump), on a marketplace switch (`harness-maker-local` cache ↔ GitHub
# `harness-maker` cache), and for dev-repo installs (`--with /home/noel/...`).
# The module namespace is the stable identity — `harness_maker.*` is ours, so a
# match is proof of ownership. Capturing the full invocation (module + trailing
# args) keeps e.g. `loop_gate --mode stop-hook` distinct from other modes.
_HM_MANAGED_CMD_RE = re.compile(r"(?:^|\s)python -m (?P<invocation>harness_maker\.\S.*)$")


def _normalize_hm_managed_command(cmd: str) -> str:
    """Elide the volatile `uv run --with <path>` prefix from a harness-maker hook.

    Why this is the load-bearing dedup primitive: each `/plugin update` OR
    marketplace switch re-renders every hook command with a different `--with`
    path while the hook is semantically identical. Without path-agnostic
    normalization, ``_entry_identity`` treats the on-disk form and the freshly
    shipped form as distinct — the merge classifies the on-disk entry as
    "user-added" (not in the shipped set) and preserves it, accumulating
    duplicate hooks that fire 2-3x per event AND dangle at paths a later
    `/plugin update` cleans up (spoton triplication, 2026-05-28).

    Keying identity on the `python -m harness_maker.<invocation>` suffix is
    path-agnostic by design (ADR-001 of PLAN-hooks-merge-stale-path-dedup): it
    matches local-cache, GitHub-cache, dev-repo, and any future path form. The
    normalized identity is ``"<HM>:<invocation>"`` (module + trailing args).
    Commands without our module namespace (user-authored hooks) are returned
    unchanged so user identity stays exact.
    """
    m = _HM_MANAGED_CMD_RE.search(cmd)
    if m is None:
        return cmd
    return f"<HM>:{m.group('invocation')}"


# Normalized (`<HM>:`) invocations of hooks harness-maker ONCE shipped but has now
# RETIRED from every settings template (PLAN-hook-inventory-efficiency-audit ADR-001).
# `_strip_shipped_commands` drops these from a preserved user entry IN ADDITION to the
# template's currently-shipped commands, so removing a hook from the template actually
# removes it from every existing user's disk on the next re-render. The union-merge
# alone would preserve it forever as pseudo-user content (see `_merge_hooks_json`'s
# deliberate no-retire note) — this set is the ONLY thing that retires a live hook.
#
# APPEND-ONLY. Membership is bounded by ONE test-enforced invariant:
#   - ABSENT from every current NESTED hook template (settings.json AND
#     `.codex/hooks.json` — both routed through `_merge_hooks_json(schema="nested")`,
#     so `_strip_shipped_commands` applies this set to ALL of them, not just settings)
#     (`test_retired_invocations_absent_from_current_templates`) — never retire
#     something a template still ships. (Cursor's `.cursor/hooks.json` is flat-schema
#     and the strip skips flat entirely, so it is out of scope.)
#
# ⚠️ Unlike `_HARNESS_SHIPPED_DENY_LITERALS`, there is NO second "provably enforces
# nothing" invariant here: these are LIVE hooks. Deletion safety rests ENTIRELY on the
# accepted risk that no user hand-wired the exact internal module themselves — a
# deliberate, documented risk acceptance, NOT the deny-literal's proof. This is the
# narrow, curated form the REVIEW-round-1 comment in `_merge_hooks_json` demanded
# (positive membership list, never a blanket `<HM>:`-prefix inference).
_HARNESS_RETIRED_HOOK_INVOCATIONS: frozenset[str] = frozenset(
    {
        "<HM>:harness_maker.hooks.autopilot_guard",
        "<HM>:harness_maker.hooks.autopilot_guard --mode stop-hook",
    }
)


# Joins a matcher group's normalized commands into the identity tuple's command
# slot. ASCII Unit Separator — cannot occur in a real shell command, so it can
# never collide with command text.
_IDENT_CMD_SEP = "\x1f"


def _entry_identity(
    entry: Any,  # noqa: ANN401 — JSON entries are heterogeneous
    *,
    schema: Literal["nested", "flat"],
) -> tuple[str, str, str] | None:
    """Compute a hooks.json entry's identity tuple for dedup; None on malformed.

    Returns:
      - nested (Claude/Codex): ``(matcher_or_empty, <every normalized command in
        the group, joined by _IDENT_CMD_SEP>, hooks[0]['type'])``
      - flat (Cursor): ``(matcher_or_empty, normalized_command, "")`` — third slot
        always empty so both schemas share a single tuple type for set ops.

    **Why all commands, not just ``hooks[0]``** (ADR-008 of
    PLAN-permission-deny-and-hooks-wiring): a matcher group holds N commands —
    e.g. settings.json's Stage-1 SessionStart group carries both
    ``sessionid_envfile`` and ``autopilot_autoarm``. Keying on the first command
    alone made a group whose *later* commands differ look identical to the
    shipped one, so the merge classified it as "already shipped" and replaced the
    group wholesale. When a user had appended their own command to one of our
    groups, that dropped the user's command with it — a silent data loss.

    The command portion is normalized via ``_normalize_hm_managed_command``
    so harness-maker-managed entries dedup correctly across cache-version
    bumps (the original bug: each /plugin update accumulated stale entries).
    User-authored commands round-trip unchanged.

    "Malformed" includes: not a dict, non-string fields, missing required field
    (`hooks` for nested with non-empty list of dicts; `command` for flat).
    Malformed entries are dropped from both shipped and user sets — backup is
    the recovery path per ADR-001.
    """
    if not isinstance(entry, dict):
        return None
    matcher_val = entry.get("matcher", "")
    if not isinstance(matcher_val, str):
        return None
    if schema == "nested":
        hooks_list = entry.get("hooks")
        if not isinstance(hooks_list, list) or not hooks_list:
            return None
        norm_cmds: list[str] = []
        for h in hooks_list:
            if not isinstance(h, dict):
                return None
            cmd_val = h.get("command")
            if not isinstance(cmd_val, str):
                return None
            norm_cmds.append(_normalize_hm_managed_command(cmd_val))
        first = hooks_list[0]
        type_val = first.get("type", "command")
        if not isinstance(type_val, str):
            return None
        return (matcher_val, _IDENT_CMD_SEP.join(norm_cmds), type_val)
    # flat (Cursor)
    flat_cmd = entry.get("command")
    if not isinstance(flat_cmd, str):
        return None
    return (matcher_val, _normalize_hm_managed_command(flat_cmd), "")


def _is_mixed_group(hooks_list: list[Any]) -> bool:
    """Does this nested entry hold at least one command we do not manage?

    The ADR-003 ownership signal. `_normalize_hm_managed_command` folds our commands
    to a `<HM>:` form and round-trips everything else unchanged, so a command that
    survives normalization verbatim is not ours.
    """
    return any(
        isinstance(h, dict)
        and isinstance(h.get("command"), str)
        and _normalize_hm_managed_command(h["command"]) == h["command"]
        for h in hooks_list
    )


def _harness_commands_in(entry: Any) -> set[str]:  # noqa: ANN401 — heterogeneous JSON
    """Normalized harness commands a preserved user entry still carries."""
    hooks_list = entry.get("hooks") if isinstance(entry, dict) else None
    if not isinstance(hooks_list, list):
        return set()
    out: set[str] = set()
    for h in hooks_list:
        if isinstance(h, dict) and isinstance(h.get("command"), str):
            norm = _normalize_hm_managed_command(h["command"])
            if norm != h["command"]:
                out.add(norm)
    return out


def _entry_commands(entry: Any, *, schema: Literal["nested", "flat"]) -> list[str]:  # noqa: ANN401
    """Every command string an entry carries, in order — both schemas."""
    if not isinstance(entry, dict):
        return []
    if schema == "flat":
        cmd = entry.get("command")
        return [cmd] if isinstance(cmd, str) else []
    hooks_list = entry.get("hooks")
    if not isinstance(hooks_list, list):
        return []
    return [
        h["command"]
        for h in hooks_list
        if isinstance(h, dict) and isinstance(h.get("command"), str)
    ]


def _harness_commands_of(entry: Any, *, schema: Literal["nested", "flat"]) -> set[str]:  # noqa: ANN401
    """Normalized harness commands an entry carries — schema-agnostic.

    A flat (Cursor) entry holds its single command at the entry level, so
    `_harness_commands_in`, which reads `hooks[]`, finds nothing there. Routing both
    schemas through one reader is what let ADR-011 and ADR-014 extend to Cursor.
    """
    if schema == "nested":
        return _harness_commands_in(entry)
    return {
        norm
        for cmd in _entry_commands(entry, schema=schema)
        if (norm := _normalize_hm_managed_command(cmd)) != cmd
    }


#: The `--with <value>` token of a `uv run` invocation, quoted or bare. ADR-014 swaps
#: exactly this span and nothing else.
_WITH_REF_RE = re.compile(r"--with\s+(?:\"[^\"]*\"|'[^']*'|\S+)")


def _command_module(cmd: str) -> str | None:
    """The `harness_maker.<module>` a command runs, ignoring its arguments.

    `_normalize_hm_managed_command` folds module AND trailing args into one identity,
    which is right for dedup — two invocations with different flags are different hooks
    — but wrong as the key for a ref refresh: a user who appended `--exempt projects/`
    would never match the template's argument-free form and would keep a dead `--with`
    forever. Refresh keys on the module; identity still keys on the whole thing.
    """
    m = _HM_MANAGED_CMD_RE.search(cmd)
    return m.group("invocation").split()[0] if m else None


def _refresh_ref(cmd: str, shipped_refs: dict[str, str]) -> str:
    """Return `cmd` with its install ref brought up to the template's, or unchanged."""
    module = _command_module(cmd)
    token = shipped_refs.get(module) if module else None
    return _splice_install_ref(cmd, token) if token else cmd


def _splice_install_ref(cmd: str, ref_token: str) -> str:
    """Swap the `--with <value>` token, preserving everything else in the command.

    ADR-014. Replacing the WHOLE command with the template's text — what ADR-007 did
    first — discards two things the user meant: a prefix before `python -m` (an env
    assignment, a PATH shim; every Cursor command has one) and any trailing arguments.
    Only the ref is stale, so only the ref is replaced.
    """
    if _WITH_REF_RE.search(cmd) is None:
        return cmd
    return _WITH_REF_RE.sub(lambda _: ref_token, cmd, count=1)


def _drop_commands_from_entry(
    entry: Any,  # noqa: ANN401 — heterogeneous JSON
    drop: set[str],
    *,
    schema: Literal["nested", "flat"] = "nested",
) -> Any | None:  # noqa: ANN401
    """Command-level removal (ADR-004), preserving siblings, order and metadata.

    Entry-level removal would take co-located commands the user never scoped —
    `permission_gate` and `worktree_gate` share `spec_gate`'s group.

    ADR-015: a flat (Cursor) entry holds ONE command at the entry level, so command-level
    and entry-level removal coincide there. ADR-009 had withdrawn flat suppression because
    the only choice available was delete-or-not; ADR-011 added a third action (subtract),
    which is what makes it safe to re-enter this path.
    """
    if schema == "flat":
        cmd = entry.get("command") if isinstance(entry, dict) else None
        if isinstance(cmd, str) and _command_module(cmd) in drop:
            return None
        return entry
    hooks_list = entry.get("hooks") if isinstance(entry, dict) else None
    if not isinstance(hooks_list, list):
        return entry
    kept = [
        h
        for h in hooks_list
        if not (
            isinstance(h, dict)
            and isinstance(h.get("command"), str)
            and _command_module(h["command"]) in drop
        )
    ]
    if not kept:
        return None
    if len(kept) == len(hooks_list):
        return entry
    return {**entry, "hooks": kept}


def _matcher_terms(matcher: str) -> frozenset[str] | None:
    """A tool-name alternation as a set, or None when the matcher is not one.

    Claude Code matches a hook's `matcher` against the TOOL NAME, and every matcher this
    harness ships is either such an alternation (`Write|Edit|MultiEdit`, `Bash`, `auto`)
    or the wildcard `*`. `*` and any regex-shaped matcher return None, which routes the
    caller to the conservative branch rather than to a subtraction it cannot justify.
    """
    if not matcher:
        return None
    parts = matcher.split("|")
    if not all(p and p.replace("_", "").isalnum() for p in parts):
        return None
    return frozenset(parts)


def _residual_matcher(template_matcher: str, user_matchers: set[str]) -> str | None:
    """What the template must still cover after the user's matchers take their share.

    Returns `""` when the user covers everything (the template entry gives the command
    up entirely), the original matcher when the two are disjoint (nothing to do), a
    narrowed alternation in between, and None when either side is not decidable.
    Template term ORDER is preserved — the residual is the template's own string with
    the covered terms removed, not a re-sorted set.
    """
    t_terms = _matcher_terms(template_matcher)
    if t_terms is None:
        return None
    covered: set[str] = set()
    for um in user_matchers:
        u_terms = _matcher_terms(um)
        if u_terms is None:
            return None
        covered |= u_terms
    return "|".join(p for p in template_matcher.split("|") if p not in covered)


def _residual_entries(
    entry: Any,  # noqa: ANN401
    residual: list[tuple[str, str]],
    *,
    schema: Literal["nested", "flat"] = "nested",
) -> list[Any]:
    """Re-emit each residual command as its own entry under the narrowed matcher.

    The hook dict is carried over verbatim so `timeout` / `statusMessage` survive; only
    the entry's `matcher` changes. Commands sharing one residual matcher are grouped.
    """
    if not residual:
        return []
    if schema == "flat":
        # One command per entry, so the residual is the same entry under a new matcher.
        cmd = entry.get("command") if isinstance(entry, dict) else None
        if not isinstance(cmd, str):
            return []
        module = _command_module(cmd)
        return [{**entry, "matcher": rest} for c, rest in residual if c == module]
    hooks_list = entry.get("hooks") if isinstance(entry, dict) else None
    if not isinstance(hooks_list, list):
        return []
    by_matcher: dict[str, list[Any]] = {}
    for h in hooks_list:
        if not (isinstance(h, dict) and isinstance(h.get("command"), str)):
            continue
        module = _command_module(h["command"])
        for cmd, rest in residual:
            if cmd == module:
                by_matcher.setdefault(rest, []).append(h)
    return [{**entry, "matcher": rest, "hooks": hooks} for rest, hooks in by_matcher.items()]


def _warn_live_double_fires(
    *,
    event: str,
    new_entries: list[Any],
    per_entry_drop: list[set[str]],
    user_scoped: dict[str, set[str]],
    schema: Literal["nested", "flat"] = "nested",
) -> None:
    """Warn per (command, template matcher, user matcher) that can BOTH fire.

    Keying this per-command — "warn when no entry gave the command up" — was too narrow:
    a command suppressed on one template entry and left on another is a real double-fire
    that stayed silent. Two matchers can both fire when their tool-name sets intersect,
    or when either is not decidable (a regex or `*`), in which case overlap is assumed.
    """
    live: list[tuple[str, str, str]] = []
    for e, drop in zip(new_entries, per_entry_drop, strict=True):
        tm = e.get("matcher", "") if isinstance(e, dict) else ""
        tm = tm if isinstance(tm, str) else ""
        modules = {m for c in _entry_commands(e, schema=schema) if (m := _command_module(c))}
        for cmd in sorted(modules - drop):
            for um in sorted(user_scoped.get(cmd, set())):
                t_terms, u_terms = _matcher_terms(tm), _matcher_terms(um)
                if t_terms is None or u_terms is None or (t_terms & u_terms):
                    live.append((cmd, tm, um))
    if not live:
        return
    import typer  # local, matching this module's existing lazy-import convention

    for cmd, tm, um in live:
        typer.echo(
            f"WARN: {event}: {cmd!r} is registered twice — the template ships it under "
            f"matcher {tm!r} and your own entry carries it under {um!r}, which can match "
            "the same tool. It will fire twice. Scope it under the template's matcher, or "
            "remove it from your entry, to silence this.",
            err=True,
        )


def _strip_shipped_commands(
    entry: Any,  # noqa: ANN401 — JSON entries are heterogeneous
    shipped_cmds: set[str],
    *,
    schema: Literal["nested", "flat"],
    shipped_refs: dict[str, str] | None = None,
) -> Any | None:  # noqa: ANN401
    """Drop commands the template already ships (or has RETIRED) from a preserved entry.

    Returns None when nothing would remain (the caller then omits the entry).

    Only ``<HM>:``-normalized commands can match ``shipped_cmds`` or
    ``_HARNESS_RETIRED_HOOK_INVOCATIONS``, so a user's own command is never removed
    here. Retired invocations (ADR-001 of PLAN-hook-inventory-efficiency-audit) are
    dropped even though the current template no longer ships them — that is how a
    hook removed from the template gets removed from an existing user's disk. A flat
    (Cursor) entry is never STRIPPED — the retired hooks were only ever in
    `.claude/settings.json` (nested) — but ADR-015 does refresh its install ref, because
    a preserved flat entry carrying a pruned plugin-cache path is a dead blocking gate
    on exactly the same terms as the nested one.
    """
    if schema == "flat":
        cmd = entry.get("command") if isinstance(entry, dict) else None
        if not (isinstance(cmd, str) and shipped_refs):
            return entry
        fresh = _refresh_ref(cmd, shipped_refs)
        return entry if fresh == cmd else {**entry, "command": fresh}
    hooks_list = entry.get("hooks")
    if not isinstance(hooks_list, list):
        return entry
    # PLAN-render-degrades-live-harness ADR-003/005. A MIXED group — one holding at
    # least one command that is not harness-managed — is evidence the user owns this
    # entry, so our commands stay inside their scoping. A PURE-harness group is
    # indistinguishable from our own older entry (there is no provenance at merge
    # time), and preserving it would silently revert the gate to the previous
    # release's matcher, so it keeps being stripped.
    #
    # ADR-005: retirement is UNCONDITIONAL. A retired command has no template matcher
    # to reason about, and membership in the retired set is curated — the one place
    # where provenance is positive by construction.
    mixed = _is_mixed_group(hooks_list)
    to_strip = (
        set(_HARNESS_RETIRED_HOOK_INVOCATIONS)
        if mixed
        else (shipped_cmds | _HARNESS_RETIRED_HOOK_INVOCATIONS)
    )
    kept = [
        h
        for h in hooks_list
        if not (
            isinstance(h, dict)
            and isinstance(h.get("command"), str)
            and _normalize_hm_managed_command(h["command"]) in to_strip
        )
    ]
    if not kept:
        return None
    # ADR-007. A preserved harness command is kept under the USER's matcher but with the
    # TEMPLATE's current text. `_normalize_hm_managed_command` elides the
    # `uv run --with <path>` prefix for identity, so without this the user's copy — which
    # may name a plugin-cache dir a later `/plugin update` pruned — wins over the freshly
    # validated one and the suppression below deletes the only working copy. That froze a
    # dead blocking gate permanently: re-render reproduced the same output byte for byte,
    # so nothing could repair it. It is the failure ADR-003's own Context predicted.
    refreshed = kept
    if mixed and shipped_refs:
        refreshed = [
            {**h, "command": fresh}
            if (
                isinstance(h, dict)
                and isinstance(h.get("command"), str)
                and (fresh := _refresh_ref(h["command"], shipped_refs)) != h["command"]
            )
            else h
            for h in kept
        ]
    if refreshed == hooks_list:
        return entry
    return {**entry, "hooks": refreshed}


# Codex's hooks parser is strict: it accepts exactly these two top-level keys and
# rejects the WHOLE file on anything else ("unknown field `preset`, expected
# `description` or `hooks`"), so every hook in it goes dead. harness-maker shipped a
# `preset` provenance stamp here until 0.51.1 — the merge below has to prune it back
# out of a user's on-disk file, because top-level merge is existing-survives-when-
# template-is-silent and simply dropping it from the template would leave the stale
# key (and the broken file) in place forever.
_CODEX_HOOKS_ALLOWED_TOP_LEVEL = frozenset({"description", "hooks"})


def _merge_hooks_json(
    existing: dict[str, Any],
    new_data: dict[str, Any],
    *,
    schema: Literal["nested", "flat"],
    allowed_top_level: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Schema-aware in-place 3-way merge of hooks.json (ADR-003/006).

    Per-event union: template entries (in template order) + user entries whose
    identity tuple is NOT in the template set (preserving original disk order
    within the user-entries group).

    Events present in existing but not in new_data (user-added events for
    custom hook surfaces) are preserved verbatim.

    Top-level non-``hooks`` keys (e.g., Cursor's ``"version": 1``) follow
    template-wins-on-conflict, existing-survives-when-absent — same shape as
    ``_shallow_merge_existing_json``. ``allowed_top_level`` overrides that for a
    consumer whose parser rejects unknown keys (Codex): keys outside the set are
    pruned from BOTH sides with a stderr warning, because existing-survives means
    a stale harness-shipped key would otherwise never leave the user's disk.
    """
    existing_hooks = existing.get("hooks", {})
    new_hooks = new_data.get("hooks", {})

    if not isinstance(existing_hooks, dict) or not isinstance(new_hooks, dict):
        # Malformed shape on either side — fall back to template overwrite.
        return new_data

    if allowed_top_level is not None:
        dropped = sorted(set(existing) - allowed_top_level)
        if dropped:
            import typer

            typer.echo(
                "WARN: dropping top-level key(s) "
                + ", ".join(repr(k) for k in dropped)
                + " from .codex/hooks.json — Codex accepts only "
                + ", ".join(repr(k) for k in sorted(allowed_top_level))
                + " and rejects the whole file otherwise.",
                err=True,
            )
        existing = {k: v for k, v in existing.items() if k in allowed_top_level}
        new_data = {k: v for k, v in new_data.items() if k in allowed_top_level}

    merged_hooks: dict[str, list[Any]] = {}
    all_events = set(existing_hooks.keys()) | set(new_hooks.keys())

    for event in all_events:
        existing_entries = existing_hooks.get(event, [])
        new_entries = new_hooks.get(event, [])

        if not isinstance(existing_entries, list):
            existing_entries = []
        if not isinstance(new_entries, list):
            new_entries = []

        shipped_identities: set[tuple[str, str, str]] = set()
        for e in new_entries:
            ident = _entry_identity(e, schema=schema)
            if ident is not None:
                shipped_identities.add(ident)

        shipped_cmds: set[str] = set()
        for e in new_entries:
            ident = _entry_identity(e, schema=schema)
            if ident is not None:
                shipped_cmds.update(ident[1].split(_IDENT_CMD_SEP))

        # ADR-007/008/014. The template side, indexed two ways. `shipped_refs` maps a
        # harness MODULE to the `--with <ref>` token this render produced for it — the
        # value a preserved user copy is refreshed to. Keyed on the module, not the full
        # normalized identity, so a command the user gave extra arguments still refreshes
        # (ADR-014). `shipped_matchers` maps the normalized identity to the matcher(s) it
        # ships under, which is what makes suppression matcher-aware, not event-global.
        shipped_refs: dict[str, str] = {}
        shipped_matchers: dict[str, set[str]] = {}
        shipped_modules: set[str] = set()
        for e in new_entries:
            if not isinstance(e, dict):
                continue
            matcher = e.get("matcher", "")
            matcher = matcher if isinstance(matcher, str) else ""
            for raw in _entry_commands(e, schema=schema):
                norm = _normalize_hm_managed_command(raw)
                if norm == raw:  # not ours
                    continue
                module = _command_module(raw)
                if module is None:
                    continue
                shipped_modules.add(module)
                shipped_matchers.setdefault(module, set()).add(matcher)
                ref = _WITH_REF_RE.search(raw)
                if ref:
                    shipped_refs.setdefault(module, ref.group(0))

        user_entries: list[Any] = []
        for e in existing_entries:
            ident = _entry_identity(e, schema=schema)
            if ident is None or ident in shipped_identities:
                continue
            # NOTE — there is deliberately NO "retire" branch here (REVIEW round 1).
            # A draft dropped any entry whose commands all normalize to `<HM>:`, on
            # the theory that a harness hook absent from the template is retired.
            # `<HM>:` marks our *namespace*, not our *authorship*: a user who
            # hand-wires `python -m harness_maker.gates.permission_gate` — a module
            # the staged rollout deliberately does not ship yet — would have it
            # silently deleted. The staged rollout itself creates that population.
            # The rule also bought nothing here: retirement only matters once a
            # template STOPS shipping something, which no current template does.
            # When it does (a dev_mode flip retiring spec_gate), gate it on positive
            # provenance — a prior-render manifest — not on a forgeable prefix.
            #
            # A MIXED group (our command(s) + the user's) is theirs — preserve it.
            # But appending it verbatim beside the shipped group would register our
            # command TWICE for the same event, so it fires twice: exactly the
            # duplication `_normalize_hm_managed_command` exists to prevent (the
            # 2026-05-28 spoton triplication). Reachable in practice because Claude
            # Code's `/hooks` UI appends into an existing matcher group. So keep the
            # user's commands and drop only the ones the template already ships.
            trimmed = _strip_shipped_commands(
                e, shipped_cmds, schema=schema, shipped_refs=shipped_refs
            )
            if trimmed is not None:
                user_entries.append(trimmed)

        # ADR-004. Whatever a preserved user group still carries of ours must NOT also
        # ship from the template: Claude Code runs EVERY matching hook, so it would
        # fire twice and the user's narrower matcher would buy nothing — the defect
        # would survive its own fix. Command-level, so siblings keep shipping.
        #
        # ADR-008 amends WHICH template entry gives the command up. ADR-009 had removed the
        # flat arm — a flat entry holds one command, so there is no mixed-group evidence and
        # the only signal left was the matcher difference ADR-003 rejected. **ADR-015
        # restores it**, because ADR-011 supplied a third action: subtract. Withdrawal was
        # the right call when the choice was delete-or-not; it is not once the residual can
        # be shipped. Cursor's duplicate was never harmless either — the preserved entry
        # keeps a pruned `--with` (a dead blocking gate) and `telemetry` on `postToolUse *`
        # appends a row per call, so the duplicate doubles the ledger's denominator.
        emitted_template: list[Any] = list(new_entries)
        if new_entries or user_entries:
            # ADR-016. Keyed on the MODULE, not the normalized identity. The reported
            # incident is a user who scoped `spec_gate` with an ARGUMENT — `--exempt
            # projects/` — not with a matcher (a Claude Code matcher matches tool names, so
            # a path exemption cannot be expressed in one at all). Trailing args are part of
            # the identity, so an identity-keyed rule never saw their variant as "ours", the
            # template's bare copy kept shipping beside it, and both fired: the exemption
            # bought nothing. That is the sentence this PLAN was opened with.
            #
            # Safe because no single event ships one module twice with different arguments
            # (verified across both settings templates × both dev_modes and cursor's), so
            # module and identity coincide on the template side today.
            user_scoped: dict[str, set[str]] = {}
            for e in user_entries:
                m = e.get("matcher", "") if isinstance(e, dict) else ""
                m = m if isinstance(m, str) else ""
                for cmd in _entry_commands(e, schema=schema):
                    module = _command_module(cmd)
                    if module and module in shipped_modules:
                        user_scoped.setdefault(module, set()).add(m)

            per_entry_drop: list[set[str]] = []
            # index → [(cmd, residual_matcher)] to re-emit beside that entry (ADR-011).
            per_entry_residual: list[list[tuple[str, str]]] = []
            for e in new_entries:
                tm = e.get("matcher", "") if isinstance(e, dict) else ""
                tm = tm if isinstance(tm, str) else ""
                drop: set[str] = set()
                residual: list[tuple[str, str]] = []
                for cmd, user_matchers in user_scoped.items():
                    ships_under = shipped_matchers.get(cmd, set())
                    if tm in user_matchers:
                        drop.add(cmd)  # branch 1 — the /hooks-UI shape: matchers coincide
                        continue
                    if len(ships_under) != 1 or tm not in ships_under:
                        continue  # branch 3 — several template homes; see the warning below
                    # ADR-011. The user's matcher differs and the command has ONE template
                    # home. Branch 2 used to drop it outright, which is the matcher-difference
                    # inference ADR-003 rejected and ADR-009 withdrew on the flat path: a user
                    # whose /hooks group carries a PREVIOUS release's matcher would pin the
                    # gate to it forever, so widening `Write|Edit` to `Write|Edit|MultiEdit`
                    # left MultiEdit permanently ungated with no diagnostic. Instead, subtract
                    # what the user now covers and keep shipping the remainder.
                    rest = _residual_matcher(tm, user_matchers)
                    if rest is None:
                        continue  # not decidable (regex/`*` form) — branch 3
                    if rest == "":
                        drop.add(cmd)  # the user covers everything this entry did
                    elif rest != tm:
                        drop.add(cmd)
                        residual.append((cmd, rest))
                    # rest == tm → the two matchers are disjoint, so there is no double-fire
                    # and nothing to do.
                per_entry_drop.append(drop)
                per_entry_residual.append(residual)

            _warn_live_double_fires(
                event=event,
                new_entries=new_entries,
                per_entry_drop=per_entry_drop,
                user_scoped=user_scoped,
                schema=schema,
            )

            if any(per_entry_drop):
                rebuilt: list[Any] = []
                for e, d, res in zip(new_entries, per_entry_drop, per_entry_residual, strict=True):
                    trimmed = _drop_commands_from_entry(e, d, schema=schema) if d else e
                    if trimmed is not None:
                        rebuilt.append(trimmed)
                    rebuilt.extend(_residual_entries(e, res, schema=schema))
                emitted_template = rebuilt

        merged_hooks[event] = emitted_template + user_entries

    # Top-level: template wins on overlap; existing survives where template
    # is silent. ``hooks`` is overwritten with the merged dict explicitly.
    result: dict[str, Any] = {**existing, **new_data}
    result["hooks"] = merged_hooks
    return result


def _render_hooks_json_merged(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,  # noqa: ARG001 — dispatch signature parity
) -> Path:
    """Render hooks.json with in-place 3-way merge (ADR-003/006).

    Schema dispatch by path:
      - ``.cursor/hooks.json`` → flat (lowercase camelCase, command at entry level)
      - everything else (``hooks/hooks.json``, ``.codex/hooks.json``) → nested

    Malformed existing JSON → fall back to template overwrite with warning on
    stderr. Backup (``.backup-<ts>/``) is the recovery path per ADR-001.

    ``fe.body_sha256`` is set to the MERGED file's hash (not template-only) so
    ``sweep_orphans()`` classifies the merged file as "ours-clean" via the
    manifest match path (resolves validator pass-2 W8).
    """
    _assert_portable_install_ref(fe.context.get("harness_maker_src_path"))
    template = env.get_template(fe.template)
    rendered = template.render(**fe.context)
    try:
        new_data: dict[str, Any] = json.loads(rendered)
    except json.JSONDecodeError as e:
        msg = f"Template {fe.template} rendered invalid JSON for {fe.path}: {e}"
        raise ValueError(msg) from e
    if not isinstance(new_data, dict):
        msg = f"Template {fe.template} must render a JSON object (got {type(new_data).__name__})"
        raise ValueError(msg)

    out = resolve_output_path(target_dir, fe.path)
    schema: Literal["nested", "flat"] = "flat" if str(fe.path) == ".cursor/hooks.json" else "nested"
    allowed_top_level = (
        _CODEX_HOOKS_ALLOWED_TOP_LEVEL if str(fe.path) == ".codex/hooks.json" else None
    )

    merged_data: dict[str, Any] = new_data
    if out.exists():
        try:
            existing_text = out.read_text(encoding="utf-8")
            existing_data = json.loads(existing_text)
        except (OSError, json.JSONDecodeError) as exc:
            # REVIEW fix (3/3 weak-consensus P1): use typer.echo(err=True) so
            # the warning is consistent with cli.py's stderr-aggregation and
            # surfaces in /hm:make slash-command conversation context (bare
            # print to sys.stderr is silently dropped by some slash-command
            # runners).
            import typer

            typer.echo(
                f"WARN: could not parse existing {fe.path} ({exc}); "
                f"falling back to template overwrite. Backup is the recovery path.",
                err=True,
            )
        else:
            if isinstance(existing_data, dict):
                merged_data = _merge_hooks_json(
                    existing_data,
                    new_data,
                    schema=schema,
                    allowed_top_level=allowed_top_level,
                )
            else:
                import typer

                typer.echo(
                    f"WARN: existing {fe.path} is not a JSON object "
                    f"(got {type(existing_data).__name__}); falling back to "
                    f"template overwrite. Backup is the recovery path.",
                    err=True,
                )

    body_bytes = _format_settings_json(merged_data)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    if not dry_run:
        atomic_write(out, body_bytes)
    return out


_STALE_HOOKS_JSON_TEMPLATE = "hooks/hooks.json.j2"


def render_stale_hooks_json_bytes(context: dict[str, Any]) -> bytes:
    """Pristine (no-merge) bytes of the retired `.claude/hooks/hooks.json`.

    ADR-005 (PLAN-permission-deny-and-hooks-wiring): the file is no longer a
    blueprint FileSpec, but cli must still recognise a byte-pristine (zero
    user-content) copy on disk to retire it. Mirrors the exact byte pipeline
    `_render_hooks_json_merged` uses for a FRESH render (template → json.loads →
    `_format_settings_json`), deliberately WITHOUT the merge step so a file that
    folded a user hook does not compare equal to itself.
    """
    env = _make_env()
    template = env.get_template(_STALE_HOOKS_JSON_TEMPLATE)
    rendered = template.render(**context)
    data = json.loads(rendered)
    if not isinstance(data, dict):
        msg = f"Template {_STALE_HOOKS_JSON_TEMPLATE} must render a JSON object"
        raise ValueError(msg)
    return _format_settings_json(data)


_VARIANT_KEY_RE = re.compile(r"^communication_variant:\s*([A-Za-z_-]+)\s*$", re.MULTILINE)


def _extract_source_communication_variant(template_name: str, env: Environment) -> str | None:
    """Pre-render: read template source frontmatter, return ``communication_variant``.

    ADR-002 (PLAN-antisycophancy-2026-05). Variant must be available as a
    Jinja context variable BEFORE ``template.render()`` resolves the body's
    ``{% include "agents/_partials/communication_" ~ communication_variant ~ ".md.j2" %}``.
    The existing ``_split_template_frontmatter`` reads RENDERED output
    (post-render) and is unrelated. This is a separate, new code path.

    Uses regex on the raw frontmatter block instead of ``yaml.safe_load``
    because template-side frontmatter may carry Jinja expressions (e.g.
    ``name: {{ name }}``) that break YAML parsing. We only need the one key.

    Returns the variant string when frontmatter declares it; ``None`` when
    the source has no frontmatter or no key (caller decides whether absence
    is an error — Jinja's StrictUndefined makes the consequence loud).
    """
    if env.loader is None:
        return None
    try:
        source, _, _ = env.loader.get_source(env, template_name)
    except Exception:  # noqa: BLE001 — template missing is the caller's concern
        return None
    if not source.startswith("---\n"):
        return None
    end = source.find("\n---\n", 4)
    if end == -1:
        return None
    m = _VARIANT_KEY_RE.search(source[4:end])
    if not m:
        return None
    variant = m.group(1)
    if variant not in {"full", "reframe", "soft"}:
        return None
    return variant


def _split_template_frontmatter(rendered: str) -> tuple[dict[str, Any], str]:
    """If rendered text starts with YAML frontmatter (---...---), split and parse it.

    Returns (template_frontmatter_dict, body_without_frontmatter). When no
    frontmatter is present returns ({}, rendered) unchanged.
    """
    if not rendered.startswith("---\n"):
        return {}, rendered
    end = rendered.find("\n---\n", 4)
    if end == -1:
        return {}, rendered
    try:
        parsed = yaml.safe_load(rendered[4:end])
    except yaml.YAMLError:
        return {}, rendered
    if not isinstance(parsed, dict):
        return {}, rendered
    return parsed, rendered[end + 5 :]


def _render_text_file(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,
    merge_reports: dict[Path, MergeReport] | None = None,
) -> Path:
    template = env.get_template(fe.template)
    # Pre-render: inject communication_variant from source frontmatter so body
    # templates can resolve the variant-aware {% include %} (ADR-002).
    variant = _extract_source_communication_variant(fe.template, env)
    render_context = (
        {**fe.context, "communication_variant": variant} if variant is not None else fe.context
    )
    rendered = template.render(**render_context)
    # If template authored its own frontmatter (e.g. SubAgent name/description/tools/model),
    # merge it into the single provenance frontmatter so Claude Code's loaders see one block.
    template_fm, body_text = _split_template_frontmatter(rendered)
    # REVIEW P2 #1 (ADR-004): communication_variant is template-side-only;
    # do not propagate to rendered output frontmatter. Variant identity
    # rides on the body's HTML comment marker instead.
    template_fm.pop("communication_variant", None)
    out = resolve_output_path(target_dir, fe.path)
    # Block-merge: caller signals "this file is mergeable" by passing a
    # non-None merge_reports dict. We splice OLD user blocks into NEW before
    # hashing. Parse failures fall through to plain REPLACE.
    if merge_reports is not None and out.exists():
        body_text = _try_block_merge(out, body_text, fe.path, merge_reports)
    # harness.yaml: preserve top-level keys the user added that the template
    # doesn't emit (e.g. `memory:`). Without this, free-form user blocks get
    # wiped on every re-render. Hash is computed on the post-preservation body.
    if fe.path.name == "harness.yaml":
        body_text = _preserve_yaml_user_keys(out, body_text)
    body_bytes = _normalize_body(body_text)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    fm = _build_provenance(fe, freeze_time)
    # Template-supplied keys take precedence for display fields (name/description/tools/model);
    # provenance fields stay authoritative.
    for k, v in template_fm.items():
        fm.setdefault(k, v)
    # Memory files are user-append targets (wrapup writes to them freely).
    # Injecting content_hash would cause verify to fail after any wrapup write.
    if not str(fe.path).startswith("memory/"):
        fm["content_hash"] = body_hash
    final_bytes = _format_frontmatter(fm).encode("utf-8") + body_bytes
    if not dry_run:
        atomic_write(out, final_bytes)
    return out


# Retired top-level harness.yaml keys. The list itself lives in `io_utils` (single source
# of truth — see the comment there); this alias keeps the render-side reference readable.
#
# `_preserve_yaml_user_keys` below reads through `load_harness_yaml`, which now strips these
# keys, so its own filter is **currently unreachable** — verified by deleting the clause and
# watching the behaviour test still pass. It is kept as a second layer because that function
# classifies "in the existing file but not in the new render" as a user addition, and it is
# the layer that must refuse to re-append a retired key under an "@hm:user:extensions"
# banner telling the user it is theirs; a future refactor that stops routing through the
# loader would otherwise regrow the key with no gate. Because the clause is unreachable on
# the live path, `test_retired_key_migration.py` reaches it by stubbing the loader — do not
# delete either the clause or that test without deleting both.
# (An earlier version of this comment claimed a regrown key would fail
# `HarnessConfig`'s `extra="forbid"` on the next load. It would not — nothing validates a
# user's harness.yaml into that model; `answers_from_harness_yaml` reads selected keys.)
_RETIRED_TOP_LEVEL_KEYS = RETIRED_TOP_LEVEL_KEYS


def _preserve_yaml_user_keys(out: Path, new_body: str) -> str:
    """Append top-level YAML keys from the existing file that the new render omits.

    harness.yaml is the project's primary config. The template only emits
    schema-known keys (preset, locale, reviewers, ...). Users may add
    free-form top-level blocks (e.g. ``memory:`` for cross-session memory
    paths, ``custom:`` for project-specific config) that the template
    doesn't know about. A naive REPLACE wipes those blocks on every
    re-render.

    Strategy:
    - Parse existing file via the canonical multi-doc loader (skips the
      provenance frontmatter; returns the body data only).
    - Parse the rendered new_body.
    - Diff top-level keys: anything in existing but not in new_body is
      user-only — append it as a YAML block after a marker comment.
    - On any parse failure (truncated file, mid-write race, malformed
      user YAML), silently fall back to new_body unchanged. Re-render
      then behaves as before this patch.

    Template-emitted keys always win on overlap — if a future template
    natively adds ``memory:``, the template's value replaces the user's
    on the next re-render. Users can re-customize via /hm:configure if
    that happens.
    """
    if not out.exists():
        return new_body
    # Avoid an import cycle at module top: io_utils transitively imports yaml.
    from harness_maker.io_utils import load_harness_yaml

    try:
        existing_data = load_harness_yaml(out)
    except (OSError, yaml.YAMLError):
        return new_body
    if not isinstance(existing_data, dict) or not existing_data:
        return new_body
    try:
        new_data = yaml.safe_load(new_body)
    except yaml.YAMLError:
        return new_body
    if not isinstance(new_data, dict):
        return new_body
    user_only = [k for k in existing_data if k not in new_data and k not in _RETIRED_TOP_LEVEL_KEYS]
    if not user_only:
        return new_body
    blocks: list[str] = [
        "",
        "# @hm:user:extensions — top-level keys preserved across re-renders.",
        "# Add free-form blocks here (memory:, custom:, etc.); the renderer",
        "# leaves them alone unless a future template natively emits the key.",
    ]
    for key in user_only:
        block = yaml.safe_dump(
            {key: existing_data[key]},
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )
        blocks.append(block.rstrip("\n"))
    appendix = "\n".join(blocks) + "\n"
    if not new_body.endswith("\n"):
        new_body += "\n"
    return new_body + appendix


def _try_block_merge(
    out: Path,
    new_body: str,
    rel_path: Path,
    merge_reports: dict[Path, MergeReport],
) -> str:
    """Read OLD body (sans frontmatter) at ``out`` and merge with ``new_body``.

    On any parse failure, log nothing and return ``new_body`` unchanged — the
    caller already vetted mergeability via reconcile, so a parse failure here
    is a rare race (file edited mid-make). Falling through to plain REPLACE
    is the safe behaviour.
    """
    try:
        existing = out.read_text(encoding="utf-8")
    except OSError:
        return new_body
    _, old_body = _split_existing_frontmatter(existing)
    try:
        merged, report = block_merge(old_body, new_body)
    except Exception:  # noqa: BLE001 — fall back to REPLACE on any merge failure
        return new_body
    merge_reports[rel_path] = report
    return merged


def _split_existing_frontmatter(text: str) -> tuple[str, str]:
    """Strip a leading ``---\\n…\\n---\\n`` block; return (frontmatter, body)."""
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 4)
    if end == -1:
        return "", text
    return text[: end + 5], text[end + 5 :]


def _strip_agents_md_metadata(text: str) -> str:
    """Strip the leading ``<!-- harness-maker: ... -->\\n`` line from AGENTS.md.

    AGENTS.md uses an HTML-comment first line instead of YAML frontmatter so
    Codex doesn't display provenance fields as literal text. This function
    removes that line so block_merge receives only the template body.
    """
    if text.startswith("<!-- harness-maker:"):
        newline = text.find("\n")
        if newline != -1:
            return text[newline + 1 :]
    return text


_SIBLING_TREE_PREFIXES = (".cursor/", ".codex/", ".agents/")


def _manifest_key_for(fe_path: Path) -> str:
    """Project-root-relative key for the manifest, derived from ``fe.path``.

    Matches the orphan-sweep's disk walk (``_iter_disk_files`` returns keys
    like ``.claude/commands/hm/x.md`` or ``.cursor/rules/x.mdc``). The
    ``synthesize.py`` convention is to store sibling-tree files (``.cursor/
    ``, ``.codex/``, ``.agents/``) and ``AGENTS.md`` WITH their prefix and
    ``.claude/``-bound files WITHOUT it; this helper restores the missing
    ``.claude/`` so writer and reader agree on a single key shape.

    Deriving from ``fe.path`` (not the resolved ``out_path``) keeps the
    manifest deterministic across runs even when callers pass a transient
    ``target_dir`` (e.g. ``tmp_path`` in unit tests) — the manifest key
    must never leak parent-dir basenames.
    """
    p = str(fe_path).replace("\\", "/")
    if p == "AGENTS.md" or p.startswith(_SIBLING_TREE_PREFIXES):
        return p
    return ".claude/" + p


def _append_render_manifest(
    target_dir: Path,
    fe_path: Path,
    content_hash: str,
    *,
    freeze_time: datetime | None,
) -> None:
    """Append one JSON line to ``<target_dir>/.hm-render-manifest.jsonl``.

    The recorded ``path`` is **project-root-relative** (derived from
    ``fe.path`` via ``_manifest_key_for``). That convention matches the
    orphan-sweep's disk walk so a key written here is queryable as-is on
    the next reconcile — covers both ``.claude/``-bound files
    (``commands/hm/x.md`` → ``.claude/commands/hm/x.md``) and sibling
    locations (``.cursor/``, ``.codex/``, ``.agents/``, ``AGENTS.md``).

    POSIX guarantees that a single ``write()`` <= PIPE_BUF (4096 bytes) is
    atomic. Each record we emit is well below that limit (path + 64-char
    hex hash + iso8601 timestamp), so a plain append is safe. Re-renders of
    the same file produce additional lines — the orphan-sweep does an
    any-match against the historical set, so duplicates are wanted, not
    a bug.

    The manifest file is created on first append. Errors are propagated:
    a render that cannot record its manifest entry would silently break
    ADR-005's orphan detection, so failure should surface.

    ``.hm-render-manifest.jsonl`` is part of the harness-churn gitignore set
    (PLAN-worktree-base-artifact-pollution ADR-002). It is added to the user's
    ``.gitignore`` by ``_ensure_harness_gitignore`` — invoked at make time
    (``cli.py``) and on every ``worktree create`` — so it no longer surfaces
    in ``git status``. The render pass itself stays gitignore-agnostic.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / RENDER_MANIFEST_NAME
    ts = (freeze_time or datetime.now(UTC)).isoformat()
    record = {
        "path": _manifest_key_for(fe_path),
        "content_hash": content_hash,
        "timestamp": ts,
    }
    line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
    # Single os.write() on O_APPEND fd — concurrent renderers cannot interleave.
    # The buffered ``open("a")`` could split across syscalls. See atomic_append docstring.
    atomic_append(manifest_path, line)


def compact_render_manifest(
    target_dir: Path,
    *,
    line_threshold: int = RENDER_MANIFEST_COMPACT_LINE_THRESHOLD,
) -> bool:
    """Dedupe compact the render manifest while preserving reconcile semantics.

    Keeps one latest-timestamp record for every unique ``(path, content_hash)``
    pair. Returns True when the file was rewritten.
    """
    manifest_path = target_dir / RENDER_MANIFEST_NAME
    if not manifest_path.is_file():
        return False
    try:
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    if len(lines) <= line_threshold:
        return False

    latest: dict[tuple[str, str], dict[str, object]] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            rec = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        path = rec.get("path")
        content_hash = rec.get("content_hash")
        timestamp = rec.get("timestamp")
        if not isinstance(path, str) or not isinstance(content_hash, str):
            continue
        key = (path, content_hash)
        prior = latest.get(key)
        if prior is None or str(timestamp) >= str(prior.get("timestamp", "")):
            latest[key] = rec

    compacted = sorted(
        latest.values(),
        key=lambda r: (str(r.get("path", "")), str(r.get("content_hash", ""))),
    )
    body = "".join(json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n" for rec in compacted)
    atomic_write(manifest_path, body)
    return True


def render(
    blueprint: Blueprint,
    target_dir: Path,
    *,
    dry_run: bool = False,
    freeze_time: datetime | None = None,
    merge_paths: set[Path] | None = None,
    merge_json_paths: set[Path] | None = None,
    merge_reports: dict[Path, MergeReport] | None = None,
) -> list[Path]:
    """Render blueprint to target_dir.

    ``merge_paths`` — when non-empty, files at those (relative) paths receive
    block-marker-aware merge: NEW template structure with OLD ``user:<id>``
    block contents preserved. Spec: docs/reference/block-merge-spec.md.

    ``merge_json_paths`` — when non-empty, hooks.json files at those (relative)
    paths receive schema-aware in-place 3-way merge per ADR-003/006: shipped
    entries from the freshly rendered template + user entries from disk whose
    identity tuple is not in the template set. ``.cursor/mcp.json`` is NOT a
    hook file and is excluded from this dispatch (retains pure-render path).

    ``merge_reports`` — optional out-dict. When provided, each successfully
    merged path is recorded with its ``MergeReport`` so the CLI can display
    what was preserved/seeded/orphaned.

    Side-effect: every rendered FileEntry appends one JSON line to
    ``<target_dir>/.hm-render-manifest.jsonl`` (ADR-005). Skipped when
    ``dry_run`` is True so the audit log only reflects on-disk state.

    Returns list of paths written (or would-write paths if dry_run).
    """
    env = _make_env()
    written: list[Path] = []
    paths_to_merge = merge_paths or set()
    json_merge_paths = merge_json_paths or set()
    if not dry_run:
        compact_render_manifest(target_dir)
    for fe in blueprint.files:
        if _is_hooks_json(fe) or _is_codex_hooks_json(fe):
            # Hook files (Claude/Cursor/Codex): in-place merge when existing
            # file is on disk (reconcile decided MERGE_JSON); template-render
            # otherwise. .cursor/mcp.json is NOT a hook file (Phase 1+3 W2 fix).
            if fe.path in json_merge_paths:
                out = _render_hooks_json_merged(
                    fe,
                    env,
                    target_dir,
                    dry_run=dry_run,
                    freeze_time=freeze_time,
                )
            else:
                out = _render_pure_json(
                    fe,
                    env,
                    target_dir,
                    dry_run=dry_run,
                    freeze_time=freeze_time,
                )
        elif _is_cursor_mcp_json(fe):
            # .cursor/mcp.json is MCP server config, NOT a hook file. Retains
            # the existing pure-render path unchanged by Phase 1+3. Out of scope
            # for PLAN-onboarding-backup-friction.
            out = _render_pure_json(
                fe,
                env,
                target_dir,
                dry_run=dry_run,
                freeze_time=freeze_time,
            )
        elif _is_schemas_json(fe):
            # .claude/schemas/*.json — pure JSON Schema for external consumers
            # (codex exec --output-schema, jsonschema-aware tooling). No YAML
            # provenance prefix, no content_hash. PLAN-codex-second-llm-integration
            # ADR-008 P-W3: reuses the existing _render_pure_json renderer.
            out = _render_pure_json(
                fe,
                env,
                target_dir,
                dry_run=dry_run,
                freeze_time=freeze_time,
            )
        elif _is_codex_config_toml(fe) or _is_codex_agent_toml(fe):
            # Phase 2 v0.23.1 (ADR-004/007): when reconcile flagged this TOML
            # path as MERGE_BLOCK (both shipped + existing carry HASH_COMMENT
            # `# @hm:user:*` markers), invoke block_merge to preserve user-block
            # content. Otherwise plain template overwrite.
            toml_merge_reports = (
                merge_reports if merge_reports is not None and fe.path in paths_to_merge else None
            )
            out = _render_pure_toml(
                fe,
                env,
                target_dir,
                dry_run=dry_run,
                freeze_time=freeze_time,
                merge_with_existing=fe.path in paths_to_merge,
                merge_reports=toml_merge_reports,
            )
        elif _is_agents_md(fe):
            agents_merge = (
                merge_reports if merge_reports is not None and fe.path in paths_to_merge else None
            )
            out = _render_agents_md(
                fe,
                env,
                target_dir,
                dry_run=dry_run,
                freeze_time=freeze_time,
                merge_reports=agents_merge,
            )
        elif _is_settings_json(fe):
            out = _render_json_file(
                fe,
                env,
                target_dir,
                dry_run=dry_run,
                freeze_time=freeze_time,
            )
        elif _is_pure_text(fe) or _is_cursor_mdc(fe) or _is_cursor_command(fe):
            out = _render_pure_text(
                fe,
                env,
                target_dir,
                dry_run=dry_run,
                freeze_time=freeze_time,
            )
        else:
            # Only mergeable text files plumb the merge_reports map; JSON
            # files don't support markers in v1.
            file_merge_reports = (
                merge_reports if merge_reports is not None and fe.path in paths_to_merge else None
            )
            out = _render_text_file(
                fe,
                env,
                target_dir,
                dry_run=dry_run,
                freeze_time=freeze_time,
                merge_reports=file_merge_reports,
            )
        written.append(out)
        # ADR-005: record the on-disk render. Skip during dry_run so the
        # audit log only reflects files that actually exist.
        if not dry_run and fe.body_sha256 is not None:
            _append_render_manifest(
                target_dir,
                fe.path,
                fe.body_sha256,
                freeze_time=freeze_time,
            )
    return written
