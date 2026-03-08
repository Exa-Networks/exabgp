#!/usr/bin/env python3
"""PreToolUse hook: Block operations on forbidden paths.

Prevents Claude from working in exabgp-5.0 worktree (wrong path).
The correct 5.0 worktree is at ../5.0.
"""

import json
import sys

FORBIDDEN = [
    '/Users/thomas/Code/github.com/exa-networks/exabgp/exabgp-5.0',
]

BLOCKED_TOOLS = ('Write', 'Edit', 'Bash', 'Read')


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return

    tool_name = input_data.get('tool_name', '')
    if tool_name not in BLOCKED_TOOLS:
        return

    tool_input = input_data.get('tool_input', {})

    # Check file_path for Write/Edit/Read
    file_path = tool_input.get('file_path', '')
    # Check command for Bash
    command = tool_input.get('command', '')

    text_to_check = f'{file_path} {command}'

    for forbidden in FORBIDDEN:
        if forbidden in text_to_check:
            print(f'BLOCKED: {forbidden} is a forbidden path.', file=sys.stderr)
            print('Use ../5.0 for 5.0 branch work, not exabgp-5.0.', file=sys.stderr)
            sys.exit(2)


if __name__ == '__main__':
    main()
