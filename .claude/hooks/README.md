# Claude Code Hooks

This directory contains hooks that extend Claude Code's functionality for ExaBGP development.

## Available Hooks

### auto_linter.py

**Trigger:** PostToolUse (Write, Edit)
**Mode:** Advisory (non-blocking)

Automatically formats and lints Python files after they are written or edited.

**What it does:**
1. Runs `uv run ruff format <file>` to auto-format
2. Runs `uv run ruff check --fix <file>` to auto-fix lint issues
3. Reports any remaining unfixable issues as warnings

**Configuration:** Enabled in `.claude/settings.local.json`:
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/auto_linter.py",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

## Adding New Hooks

### Hook Types

Claude Code supports these hook events:
- **PreToolUse** - Before a tool executes (can block)
- **PostToolUse** - After a tool executes (can provide feedback)
- **Notification** - For status updates

### Creating a Hook

1. Create a Python or Bash script in `.claude/hooks/`
2. Make it executable: `chmod +x script.py`
3. Add configuration to `.claude/settings.local.json`

### Hook Input Format

Hooks receive JSON on stdin:
```json
{
  "hook_event_name": "PostToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.py",
    "content": "..."
  },
  "tool_response": {
    "success": true
  },
  "cwd": "/project/root",
  "session_id": "..."
}
```

### Exit Codes

- **Exit 0:** Success (stdout shown in verbose mode)
- **Exit 1:** Non-blocking warning (stderr shown)
- **Exit 2:** Blocking error (prevents further processing)

### Example: Security Check Hook

```python
#!/usr/bin/env python3
import json
import re
import sys

input_data = json.load(sys.stdin)
content = input_data.get('tool_input', {}).get('content', '')

# Check for hardcoded secrets
if re.search(r'(?i)(password|api_key|secret)\s*=\s*["\'][^"\']+["\']', content):
    print('Possible hardcoded secret detected', file=sys.stderr)
    sys.exit(2)  # Block the write
```

## Debugging Hooks

Test a hook manually:
```bash
echo '{"tool_name":"Write","tool_input":{"file_path":"test.py"}}' | ./.claude/hooks/auto_linter.py
echo $?  # Check exit code
```

## References

- [Claude Code Hooks Documentation](https://docs.anthropic.com/claude-code/hooks)
- `.claude/settings.local.json` - Hook configuration
