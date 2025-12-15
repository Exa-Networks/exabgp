"""dispatch/v4.py

Dispatcher for v4 format API commands.

v4 format: action-first syntax
- shutdown
- announce route 10.0.0.0/24 next-hop 1.2.3.4
- neighbor 192.168.1.1 announce route ...
- show adj-rib in

This module translates v4 commands to v6 format and delegates to dispatch_v6().
For neighbor-prefixed commands, it uses the original dispatch logic to handle
legacy comma-separated selector syntax properly.

Created on 2025-12-05.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from exabgp.reactor.api.dispatch.common import Handler, UnknownCommand, NoMatchingPeers
from exabgp.reactor.api.command.limit import extract_neighbors, match_neighbors

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor


# Translation table for simple v4 commands → v6 prefix
# Format: v4_keyword → v6_prefix (remaining args appended)
V4_SIMPLE_TRANSLATIONS: dict[str, str] = {
    # Daemon commands
    'shutdown': 'daemon shutdown',
    'reload': 'daemon reload',
    'restart': 'daemon restart',
    'status': 'daemon status',
    # Session commands (hyphenated → nested)
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
}

# Valid announce subcommands in v4
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

# Valid withdraw subcommands in v4
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


def translate_v4_to_v6(command: str) -> str | None:
    """Translate v4 command to v6 format.

    Note: Does NOT handle neighbor-prefixed commands due to legacy
    comma-separated selector syntax. Those use direct dispatch.

    Args:
        command: The v4 format command string

    Returns:
        Translated v6 format command, or None if no translation needed/possible
    """
    parts = command.split()
    if not parts:
        return None

    first = parts[0]
    rest = ' '.join(parts[1:])

    # Simple translations (single keyword → prefix)
    if first in V4_SIMPLE_TRANSLATIONS:
        v6_prefix = V4_SIMPLE_TRANSLATIONS[first]
        return f'{v6_prefix} {rest}'.strip()

    # api version X → system api version X
    if first == 'api' and len(parts) >= 2 and parts[1] == 'version':
        return f'system api version {" ".join(parts[2:])}'.strip()

    # show adj-rib in/out → rib show in/out
    if first == 'show':
        if len(parts) >= 3 and parts[1] == 'adj-rib' and parts[2] in ('in', 'out'):
            direction = parts[2]
            remaining = ' '.join(parts[3:])
            return f'rib show {direction} {remaining}'.strip()
        if len(parts) >= 2 and parts[1] == 'neighbor':
            remaining = ' '.join(parts[2:])
            return f'peer show {remaining}'.strip()
        return None

    # flush adj-rib out → rib flush out
    if first == 'flush':
        if len(parts) >= 3 and parts[1] == 'adj-rib' and parts[2] == 'out':
            remaining = ' '.join(parts[3:])
            return f'rib flush out {remaining}'.strip()
        return None

    # clear adj-rib in/out → rib clear in/out
    if first == 'clear':
        if len(parts) >= 3 and parts[1] == 'adj-rib' and parts[2] in ('in', 'out'):
            direction = parts[2]
            remaining = ' '.join(parts[3:])
            return f'rib clear {direction} {remaining}'.strip()
        return None

    # create neighbor X → peer create X
    if first == 'create' and len(parts) >= 2 and parts[1] == 'neighbor':
        remaining = ' '.join(parts[2:])
        return f'peer create {remaining}'.strip()

    # delete neighbor <selector> → peer delete <selector>
    if first == 'delete' and len(parts) >= 2 and parts[1] == 'neighbor':
        remaining = ' '.join(parts[2:])
        return f'peer delete {remaining}'.strip()

    # teardown X → peer * teardown X (affects all peers)
    if first == 'teardown':
        return f'peer * teardown {rest}'.strip()

    # announce <type> ... → peer * announce <type> ...
    if first == 'announce':
        return f'peer * announce {rest}'.strip()

    # withdraw <type> ... → peer * withdraw <type> ...
    if first == 'withdraw':
        return f'peer * withdraw {rest}'.strip()

    # neighbor commands are NOT translated - they use direct dispatch
    # to handle legacy comma-separated selector syntax

    return None


def dispatch_v4(
    command: str,
    reactor: 'Reactor',
    service: str,
) -> tuple[Handler, list[str], str]:
    """Dispatch v4 format command.

    Most commands are translated to v6 format and delegated.
    Neighbor-prefixed commands use direct dispatch to handle
    legacy comma-separated selector syntax properly.

    Args:
        command: The v4 format command string
        reactor: Reactor instance for peer lookup
        service: Service name for peer filtering

    Returns:
        Tuple of (handler, peers, remaining_command)
        - handler: The function to call
        - peers: List of matching peer names (empty for non-neighbor commands)
        - remaining_command: Command with action prefix and selectors stripped

    Raises:
        UnknownCommand: If the command cannot be routed
        NoMatchingPeers: If neighbor_support=True but no peers match
    """
    from exabgp.reactor.api.dispatch.v6 import dispatch_v6

    command = command.strip()

    # Empty command or comment - delegate directly
    if not command or command.startswith('#'):
        return dispatch_v6(command, reactor, service)

    parts = command.split()
    first = parts[0] if parts else ''

    # Commands already in v6 format - delegate directly
    if first in ('daemon', 'session', 'system', 'rib', 'peer'):
        return dispatch_v6(command, reactor, service)

    # Neighbor-prefixed commands use direct dispatch
    # to handle legacy comma-separated selector syntax
    if first == 'neighbor':
        return _dispatch_neighbor_v4(command, reactor, service)

    # Try to translate v4 → v6
    v6_command = translate_v4_to_v6(command)
    if v6_command is not None:
        return dispatch_v6(v6_command, reactor, service)

    # No translation found
    raise UnknownCommand(command)


def _dispatch_neighbor_v4(
    command: str,
    reactor: 'Reactor',
    service: str,
) -> tuple[Handler, list[str], str]:
    """Dispatch neighbor-prefixed v4 commands.

    Uses original dispatch logic with extract_neighbors/match_neighbors
    to handle legacy comma-separated selector syntax properly.

    Format: neighbor <ip> [selector-key value]... <action> [args...]
    """
    from exabgp.reactor.api.command import announce as announce_cmd
    from exabgp.reactor.api.command import neighbor as neighbor_cmd
    from exabgp.reactor.api.command import watchdog as watchdog_cmd

    # Use extract_neighbors to parse selector and get remaining command
    descriptions, remaining = extract_neighbors(command)
    peers = list(match_neighbors(reactor.peers(service), descriptions))

    remaining_parts = remaining.split()
    if not remaining_parts:
        raise UnknownCommand(command)

    action = remaining_parts[0]
    action_args = ' '.join(remaining_parts[1:])

    if action == 'teardown':
        if not peers:
            raise NoMatchingPeers(command)
        return neighbor_cmd.teardown, peers, action_args

    if action == 'announce':
        if not peers:
            raise NoMatchingPeers(command)
        return _dispatch_announce_v4(command, remaining_parts, peers, announce_cmd, watchdog_cmd)

    if action == 'withdraw':
        if not peers:
            raise NoMatchingPeers(command)
        return _dispatch_withdraw_v4(command, remaining_parts, peers, announce_cmd, watchdog_cmd)

    raise UnknownCommand(command)


def _dispatch_announce_v4(
    command: str,
    parts: list[str],
    peers: list[str],
    announce_cmd,
    watchdog_cmd,
) -> tuple[Handler, list[str], str]:
    """Dispatch announce subcommand (v4).

    parts: ['announce', '<type>', ...]
    """
    if len(parts) < 2:
        raise UnknownCommand(command)

    announce_type = parts[1]
    remaining = ' '.join(parts[2:])

    if announce_type not in ANNOUNCE_SUBCOMMANDS:
        raise UnknownCommand(command)

    # Note: api_* methods expect full "announce <type> ..." format
    if announce_type == 'route':
        return announce_cmd.announce_route, peers, f'announce route {remaining}'.strip()
    if announce_type == 'route-refresh':
        return announce_cmd.announce_refresh, peers, f'announce route-refresh {remaining}'.strip()
    if announce_type == 'ipv4':
        return announce_cmd.announce_ipv4, peers, f'announce ipv4 {remaining}'.strip()
    if announce_type == 'ipv6':
        return announce_cmd.announce_ipv6, peers, f'announce ipv6 {remaining}'.strip()
    if announce_type == 'flow':
        return announce_cmd.announce_flow, peers, f'announce flow {remaining}'.strip()
    if announce_type == 'eor':
        return announce_cmd.announce_eor, peers, f'announce eor {remaining}'.strip()
    if announce_type == 'watchdog':
        return watchdog_cmd.announce_watchdog, peers, f'announce watchdog {remaining}'.strip()
    if announce_type in ('attribute', 'attributes'):
        return announce_cmd.announce_attributes, peers, f'announce {announce_type} {remaining}'.strip()
    if announce_type == 'operational':
        return announce_cmd.announce_operational, peers, f'announce operational {remaining}'.strip()
    if announce_type == 'vpls':
        return announce_cmd.announce_vpls, peers, f'announce vpls {remaining}'.strip()

    raise UnknownCommand(command)


def _dispatch_withdraw_v4(
    command: str,
    parts: list[str],
    peers: list[str],
    announce_cmd,
    watchdog_cmd,
) -> tuple[Handler, list[str], str]:
    """Dispatch withdraw subcommand (v4).

    parts: ['withdraw', '<type>', ...]
    """
    if len(parts) < 2:
        raise UnknownCommand(command)

    withdraw_type = parts[1]
    remaining = ' '.join(parts[2:])

    if withdraw_type not in WITHDRAW_SUBCOMMANDS:
        raise UnknownCommand(command)

    # Note: api_* methods expect full "withdraw <type> ..." format
    if withdraw_type == 'route':
        return announce_cmd.withdraw_route, peers, f'withdraw route {remaining}'.strip()
    if withdraw_type == 'ipv4':
        return announce_cmd.withdraw_ipv4, peers, f'withdraw ipv4 {remaining}'.strip()
    if withdraw_type == 'ipv6':
        return announce_cmd.withdraw_ipv6, peers, f'withdraw ipv6 {remaining}'.strip()
    if withdraw_type == 'flow':
        return announce_cmd.withdraw_flow, peers, f'withdraw flow {remaining}'.strip()
    if withdraw_type == 'watchdog':
        return watchdog_cmd.withdraw_watchdog, peers, f'withdraw watchdog {remaining}'.strip()
    if withdraw_type in ('attribute', 'attributes'):
        return announce_cmd.withdraw_attribute, peers, f'withdraw {withdraw_type} {remaining}'.strip()
    if withdraw_type == 'vpls':
        return announce_cmd.withdraw_vpls, peers, f'withdraw vpls {remaining}'.strip()

    raise UnknownCommand(command)
