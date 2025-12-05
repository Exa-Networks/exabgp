"""transform.py

Transform v4 (action-first) API commands to v6 (target-first) format.

When API version is v4, incoming commands are transformed to v6 format
before parsing. This ensures both API versions share the same core parser.

Created on 2025-12-05.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

# Type alias for dispatch tree: leaf is str (replacement), branch is nested dict
# None key in dict = default/catch-all handler for unmatched words
DispatchNode = str | dict[str | None, 'DispatchNode']

# Valid announce/withdraw subcommands in v4
ANNOUNCE_SUBCOMMANDS = frozenset(
    {
        'route',
        'route-refresh',
        'ipv4',
        'ipv6',
        'flow',
        'eor',
        'watchdog',
        'attribute',
        'attributes',
        'operational',
        'vpls',
    }
)

WITHDRAW_SUBCOMMANDS = frozenset(
    {
        'route',
        'ipv4',
        'ipv6',
        'flow',
        'watchdog',
        'attribute',
        'attributes',
        'vpls',
    }
)

# Valid neighbor selector keys (key-value pairs after IP/*)
NEIGHBOR_SELECTOR_KEYS = frozenset(
    {
        'peer-as',
        'local-as',
        'local-ip',
        'router-id',
        'family-allowed',
    }
)

# Valid actions after neighbor selector
NEIGHBOR_ACTIONS = frozenset(
    {
        'announce',
        'withdraw',
        'teardown',
    }
)

# Hierarchical dispatch tree: v4 command words → v6 prefix
# Navigate by splitting command into words and traversing the tree
# String leaf = v6 prefix to use; dict = continue to next word
DISPATCH: dict[str | None, DispatchNode] = {
    # Daemon control
    'shutdown': 'daemon shutdown',
    'reload': 'daemon reload',
    'restart': 'daemon restart',
    'status': 'daemon status',
    # Session management
    'enable-ack': 'session ack enable',
    'disable-ack': 'session ack disable',
    'silence-ack': 'session ack silence',
    'enable-sync': 'session sync enable',
    'disable-sync': 'session sync disable',
    'reset': 'session reset',
    'ping': 'session ping',
    'bye': 'session bye',
    # System commands
    'help': 'system help',
    'version': 'system version',
    'crash': 'system crash',
    'queue-status': 'system queue-status',
    'api': {
        'version': 'system api version',
    },
    # Peer operations (v6 uses 'peer' instead of 'neighbor')
    'teardown': 'peer * teardown',
    # RIB operations (layered: show/flush/clear → adj-rib → in/out)
    'show': {
        'adj-rib': {
            'in': 'rib show in',
            'out': 'rib show out',
        },
        'neighbor': 'peer show',
    },
    'flush': {
        'adj-rib': {
            'out': 'rib flush out',
        },
    },
    'clear': {
        'adj-rib': {
            'in': 'rib clear in',
            'out': 'rib clear out',
        },
    },
    # Peer management
    'create': {
        'neighbor': 'peer create',
    },
    'delete': {
        'neighbor': 'peer delete',
    },
    # Announce - explicit subcommands (v6 uses 'peer' instead of 'neighbor')
    'announce': {
        'route': 'peer * announce route',
        'route-refresh': 'peer * announce route-refresh',
        'ipv4': 'peer * announce ipv4',
        'ipv6': 'peer * announce ipv6',
        'flow': 'peer * announce flow',
        'eor': 'peer * announce eor',
        'watchdog': 'peer * announce watchdog',
        'attribute': 'peer * announce attribute',
        'attributes': 'peer * announce attributes',
        'operational': 'peer * announce operational',
        'vpls': 'peer * announce vpls',
    },
    # Withdraw - explicit subcommands (v6 uses 'peer' instead of 'neighbor')
    'withdraw': {
        'route': 'peer * withdraw route',
        'ipv4': 'peer * withdraw ipv4',
        'ipv6': 'peer * withdraw ipv6',
        'flow': 'peer * withdraw flow',
        'watchdog': 'peer * withdraw watchdog',
        'attribute': 'peer * withdraw attribute',
        'attributes': 'peer * withdraw attributes',
        'vpls': 'peer * withdraw vpls',
    },
    # neighbor is handled specially - see _transform_neighbor()
}


def _is_ip_or_wildcard(word: str) -> bool:
    """Check if word is an IP address or wildcard."""
    if word == '*':
        return True
    # IPv4: contains exactly 3 dots
    if word.count('.') == 3:
        return True
    # IPv6: contains colons
    if ':' in word:
        return True
    return False


def _parse_selector_group(words: list[str], start_idx: int) -> tuple[list[str], int]:
    """Parse a single selector group (IP + optional key-value pairs).

    Returns: (selector_parts, next_index)
    - selector_parts: list of words forming this selector (e.g., ['10.0.0.1', 'router-id', '1.2.3.4'])
    - next_index: index of next word after this selector group
    """
    parts: list[str] = []
    idx = start_idx

    # First word must be IP or *
    if idx >= len(words):
        raise ValueError('expected IP or * in selector')
    if not _is_ip_or_wildcard(words[idx]):
        raise ValueError(f'expected IP or * in selector, got: {words[idx]}')
    parts.append(words[idx])
    idx += 1

    # Parse optional key-value pairs
    while idx < len(words):
        word = words[idx]

        # Check for comma (end of this selector group)
        if word == ',':
            break
        if word.endswith(','):
            # Value with trailing comma - strip and include
            parts.append(word.rstrip(','))
            idx += 1
            break

        # Check if this is an action (end of selectors)
        if word in NEIGHBOR_ACTIONS:
            break

        # Check if this is a selector key
        if word in NEIGHBOR_SELECTOR_KEYS:
            parts.append(word)
            if idx + 1 >= len(words):
                raise ValueError(f'selector {word} requires a value')

            # family-allowed special handling
            if word == 'family-allowed':
                value = words[idx + 1]
                if value == 'in-open' or '-' in value:
                    parts.append(value.rstrip(','))
                    idx += 2
                    if value.endswith(','):
                        break
                else:
                    if idx + 2 >= len(words):
                        raise ValueError('family-allowed requires afi and safi (or in-open or afi-safi)')
                    parts.append(words[idx + 1])
                    val2 = words[idx + 2]
                    parts.append(val2.rstrip(','))
                    idx += 3
                    if val2.endswith(','):
                        break
            else:
                value = words[idx + 1]
                parts.append(value.rstrip(','))
                idx += 2
                if value.endswith(','):
                    break
            continue

        # Unknown word - end of selector
        break

    return parts, idx


def _transform_neighbor(words: list[str]) -> str:
    """Parse and validate neighbor-prefixed v4 command, transform to v6.

    Format: neighbor <ip|*> [<selector-key> <selector-value>]... <action> [args...]
    Output (single): peer <ip|*> [<selector-key> <selector-value>]... <action> [args...]

    Also handles comma-separated neighbor selectors:
    Format: neighbor <ip> <key> <val>, neighbor <ip> <action> [args...]
    Output (multiple): peer [<ip> <key> <val>, <ip>] <action> [args...]

    v6 bracket syntax rules:
    - Single selector: peer <ip> <action> (no brackets)
    - Wildcard: peer * <action> (no brackets)
    - Multiple selectors: peer [<sel1>, <sel2>] <action> (brackets required)

    Validates structure and converts 'neighbor' to 'peer' for v6.
    Raises ValueError if structure is invalid.
    """
    if len(words) < 2:
        raise ValueError('neighbor requires at least IP/wildcard')

    # words[0] is 'neighbor'
    if not _is_ip_or_wildcard(words[1]):
        raise ValueError(f'expected IP or * after neighbor, got: {words[1]}')

    # Parse all selector groups
    selector_groups: list[list[str]] = []
    idx = 1  # Start after 'neighbor'

    while idx < len(words):
        # Skip 'neighbor' keyword at start of each group
        if words[idx] == 'neighbor':
            idx += 1
            continue

        # Check if we've hit an action
        if words[idx] in NEIGHBOR_ACTIONS:
            break

        # Skip comma separators
        if words[idx] == ',':
            idx += 1
            continue

        # Parse a selector group
        group, idx = _parse_selector_group(words, idx)
        if group:
            selector_groups.append(group)

    if not selector_groups:
        raise ValueError('neighbor command missing selector')

    # Find and validate action
    action_idx = idx
    if action_idx >= len(words):
        raise ValueError('neighbor command missing action (announce/withdraw/teardown)')

    action = words[action_idx]
    if action not in NEIGHBOR_ACTIONS:
        raise ValueError(f'expected action, got: {action}')

    # Validate subcommand
    if action == 'announce':
        if action_idx + 1 < len(words):
            subcommand = words[action_idx + 1]
            if subcommand not in ANNOUNCE_SUBCOMMANDS:
                raise ValueError(f'unknown announce subcommand: {subcommand}')
    elif action == 'withdraw':
        if action_idx + 1 < len(words):
            subcommand = words[action_idx + 1]
            if subcommand not in WITHDRAW_SUBCOMMANDS:
                raise ValueError(f'unknown withdraw subcommand: {subcommand}')

    # Build v6 output
    action_and_args = ' '.join(words[action_idx:])

    # Check for wildcard (single selector with just '*')
    if len(selector_groups) == 1 and selector_groups[0] == ['*']:
        return f'peer * {action_and_args}'

    # Single selector - no brackets
    if len(selector_groups) == 1:
        selector_str = ' '.join(selector_groups[0])
        return f'peer {selector_str} {action_and_args}'

    # Multiple selectors - use brackets
    selector_strs = [' '.join(g) for g in selector_groups]
    return f'peer [{", ".join(selector_strs)}] {action_and_args}'


def v4_to_v6(command: str) -> str:
    """Transform v4 command to v6 format.

    Args:
        command: The v4 command string to transform

    Returns:
        Transformed v6 command string

    Raises:
        ValueError: If command structure is invalid

    Examples:
        >>> v4_to_v6('shutdown')
        'daemon shutdown'
        >>> v4_to_v6('announce route 10.0.0.0/24 next-hop 1.2.3.4')
        'neighbor * announce route 10.0.0.0/24 next-hop 1.2.3.4'
        >>> v4_to_v6('neighbor 192.168.1.1 announce route 10.0.0.0/24')
        'neighbor 192.168.1.1 announce route 10.0.0.0/24'
    """
    command = command.strip()

    # Empty command or comment - return as-is
    if not command or command.startswith('#'):
        return command

    # Commands already in v6 format - return as-is
    # Note: 'peer ' is v6 format (v4 uses 'neighbor')
    if command.startswith(('daemon ', 'session ', 'system ', 'rib ', 'peer ')):
        return command

    words = command.split()
    if not words:
        return command

    # Special handling for neighbor-prefixed commands
    if words[0] == 'neighbor':
        return _transform_neighbor(words)

    # Navigate dispatch tree
    node: DispatchNode = DISPATCH
    consumed = 0

    for word in words:
        if isinstance(node, str):
            # Hit a leaf - use this prefix
            break
        if word in node:
            node = node[word]
            consumed += 1
        elif None in node:
            # Default handler for this level
            node = node[None]
            break
        else:
            # No match at this level
            break

    # If we ended on a string, it's our v6 prefix
    if isinstance(node, str):
        rest = ' '.join(words[consumed:])
        return f'{node} {rest}'.strip()

    # Check for default handler if we ended on a dict
    if isinstance(node, dict) and None in node:
        default = node[None]
        if isinstance(default, str):
            rest = ' '.join(words[consumed:])
            return f'{default} {rest}'.strip()

    # No transformation matched - return as-is
    return command


def is_v4_command(command: str) -> bool:
    """Check if a command appears to be in v4 format.

    Args:
        command: The command string to check

    Returns:
        True if the command appears to be v4 format
    """
    command = command.strip()

    if not command or command.startswith('#'):
        return False

    # v6-only prefixes
    if command.startswith(('daemon ', 'session ', 'system ', 'rib ', 'peer ')):
        return False

    words = command.split()
    if not words:
        return False

    # Check if first word starts a valid dispatch path
    return words[0] in DISPATCH or words[0] == 'neighbor'
