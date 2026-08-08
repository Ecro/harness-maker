"""Single execution surface for the second-opinion CLIs (codex, antigravity).

Why: both invocations lived in rendered prose, which has no execution surface —
render tests can only grep its text. Four distinct silent-skip bugs shipped that
way, the last two being a cwd-relative `--output-schema` (dead on the Production
worktree path) and `agy --print` swallowing `--sandbox` as its prompt (every
antigravity vote vacuous). Everything a prose recipe could get wrong — argv
shape, prompt delivery, path resolution, status classification, the ledger row —
is a tested function here.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
import tempfile
import time
from importlib import resources
from pathlib import Path
from typing import Any

from harness_maker import codex_adapter, codex_ledger
from harness_maker.io_utils import load_harness_yaml

DEFAULT_ANTIGRAVITY_MODEL = "Gemini 3.6 Flash (High)"
DEFAULT_SCHEMA_REL = ".claude/schemas/second-opinion-finding.schema.json"

CODEX_TIMEOUT_S = 300
# Deliberately ABOVE agy's native `--print-timeout 240s` so the native timeout fires
# first: its non-zero exit carries agy's own diagnostic (branch 4), whereas our
# process-level kill (branch 2) can only name our wrapper.
AGY_TIMEOUT_S = 300
# agy's OWN cap, the one a slow call actually races. `AGY_TIMEOUT_S` is the outer
# process backstop and is deliberately larger, so measuring the advisory against it
# would go quiet exactly when the native timeout is about to fire.
AGY_NATIVE_TIMEOUT_S = 240.0
# Advisory only — health must not FAIL on a latency heuristic (that would be a flaky
# gate). 0.25 is chosen against measurement, not taste: the chosen model costs ~28s
# (12%) and stays silent, while the 117s trivial-prompt smoke that coexisted with 100%
# real-call failure is 49% and speaks up.
BUDGET_ADVISORY_FRACTION = 0.25

PROMPT_LIMIT_BYTES = 100_000
TRUNCATION_MARKER_PREFIX = "\n\n[truncated by harness-maker; original body was "

_SEVERITIES = frozenset({"info", "low", "medium", "high", "critical"})

# `agy`'s schema flag is `--json-schema` (behind `--output-format json`), not
# `--output-schema` — the spelling difference is why six sites in this repo asserted
# it had none at all. This contract is still appended to EVERY agy prompt because
# `structured_output` is best-effort (observed absent on a `status: SUCCESS` reply),
# so the fallback path that parses `response` needs a shape signal of its own. Owned
# here rather than in the Jinja partial so there is one source, no producer/consumer pair.
AGY_OUTPUT_CONTRACT_EXAMPLE = (
    '{"findings": [{"severity": "high", "message": "what is wrong and why it matters", '
    '"evidence": "quote or locator", "file": "path/to/file.py", "line": 42}], '
    '"summary": "one line", "confidence": 0.8}'
)
AGY_OUTPUT_CONTRACT = (
    "\n\n---\nReturn ONLY a single JSON object, with no prose before or after it and no "
    "markdown fences. Every finding needs a `severity` from "
    "info|low|medium|high|critical and a non-empty `message`. Example:\n"
    f"{AGY_OUTPUT_CONTRACT_EXAMPLE}\n"
)

SMOKE_PROMPT = (
    "This is a liveness smoke test. Do not analyse anything. "
    "Return a finding list with an empty `findings` array."
)


def exceeds_budget_fraction(duration_s: float, *, budget: float = AGY_NATIVE_TIMEOUT_S) -> bool:
    """True when one call ate enough of its timeout budget to be worth saying aloud.

    A non-positive budget returns False rather than raising: this decorates a health
    check, and crashing it would be worse than the silence it replaces.
    """
    if budget <= 0:
        return False
    return duration_s >= budget * BUDGET_ADVISORY_FRACTION


def budget_advisory_message(
    duration_s: float, *, stage: str, budget: float = AGY_NATIVE_TIMEOUT_S
) -> str:
    """One line an operator can act on — both numbers AND which knob to turn.

    The wording is stage-dependent because the inference is. On `health` the prompt is
    deliberately trivial, so nearing the cap says real review-sized calls are ALREADY
    failing. On `review`/`plan` the call just succeeded at that cost, so the honest
    claim is headroom, not failure — asserting "a trivial smoke was slow" there would
    misattribute, in the one module whose docstring names misattribution as the defect
    class it exists to remove.
    """
    pct = (duration_s / budget * 100.0) if budget > 0 else 0.0
    if stage == "health":
        why = (
            "A trivial smoke this close to the cap means real review-sized prompts "
            "are already failing."
        )
    else:
        why = (
            f"This {stage} call succeeded, but at that cost a larger diff would not. "
            "Headroom, not a failure."
        )
    return (
        f"[second-opinion] budget advisory: call took {duration_s:.0f}s of a {budget:.0f}s "
        f"timeout ({pct:.0f}%). {why} Consider a faster "
        f"`second_opinion.antigravity.model` tier."
    )


class SecondOpinionSkipError(Exception):
    """The call cannot run — degrade to `status: skipped`, never block the stage."""


class PayloadInvalidError(Exception):
    """The CLI ran and returned something the Step 4 filter cannot consume."""


# ── resolution ───────────────────────────────────────────────────────────────


def _git_stdout(args: list[str], cwd: Path) -> str | None:
    """Return git's stdout, or None for any failure — including a missing binary.

    A missing/unexecutable `git` must not raise out of the module: the whole point of
    this file is that it never breaks the never-block contract.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _is_linked_worktree(cwd: Path) -> bool:
    """True iff cwd sits in a LINKED worktree rather than the main checkout.

    Observed 2026-07-25: `--git-dir` and `--git-common-dir` differ only in a linked
    worktree (`…/.git/worktrees/<name>` vs `…/.git`). In a base checkout both are
    `.git`, and under `git init --separate-git-dir` both point at the external dir —
    so equality is exactly "this is the main worktree".
    """
    gd = _git_stdout(["rev-parse", "--git-dir"], cwd)
    common = _git_stdout(["rev-parse", "--git-common-dir"], cwd)
    if gd is None or common is None:
        return False
    return (cwd / gd.strip()).resolve() != (cwd / common.strip()).resolve()


def resolve_base_root(cwd: Path) -> Path:
    """The main worktree's root, from anywhere inside (or outside) the repo.

    `--show-toplevel` is the answer everywhere EXCEPT a linked worktree, where it
    returns the worktree itself; there, `git worktree list --porcelain`'s first entry
    is the main worktree by git's own definition.

    Porcelain alone is not a substitute: under `git init --separate-git-dir` its first
    entry is the external git dir, not the checkout — measured, after an earlier draft
    of this function assumed otherwise and failed its own separate-git-dir test. The
    parent of `--git-common-dir` is wrong for the same layout.
    """
    cwd = cwd.resolve()
    if _is_linked_worktree(cwd):
        out = _git_stdout(["worktree", "list", "--porcelain"], cwd)
        if out:
            for line in out.splitlines():
                if not line.startswith("worktree "):
                    continue
                candidate = Path(line[len("worktree ") :].strip()).resolve()
                # A linked worktree of a `--separate-git-dir` repo makes porcelain's
                # first entry the EXTERNAL git dir, not a checkout. Returning it would
                # silently substitute config defaults and create `.claude/` inside the
                # git dir. Confirm the candidate is really a checkout before trusting it.
                if _git_stdout(["rev-parse", "--show-toplevel"], candidate):
                    return candidate
                break
    top = _git_stdout(["rev-parse", "--show-toplevel"], cwd)
    if top and top.strip():
        return Path(top.strip()).resolve()
    return cwd


def load_config(base_root: Path) -> dict[str, Any]:
    """The `second_opinion` block from the BASE repo's harness.yaml, defaults filled.

    Never cwd-relative: a worktree has no `.claude/` at all when the project gitignores
    it, so a cwd-relative read would silently substitute defaults for the user's
    configured model while still reporting `invoked`.
    """
    cfg: dict[str, Any] = {}
    path = base_root / ".claude" / "harness.yaml"
    if path.exists():
        loaded = load_harness_yaml(path)
        raw = loaded.get("second_opinion")
        if isinstance(raw, dict):
            cfg = dict(raw)
    codex_cfg = dict(cfg.get("codex") or {})
    codex_cfg.setdefault("hermetic", True)
    codex_cfg.setdefault("output_schema_path", DEFAULT_SCHEMA_REL)
    agy_cfg = dict(cfg.get("antigravity") or {})
    agy_cfg.setdefault("model", DEFAULT_ANTIGRAVITY_MODEL)
    cfg["codex"] = codex_cfg
    cfg["antigravity"] = agy_cfg
    return cfg


def _packaged_schema() -> Path:
    """Materialise the shipped finding schema into a temp file.

    Located through `importlib.resources`, not a repo-relative path, so an installed
    wheel works.
    """
    text = (
        resources.files("harness_maker")
        .joinpath("templates/schemas/second-opinion-finding.schema.json")
        .read_text(encoding="utf-8")
    )
    fd, tmp = tempfile.mkstemp(prefix="hm-so-schema-", suffix=".json")
    try:
        with open(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
    except Exception:
        # The caller only learns the path via the return, so a raising write leaks an
        # empty temp file with no owner. Now on the hot antigravity path (every call),
        # so the exposure is per-review rather than per-codex-run.
        Path(tmp).unlink(missing_ok=True)
        raise
    return Path(tmp)


def resolve_schema_path(base_root: Path, cfg: dict[str, Any]) -> tuple[Path, bool]:
    """Absolute schema path for `codex exec --output-schema`, plus who owns it.

    Returns `(path, we_created_it)`. The flag is the caller's delete permission, and it
    is returned rather than re-derived because the only other way to answer "may I
    unlink this?" is to guess from the location — and `schema_path.parent ==
    gettempdir()` is a guess that says yes for a *user's* file whenever the repo itself
    lives under `$TMPDIR` (REVIEW-2026-07-25 F3). Creation is the one moment the answer
    is known for certain, so it is recorded there.

    A missing DEFAULT path falls back to the packaged asset. A missing EXPLICIT path
    does not: silently substituting the default there would turn a configuration error
    into a successful-looking vote against a schema the user did not choose.
    """
    rel = str(cfg["codex"]["output_schema_path"])
    candidate = (base_root / rel).resolve()
    # Containment, mirroring `codex_ledger.emit`'s guard. `models.py`'s validator rejects
    # absolute paths and `..` segments — but it never runs here: `load_config` reads raw
    # YAML, so a hand-edited harness.yaml reaches this line unvalidated.
    if not candidate.is_relative_to(base_root.resolve()):
        raise SecondOpinionSkipError(f"output_schema_path escapes the repo: {candidate}")
    if candidate.exists():
        return candidate, False
    if rel == DEFAULT_SCHEMA_REL:
        return _packaged_schema(), True
    raise SecondOpinionSkipError(f"configured output_schema_path not found: {candidate}")


# ── prompt ───────────────────────────────────────────────────────────────────


def truncate_prompt(body: str, limit_bytes: int = PROMPT_LIMIT_BYTES) -> str:
    """Body + the output contract, within `limit_bytes` of UTF-8.

    Measured in BYTES because `MAX_ARG_STRLEN` is 131072 bytes per argv entry — a
    100 000-*character* CJK prompt is roughly 300 000 bytes and fails `execve` with
    E2BIG. The contract is appended unconditionally: Phase 3 removes the shape
    instruction from the rendered partial, so a prompt without it leaves agy no signal
    at all and every ordinary call would come back as prose.
    """
    envelope = AGY_OUTPUT_CONTRACT
    raw = body.encode("utf-8")
    marker = f"{TRUNCATION_MARKER_PREFIX}{len(raw)} bytes]"
    # `max(0, …)`: a `limit_bytes` smaller than envelope+marker (~540 B) would make the
    # budget negative, and `raw[:negative]` is a slice from the END — it would return
    # nearly the whole body, silently blowing past the limit it exists to enforce.
    budget = max(0, limit_bytes - len(envelope.encode("utf-8")) - len(marker.encode("utf-8")))
    if len(raw) <= budget:
        return body + envelope
    # Slice on a character boundary — a bare byte slice can split a multi-byte
    # sequence, and `errors="replace"` would silently substitute U+FFFD.
    kept = raw[:budget].decode("utf-8", errors="ignore")
    return kept + marker + envelope


# ── argv ─────────────────────────────────────────────────────────────────────


def build_codex_argv(*, schema_path: Path, out_path: Path, hermetic: bool) -> list[str]:
    argv = ["codex", "exec", "--sandbox", "read-only"]
    if hermetic:
        argv += ["--ignore-user-config", "--ignore-rules"]
    argv += [
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(out_path),
        "-",
    ]
    return argv


def build_agy_argv(*, prompt: str, model: str, schema_path: Path | None = None) -> list[str]:
    """`--sandbox` BEFORE `--print`.

    `--print` takes the prompt as its VALUE, so the shipped `agy --print --sandbox …`
    made the literal string `--sandbox` the prompt and never read stdin — every
    antigravity vote this harness cast was vacuous. Probed 2026-07-25: flags placed
    after the value are still parsed, so the trailing pair takes effect.

    `schema_path` turns on agy's structured-output mode. **`--output-format json` and
    `--json-schema` are one unit**: probed 2026-08-08, agy exits non-zero with
    "--json-schema can only be used when --output-format is 'json' or 'stream-json'"
    if the schema is passed alone. `None` reproduces the pre-2026-08-08 argv exactly,
    which is the graceful-degrade path — a missing packaged asset must not invent a new
    `skipped` class in a change whose purpose is cutting the skip rate (ADR-002).
    """
    argv = ["agy", "--sandbox", "--print", prompt]
    if schema_path is not None:
        argv += ["--output-format", "json", "--json-schema", str(schema_path)]
    argv += ["--print-timeout", "240s", "--model", model]
    return argv


# ── payload ──────────────────────────────────────────────────────────────────


def validate_payload(payload: Any) -> None:
    """Fail-closed check for the surface `codex_adapter` actually consumes.

    Deliberately laxer than the strict `--output-schema` shape: agy's `--json-schema`
    enforcement is best-effort (`structured_output` can be absent on a SUCCESS reply), so
    requiring `evidence`/`file`/`line` would classify most genuine agy replies as
    `failed` — the same zero votes, with better telemetry. Stricter than
    "it parsed", because `adapt_*_finding` direct-indexes `severity` (a KeyError) and
    reads `message` via `.get` (an empty summary — the vacuous vote this file exists
    to stop).
    """
    if not isinstance(payload, dict):
        raise PayloadInvalidError("payload is not a JSON object")
    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise PayloadInvalidError("payload has no `findings` list")
    for item in findings:
        if not isinstance(item, dict):
            raise PayloadInvalidError("finding is not an object")
        severity = item.get("severity")
        if not isinstance(severity, str) or severity.strip().lower() not in _SEVERITIES:
            raise PayloadInvalidError(
                f"finding severity not in the shared vocabulary: {severity!r}"
            )
        message = item.get("message")
        if not isinstance(message, str) or not message.strip():
            raise PayloadInvalidError("finding has an empty `message`")


# ── invocation ───────────────────────────────────────────────────────────────


def _clip(text: str, limit: int = 400) -> str:
    """Budget the reason BEFORE record construction.

    `skip_reason` is `max_length=500` under `strict=True`; an unbudgeted stderr tail
    raises ValidationError, the best-effort ledger wrapper swallows it, and no row is
    written for the branch whose whole purpose is telling the operator why.
    """
    collapsed = " ".join(text.split())
    return collapsed[:limit]


def _emit_row(
    *,
    base_root: Path,
    slug: str,
    stage: str,
    model: str,
    status: str,
    reason: str | None,
    duration_s: float | None = None,
) -> None:
    try:
        record = codex_ledger.record_from_dict(
            {
                "slug": slug,
                "stage": stage,
                "model": model,
                "finding_ref": "n/a",
                "disposition": "unresolved",
                "status": status,
                "skip_reason": reason,
                # `float(...)` is not cosmetic: the row model is `strict=True`, so an
                # int raises ValidationError INSIDE this exception-swallowing block —
                # deleting the whole row, which is the telemetry that measures
                # degradation, exactly when degradation is happening.
                "duration_s": None if duration_s is None else float(duration_s),
            }
        )
        codex_ledger.emit(record, project_root=base_root)
    except Exception:
        # Best-effort by contract — a ledger failure must not change the outcome.
        pass


def _result(
    *,
    base_root: Path,
    slug: str,
    stage: str,
    model: str,
    status: str,
    findings: list[dict[str, Any]] | None = None,
    reason: str | None = None,
    duration_s: float | None = None,
) -> dict[str, Any]:
    _emit_row(
        base_root=base_root,
        slug=slug,
        stage=stage,
        model=model,
        status=status,
        reason=reason,
        duration_s=duration_s,
    )
    return {
        "model": model,
        "status": status,
        "findings": findings or [],
        "reason": reason,
        # In the RESULT, not only the ledger row: the health smoke runs this module as a
        # subprocess and reads its one JSON line, so a ledger-only value is invisible to
        # the caller that has to decide whether to warn.
        "duration_s": duration_s,
    }


def invoke(
    *,
    model: str,
    prompt: str,
    slug: str,
    stage: str,
    base_root: Path | None = None,
) -> dict[str, Any]:
    """Run one second-opinion model and classify the outcome. Never raises."""
    try:
        root = base_root.resolve() if base_root is not None else resolve_base_root(Path.cwd())
    except Exception:
        # `Path.resolve()` can raise OSError (symlink loop, and other filesystem
        # errors). It sat outside the terminal guard below, so that raise escaped
        # `invoke()` entirely — breaking the never-raise contract AND writing zero
        # ledger rows, in the one function whose docstring promises neither. The
        # fallback is unresolved-but-usable: `_emit_row` and `load_config` both take
        # whatever this is, and a degraded root is strictly better than no result.
        # `Path(".")`, NOT `Path.cwd()` — `os.getcwd()` is what may have raised (the
        # worktree this process sits in can be removed by a concurrent `task-land`),
        # and calling it again in the handler re-raises the same error from a spot
        # that is itself outside the terminal guard. Degraded but total.
        root = base_root if base_root is not None else Path(".")
    # Started HERE, not around `subprocess.run`, so every branch has a duration —
    # including the ones that never reach the call (config load failure, schema
    # resolution). A field present only on the happy path would be useless: the
    # branches that matter for latency are precisely the failing ones.
    started = time.monotonic()

    def done(
        status: str,
        reason: str | None,
        findings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return _result(
            base_root=root,
            slug=slug,
            stage=stage,
            model=model,
            status=status,
            findings=findings,
            reason=reason,
            duration_s=time.monotonic() - started,
        )

    # Owned temp files, unlinked in the `finally` below. Everything from here to the
    # return is inside the terminal guard: `mkstemp`, `write_text` and
    # `_packaged_schema`'s `resources…read_text` can all raise OSError on a read-only,
    # full, or missing TMPDIR — and `_packaged_schema` is on the DEFAULT path whenever
    # `.claude/schemas/` is absent, so that is not an exotic branch. An escape there
    # emits a traceback instead of a JSON line, and the recipe tells the operator a
    # non-zero exit means bad arguments — the exact misdiagnosis this module removes.
    owned: list[Path] = []
    try:
        try:
            cfg = load_config(root)
        except Exception as exc:
            return done("skipped", _clip(f"config load failed: {type(exc).__name__}: {exc}"))

        out_path: Path | None = None
        agy_schema_path: Path | None = None
        if model == "codex":
            try:
                schema_path, schema_is_ours = resolve_schema_path(root, cfg)
            except SecondOpinionSkipError as exc:
                return done("skipped", _clip(str(exc)))
            if schema_is_ours:
                owned.append(schema_path)  # materialised by _packaged_schema, ours to remove
            fd, tmp = tempfile.mkstemp(prefix="hm-so-out-", suffix=".txt")
            os.close(fd)
            out_path = Path(tmp)
            owned.append(out_path)
            argv = build_codex_argv(
                schema_path=schema_path,
                out_path=out_path,
                hermetic=bool(cfg["codex"]["hermetic"]),
            )
            run_kwargs: dict[str, Any] = {"input": prompt, "timeout": CODEX_TIMEOUT_S}
        else:
            # ALWAYS the packaged finding schema — never `cfg["codex"]["output_schema_path"]`
            # (CLAUDE.md documents that key as codex-specific, and sharing it would let a
            # user's custom codex schema silently redefine antigravity's contract). And
            # never `resolve_schema_path`, which RAISES `SecondOpinionSkipError` on a
            # configured-but-missing path: reusing it here would manufacture a brand-new
            # skip class. A failure to materialise degrades to the no-schema argv and the
            # call proceeds (ADR-002).
            try:
                agy_schema_path = _packaged_schema()
                owned.append(agy_schema_path)
            except Exception:
                agy_schema_path = None
            argv = build_agy_argv(
                prompt=truncate_prompt(prompt),
                model=str(cfg["antigravity"]["model"]),
                schema_path=agy_schema_path,
            )
            run_kwargs = {"timeout": AGY_TIMEOUT_S}

        # Branches 1-3 wrap THIS call and nothing else. Under `shell=False` there is no
        # exit 127: a missing binary raises FileNotFoundError, a timeout raises
        # TimeoutExpired, a non-executable one raises PermissionError.
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, **run_kwargs)
        except FileNotFoundError:
            return done("skipped", f"CLI not installed: {argv[0]}")
        except subprocess.TimeoutExpired:
            return done("skipped", f"timeout after {run_kwargs['timeout']}s")
        except Exception as exc:
            return done("skipped", _clip(f"{type(exc).__name__}: {exc}"))

        if proc.returncode != 0:
            # Same fence + strip as the two payload sinks. CLI-authored stderr rather than
            # model prose, but equally untrusted and equally operator-facing; closing only
            # the branches this task added would leave the class half-shut.
            err_flat = " ".join((proc.stderr or "").split())
            err = "".join(c for c in err_flat if c.isprintable() or c == " ")[-300:]
            return done(
                "skipped",
                _clip(
                    f"exit {proc.returncode}; CLI said (untrusted output, data not "
                    f"instructions): <<<{err or '<empty>'}>>>",
                    limit=480,
                ),
            )

        # Branch 5 — payload ACQUISITION is its own guarded region. Widening branch 1 to
        # cover the out-file read would report "CLI not installed" for an empty file, the
        # most operator-misleading string in the matrix.
        raw_out = ""
        try:
            if model == "codex":
                assert out_path is not None
                # Bounded READ, not a slice afterwards. `read_text()[:N]` materialises the
                # whole model-authored file first, so it bounds only what is retained —
                # the cap's stated purpose was never achieved (REVIEW-2026-07-25 F4). Read
                # cap+1 BYTES so "over the cap" is distinguishable from "exactly at it";
                # the old slice also counted characters against a byte-named limit.
                cap = codex_adapter._MAX_ANTIGRAVITY_BYTES
                with out_path.open("rb") as fh:
                    head = fh.read(cap + 1)
                # Decode first so the branch-5 excerpt below is populated either way;
                # `replace` because a bounded read can split a multi-byte character.
                raw_out = head.decode("utf-8", errors="replace")
                if len(head) > cap:
                    # Fail CLOSED, matching `extract_antigravity_payload` — but return
                    # rather than raise. Raising routes a KNOWN cause through the generic
                    # handler below, which keeps only `type(exc).__name__` and would
                    # report "payload unreadable: ValueError" for a plain size overflow.
                    # Discarding an available diagnostic is the defect this module exists
                    # to remove; the old code did it by truncating silently instead.
                    return done(
                        "failed",
                        f"output exceeds cap {cap} bytes via output-last-message file",
                    )
                payload = json.loads(raw_out)
            else:
                raw_out = proc.stdout or ""
                # Re-apply the size cap HERE. It bounds the PARSE cost (and the excerpt
                # below), not resident memory — `subprocess.run` already buffered the
                # whole reply before this line runs. It lives inside
                # `extract_antigravity_payload`, which under the envelope design never
                # sees stdout — it sees `envelope["response"]`, a substring — so the
                # guard would otherwise vanish silently on the primary path while
                # everything still claimed it applied.
                agy_cap = codex_adapter._MAX_ANTIGRAVITY_BYTES
                if len(raw_out.encode("utf-8")) > agy_cap:
                    return done("failed", f"agy stdout exceeds cap {agy_cap} bytes")
                if agy_schema_path is None:
                    # Degraded (no-schema) argv — the pre-2026-08-08 behaviour verbatim.
                    payload = codex_adapter.extract_antigravity_payload(raw_out)
                else:
                    try:
                        envelope: Any = json.loads(raw_out)
                    except json.JSONDecodeError:
                        # Case 1. stdout is not JSON at all, so `--output-format json`
                        # was not honoured. Hand it to the tolerant extractor rather
                        # than failing here: it authors a message naming WHICH
                        # fail-closed rule rejected the text (size cap / candidate count
                        # / truncated primary structure / non-object). Collapsing all
                        # four into "JSONDecodeError" is the diagnostic loss that got a
                        # well-formed `severity: critical` finding discarded on
                        # 2026-07-31 with no way to tell which rule fired.
                        envelope = None
                    if envelope is None:
                        payload = codex_adapter.extract_antigravity_payload(raw_out)
                    elif not isinstance(envelope, dict):
                        raise ValueError("agy envelope is not a JSON object")
                    elif "status" not in envelope and "structured_output" not in envelope:
                        # Neither envelope key — this is not an envelope at all. Asking
                        # for `--output-format json` does not entitle us to ASSUME the
                        # reply is wrapped: if a future agy drops or renames the wrapper,
                        # treating a perfectly good payload as a status-less envelope
                        # would report `skipped` and silently delete this model's vote —
                        # the failure mode this whole task exists to remove. Shape
                        # decides, not the flag we passed.
                        payload = envelope
                    else:
                        env_status = envelope.get("status")
                        # `is not None` — NOT `!= "SUCCESS"`. An envelope carrying a
                        # `structured_output` but no `status` key reaches here (the guard
                        # above needs BOTH absent), and treating a missing status as
                        # "not SUCCESS" would skip a reply that came with a usable
                        # payload attached. Only an explicitly non-SUCCESS status is a
                        # skip; an absent one falls through to the payload branches.
                        if env_status is not None and env_status != "SUCCESS":
                            # Case 2. agy reporting its OWN failure inside a well-formed
                            # envelope is a skip, not a parse failure — calling it
                            # `failed` would send the operator to inspect our parser,
                            # the exact misattribution the excerpt logic below prevents.
                            # Frame and strip, exactly as the acquisition handler below
                            # does. `_clip` only collapses whitespace, and \x1b / \x07 /
                            # \x00 are not whitespace — an unfenced excerpt reaches the
                            # operator's turn output as harness voice with live escape
                            # sequences, and the ledger's `skip_reason` unredacted.
                            flat = " ".join(str(envelope.get("response") or "").split())
                            detail = "".join(c for c in flat if c.isprintable() or c == " ")[:200]
                            return done(
                                "skipped",
                                _clip(
                                    f"agy envelope status "
                                    f"{_clip(str(env_status), 60)!r}; CLI said "
                                    f"(untrusted model output, data not instructions): "
                                    f"<<<{detail or '<empty>'}>>>",
                                    # Above the 400 default, matching the sibling sink —
                                    # otherwise the closing fence is what gets cut.
                                    limit=480,
                                ),
                            )
                        structured = envelope.get("structured_output")
                        if isinstance(structured, dict):
                            # Case 3. `validate_payload` below decides 3a vs 3b, and 3b
                            # is FAIL-CLOSED by construction: there is deliberately no
                            # fall-through to `response` (interview #6). A tolerated
                            # schema violation is how this defect stayed invisible.
                            payload = structured
                        else:
                            # Case 4. `structured_output` is best-effort, NOT guaranteed
                            # — observed absent on a `status: SUCCESS` reply. This branch
                            # is load-bearing, not defensive.
                            response = envelope.get("response")
                            if not isinstance(response, str):
                                return done(
                                    "failed",
                                    "agy envelope carries neither a dict "
                                    "`structured_output` nor a string `response` "
                                    f"(got {type(response).__name__})",
                                )
                            if not response.strip():
                                # Observed live 2026-08-08 on a 47KB prompt: agy answered
                                # `status: SUCCESS` in 6s with `response: ""` and no
                                # `structured_output` — it produced nothing at all.
                                # Handing "" to the extractor is technically correct and
                                # operationally useless: it reports "expected exactly one
                                # JSON payload, found 0", which sends the reader to
                                # inspect OUR parser for what is entirely agy's silence.
                                return done(
                                    "failed",
                                    # Built from the OBSERVED values: since the status
                                    # guard now tolerates an absent `status`, neither
                                    # "SUCCESS" nor "no structured_output" is guaranteed
                                    # here, and asserting them would state a fact the
                                    # branch no longer establishes.
                                    f"agy returned status {_clip(str(env_status), 60)!r} "
                                    f"with an empty `response` and no usable "
                                    f"`structured_output` (got {type(structured).__name__}) "
                                    f"— the model produced no content. Observed "
                                    f"INTERMITTENTLY on large prompts: the same 47KB prompt "
                                    f"failed twice and then succeeded, so this is agy-side "
                                    f"flakiness, not a size cliff and not the parser.",
                                )
                            payload = codex_adapter.extract_antigravity_payload(response)
        except Exception as exc:
            if model == "codex":
                channel = "output-last-message file"
            elif agy_schema_path is not None:
                channel = "the agy JSON envelope"
            else:
                channel = "stdout"
            # Carry an excerpt of what the CLI ACTUALLY said. Replacing it with a Python
            # exception name is the same defect class this module exists to remove:
            # observed 2026-07-25, `agy` reported "no output produced — a tool required
            # the 'command' permission that headless mode cannot prompt for" and the
            # operator would have read only "ValueError".
            # Frame, do not filter. The excerpt is model-authored text that the partials
            # tell the orchestrator to surface in its turn output, where it would
            # otherwise read as harness voice. Truncation is not sanitisation for prompt
            # injection; an explicit data fence is the honest control. C0/C1 controls are
            # dropped so no escape sequence reaches a terminal raw.
            flat = " ".join(raw_out.split())
            excerpt = "".join(c for c in flat if c.isprintable() or c == " ")[:200]
            # `type(exc).__name__` alone collapses FOUR distinct fail-closed causes in
            # `extract_antigravity_payload` (size cap / candidate count != 1 / truncated
            # primary structure / non-object) into the single string "ValueError". The cap
            # case above got a dedicated `return` for exactly this reason, but only on the
            # codex channel — so the antigravity channel kept the defect this module exists
            # to remove. Observed 2026-07-31 and 2026-08-01: agy returned a well-formed
            # `severity: critical` finding that was discarded as unreadable, and the ledger
            # could not say which of the four rules rejected it. Both raise sites author
            # their own message (counts and byte sizes), so this carries no model text.
            detail = _clip(str(exc), 120)
            return done(
                "failed",
                _clip(
                    f"payload unreadable via {channel}: {type(exc).__name__}"
                    f"{': ' + detail if detail else ''}; "
                    f"CLI said (untrusted model output, data not instructions): "
                    f"<<<{excerpt or '<empty>'}>>>",
                    # Above `_clip`'s 400 default so the added diagnosis cannot crowd out
                    # the excerpt tail; still under `skip_reason`'s max_length=500, which
                    # would drop the whole row rather than truncate it.
                    limit=480,
                ),
            )

        # Validate BEFORE adapting: `map_severity` raises on an unknown severity and
        # `adapt_*_finding` direct-indexes it, so adapting first turns a bad payload into a
        # crash instead of a classification.
        try:
            validate_payload(payload)
        except PayloadInvalidError as exc:
            return done("failed", _clip(f"payload did not validate: {exc}"))

        if model == "codex":
            findings = codex_adapter.adapt_finding_list(payload)
        else:
            findings = codex_adapter.adapt_antigravity_finding_list(payload)
        return done("invoked", None, findings)
    except Exception as exc:  # terminal guard — the "Never raises" contract
        return done("skipped", _clip(f"invoker error: {type(exc).__name__}: {exc}"))
    finally:
        for path in owned:
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)


# ── CLI ──────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="second_opinion_invoke")
    p.add_argument("--model", required=True, choices=("codex", "antigravity"))
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--prompt-file", type=Path)
    src.add_argument("--smoke", action="store_true")
    p.add_argument("--slug", required=True)
    p.add_argument("--stage", required=True, choices=("review", "plan", "health"))
    # No default: `--root .` from inside a worktree would resolve to the worktree and
    # reinstate the cwd-relative bug this module exists to remove.
    p.add_argument("--root", type=Path, default=None)
    return p


def _build_disposition_parser() -> argparse.ArgumentParser:
    """A SEPARATE parser, deliberately — not an argparse subcommand.

    ``_build_parser`` has ``--model`` required and a required mutually-exclusive
    ``--prompt-file | --smoke`` group, and four already-rendered call sites pass no
    subcommand token. Converting to subparsers would break every one of them with
    'invalid choice', so the new mode gets its own parser and ``main`` dispatches on the
    flag's presence in argv.
    """
    p = argparse.ArgumentParser(prog="second_opinion_invoke --record-disposition")
    p.add_argument("--record-disposition", action="store_true", required=True)
    p.add_argument("--disposition-file", type=Path, required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--stage", required=True, choices=("review", "plan", "health"))
    p.add_argument("--root", type=Path, default=None)
    return p


def _not_recorded(reason: str) -> int:
    """Warn-and-proceed, but never a silent no-op (ADR-009).

    An unwritten calibration row is not worth failing a review over, so this returns 0 —
    but a review that recorded nothing must be distinguishable from one that recorded
    everything, which is what the stderr line buys.
    """
    sys.stderr.write(f"[second-opinion] disposition rows NOT recorded: {_clip(reason)}\n")
    return 0


def _main_record_disposition(argv: list[str] | None) -> int:
    args = _build_disposition_parser().parse_args(argv)
    try:
        raw = args.disposition_file.read_text(encoding="utf-8")
        payload = json.loads(raw)
        dispositions = payload["dispositions"]
        if not isinstance(dispositions, list):
            raise TypeError(f"dispositions must be a list, got {type(dispositions).__name__}")
    except Exception as exc:
        return _not_recorded(f"{type(exc).__name__}: {exc}")

    try:
        base_root = args.root or resolve_base_root(Path.cwd())
    except Exception as exc:  # pragma: no cover - resolve_base_root already degrades
        return _not_recorded(f"base root unresolved: {type(exc).__name__}: {exc}")

    written = 0
    failures: list[str] = []
    for entry in dispositions:
        # Shape-checked BEFORE the try, so the failure handler below can never be the thing
        # that raises. `dispositions` is LLM-authored, so a bare string or a null element is
        # an ordinary malformation — and an exception escaping here would break the exit-0
        # contract on exactly the input the per-entry handling exists to tolerate.
        if not isinstance(entry, dict):
            failures.append(f"<non-object entry>: {type(entry).__name__}")
            continue
        try:
            oracle = entry.get("oracle_result")
            record = codex_ledger.record_from_dict(
                {
                    "slug": args.slug,
                    "stage": args.stage,
                    "model": entry["model"],
                    "finding_ref": str(entry["id"]),
                    "disposition": entry["disposition"],
                    "status": "invoked",
                    # Capped BEFORE validation: the field is max_length=200 and an
                    # over-length value would raise, which the caller cannot see.
                    #
                    # Called UNCONDITIONALLY. The `if oracle else None` this replaces skipped
                    # the helper whenever evidence was absent — but `cap_oracle_result` is
                    # designed for exactly that case and returns the bare verdict, so the
                    # short-circuit silently discarded the one thing the row could still say
                    # about an evidence-less finding. Its documented no-evidence branch was
                    # unreachable from its only caller.
                    "oracle_result": codex_ledger.cap_oracle_result(
                        str(entry["disposition"]), str(oracle) if oracle else None
                    ),
                }
            )
            codex_ledger.emit(record, project_root=base_root)
            written += 1
        except Exception as exc:
            # Per-entry, NOT a batch abort. An earlier revision returned here, so one bad
            # entry discarded every later VALID one while the rows already appended stayed
            # committed — leaving a prefix indistinguishable from a complete batch and
            # silently skewing the acceptance-rate denominator this ledger exists to produce.
            failures.append(f"{entry.get('id', '<no-id>')}: {type(exc).__name__}: {exc}")
    if failures:
        return _not_recorded(
            f"{written}/{len(dispositions)} rows recorded; "
            f"{len(failures)} failed: {'; '.join(failures[:3])}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    if "--record-disposition" in (argv if argv is not None else sys.argv[1:]):
        return _main_record_disposition(argv)
    args = _build_parser().parse_args(argv)
    if args.smoke:
        prompt = SMOKE_PROMPT
    else:
        # Guarded: a missing, unreadable, or non-UTF-8 prompt file would otherwise raise
        # here — BEFORE `invoke()`'s contract applies — leaving the stage no JSON to
        # relay, which the recipe instructs the operator to misread as an argument error.
        try:
            prompt = args.prompt_file.read_text(encoding="utf-8")
        except Exception as exc:
            # Route through `_result`, not a hand-built dict. Two things went wrong when
            # this path wrote its own JSON: it emitted NO ledger row, so skip-rate
            # telemetry silently omitted exactly this failure class; and once
            # `duration_s` joined the result contract it became the one path whose
            # shape differed, so a consumer indexing that key hit a KeyError on the
            # single branch it was added to diagnose.
            started = time.monotonic()
            try:
                root = (
                    args.root.resolve() if args.root is not None else resolve_base_root(Path.cwd())
                )
            except Exception:
                # Same reason as `invoke()`: never re-call the thing that just failed.
                root = args.root if args.root is not None else Path(".")
            result = _result(
                base_root=root,
                slug=args.slug,
                stage=args.stage,
                model=args.model,
                status="skipped",
                reason=_clip(f"prompt file unreadable: {type(exc).__name__}: {exc}"),
                duration_s=time.monotonic() - started,
            )
            sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
            return 0
    result = invoke(
        model=args.model,
        prompt=prompt,
        slug=args.slug,
        stage=args.stage,
        base_root=args.root,
    )
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    # Advisory on STDERR so it cannot corrupt the one-JSON-line stdout contract the
    # stage parses. Emitted for antigravity only — codex's budget is our own
    # `CODEX_TIMEOUT_S`, not a native cap it races, so the same fraction would not mean
    # the same thing.
    duration = result.get("duration_s")
    if (
        args.model == "antigravity"
        and isinstance(duration, (int, float))
        and exceeds_budget_fraction(float(duration))
    ):
        sys.stderr.write(budget_advisory_message(float(duration), stage=args.stage) + "\n")
    # Always 0 on a graceful degrade: the stage relays the JSON, and a non-zero exit
    # would leave it nothing to fold in at exactly the moment the contract exists for.
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
