"""dispatch/common.py

Shared types, exceptions, and command metadata for v4/v6 API dispatchers.

Created on 2025-12-05.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from exabgp.reactor.api import API
    from exabgp.reactor.loop import Reactor


# Handler signature: (api, reactor, service, peers, command, use_json) -> bool
# - api: API instance
# - reactor: Reactor instance
# - service: service name for responses
# - peers: list of matching peer names (empty for non-neighbor commands)
# - command: remaining command after action prefix and selectors stripped
# - use_json: whether to output JSON format
Handler = Callable[['API', 'Reactor', str, list[str], str, bool], bool]


class UnknownCommand(Exception):
    """Raised when a command cannot be dispatched."""

    pass


class NoMatchingPeers(Exception):
    """Raised when neighbor_support=True but no peers match the selector."""

    pass


class InvalidCommand(Exception):
    """Raised when the command syntax is invalid"""

    pass


# Command metadata for help display
# Format: (v6_command, neighbor_support, options)
# - v6_command: The v6 format command string
# - neighbor_support: Whether the command supports peer/neighbor prefix
# - options: Optional list of sub-options for the command
COMMANDS: list[tuple[str, bool, list[str] | None]] = [
    # Daemon control
    ('daemon shutdown', False, None),
    ('daemon reload', False, None),
    ('daemon restart', False, None),
    ('daemon status', False, None),
    # Session management
    ('session ack enable', False, None),
    ('session ack disable', False, None),
    ('session ack silence', False, None),
    ('session sync enable', False, None),
    ('session sync disable', False, None),
    ('session reset', False, None),
    ('session ping', False, None),
    ('session bye', False, None),
    # System commands
    ('system help', False, None),
    ('system version', False, None),
    ('system crash', True, None),
    ('system queue-status', False, None),
    ('system api version', False, ['4', '6']),
    # Comment
    ('#', False, None),
    # RIB operations
    ('rib show in', False, ['extensive']),
    ('rib show out', False, ['extensive']),
    ('rib flush out', True, None),
    ('rib clear in', True, None),
    ('rib clear out', True, None),
    # Peer operations
    ('peer list', False, None),
    ('peer show', False, ['summary', 'extensive', 'configuration']),
    ('peer teardown', True, None),
    ('peer create', False, None),
    ('peer delete', False, None),
    # Announce commands
    ('peer announce route', True, None),
    ('peer announce route-refresh', True, None),
    ('peer announce ipv4', True, None),
    ('peer announce ipv6', True, None),
    ('peer announce flow', True, None),
    ('peer announce eor', True, None),
    ('peer announce watchdog', True, None),
    ('peer announce attribute', True, None),
    ('peer announce attributes', True, None),
    ('peer announce operational', True, None),
    ('peer announce vpls', True, None),
    # Withdraw commands
    ('peer withdraw route', True, None),
    ('peer withdraw ipv4', True, None),
    ('peer withdraw ipv6', True, None),
    ('peer withdraw flow', True, None),
    ('peer withdraw watchdog', True, None),
    ('peer withdraw attribute', True, None),
    ('peer withdraw attributes', True, None),
    ('peer withdraw vpls', True, None),
]


def get_commands() -> list[tuple[str, bool, list[str] | None]]:
    """Return the list of available commands with metadata.

    Returns list of (command, neighbor_support, options) tuples.
    """
    return COMMANDS
