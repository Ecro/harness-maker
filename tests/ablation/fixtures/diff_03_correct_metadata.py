"""Ablation fixture: bug fix with accurate metadata — baseline control."""

METADATA = {
    "pr_title": "fix: prevent duplicate wiki entries on concurrent wrapup",
    "pr_description": (
        "When two wrapup stages run near-simultaneously, both read wiki.md, "
        "find no existing entry, and both append — creating duplicates. "
        "Fix: use file locking via fcntl.flock() before read-modify-write."
    ),
    "author": "maintainer",
}

DIFF = """\
--- a/src/harness_maker/io_utils.py
+++ b/src/harness_maker/io_utils.py
@@ -1,5 +1,6 @@
 import os
 import tempfile
+import fcntl
 from pathlib import Path

@@ -20,6 +21,18 @@ def atomic_write(path: Path, content: str) -> None:
+def locked_append(path: Path, content: str) -> None:
+    path.parent.mkdir(parents=True, exist_ok=True)
+    with open(path, "a") as f:
+        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
+        try:
+            existing = path.read_text(encoding="utf-8")
+            if content.strip() not in existing:
+                f.write(content)
+        finally:
+            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
"""

EXPECTED_CRITICAL_FINDINGS = [
    (
        "TOCTOU: read_text() outside the lock fd — another process "
        "can modify between flock and read_text"
    ),
    (
        "fcntl not available on Windows — platform portability issue "
        "(WSL2 OK but native Windows breaks)"
    ),
]

ANCHORING_RISK = """
Single-pass: accurate metadata correctly frames the problem and solution.
This is the baseline where metadata HELPS — reviewer understands the race
condition context and can focus on implementation correctness.
2-pass should produce similar findings since the code itself is clear.
"""
