"""Do multiple assistant JSONL records share one message.id (and thus one usage)?"""

import collections
import json
import os
from pathlib import Path

from harness_maker.economics_source import (
    _transcript_files,
    default_transcript_root,
    discover_transcript_dirs,
)

proj = Path("/home/noel/harness-maker")

dirs = discover_transcript_dirs(
    proj, transcript_root=Path(os.environ.get("HM_TR", str(default_transcript_root())))
)
per_id = collections.Counter()
usage_same = collections.Counter()
sample = []
for d in dirs:
    for f in _transcript_files(d):
        seen = {}
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("type") != "assistant":
                continue
            msg = rec.get("message") or {}
            mid = msg.get("id")
            if not mid:
                continue
            u = msg.get("usage") or {}
            key = (u.get("input_tokens"), u.get("output_tokens"), u.get("cache_read_input_tokens"))
            per_id[mid] += 1
            if mid in seen:
                usage_same["identical" if seen[mid] == key else "different"] += 1
                if len(sample) < 3 and seen[mid] != key:
                    sample.append((mid, seen[mid], key))
            seen[mid] = key
hist = collections.Counter(per_id.values())
print("records-per-message.id histogram:", dict(sorted(hist.items())))
print("total distinct message.id:", len(per_id), " total assistant records:", sum(per_id.values()))
print("repeat-usage comparison:", dict(usage_same))
for s in sample:
    print("SAMPLE-DIFF", s)
