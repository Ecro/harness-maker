"""Cursor's `sessionStart` wiring — and the one hook deliberately kept out of it.

Until 2026-08-16 `.cursor/hooks.json` rendered no session event at all, so a harness with
`autonomy.autopilot_persistent: true` auto-armed on Claude Code and Codex and silently did
not on Cursor. The event was assumed absent; it is not. Probed against the installed Cursor
bundle: the extension host's hook-event enum lists `sessionStart` beside the four events
already rendered here, and Cursor ships an explicit Claude->Cursor mapping table
(`{PreToolUse: preToolUse, ..., SessionStart: sessionStart, ...}`).

The interesting half of this contract is the exclusion. `sessionid_envfile` writes to
`$CLAUDE_ENV_FILE`, which Cursor does not define (zero occurrences in that same bundle), so
its `main()` would take the `env_file is None` early return on every invocation. Rendering it
"for parity" would ship a hook that cannot do anything — the `.claude/hooks/hooks.json`
mistake, which stayed dead for months precisely because nothing asserted against it.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from harness_maker.models import HarnessConfig
from harness_maker.render import _make_env

_CURSOR = "cursor/hooks.json.j2"
_CLAUDE = "settings/Production.json.j2"


def _render(template: str) -> dict[str, Any]:
    config = HarnessConfig().model_dump(mode="json")
    return json.loads(  # type: ignore[no-any-return]
        _make_env()
        .get_template(template)
        .render(preset="Side", config=config, harness_maker_src_path="/fake/src/path")
    )


def _commands(rendered: dict[str, Any], event: str) -> list[str]:
    """Every command string under `event`, flattened across both hook schemas."""
    out: list[str] = []
    for entry in rendered.get("hooks", {}).get(event, []):
        if "command" in entry:
            out.append(entry["command"])
        else:
            out.extend(h["command"] for h in entry.get("hooks", []))
    return out


def test_cursor_renders_a_session_start_event() -> None:
    """Non-vacuity for everything below — they are all assertions about ITS contents."""
    assert _commands(_render(_CURSOR), "sessionStart"), (
        "Cursor renders no sessionStart hook. `autopilot_persistent: true` then arms on "
        "Claude Code and Codex but never on Cursor, with nothing reporting the difference."
    )


def test_cursor_auto_arms_autopilot_on_session_start() -> None:
    commands = _commands(_render(_CURSOR), "sessionStart")
    assert any("autopilot_autoarm" in c for c in commands), (
        f"autopilot_autoarm missing from Cursor sessionStart: {commands}"
    )


def test_cursor_does_not_render_the_env_file_hook() -> None:
    """The exclusion is the design, not an oversight — assert it so nobody "fixes" it.

    A future contributor comparing the three IDEs will see two hooks on Claude/Codex and one
    here. Without this test the natural correction is to add the second one, which would ship
    a guaranteed no-op: `$CLAUDE_ENV_FILE` does not exist in Cursor.
    """
    commands = _commands(_render(_CURSOR), "sessionStart")
    assert not any("sessionid_envfile" in c for c in commands), (
        "sessionid_envfile is rendered into Cursor's sessionStart. It writes to "
        "$CLAUDE_ENV_FILE, which Cursor does not define, so it can only ever take its "
        "`env_file is None` early return. Cursor sessions are id-less BY DESIGN and share "
        "the degraded autopilot marker."
    )


@pytest.mark.parametrize("event", ["sessionStart", "preToolUse", "postToolUse", "stop"])
def test_cursor_hook_events_stay_lowercase_camel(event: str) -> None:
    """Cursor's own schema, not Claude's PascalCase — a wrong key silently never fires."""
    assert event in _render(_CURSOR).get("hooks", {}), f"{event} missing or misspelled"


def test_claude_still_wires_both_session_start_hooks() -> None:
    """The Cursor exclusion must not be mirrored back onto the IDE that needs both.

    `$CLAUDE_ENV_FILE` is real on Claude Code, and `HM_SESSION_ID` is what makes loop markers
    session-scoped there. Dropping it would re-open the degraded-fallback path for every
    Claude session.
    """
    commands = _commands(_render(_CLAUDE), "SessionStart")
    assert any("sessionid_envfile" in c for c in commands), commands
    assert any("autopilot_autoarm" in c for c in commands), commands
