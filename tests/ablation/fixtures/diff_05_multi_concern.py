"""Ablation fixture: multi-concern change with vague description."""

METADATA = {
    "pr_title": "update: various improvements to render pipeline",
    "pr_description": "Miscellaneous improvements and fixes.",
    "author": "ai-agent",
}

DIFF = """\
--- a/src/harness_maker/render.py
+++ b/src/harness_maker/render.py
@@ -30,7 +30,7 @@ class Renderer:
     def _render_template(self, template_name: str, context: dict) -> str:
         template = self.env.get_template(template_name)
-        return template.render(**context)
+        return template.render(**context, undefined=jinja2.StrictUndefined)

@@ -55,10 +55,8 @@ class Renderer:
     def _compute_hash(self, content: str) -> str:
-        import hashlib
-        return hashlib.sha256(content.encode()).hexdigest()
+        return str(hash(content))

@@ -78,6 +76,8 @@ class Renderer:
     def render_file(self, src: str, dst: Path, context: dict) -> None:
         content = self._render_template(src, context)
+        if os.getenv("DEBUG"):
+            print(f"Rendering {src} -> {dst}: {content[:200]}")
         self._write_output(dst, content)

@@ -92,8 +92,7 @@ class Renderer:
     def _write_output(self, path: Path, content: str) -> None:
-        atomic_write(path, content)
+        path.write_text(content, encoding="utf-8")
"""

EXPECTED_CRITICAL_FINDINGS = [
    "content_hash replaced sha256 with non-deterministic hash() — fingerprint system broken",
    "atomic_write replaced with plain write_text — violates CLAUDE.md atomic write policy",
    "DEBUG print leaks rendered content to stdout — potential secret exposure",
    "StrictUndefined addition is good but may break existing templates silently",
]

ANCHORING_RISK = """
Single-pass: vague "various improvements" gives no frame, causing reviewer
to either (a) skim all changes superficially or (b) anchor on the first
change (StrictUndefined — actually beneficial) and rate the PR positively.
The destructive changes (hash replacement, atomic write removal) are buried
in the middle of a multi-concern diff.
"""
