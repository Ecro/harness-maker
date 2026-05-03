"""Static message catalog keyed by locale code (``"ko"``/``"en"``)."""

from __future__ import annotations

# Keyed by Locale.value (str) to avoid a circular import with i18n.py.
MESSAGES: dict[str, dict[str, str]] = {
    "ko": {
        "q1_choose_language": "사용할 언어를 선택하세요: {lang}",
        "apply_done": "적용 완료.",
        "error_no_yaml": ".claude/harness.yaml 파일을 찾을 수 없습니다.",
    },
    "en": {
        "q1_choose_language": "Choose your language: {lang}",
        "apply_done": "Apply complete.",
        "error_no_yaml": ".claude/harness.yaml not found.",
    },
}
