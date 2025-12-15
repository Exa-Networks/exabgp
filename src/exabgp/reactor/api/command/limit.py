"""command/limit.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import re
from typing import Iterable, Iterator


def extract_neighbors(command: str) -> tuple[list[list[str]], str]:
    """Return a list of neighbor definitions for matching against peers.

    Returns (definitions, remaining_command) where:
    - definitions: list of selector lists, each selector list contains strings like
      ['neighbor <ip>', 'router-id <id>'] to match against peer names
    - remaining_command: the action and arguments after selectors

    Supports multiple formats:
    - v4: neighbor <ip> [key value]... <action>
    - v4: neighbor <ip> [key val], neighbor <ip> <action>  (comma-separated)
    - v6: peer <ip> [key value]... <action>
    - v6: peer [<ip> key val, <ip>] <action>  (bracket syntax)
    """
    parts = command.split(' ', 1)
    if len(parts) == 1:
        return [], command

    prefix, remaining = parts

    # Accept both 'neighbor' (v4) and 'peer' (v6) prefixes
    if prefix not in ('neighbor', 'peer'):
        return [], command

    # Check for v6 bracket syntax: peer [selector1, selector2] action
    remaining = remaining.strip()
    if remaining.startswith('['):
        return _extract_bracket_selectors(remaining)

    # Non-bracket format: parse as before
    return _extract_legacy_selectors(prefix, remaining)


# Valid selector keys for filtering
SELECTOR_KEYS = frozenset(['local-ip', 'local-as', 'peer-as', 'router-id', 'family-allowed'])


def _extract_bracket_selectors(remaining: str) -> tuple[list[list[str]], str]:
    """Parse v6 bracket syntax: [<ip1> key val, <ip2>] action args.

    Returns (definitions, remaining_command).
    """
    # Find closing bracket
    bracket_end = remaining.find(']')
    if bracket_end == -1:
        # Malformed - no closing bracket, return empty
        return [], remaining

    bracket_content = remaining[1:bracket_end].strip()  # Content inside brackets
    after_bracket = remaining[bracket_end + 1 :].strip()  # Action and args

    # Split on comma to get individual selectors
    selector_strs = [s.strip() for s in bracket_content.split(',')]

    definitions: list[list[str]] = []
    for sel_str in selector_strs:
        if not sel_str:
            continue
        definition = _parse_single_selector(sel_str)
        if definition:
            definitions.append(definition)

    return definitions, after_bracket


def _parse_single_selector(sel_str: str) -> list[str]:
    """Parse a single selector string into a definition list.

    Input: '10.0.0.1 router-id 1.2.3.4'
    Output: ['neighbor 10.0.0.1', 'router-id 1.2.3.4']
    """
    words = sel_str.split()
    if not words:
        return []

    # First word is IP or *
    ip = words[0]
    definition: list[str] = [f'neighbor {ip}']

    # Parse remaining key-value pairs
    idx = 1
    while idx < len(words):
        key = words[idx]
        if key not in SELECTOR_KEYS:
            # Unknown key - stop parsing this selector
            break
        if idx + 1 >= len(words):
            # Key without value - stop
            break
        value = words[idx + 1]
        definition.append(f'{key} {value}')
        idx += 2

    return definition


def _extract_legacy_selectors(prefix: str, remaining: str) -> tuple[list[list[str]], str]:
    """Parse legacy format: <ip> [key val]... [, neighbor/peer <ip>]... action.

    Handles both v4 (neighbor) and v6 (peer) without brackets.
    """
    returned: list[list[str]] = []

    parts = remaining.split(' ', 1)
    if len(parts) == 1:
        return [], remaining

    ip, command = parts
    definition: list[str] = [f'neighbor {ip}']

    if ' ' not in command:
        return [definition], command

    while True:
        try:
            key, value, rest = command.split(' ', 2)
        except ValueError:
            # Two or fewer words remaining
            keyval = command.split(' ', 1)
            if len(keyval) == 1:
                return [definition] if definition else returned, command
            key, value = keyval
            rest = ''

        # Check for comma separator (v4 style multiple selectors)
        if key == ',':
            returned.append(definition)
            # After comma, expect 'neighbor' or 'peer' keyword
            parts = command.split(' ', 2)
            if len(parts) >= 2 and parts[1] in ('neighbor', 'peer'):
                # Skip comma and keyword, get IP
                if len(parts) >= 3:
                    ip_and_rest = parts[2].split(' ', 1)
                    ip = ip_and_rest[0]
                    command = ip_and_rest[1] if len(ip_and_rest) > 1 else ''
                    definition = [f'neighbor {ip}']
                    continue
            break

        # Check if this is a selector key
        if key in SELECTOR_KEYS or key in ('neighbor', 'peer'):
            definition.append(f'{key} {value}')
            command = rest
            continue

        # Not a selector key - we've hit the action
        if definition:
            returned.append(definition)
        break

    return returned, command


def match_neighbor(description: list[str], name: str) -> bool:
    for string in description:
        stripped = string.strip()
        # Accept both 'neighbor *' (v4) and 'peer *' (v6) wildcards
        if stripped in ('neighbor *', 'peer *'):
            return True
        pattern = rf'(^|\s){re.escape(string)}($|\s|,)'
        if re.search(pattern, name) is None:
            return False
    return True


def match_neighbors(peers: Iterable[str], descriptions: list[list[str]]) -> Iterator[str]:
    """Yield peers matching the description passed, or all peers if no description is given."""
    if not descriptions:
        yield from peers
        return

    seen: set[str] = set()
    for peer_name in peers:
        if peer_name in seen:
            continue
        for description in descriptions:
            if match_neighbor(description, peer_name):
                seen.add(peer_name)
                yield peer_name
                break
