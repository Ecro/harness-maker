"""Security scanner package — 5 gates.

Gates: secrets, permissions, hook injection, CVEs, prompt injection.
"""

from __future__ import annotations

from harness_maker.models import Finding
from harness_maker.secscan.dependency_cves import scan as scan_dependency_cves
from harness_maker.secscan.hook_injection import scan as scan_hook_injection
from harness_maker.secscan.permissions import scan as scan_permissions
from harness_maker.secscan.prompt_injection import scan as scan_prompt_injection
from harness_maker.secscan.prompt_injection import scan_with_llm as scan_prompt_injection_llm
from harness_maker.secscan.secrets import scan as scan_secrets

__all__ = [
    "Finding",
    "scan_dependency_cves",
    "scan_hook_injection",
    "scan_permissions",
    "scan_prompt_injection",
    "scan_prompt_injection_llm",
    "scan_secrets",
]
