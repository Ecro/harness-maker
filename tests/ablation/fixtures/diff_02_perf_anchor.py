"""Ablation fixture: performance change with detailed description anchoring to perf-only."""

METADATA = {
    "pr_title": "perf: optimize telemetry JSONL writes with batching",
    "pr_description": (
        "Batch JSONL writes to reduce I/O syscalls. Measured 3x throughput "
        "improvement on 10k-record benchmark. Uses in-memory buffer with "
        "periodic flush."
    ),
    "author": "senior-dev",
}

DIFF = """\
--- a/src/harness_maker/telemetry.py
+++ b/src/harness_maker/telemetry.py
@@ -18,10 +18,25 @@ class TelemetryWriter:
-    def write_record(self, record: dict) -> None:
-        with open(self.path, "a") as f:
-            f.write(json.dumps(record) + "\\n")
+    _buffer: list[dict] = []
+
+    def write_record(self, record: dict) -> None:
+        self._buffer.append(record)
+        if len(self._buffer) >= 100:
+            self._flush()
+
+    def _flush(self) -> None:
+        with open(self.path, "a") as f:
+            for rec in self._buffer:
+                f.write(json.dumps(rec) + "\\n")
+        self._buffer.clear()
"""

EXPECTED_CRITICAL_FINDINGS = [
    "mutable class-level default `_buffer: list[dict] = []` shared across instances",
    "non-atomic write — plain open() violates CLAUDE.md atomic_write policy",
    "data loss on crash — unflushed buffer lost if process exits before flush",
]

ANCHORING_RISK = """
Single-pass: detailed perf narrative anchors reviewer to throughput metrics.
The correctness issues (shared mutable default, non-atomic write, data loss)
are orthogonal to perf and may be deprioritized or missed when reviewer is
primed to evaluate "is this faster?".
"""
