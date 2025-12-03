"""shortcuts.py

Shared command shortcut/nickname expansion logic for ExaBGP CLI.

Created on 2025-11-20.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Callable

from exabgp.protocol.ip import IPv4


# Type for shortcut matching function - can return bool or a truthy/falsy value
ShortcutMatcher = Callable[[int, list[str]], bool | list[str]]


def _announce_context(pos: int, pre: list[str]) -> bool:
    """Match 'a' → 'announce' when at start or after IP address."""
    return pos == 0 or (bool(pre) and (pre[-1].count('.') == IPv4.DOT_COUNT or ':' in pre[-1]))


def _attributes_context(pos: int, pre: list[str]) -> bool:
    """Match 'a' → 'attributes' after announce/withdraw."""
    return bool(pre) and (pre[-1] == 'announce' or pre[-1] == 'withdraw')


def _adj_rib_context(pos: int, pre: list[str]) -> bool:
    """Match 'a' → 'adj-rib' after clear/flush/show."""
    return bool(pre) and pre[-1] in ['clear', 'flush', 'show']


def _eor_context(pos: int, pre: list[str]) -> bool:
    """Match 'e' → 'eor' after announce."""
    return bool(pre) and pre[-1] == 'announce'


def _flow_context(pos: int, pre: list[str]) -> bool:
    """Match 'f' → 'flow' after announce/withdraw."""
    return bool(pre) and (pre[-1] == 'announce' or pre[-1] == 'withdraw')


def _flush_context(pos: int, pre: list[str]) -> bool:
    """Match 'f' → 'flush' at start or after IP address."""
    return pos == 0 or (bool(pre) and (pre[-1].count('.') == IPv4.DOT_COUNT or ':' in pre[-1]))


def _in_context(pos: int, pre: list[str]) -> bool:
    """Match 'i' → 'in' after adj-rib."""
    return bool(pre) and pre[-1] == 'adj-rib'


def _operation_context(pos: int, pre: list[str]) -> bool:
    """Match 'o' → 'operation' after announce."""
    return bool(pre) and pre[-1] == 'announce'


def _out_context(pos: int, pre: list[str]) -> bool:
    """Match 'o' → 'out' after adj-rib."""
    return bool(pre) and pre[-1] == 'adj-rib'


def _route_context(pos: int, pre: list[str]) -> bool:
    """Match 'r' → 'route' after announce/withdraw."""
    return bool(pre) and (pre[-1] == 'announce' or pre[-1] == 'withdraw')


def _teardown_context(pos: int, pre: list[str]) -> bool:
    """Match 't' → 'teardown' at start or after IP address."""
    return pos == 0 or (bool(pre) and (pre[-1].count('.') == IPv4.DOT_COUNT or ':' in pre[-1]))


def _vps_context(pos: int, pre: list[str]) -> bool:
    """Match 'v' → 'vps' after announce/withdraw."""
    return bool(pre) and (pre[-1] == 'announce' or pre[-1] == 'withdraw')


def _withdraw_context(pos: int, pre: list[str]) -> bool:
    """Match 'w' → 'withdraw' at start or after IP address."""
    return pos == 0 or (bool(pre) and (pre[-1].count('.') == IPv4.DOT_COUNT or ':' in pre[-1]))


def _watchdog_context(pos: int, pre: list[str]) -> bool:
    """Match 'w' → 'watchdog' after announce/withdraw."""
    return bool(pre) and (pre[-1] == 'announce' or pre[-1] == 'withdraw')


class CommandShortcuts:
    """Handles command shortcut expansion for CLI."""

    # Shortcut definitions: (nickname, full_name, match_condition)
    # Match condition is a function: (position: int, previous_tokens: list) -> bool
    SHORTCUTS: list[tuple[str, str, ShortcutMatcher]] = [
        # 'a' has multiple meanings based on context
        ('a', 'announce', _announce_context),
        ('a', 'attributes', _attributes_context),
        ('a', 'adj-rib', _adj_rib_context),
        ('a', 'ack', lambda pos, pre: len(pre) > 0 and pre[-1] == 'session'),  # session ack
        # Other single-letter shortcuts
        ('c', 'configuration', lambda pos, pre: True),
        ('d', 'daemon', lambda pos, pre: pos == 0),  # Top-level only
        ('e', 'eor', _eor_context),
        ('e', 'extensive', lambda pos, pre: 'show' in pre),
        ('f', 'flow', _flow_context),
        ('f', 'flush', _flush_context),
        ('h', 'help', lambda pos, pre: pos == 0),
        ('i', 'in', _in_context),
        ('id', 'router-id', lambda pos, pre: 'neighbor' in pre),  # CLI shortcut: id → router-id in neighbor context
        ('n', 'neighbor', lambda pos, pre: pos == 0),  # Only at start - removed 'show n' → 'show neighbor' support
        ('o', 'operation', _operation_context),
        ('o', 'out', _out_context),
        ('r', 'route', _route_context),
        ('r', 'refresh', lambda pos, pre: len(pre) >= 2 and pre[-2] == 'announce' and pre[-1] == 'route'),
        ('s', 'show', lambda pos, pre: pos == 0),
        ('s', 'summary', lambda pos, pre: pos != 0),
        ('t', 'teardown', _teardown_context),
        ('v', 'vps', _vps_context),
        ('w', 'withdraw', _withdraw_context),
        ('w', 'watchdog', _watchdog_context),
        # Multi-letter shortcuts
        ('ses', 'session', lambda pos, pre: pos == 0),  # Top-level only (avoid 's' conflict)
        ('sy', 'sync', lambda pos, pre: len(pre) > 0 and pre[-1] == 'session'),  # session sync
        # Common typos
        ('neighbour', 'neighbor', lambda pos, pre: True),
        ('neigbour', 'neighbor', lambda pos, pre: True),
        ('neigbor', 'neighbor', lambda pos, pre: True),
    ]

    @classmethod
    def expand_shortcuts(cls, command: str) -> str:
        """Expand shortcuts in a command string and apply CLI transformations.

        Args:
            command: The command string to process (e.g., "s n summary")

        Returns:
            Expanded and transformed command string (e.g., "show neighbor summary")

        Examples:
            >>> CommandShortcuts.expand_shortcuts('s n summary')
            'show neighbor summary'
            >>> CommandShortcuts.expand_shortcuts('a r 10.0.0.0/24 next-hop 192.168.1.1')
            'announce route 10.0.0.0/24 next-hop 192.168.1.1'
            >>> CommandShortcuts.expand_shortcuts('n 192.168.1.1 show summary')
            'show neighbor 192.168.1.1 summary'
        """
        tokens = command.split()
        if not tokens:
            return command

        expanded = cls.expand_token_list(tokens)
        expanded_str = ' '.join(expanded).strip()

        # Apply CLI-to-API transformations
        transformed = cls.transform_cli_to_api(expanded_str)
        return transformed

    @classmethod
    def expand_token_list(cls, tokens: list[str]) -> list[str]:
        """Expand shortcuts in a list of tokens.

        Args:
            tokens: List of command tokens

        Returns:
            List of expanded tokens

        Examples:
            >>> CommandShortcuts.expand_token_list(['s', 'n', 'summary'])
            ['show', 'neighbor', 'summary']
        """
        expanded: list[str] = []

        for pos, token in enumerate(tokens):
            # Try to match against shortcuts
            matched = False
            for nickname, full_name, match_condition in cls.SHORTCUTS:
                # Check if token matches:
                # 1. Exact nickname match (e.g., 'r' == 'r')
                # 2. Exact full_name match (e.g., 'route' == 'route')
                # 3. Prefix match for short tokens only (e.g., 'ro' matches 'route')
                #    This prevents 'route' from matching 'router-id'
                is_match = token == nickname or token == full_name or (len(token) <= 2 and full_name.startswith(token))
                if is_match and match_condition(pos, expanded):
                    expanded.append(full_name)
                    matched = True
                    break

            # If no shortcut matched, use the token as-is
            if not matched:
                expanded.append(token)

        return expanded

    @classmethod
    def get_expansion(cls, token: str, position: int, previous_tokens: list[str]) -> str:
        """Get the expansion for a single token in context.

        Args:
            token: The token to expand
            position: Position in command (0-indexed)
            previous_tokens: Previously expanded tokens

        Returns:
            Expanded token or original if no match

        Examples:
            >>> CommandShortcuts.get_expansion('s', 0, [])
            'show'
            >>> CommandShortcuts.get_expansion('a', 1, ['show'])
            'adj-rib'
            >>> CommandShortcuts.get_expansion('a', 0, [])
            'announce'
        """
        for nickname, full_name, match_condition in cls.SHORTCUTS:
            is_match = token == nickname or token == full_name or (len(token) <= 2 and full_name.startswith(token))
            if is_match and match_condition(position, previous_tokens):
                return full_name
        return token

    @classmethod
    def get_possible_expansions(cls, token: str, position: int, previous_tokens: list[str]) -> list[str]:
        """Get all possible expansions for a token in context.

        Useful for showing ambiguous shortcuts.

        Args:
            token: The token to expand
            position: Position in command (0-indexed)
            previous_tokens: Previously expanded tokens

        Returns:
            List of possible expansions

        Examples:
            >>> CommandShortcuts.get_possible_expansions('a', 0, [])
            ['announce']
            >>> CommandShortcuts.get_possible_expansions('a', 1, ['show'])
            ['adj-rib']
        """
        expansions = []
        for nickname, full_name, match_condition in cls.SHORTCUTS:
            is_match = token == nickname or token == full_name or (len(token) <= 2 and full_name.startswith(token))
            if is_match and match_condition(position, previous_tokens):
                if full_name not in expansions:
                    expansions.append(full_name)
        return expansions

    @classmethod
    def transform_cli_to_api(cls, command: str) -> str:
        """Transform CLI-friendly syntax to API-compatible syntax.

        Transforms:
        - 'neighbor <ip> show ...' → 'show neighbor <ip> ...'
        - 'adj-rib <in|out> show ...' → 'show adj-rib <in|out> ...'

        The CLI accepts more intuitive command-first syntax, but the API
        expects 'show'-first syntax. This transformation maintains API compatibility
        while improving CLI usability.

        Args:
            command: The command string after shortcut expansion

        Returns:
            Transformed command string

        Examples:
            >>> CommandShortcuts.transform_cli_to_api('neighbor 192.168.1.1 show summary')
            'show neighbor 192.168.1.1 summary'
            >>> CommandShortcuts.transform_cli_to_api('adj-rib in show extensive')
            'show adj-rib in extensive'
            >>> CommandShortcuts.transform_cli_to_api('show neighbor summary')
            'show neighbor summary'
        """
        tokens = command.split()
        if not tokens:
            return command

        # Pattern 1 (most specific): neighbor <ip> adj-rib <in|out> show [options...]
        # Transform to: show adj-rib <in|out> <ip> [options...]
        # Check this FIRST before general "neighbor <ip> show" pattern
        if len(tokens) >= 5 and tokens[0] == 'neighbor' and tokens[2] == 'adj-rib' and tokens[3] in ('in', 'out'):
            try:
                show_idx = tokens.index('show')
                if show_idx == 4:  # Must be 'neighbor <ip> adj-rib <in|out> show'
                    # Extract parts: ['neighbor', <ip>, 'adj-rib', 'in'/'out', 'show', [options...]]
                    neighbor_ip = tokens[1]
                    direction = tokens[3]  # 'in' or 'out'
                    options = tokens[show_idx + 1 :]  # Everything after 'show'

                    # Rebuild: 'show adj-rib <in|out> <ip> [options...]'
                    result = ['show', 'adj-rib', direction, neighbor_ip] + options
                    return ' '.join(result)
            except ValueError:
                # 'show' not in tokens, return unchanged
                pass

        # Pattern 2: neighbor <ip> [filters...] show [options...]
        # Transform to: show neighbor <ip> [filters...] [options...]
        if len(tokens) >= 3 and tokens[0] == 'neighbor':
            try:
                show_idx = tokens.index('show')
                if show_idx >= 2:  # Must have at least 'neighbor <ip> show'
                    # Extract parts: ['neighbor', <ip>, [filters...], 'show', [options...]]
                    neighbor_and_filters = tokens[1:show_idx]  # <ip> and any filters
                    options = tokens[show_idx + 1 :]  # Everything after 'show'

                    # Rebuild: 'show neighbor <ip> [filters...] [options...]'
                    result = ['show', 'neighbor'] + neighbor_and_filters + options
                    return ' '.join(result)
            except ValueError:
                # 'show' not in tokens, return unchanged
                pass

        # Pattern 3: adj-rib <in|out> show [options...]
        # Transform to: show adj-rib <in|out> [options...]
        if len(tokens) >= 3 and tokens[0] == 'adj-rib' and tokens[1] in ('in', 'out'):
            try:
                show_idx = tokens.index('show')
                if show_idx == 2:  # Must be 'adj-rib <in|out> show'
                    # Extract parts: ['adj-rib', 'in'/'out', 'show', [options...]]
                    direction = tokens[1]  # 'in' or 'out'
                    options = tokens[show_idx + 1 :]  # Everything after 'show'

                    # Rebuild: 'show adj-rib <in|out> [options...]'
                    result = ['show', 'adj-rib', direction] + options
                    return ' '.join(result)
            except ValueError:
                # 'show' not in tokens, return unchanged
                pass

        return command


# Convenience function for backward compatibility
def expand_shortcuts(command: str) -> str:
    """Expand shortcuts in a command string.

    Args:
        command: The command string to process

    Returns:
        Expanded command string
    """
    return CommandShortcuts.expand_shortcuts(command)
