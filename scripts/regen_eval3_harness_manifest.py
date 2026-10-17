"""Recompute the eval-3 replay manifest and its provenance from the original run trees.

SPEC-retired-text AC-006. The replay test pins its regenerated harness commit to the 36 original
eval-3 hm runs' "harness" commits. This reads those commits from `--runs` (the eval-3 output's
`runs/` dir, default `/var/tmp/hm-eval-3/runs`), digests each with the replay test's own
normalisation, refuses unless all 36 agree, and writes `harness_manifest.json` plus
`harness_manifest_provenance.json` under `tests/fixtures/hm_check_eval3/`.

Usage:
    uv run python scripts/regen_eval3_harness_manifest.py [--runs DIR]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness_maker.io_utils import atomic_write  # noqa: E402
from tests.integration.test_overhaul_p1_eval3_replay import (  # noqa: E402
    FIXTURES,
    manifest_sha256,
    original_harness_digest,
)


def _harness_commit(work: Path) -> str:
    log = subprocess.run(
        ["git", "log", "--format=%H %s"],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout
    found = [line.split(" ", 1)[0] for line in log.splitlines() if line.endswith(" harness")]
    if len(found) != 1:
        raise SystemExit(f"{work}: expected one 'harness' commit, found {len(found)}")
    return found[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=Path, default=Path("/var/tmp/hm-eval-3/runs"))
    args = parser.parse_args()
    originals = []
    digests = []
    for run in sorted(args.runs.glob("t*-hm-*")):
        work = run / "work"
        commit = _harness_commit(work)
        digest = original_harness_digest(work, commit)
        digests.append(digest)
        originals.append(
            {"run": run.name, "harness_commit": commit, "digest_sha256": manifest_sha256(digest)}
        )
    if len(originals) != 36:
        raise SystemExit(f"expected 36 hm runs under {args.runs}, found {len(originals)}")
    if len({o["digest_sha256"] for o in originals}) != 1:
        raise SystemExit("the original harness commits disagree")
    manifest = digests[0]
    atomic_write(
        FIXTURES / "harness_manifest.json", json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    )
    provenance = {
        "source": str(args.runs),
        "normalisation": "digest_text: provenance masked, install ref -> <REF>, "
        "newline+indent runs collapsed inside .md YAML frontmatter; "
        "digest_sha256 = manifest_sha256(per-run digest)",
        "originals": originals,
    }
    atomic_write(
        FIXTURES / "harness_manifest_provenance.json",
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
    )
    print(f"wrote manifest ({len(manifest)} files) from {len(originals)} original runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
