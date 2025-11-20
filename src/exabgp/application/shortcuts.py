"""shortcuts.py

Shared command shortcut/nickname expansion logic for ExaBGP CLI.

Created on 2025-11-20.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import List, Tuple, Callable

from exabgp.protocol.ip import IPv4


# Type for shortcut matching function
ShortcutMatcher = Callable[[int, List[str]], bool]


class CommandShortcuts:
    """Handles command shortcut expansion for CLI."""

    # Shortcut definitions: (nickname, full_name, match_condition)
    # Match condition is a function: (position: int, previous_tokens: list) -> bool
    SHORTCUTS: List[Tuple[str, str, ShortcutMatcher]] = [
        # 'a' has multiple meanings based on context
        ('a', 'announce', lambda pos, pre: pos == 0 or pre[-1].count('.') == IPv4.DOT_COUNT or ':' in pre[-1]),
        ('a', 'attributes', lambda pos, pre: pre and (pre[-1] == 'announce' or pre[-1] == 'withdraw')),
        ('a', 'adj-rib', lambda pos, pre: pre and pre[-1] in ['clear', 'flush', 'show']),
        # Other single-letter shortcuts
        ('c', 'configuration', lambda pos, pre: True),
        ('e', 'eor', lambda pos, pre: pre and pre[-1] == 'announce'),
        ('e', 'extensive', lambda pos, pre: 'show' in pre),
        ('f', 'flow', lambda pos, pre: pre and (pre[-1] == 'announce' or pre[-1] == 'withdraw')),
        ('f', 'flush', lambda pos, pre: pos == 0 or pre[-1].count('.') == IPv4.DOT_COUNT or ':' in pre[-1]),
        ('h', 'help', lambda pos, pre: pos == 0),
        ('i', 'in', lambda pos, pre: pre and pre[-1] == 'adj-rib'),
        ('n', 'neighbor', lambda pos, pre: pos == 0 or (pre and pre[-1] == 'show')),
        ('o', 'operation', lambda pos, pre: pre and pre[-1] == 'announce'),
        ('o', 'out', lambda pos, pre: pre and pre[-1] == 'adj-rib'),
        ('r', 'route', lambda pos, pre: pre and (pre[-1] == 'announce' or pre[-1] == 'withdraw')),
        ('rr', 'route-refresh', lambda pos, pre: pre and pre[-1] == 'announce'),
        ('s', 'show', lambda pos, pre: pos == 0),
        ('s', 'summary', lambda pos, pre: pos != 0),
        ('t', 'teardown', lambda pos, pre: pos == 0 or pre[-1].count('.') == IPv4.DOT_COUNT or ':' in pre[-1]),
        ('v', 'vps', lambda pos, pre: pre and (pre[-1] == 'announce' or pre[-1] == 'withdraw')),
        ('w', 'withdraw', lambda pos, pre: pos == 0 or pre[-1].count('.') == IPv4.DOT_COUNT or ':' in pre[-1]),
        ('w', 'watchdog', lambda pos, pre: pre and (pre[-1] == 'announce' or pre[-1] == 'withdraw')),
        # Multi-letter shortcuts
        ('rr', 'route-refresh', lambda pos, pre: pre and pre[-1] == 'announce'),
        # Common typos
        ('neighbour', 'neighbor', lambda pos, pre: True),
        ('neigbour', 'neighbor', lambda pos, pre: True),
        ('neigbor', 'neighbor', lambda pos, pre: True),
    ]

    @classmethod
    def expand_shortcuts(cls, command: str) -> str:
        """Expand shortcuts in a command string.

        Args:
            command: The command string to process (e.g., "s n summary")

        Returns:
            Expanded command string (e.g., "show neighbor summary")

        Examples:
            >>> CommandShortcuts.expand_shortcuts('s n summary')
            'show neighbor summary'
            >>> CommandShortcuts.expand_shortcuts('a r 10.0.0.0/24 next-hop 192.168.1.1')
            'announce route 10.0.0.0/24 next-hop 192.168.1.1'
        """
        tokens = command.split()
        if not tokens:
            return command

        expanded = cls.expand_token_list(tokens)
        return ' '.join(expanded).strip()

    @classmethod
    def expand_token_list(cls, tokens: List[str]) -> List[str]:
        """Expand shortcuts in a list of tokens.

        Args:
            tokens: List of command tokens

        Returns:
            List of expanded tokens

        Examples:
            >>> CommandShortcuts.expand_token_list(['s', 'n', 'summary'])
            ['show', 'neighbor', 'summary']
        """
        expanded = []

        for pos, token in enumerate(tokens):
            # Try to match against shortcuts
            matched = False
            for nickname, full_name, match_condition in cls.SHORTCUTS:
                # Check if token matches nickname exactly or starts with full_name
                if (token == nickname or full_name.startswith(token)) and match_condition(pos, expanded):
                    expanded.append(full_name)
                    matched = True
                    break

            # If no shortcut matched, use the token as-is
            if not matched:
                expanded.append(token)

        return expanded

    @classmethod
    def get_expansion(cls, token: str, position: int, previous_tokens: List[str]) -> str:
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
            if (token == nickname or full_name.startswith(token)) and match_condition(position, previous_tokens):
                return full_name
        return token

    @classmethod
    def get_possible_expansions(cls, token: str, position: int, previous_tokens: List[str]) -> List[str]:
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
            if (token == nickname or full_name.startswith(token)) and match_condition(position, previous_tokens):
                if full_name not in expansions:
                    expansions.append(full_name)
        return expansions


# Convenience function for backward compatibility
def expand_shortcuts(command: str) -> str:
    """Expand shortcuts in a command string.

    Args:
        command: The command string to process

    Returns:
        Expanded command string
    """
    return CommandShortcuts.expand_shortcuts(command)
