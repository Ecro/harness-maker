"""Static message catalog keyed by locale code (``"ko"``/``"en"``).

English is the canonical baseline; other catalogs may be partial — ``i18n.t()``
falls back to English per-key for missing translations.
"""

from __future__ import annotations

# Keyed by Locale.value (str) to avoid a circular import with i18n.py.
MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "q1_choose_language": "Choose your language: {lang}",
        "apply_done": "Apply complete.",
        "error_no_yaml": ".claude/harness.yaml not found.",
        "spec_gate_missing_warn": (
            "spec-gate (warn): no SPEC referencing {test_path} found in "
            "{spec_dir}/. Add a SPEC-*.md or switch dev_mode=task-driven."
        ),
        "spec_gate_missing_block": (
            "spec-gate (block): refusing test write — no SPEC referencing "
            "{test_path} found in {spec_dir}/. Add a SPEC-*.md or switch "
            "dev_mode=task-driven in .claude/harness.yaml."
        ),
        "permission_gate_blocked": (
            "permission-gate: command rejected — matched dangerous pattern "
            "{pattern!r}. Reword the command or remove the unsafe construct."
        ),
    },
    "ko": {
        "q1_choose_language": "사용할 언어를 선택하세요: {lang}",
        "apply_done": "적용 완료.",
        "error_no_yaml": ".claude/harness.yaml 파일을 찾을 수 없습니다.",
        "spec_gate_missing_warn": (
            "spec-gate (warn): {test_path} 를 참조하는 SPEC 가 {spec_dir}/ 에 "
            "없습니다. SPEC-*.md 추가 혹은 dev_mode=task-driven 전환을 검토하세요."
        ),
        "spec_gate_missing_block": (
            "spec-gate (block): 테스트 쓰기 차단 — {test_path} 를 참조하는 "
            "SPEC 가 {spec_dir}/ 에 없습니다. SPEC-*.md 추가 혹은 "
            ".claude/harness.yaml 의 dev_mode 를 task-driven 으로."
        ),
        "permission_gate_blocked": (
            "permission-gate: 명령 차단 — 위험 패턴 {pattern!r} 매칭. "
            "안전한 형태로 재작성하거나 위험 구문을 제거하세요."
        ),
    },
}
