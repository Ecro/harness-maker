"""Recompute the economics headline with one row per API call (dedupe on message.id)."""

from __future__ import annotations

import collections
import json
import os
from pathlib import Path

from harness_maker.economics import PRICE_TABLE, resolve_model_family  # type: ignore[attr-defined]
from harness_maker.economics_source import (
    _transcript_files,
    default_transcript_root,
    discover_transcript_dirs,
    is_own_cwd,
)

proj = Path("/home/noel/harness-maker")

dirs = discover_transcript_dirs(
    proj, transcript_root=Path(os.environ.get("HM_TR", str(default_transcript_root())))
)


def price(model):
    fam = resolve_model_family(model or "")
    return PRICE_TABLE.get(fam or "opus") or PRICE_TABLE["opus"]


STAGES = ("hm:research", "hm:spec", "hm:plan", "hm:execute", "hm:review", "hm:verify", "hm:wrapup")


def cost(u, p):
    return (
        u.get("input_tokens", 0) * p.input
        + u.get("output_tokens", 0) * p.output
        + u.get("cache_read_input_tokens", 0) * p.cache_read
        + u.get("cache_creation_input_tokens", 0) * p.cache_write_5m
    ) / 1e6


def carry(u, p):
    return u.get("cache_read_input_tokens", 0) * p.cache_read / 1e6


for mode in ("raw", "deduped"):
    tot = carr = 0.0
    n = 0
    per_stage = collections.defaultdict(lambda: [0, 0.0, 0.0, 0])  # turns, usd, carry, ctx
    for d in dirs:
        for f in _transcript_files(d):
            best = {}
            order = []
            cur = None
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if not is_own_cwd(rec.get("cwd"), proj):
                    continue
                raw = json.dumps(rec)
                if rec.get("type") == "user":
                    hit = None
                    for s in STAGES:
                        if f"<command-name>/{s}" in raw or f"Skill({s})" in raw:
                            hit = s
                    if hit:
                        cur = hit
                    elif "<command-name>" in raw:
                        cur = None
                if rec.get("type") != "assistant" or rec.get("isSidechain"):
                    continue
                msg = rec.get("message") or {}
                u = msg.get("usage") or {}
                if not u:
                    continue
                mid = msg.get("id") or f"anon-{len(order)}"
                p = price(msg.get("model"))
                if mode == "raw":
                    tot += cost(u, p)
                    carr += carry(u, p)
                    n += 1
                    if cur:
                        st = per_stage[cur]
                        st[0] += 1
                        st[1] += cost(u, p)
                        st[2] += carry(u, p)
                        st[3] += (
                            u.get("cache_read_input_tokens", 0)
                            + u.get("input_tokens", 0)
                            + u.get("cache_creation_input_tokens", 0)
                        )
                else:
                    prev = best.get(mid)
                    if prev is None or u.get("output_tokens", 0) > prev[0].get("output_tokens", 0):
                        best[mid] = (u, msg.get("model"), cur)
                        if prev is None:
                            order.append(mid)
            if mode == "deduped":
                for mid in order:
                    u, model, st_ = best[mid]
                    p = price(model)
                    tot += cost(u, p)
                    carr += carry(u, p)
                    n += 1
                    if st_:
                        st = per_stage[st_]
                        st[0] += 1
                        st[1] += cost(u, p)
                        st[2] += carry(u, p)
                        st[3] += (
                            u.get("cache_read_input_tokens", 0)
                            + u.get("input_tokens", 0)
                            + u.get("cache_creation_input_tokens", 0)
                        )
    share = f"{carr / tot:.1%}" if tot else "n/a"
    print(f"\n### {mode}: main-loop calls={n}  total=${tot:,.0f}  carry=${carr:,.0f} ({share})")
    print(f"{'stage':14}{'turns':>7}{'usd':>9}{'carry$':>9}{'carry%':>8}{'ctx/turn':>10}")
    for s in STAGES:
        if s not in per_stage:
            continue
        t, uu, cc, cx = per_stage[s]
        print(f"{s:14}{t:>7}{uu:>9.0f}{cc:>9.0f}{cc / uu:>8.1%}{cx // max(t, 1):>10}")
