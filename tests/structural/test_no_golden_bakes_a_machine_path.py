"""No committed golden may bake a machine-specific absolute path.

`[fail:test] snapshot-regen-inside-worktree` is at **count:13** — the highest in this
repo's failure log — and its own entry names the gate it has never had across all thirteen
instances:

    "test_no_golden_bakes_a_machine_specific_absolute_path, parametrized over every golden,
     asserting no /home|/Users|/root path survives and that the portable $HOME form is
     present. It checks the PROPERTY (no machine-specific absolute path) rather than the
     SYMPTOM (no .worktrees), so a capture from any other checkout fails too."

This is that sentence, implemented.

**Why the existing pins were not enough.** `tests/snapshot/regenerate.py` and
`tests/render/conftest.py` both pin the install ref, and the ORIGINAL failure mode is closed
by them. The count kept climbing to 13 anyway, because a **new** artifact does not inherit a
pin it does not know about: instance 13 was a brand-new `tests/render/` directory whose
goldens baked the worktree path because that directory had no `conftest.py` yet. So this
guard DERIVES its population (ADR-001) instead of listing files — a golden added tomorrow is
covered the moment it exists, with no edit here.

**The property is necessary but NOT sufficient — corrected 2026-08-07.** This docstring used
to end by rejecting `.worktrees` as a mere "symptom", on the grounds that a golden captured on
another developer's machine or in CI leaks just as badly and matches no `.worktrees` rule.
That argument is still right about what the property adds; it was **wrong that the property
subsumes the symptom**, and the failure it names is the one it missed.

`synthesize._portablize_ref` rewrites the render machine's home prefix to the literal `$HOME`
*before* the golden is written. So a snapshot regenerated inside a worktree does not emit
`/home/<user>/harness-maker/.worktrees/<slug>` — it emits **`$HOME/harness-maker/.worktrees/
<slug>`**, which this guard deliberately exempts as "the portable form we WANT". Measured:

    $HOME/harness-maker/.worktrees/x/src/f.py  -> []          # invisible to the property rule
    /home/noel/harness-maker/.worktrees/x/f.py -> ['/home/noel']

Every discriminator except the `.worktrees` segment is normalised away by the very transform
that makes the path *look* portable, so the guard was largely vacuous over
`snapshot-regen-inside-worktree` (count:13) — the failure whose own entry it quotes as its
specification. Both rules ship: the machine-path rule catches the un-portablized capture, and
the `$HOME`-rooted `.worktrees` rule catches the portablized one. Neither covers the other.

The `.worktrees` rule is anchored at `$HOME` **on purpose**: a bare `.worktrees` scan is the
false-positive disaster the old paragraph feared — the rendered command bodies say
`` `.worktrees/<slug>/` ``, `.worktrees/execute-*` and "walk up out of `.worktrees/`" in
ordinary prose, ~25 times across the committed goldens. A path *rooted at a home directory*
and descending into a checkout-local worktree is not prose; it is a captured location.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Absolute-path roots that are specific to one machine or one checkout. A plain `$HOME/...`
#: IS the portable form the renderer is supposed to emit (`synthesize._portablize_ref`), so it
#: is deliberately NOT here — but `$HOME/…/.worktrees/<slug>` is portable-looking and still
#: checkout-local, which is the shape a snapshot regenerated inside a worktree actually takes
#: (see the module docstring). Anchored at `$HOME` so ordinary `.worktrees/<slug>` prose in the
#: rendered command bodies stays clean.
_MACHINE_PATH = re.compile(
    r"(?<![$\w])(?:/mnt/[a-z])?/(?:home|Users|root)/[A-Za-z0-9._-]+"  # POSIX + WSL2 /mnt/c
    r"|(?<![\w])[A-Za-z]:[\\/]{1,2}Users[\\/]{1,2}[A-Za-z0-9._-]+"  # native Windows
    r"|\$HOME[A-Za-z0-9._/-]*/\.worktrees/"  # portablized, still checkout-local
)

#: Fixture SHAPES, not filenames — the population is whatever matches, so a new golden is
#: covered without editing this file (ADR-001).
_GOLDEN_GLOBS: tuple[str, ...] = (
    ":(glob)tests/**/*.expected.yaml",
    ":(glob)tests/**/*.expected.json",
    ":(glob)tests/**/*baseline*.json",
    ":(glob)tests/**/*.golden",
    ":(glob)tests/**/*.golden.md",
    # `*_pre_change.md` is not decoration: instance 13 — the one that took this entry from
    # count:11 to 13 — was `tests/render/`'s captured goldens, which live HERE. The first
    # version of this guard omitted the very artifact class it was written for, and its
    # population test still passed because the snapshot members it names were present.
    ":(glob)tests/**/*_pre_change.md",
)


def _committed_goldens() -> list[Path]:
    """Committed files matching a golden shape. Committed only — a local scratch file is
    not a contract, and `git ls-files` is also what makes this reproducible in CI."""
    out = subprocess.run(
        ["git", "ls-files", "-z", *_GOLDEN_GLOBS],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout
    return [REPO_ROOT / p for p in out.split("\0") if p]


def _machine_paths_in(text: str) -> list[str]:
    return sorted(set(_MACHINE_PATH.findall(text)))


# --- the population itself, before anything is asserted about its contents ------------


def test_the_golden_population_is_not_empty() -> None:
    """A discovery test that discovers nothing is a green light over a blind spot.

    Named member included on purpose: a glob that silently stops matching (a rename, a
    move) would otherwise leave this file passing while guarding zero files.
    """
    found = {p.relative_to(REPO_ROOT).as_posix() for p in _committed_goldens()}
    assert found, f"no committed goldens matched {_GOLDEN_GLOBS}"
    assert "tests/snapshot/prod-firmware-spec.expected.yaml" in found
    assert "tests/structural/surface_baseline.json" in found
    # The instance-13 artifact class. Named explicitly so a glob that stops matching it
    # fails here instead of leaving the guard green over the leak it exists to stop.
    assert "tests/fixtures/review_command_pre_change.md" in found


# --- the guard --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "golden", _committed_goldens(), ids=lambda p: p.relative_to(REPO_ROOT).as_posix()
)
def test_no_golden_bakes_a_machine_specific_absolute_path(golden: Path) -> None:
    leaked = _machine_paths_in(golden.read_text(encoding="utf-8", errors="replace"))
    assert not leaked, (
        f"{golden.relative_to(REPO_ROOT)} bakes a machine-specific absolute path: {leaked}\n"
        "Goldens must carry the portable `$HOME/...` form. This is [fail:test] "
        "snapshot-regen-inside-worktree (count:13) — regenerate from a pinned context "
        "(tests/snapshot/regenerate.py, or a conftest calling pin_install_ref) and re-commit."
    )


# --- ADR-002: the guard ships only with a demonstrated failure --------------------------
#
# Every case below is ABSENT from the tree, so the matcher above is unfalsifiable by the
# repo scan alone — it would pass identically if `_MACHINE_PATH` were `re.compile("(?!)")`.


@pytest.mark.parametrize(
    "leak",
    [
        "/home/noel/harness-maker/.worktrees/x/src/f.py",
        "/Users/someone/checkout/tests/f.py",
        "/root/build/artifact.json",
        "install_ref: /home/ci-runner/harness-maker",
        # WSL2 — THIS repo's primary platform. The first lookbehind rejected it because `c`
        # precedes `/Users`, so the most likely local leak shape sailed through.
        "/mnt/c/Users/euncheol.ro/harness-maker/x.py",
        "/mnt/d/home/dev/proj",
        r"C:\\Users\\noel\\harness-maker",
        "D:/Users/noel/proj",
        # The POST-PORTABLIZE shape — the one instance 13 actually produced, and the one the
        # machine-path rule above is blind to by construction. `_portablize_ref` has already
        # replaced the home prefix, so `$HOME` here is not evidence of portability; the
        # `.worktrees/<slug>` tail is what makes it un-reproducible on any other checkout.
        'install_ref: "$HOME/harness-maker/.worktrees/mechanical-guards"',
        "uv run --with $HOME/harness-maker/.worktrees/some-task hm health",
        "$HOME/.worktrees/x/y.py",
    ],
)
def test_the_matcher_fires_on_a_real_leak(leak: str) -> None:
    assert _machine_paths_in(leak), f"a real machine path went undetected: {leak!r}"


@pytest.mark.parametrize(
    "clean",
    [
        'install_ref: "$HOME/harness-maker"',  # the portable form we WANT
        "uv run --with $HOME/harness-maker hm health",
        "/home",  # bare root, no user segment
        "prefix/home/noel/x",  # not an absolute path
        "https://example.com/home/noel",  # a URL, not a filesystem path
        # The prose forms. These occur ~25 times across the committed goldens, which is why
        # the `.worktrees` rule is anchored at `$HOME` instead of scanning for the segment —
        # an unanchored rule would fail nearly every rendered command body on day one.
        "this stage operates inside `.worktrees/<slug>/` on branch `hm/<slug>`",
        "walk up out of `.worktrees/`",
        "any `.worktrees/execute-*` directories should be cleaned up",
        "strip the `/.worktrees/<wt-name>/` suffix",
    ],
)
def test_the_matcher_does_not_fire_on_portable_or_unrelated_text(clean: str) -> None:
    """The negative control. Without it, the four cases above pass on a matcher that flags
    every string, and the guard would reject the very `$HOME` form it exists to require."""
    assert not _machine_paths_in(clean), f"false positive on {clean!r}"
