# Codex Compatibility Fixtures

Representative hook stdin samples for Codex CLI hook contract verification.

## Files

- `hook_permission_request_allow.json` — PermissionRequest for a safe Read tool → expect `{"hookSpecificOutput": {"decision": {"behavior": "allow"}}}`
- `hook_permission_request_deny.json` — PermissionRequest for dangerous Bash (`curl | sh`) → expect `{"hookSpecificOutput": {"decision": {"behavior": "deny"}}}`
- `hook_pre_tool_use_allow.json` — PreToolUse Write within project → expect exit 0

## Usage

```bash
# Test allow path
python -m harness_maker.gates.permission_gate < hook_permission_request_allow.json
echo $?  # must be 0

# Test deny path (Codex path — exits 0, outputs JSON with deny decision)
python -m harness_maker.gates.permission_gate < hook_permission_request_deny.json
echo $?  # must be 0; stdout must contain {"hookSpecificOutput": {..., "behavior": "deny"}}
```

## Codex Hook Contract

Codex reads hook output differently from Claude Code:
- `exit 0` + JSON stdout with `hookSpecificOutput.decision.behavior` = "allow" | "deny"
- Claude Code uses exit code (0 = allow, 2 = deny) for PreToolUse/PostToolUse
- PermissionRequest is Codex-exclusive and always exits 0 regardless of decision
