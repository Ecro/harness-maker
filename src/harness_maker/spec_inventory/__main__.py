"""CLI: ``python -m harness_maker.spec_inventory <cmd>``.

Commands:
    reverse-map [--output PATH]   walk tests/ → JSON (stdout or file via atomic write)
    verify-inventory PATH         Gate A check (count + avg_confidence)
    sample-for-review PATH [-n N] Gate B helper (random sample for user review)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from harness_maker.io_utils import atomic_write
from harness_maker.spec_inventory.batch_generator import (
    load_catalog_and_inventory,
    write_specs,
)
from harness_maker.spec_inventory.reverse_map import (
    JudgeProtocol,
    reverse_map,
    sample_for_review,
    to_json,
    verify_inventory,
)


def _resolve_judge() -> JudgeProtocol | None:
    """Return a real LLM judge when ``INTEGRATION=1`` is set, else ``None``.

    ``AnthropicJudgeClient`` already exposes ``judge(system, user, model)``
    matching ``JudgeProtocol`` — no adapter needed. The INTEGRATION env-var
    gate keeps unit tests fast + deterministic (heuristic fallback) while
    enabling real LLM-driven reverse-map on user-side INTEGRATION runs.
    """
    if not os.getenv("INTEGRATION"):
        return None
    try:
        from harness_maker.llm_judge import AnthropicJudgeClient
    except ImportError:
        return None
    try:
        return AnthropicJudgeClient()
    except Exception:  # noqa: BLE001 — missing API key or SDK issue
        return None


def _cmd_reverse_map(args: argparse.Namespace) -> int:
    repo_root = Path(args.root).resolve() if args.root else Path.cwd()
    judge = _resolve_judge()
    entries = reverse_map(repo_root, judge=judge)
    payload = to_json(entries)
    if args.output:
        atomic_write(Path(args.output), payload)
        sys.stdout.write(f"wrote {len(entries)} entries → {args.output}\n")
    else:
        sys.stdout.write(payload)
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    report = verify_inventory(Path(args.path))
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return 0 if report["passes_gate_a"] else 1


def _cmd_sample(args: argparse.Namespace) -> int:
    out = sample_for_review(Path(args.path), n=args.n, seed=args.seed)
    sys.stdout.write(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    return 0


def _cmd_generate_all(args: argparse.Namespace) -> int:
    """Generate skeleton SPECs for every catalog feature (P5 skeleton phase)."""
    catalog_path = Path(args.catalog)
    inventory_path = Path(args.inventory)
    specs_dir = Path(args.specs_dir)
    catalog, inventory = load_catalog_and_inventory(catalog_path, inventory_path)
    counts = write_specs(
        catalog,
        inventory,
        specs_dir,
        skip_existing=not args.force,
    )
    sys.stdout.write(
        f"L1 stubs written={counts['l1_written']} skipped={counts['l1_skipped']}; "
        f"L2 features written={counts['l2_written']} skipped={counts['l2_skipped']}\n"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness_maker.spec_inventory")
    sub = parser.add_subparsers(dest="cmd")

    p_rev = sub.add_parser("reverse-map", help="walk tests/ → AC catalog JSON")
    p_rev.add_argument("--output", help="write to PATH via atomic_write (else stdout)")
    p_rev.add_argument("--root", help="repo root (default cwd)")

    p_ver = sub.add_parser("verify-inventory", help="Gate A check")
    p_ver.add_argument("path", help="path to test-inventory JSON")

    p_sam = sub.add_parser("sample-for-review", help="Gate B helper")
    p_sam.add_argument("path", help="path to test-inventory JSON")
    p_sam.add_argument("-n", type=int, default=20)
    p_sam.add_argument("--seed", type=int, default=42)

    p_gen = sub.add_parser(
        "generate-all", help="P5 skeleton: generate SPECs for every catalog feature"
    )
    p_gen.add_argument("--catalog", default="work-docs/spec-catalog-2026-05.yaml")
    p_gen.add_argument("--inventory", default="work-docs/test-inventory-2026-05.json")
    p_gen.add_argument("--specs-dir", default="specs")
    p_gen.add_argument("--force", action="store_true", help="overwrite existing SPEC files")

    args = parser.parse_args(argv)
    if args.cmd == "reverse-map":
        return _cmd_reverse_map(args)
    if args.cmd == "verify-inventory":
        return _cmd_verify(args)
    if args.cmd == "sample-for-review":
        return _cmd_sample(args)
    if args.cmd == "generate-all":
        return _cmd_generate_all(args)
    parser.print_help()
    return 2


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
