"""Decide whether a push to main is a release that needs its vX.Y.Z tag (auto-tag)."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path

from harness_maker.documentation_contract import VERSION_FILES
from harness_maker.release_identity import _source_versions

_MANIFEST = ".claude-plugin/plugin.json"
_RUNTIME = re.compile(r"^__version__\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)


def decide(versions: Mapping[str, str], *, changed_in_push: bool, tag_exists: bool) -> str:
    """`tag vX.Y.Z`, `skip` or `error`.

    Tagging only when the push itself changed the version keeps an old version number off new
    code: a release whose tag was missed must not be published later from whatever HEAD is.
    """
    if not changed_in_push:
        return "skip"
    found = set(versions.values())
    if len(found) != 1:
        return "error"
    if tag_exists:
        return "skip"
    return f"tag v{found.pop()}"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, timeout=60, check=False
    )


def _versions_at(root: Path, rev: str) -> dict[str, str] | None:
    """The four version files' values at `rev`, by the same rules as `_source_versions`.

    None when `rev` is unknown (an all-zero `before` on a new branch, or a force-push).
    """
    if _git(root, "cat-file", "-e", f"{rev}^{{commit}}").returncode:
        return None
    out: dict[str, str] = {}
    for rel in VERSION_FILES:
        shown = _git(root, "show", f"{rev}:{rel}")
        text = shown.stdout if shown.returncode == 0 else ""
        value: str | None = None
        try:
            if rel.endswith(".json"):
                value = str(json.loads(text)["version"])
            elif rel.endswith(".toml"):
                value = str(tomllib.loads(text)["project"]["version"])
            elif m := _RUNTIME.search(text):
                value = m.group(1)
        except (ValueError, KeyError, TypeError):
            value = None
        out[rel] = value or ""
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--before", required=True)
    args = parser.parse_args(argv)

    versions = _source_versions(args.root)
    current = versions[_MANIFEST]
    before = _versions_at(args.root, args.before)
    tag_exists = (
        _git(args.root, "rev-parse", "-q", "--verify", f"refs/tags/v{current}").returncode == 0
    )
    decision = decide(
        versions, changed_in_push=before is not None and before != versions, tag_exists=tag_exists
    )
    print(json.dumps({"decision": decision, "versions": versions, "before": before}))
    if decision == "error":
        return 1
    out = os.environ.get("GITHUB_OUTPUT")
    if out and decision.startswith("tag "):
        with Path(out).open("a", encoding="utf-8") as fh:
            fh.write(f"tag={decision.removeprefix('tag ')}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
