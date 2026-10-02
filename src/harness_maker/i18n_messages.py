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
            "{spec_dir}/. Add a SPEC-*.md or set spec.strictness: warn."
        ),
        "spec_gate_missing_block": (
            "spec-gate (block): refusing test write — no SPEC referencing "
            "{test_path} found in {spec_dir}/. Add a SPEC-*.md or set "
            "spec.strictness: warn in .claude/harness.yaml."
        ),
        "permission_gate_blocked": (
            "permission-gate: command rejected — matched dangerous pattern "
            "{pattern!r}. Reword the command or remove the unsafe construct."
        ),
        "world_model_handle_collision": (
            "world model handle {handle!r} is already a shipped skill name; choose another."
        ),
        "world_model_handle_reserved-prefix": (
            "world model handle {handle!r} starts with the reserved prefix 'hm-'; choose another."
        ),
        "world_model_handle_grammar": (
            "world model handle {handle!r} must be lowercase a-z, 0-9 and single inner hyphens."
        ),
        "world_model_handle_length": (
            "world model handle {handle!r} is longer than 64 characters."
        ),
        "world_model_handle_required": (
            "no handle can be derived from world model name {name!r}; "
            "pass --world-model-handle (a-z, 0-9, single hyphens)."
        ),
        "world_model_handle_taken": (
            "{path} is a user-owned skill, kept as-is — the world model router is NOT "
            "installed at /{handle}. Choose another handle (/hm:configure)."
        ),
    },
    "ko": {
        "q1_choose_language": "사용할 언어를 선택하세요: {lang}",
        "apply_done": "적용 완료.",
        "error_no_yaml": ".claude/harness.yaml 파일을 찾을 수 없습니다.",
        "spec_gate_missing_warn": (
            "spec-gate (warn): {test_path} 를 참조하는 SPEC 가 {spec_dir}/ 에 "
            "없습니다. SPEC-*.md 추가 혹은 spec.strictness: warn 전환을 검토하세요."
        ),
        "spec_gate_missing_block": (
            "spec-gate (block): 테스트 쓰기 차단 — {test_path} 를 참조하는 "
            "SPEC 가 {spec_dir}/ 에 없습니다. SPEC-*.md 추가 혹은 "
            ".claude/harness.yaml 의 spec.strictness 를 warn 으로."
        ),
        "permission_gate_blocked": (
            "permission-gate: 명령 차단 — 위험 패턴 {pattern!r} 매칭. "
            "안전한 형태로 재작성하거나 위험 구문을 제거하세요."
        ),
        "world_model_handle_collision": (
            "world model 핸들 {handle!r} 은 이미 기본 제공 skill 이름입니다. 다른 핸들을 고르세요."
        ),
        "world_model_handle_reserved-prefix": (
            "world model 핸들 {handle!r} 은 예약된 접두사 'hm-' 로 시작합니다. "
            "다른 핸들을 고르세요."
        ),
        "world_model_handle_grammar": (
            "world model 핸들 {handle!r} 은 소문자 a-z, 0-9, 단일 하이픈만 쓸 수 있습니다."
        ),
        "world_model_handle_length": ("world model 핸들 {handle!r} 이 64자를 넘습니다."),
        "world_model_handle_required": (
            "world model 이름 {name!r} 에서 핸들을 만들 수 없습니다. "
            "--world-model-handle 을 지정하세요 (a-z, 0-9, 단일 하이픈)."
        ),
        "world_model_handle_taken": (
            "{path} 는 사용자 소유 skill 이라 그대로 두었습니다 — world model router 는 "
            "/{handle} 에 설치되지 않았습니다. 다른 핸들을 고르세요 (/hm:configure)."
        ),
    },
}
