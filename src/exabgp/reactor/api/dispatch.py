"""dispatch.py

Explicit command dispatch for v6 API commands.

All commands arrive in v6 format (v4 commands are transformed before dispatch).
This module provides fast, explicit routing based on command prefixes.

Created on 2025-12-05.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor
    from exabgp.reactor.api import API

# Type alias for command handlers
# Handler signature: (api: API, reactor: Reactor, service: str, line: str, use_json: bool) -> bool
Handler = Callable[['API', 'Reactor', str, str, bool], bool]


class UnknownCommand(Exception):
    """Raised when a command cannot be dispatched."""

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
    ('peer list', False, None),  # List all peers
    ('peer show', False, ['summary', 'extensive', 'configuration']),  # peer <ip> show
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


def dispatch(command: str) -> tuple[Handler, bool]:
    """Route a v6 command to its handler.

    Args:
        command: The v6 format command string

    Returns:
        Tuple of (handler_function, neighbor_support)
        - handler_function: The function to call
        - neighbor_support: Whether the command supports neighbor prefix

    Raises:
        UnknownCommand: If the command cannot be routed

    All commands are in v6 format:
    - daemon shutdown/reload/restart/status
    - session ack enable/disable/silence, sync enable/disable, reset, ping, bye
    - system help/version/crash/queue-status/api version
    - rib show/flush/clear in/out
    - peer show/teardown/create/delete/announce/withdraw
    - # (comment)
    """
    # Import handlers lazily to avoid circular imports
    from exabgp.reactor.api.command import reactor as reactor_cmd
    from exabgp.reactor.api.command import neighbor as neighbor_cmd
    from exabgp.reactor.api.command import peer as peer_cmd
    from exabgp.reactor.api.command import announce as announce_cmd
    from exabgp.reactor.api.command import rib as rib_cmd
    from exabgp.reactor.api.command import watchdog as watchdog_cmd

    # Comment - always handle
    if command.startswith('#'):
        return reactor_cmd.comment, False

    # Split command for prefix matching
    parts = command.split()
    if not parts:
        raise UnknownCommand(command)

    prefix = parts[0]

    # === Daemon commands ===
    if prefix == 'daemon':
        if len(parts) < 2:
            raise UnknownCommand(command)
        action = parts[1]
        if action == 'shutdown':
            return reactor_cmd.shutdown, False
        if action == 'reload':
            return reactor_cmd.reload, False
        if action == 'restart':
            return reactor_cmd.restart, False
        if action == 'status':
            return reactor_cmd.status, False
        raise UnknownCommand(command)

    # === Session commands ===
    if prefix == 'session':
        if len(parts) < 2:
            raise UnknownCommand(command)
        action = parts[1]
        if action == 'ack':
            if len(parts) < 3:
                raise UnknownCommand(command)
            sub = parts[2]
            if sub == 'enable':
                return reactor_cmd.enable_ack, False
            if sub == 'disable':
                return reactor_cmd.disable_ack, False
            if sub == 'silence':
                return reactor_cmd.silence_ack, False
            raise UnknownCommand(command)
        if action == 'sync':
            if len(parts) < 3:
                raise UnknownCommand(command)
            sub = parts[2]
            if sub == 'enable':
                return reactor_cmd.enable_sync, False
            if sub == 'disable':
                return reactor_cmd.disable_sync, False
            raise UnknownCommand(command)
        if action == 'reset':
            return reactor_cmd.reset, False
        if action == 'ping':
            return reactor_cmd.ping, False
        if action == 'bye':
            return reactor_cmd.bye, False
        raise UnknownCommand(command)

    # === System commands ===
    if prefix == 'system':
        if len(parts) < 2:
            raise UnknownCommand(command)
        action = parts[1]
        if action == 'help':
            return reactor_cmd.help_command, False
        if action == 'version':
            return reactor_cmd.version, False
        if action == 'crash':
            return reactor_cmd.crash, True  # neighbor=True in original
        if action == 'queue-status':
            return reactor_cmd.queue_status, False
        if action == 'api':
            # system api version
            return reactor_cmd.api_version_cmd, False
        raise UnknownCommand(command)

    # === RIB commands ===
    if prefix == 'rib':
        if len(parts) < 3:
            raise UnknownCommand(command)
        action = parts[1]
        direction = parts[2]
        if action == 'show':
            if direction in ('in', 'out'):
                return rib_cmd.show_adj_rib, False
            raise UnknownCommand(command)
        if action == 'flush':
            if direction == 'out':
                return rib_cmd.flush_adj_rib_out, True
            raise UnknownCommand(command)
        if action == 'clear':
            return rib_cmd.clear_adj_rib, True
        raise UnknownCommand(command)

    # === Peer commands ===
    if prefix == 'peer':
        # peer show/teardown/create/delete/announce/withdraw
        # May have selector: peer <ip> [selectors] action
        # Or wildcard: peer * action
        # Or bracket: peer [...] action
        return _dispatch_peer_command(command, parts, neighbor_cmd, peer_cmd, announce_cmd, watchdog_cmd)

    raise UnknownCommand(command)


def _dispatch_peer_command(
    command: str,
    parts: list[str],
    neighbor_cmd,
    peer_cmd,
    announce_cmd,
    watchdog_cmd,
) -> tuple[Handler, bool]:
    """Dispatch peer-prefixed commands.

    Handles:
    - peer list - list all peers
    - peer <ip> show [summary|extensive|configuration] - show specific peer
    - peer [ip|*|bracket] teardown
    - peer create <ip> { config }
    - peer delete <ip>
    - peer [ip|*|bracket] announce <type> ...
    - peer [ip|*|bracket] withdraw <type> ...
    """
    if len(parts) < 2:
        raise UnknownCommand(command)

    # Find the action word (list, show, teardown, create, delete, announce, withdraw)
    # It may be at parts[1], or later if there are selectors

    # Check for immediate action words at parts[1]
    action = parts[1]

    if action == 'list':
        # peer list - list all peers
        return neighbor_cmd.show_neighbor, False

    if action == 'show':
        # peer show - legacy format, kept for compatibility
        return neighbor_cmd.show_neighbor, False

    if action == 'create':
        return peer_cmd.neighbor_create, False

    if action == 'delete':
        return peer_cmd.peer_delete, False

    # For teardown/announce/withdraw, need to find the action in the command
    # Could be: peer * teardown, peer 10.0.0.1 teardown, peer [bracket] teardown

    # Check if action is '*' or an IP or '[' (bracket selector start)
    # Note: bracket may be attached to IP like '[127.0.0.1'
    if action in ('*',) or action.startswith('[') or _looks_like_ip(action):
        # Find the actual action word
        return _dispatch_peer_with_selector(command, parts, neighbor_cmd, announce_cmd, watchdog_cmd)

    # Direct action after peer
    if action == 'teardown':
        return neighbor_cmd.teardown, True

    if action == 'announce':
        return _dispatch_announce(command, parts, 2, announce_cmd, watchdog_cmd)

    if action == 'withdraw':
        return _dispatch_withdraw(command, parts, 2, announce_cmd, watchdog_cmd)

    raise UnknownCommand(command)


def _dispatch_peer_with_selector(
    command: str,
    parts: list[str],
    neighbor_cmd,
    announce_cmd,
    watchdog_cmd,
) -> tuple[Handler, bool]:
    """Dispatch peer command with selector (IP, *, or bracket)."""
    # Find action word by scanning for known actions
    action_idx = None
    for i, word in enumerate(parts[1:], start=1):
        if word in ('show', 'teardown', 'announce', 'withdraw'):
            action_idx = i
            break

    if action_idx is None:
        raise UnknownCommand(command)

    action = parts[action_idx]

    if action == 'show':
        # peer <ip> show [summary|extensive|configuration]
        return neighbor_cmd.show_neighbor, False

    if action == 'teardown':
        return neighbor_cmd.teardown, True

    if action == 'announce':
        return _dispatch_announce(command, parts, action_idx + 1, announce_cmd, watchdog_cmd)

    if action == 'withdraw':
        return _dispatch_withdraw(command, parts, action_idx + 1, announce_cmd, watchdog_cmd)

    raise UnknownCommand(command)


def _dispatch_announce(
    command: str,
    parts: list[str],
    type_idx: int,
    announce_cmd,
    watchdog_cmd,
) -> tuple[Handler, bool]:
    """Dispatch announce subcommand."""
    if type_idx >= len(parts):
        raise UnknownCommand(command)

    announce_type = parts[type_idx]

    if announce_type == 'route':
        return announce_cmd.announce_route, True
    if announce_type == 'route-refresh':
        return announce_cmd.announce_refresh, True
    if announce_type == 'ipv4':
        return announce_cmd.announce_ipv4, True
    if announce_type == 'ipv6':
        return announce_cmd.announce_ipv6, True
    if announce_type == 'flow':
        return announce_cmd.announce_flow, True
    if announce_type == 'eor':
        return announce_cmd.announce_eor, True
    if announce_type == 'watchdog':
        return watchdog_cmd.announce_watchdog, True
    if announce_type in ('attribute', 'attributes'):
        return announce_cmd.announce_attributes, True
    if announce_type == 'operational':
        return announce_cmd.announce_operational, True
    if announce_type == 'vpls':
        return announce_cmd.announce_vpls, True

    raise UnknownCommand(command)


def _dispatch_withdraw(
    command: str,
    parts: list[str],
    type_idx: int,
    announce_cmd,
    watchdog_cmd,
) -> tuple[Handler, bool]:
    """Dispatch withdraw subcommand."""
    if type_idx >= len(parts):
        raise UnknownCommand(command)

    withdraw_type = parts[type_idx]

    if withdraw_type == 'route':
        return announce_cmd.withdraw_route, True
    if withdraw_type == 'ipv4':
        return announce_cmd.withdraw_ipv4, True
    if withdraw_type == 'ipv6':
        return announce_cmd.withdraw_ipv6, True
    if withdraw_type == 'flow':
        return announce_cmd.withdraw_flow, True
    if withdraw_type == 'watchdog':
        return watchdog_cmd.withdraw_watchdog, True
    if withdraw_type in ('attribute', 'attributes'):
        return announce_cmd.withdraw_attribute, True
    if withdraw_type == 'vpls':
        return announce_cmd.withdraw_vpls, True

    raise UnknownCommand(command)


def _looks_like_ip(s: str) -> bool:
    """Check if string looks like an IP address."""
    # IPv4: contains dots
    if '.' in s and s[0].isdigit():
        return True
    # IPv6: contains colons
    if ':' in s:
        return True
    return False
