#!/usr/bin/env python3
"""PostToolUse hook: Auto-lint Python files after Write/Edit operations.

Advisory mode: fixes issues silently, shows warnings but doesn't block.
"""

import json
import subprocess
import sys
from pathlib import Path

# ANSI color codes
YELLOW = '\033[33m'
CYAN = '\033[36m'
RED = '\033[31m'
GREEN = '\033[32m'
BOLD = '\033[1m'
DIM = '\033[2m'
RESET = '\033[0m'


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
            # Parse issues from ruff output
            lines = [ln for ln in result.stdout.strip().split('\n') if ln and not ln.startswith('Found')]
            if lines:
                # Build actionable output
                rel_path = path.relative_to(project_root) if path.is_relative_to(project_root) else path
                print(
                    f'{YELLOW}⚠️  Ruff found {BOLD}{len(lines)}{RESET}{YELLOW} issue(s) in {CYAN}{path.name}{RESET}{YELLOW} that need manual fixing:{RESET}',
                    file=sys.stderr,
                )
                # Show first 3 issues as preview
                for line in lines[:3]:
                    print(f'   {DIM}{line}{RESET}', file=sys.stderr)
                if len(lines) > 3:
                    print(f'   {DIM}... and {len(lines) - 3} more{RESET}', file=sys.stderr)
                print(f'   {GREEN}Run: uv run ruff check {rel_path}{RESET}', file=sys.stderr)
                sys.exit(1)  # Non-blocking warning

    except subprocess.TimeoutExpired:
        print(f'{YELLOW}⚠️  Ruff timed out{RESET}', file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        # uv not found - skip silently
        return
    except Exception as e:
        print(f'{RED}⚠️  Ruff error: {e}{RESET}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
