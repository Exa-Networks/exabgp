#!/usr/bin/env python3
"""PostToolUse hook: Auto-lint Python files after Write/Edit operations.

Advisory mode: fixes issues silently, shows warnings but doesn't block.
"""
import json
import subprocess
import sys
from pathlib import Path


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return

    tool_name = input_data.get('tool_name', '')
    if tool_name not in ('Write', 'Edit'):
        return

    tool_input = input_data.get('tool_input', {})
    file_path = tool_input.get('file_path', '')

    if not file_path.endswith('.py'):
        return

    path = Path(file_path)
    if not path.exists():
        return

    # Find project root (has pyproject.toml)
    project_root = path.parent
    while project_root != project_root.parent:
        if (project_root / 'pyproject.toml').exists():
            break
        project_root = project_root.parent
    else:
        # No pyproject.toml found, can't run uv
        return

    issues = []

    try:
        # Format (auto-fix)
        subprocess.run(
            ['uv', 'run', 'ruff', 'format', str(path)],
            cwd=project_root,
            timeout=30,
            capture_output=True,
        )

        # Check and auto-fix
        subprocess.run(
            ['uv', 'run', 'ruff', 'check', '--fix', str(path)],
            cwd=project_root,
            timeout=30,
            capture_output=True,
        )

        # Final check for remaining issues
        result = subprocess.run(
            ['uv', 'run', 'ruff', 'check', str(path)],
            cwd=project_root,
            timeout=30,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0 and result.stdout.strip():
            # Count issues
            lines = [ln for ln in result.stdout.strip().split('\n') if ln and not ln.startswith('Found')]
            if lines:
                issues.append(f'{len(lines)} lint issue(s) remaining')

    except subprocess.TimeoutExpired:
        issues.append('lint timeout')
    except FileNotFoundError:
        # uv not found - skip silently
        return
    except Exception as e:
        issues.append(f'lint error: {e}')

    # Advisory mode: report issues but don't block (exit 0)
    if issues:
        print(f'[lint] {path.name}: {", ".join(issues)}', file=sys.stderr)
        sys.exit(1)  # Non-blocking warning


if __name__ == '__main__':
    main()
