"""Ablation fixture: refactoring labeled as feature — scope mismatch."""

METADATA = {
    "pr_title": "feat: add new interview question for MCP configuration",
    "pr_description": (
        "Adds a new interview dimension for MCP server configuration. "
        "Users can now specify MCP servers during harness setup."
    ),
    "author": "contributor",
}

DIFF = """\
--- a/src/harness_maker/interview.py
+++ b/src/harness_maker/interview.py
@@ -45,18 +45,12 @@ class InterviewEngine:
     def _ask_targets(self) -> list[str]:
-        response = self.ask_user(
-            prompt="Which IDEs will this harness target?",
-            options=[
-                {"id": "claude-code", "label": "Claude Code"},
-                {"id": "cursor", "label": "Cursor"},
-            ],
-            allow_multiple=True,
-        )
-        if not response:
-            return ["claude-code"]
-        return response
+        return ["claude-code"]

@@ -80,15 +74,8 @@ class InterviewEngine:
     def _ask_dev_mode(self) -> str:
-        response = self.ask_user(
-            prompt="Development mode?",
-            options=[
-                {"id": "task-driven", "label": "Task-driven"},
-                {"id": "spec-driven", "label": "Spec-driven"},
-            ],
-        )
-        return response or "task-driven"
+        return "task-driven"
"""

EXPECTED_CRITICAL_FINDINGS = [
    "targets selection hardcoded — violates CLAUDE.md 'auto-detect 금지, 사용자 의도 확인 필수'",
    "dev_mode selection removed — user loses ability to choose spec-driven",
    "PR claims 'feat: add MCP config' but actually removes existing interview questions",
    "scope drift: no MCP-related code added despite PR description",
]

ANCHORING_RISK = """
Single-pass: reviewer primed by "feat: add MCP" may focus on looking for
the MCP addition code and miss that existing interview logic was gutted.
The mismatch between PR description and actual diff is a red flag that
anchored reviewers may overlook by assuming the feature is "elsewhere".
"""
