"""dispatch/v4.py

Dispatcher for v4 format API commands.

v4 format: action-first syntax
- shutdown
- announce route 10.0.0.0/24 next-hop 1.2.3.4
- neighbor 192.168.1.1 announce route ...
- show adj-rib in

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


def dispatch_v4(
    command: str,
    reactor: 'Reactor',
    service: str,
) -> tuple[Handler, list[str], str]:
    """Dispatch v4 format command.

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
    # Import handlers lazily to avoid circular imports
    from exabgp.reactor.api.command import reactor as reactor_cmd
    from exabgp.reactor.api.command import neighbor as neighbor_cmd
    from exabgp.reactor.api.command import peer as peer_cmd
    from exabgp.reactor.api.command import announce as announce_cmd
    from exabgp.reactor.api.command import rib as rib_cmd
    from exabgp.reactor.api.command import watchdog as watchdog_cmd

    command = command.strip()

    # Empty command or comment
    if not command or command.startswith('#'):
        return reactor_cmd.comment, [], command

    # Commands already in v6 format - delegate to v6 dispatcher
    if command.startswith(('daemon ', 'session ', 'system ', 'rib ', 'peer ')):
        from exabgp.reactor.api.dispatch.v6 import dispatch_v6

        return dispatch_v6(command, reactor, service)

    parts = command.split()
    if not parts:
        return reactor_cmd.comment, [], command

    first = parts[0]

    # === Daemon control (v4 single-word) ===
    if first == 'shutdown':
        return reactor_cmd.shutdown, [], ' '.join(parts[1:])
    if first == 'reload':
        return reactor_cmd.reload, [], ' '.join(parts[1:])
    if first == 'restart':
        return reactor_cmd.restart, [], ' '.join(parts[1:])
    if first == 'status':
        return reactor_cmd.status, [], ' '.join(parts[1:])

    # === Session management (v4 hyphenated) ===
    if first == 'enable-ack':
        return reactor_cmd.enable_ack, [], ' '.join(parts[1:])
    if first == 'disable-ack':
        return reactor_cmd.disable_ack, [], ' '.join(parts[1:])
    if first == 'silence-ack':
        return reactor_cmd.silence_ack, [], ' '.join(parts[1:])
    if first == 'enable-sync':
        return reactor_cmd.enable_sync, [], ' '.join(parts[1:])
    if first == 'disable-sync':
        return reactor_cmd.disable_sync, [], ' '.join(parts[1:])
    if first == 'reset':
        return reactor_cmd.reset, [], ' '.join(parts[1:])
    if first == 'ping':
        return reactor_cmd.ping, [], ' '.join(parts[1:])
    if first == 'bye':
        return reactor_cmd.bye, [], ' '.join(parts[1:])

    # === System commands ===
    if first == 'help':
        return reactor_cmd.help_command, [], ' '.join(parts[1:])
    if first == 'version':
        return reactor_cmd.version, [], ' '.join(parts[1:])
    if first == 'crash':
        return reactor_cmd.crash, [], ' '.join(parts[1:])
    if first == 'queue-status':
        return reactor_cmd.queue_status, [], ' '.join(parts[1:])
    if first == 'api':
        # api version [4|6]
        if len(parts) >= 2 and parts[1] == 'version':
            return reactor_cmd.api_version_cmd, [], ' '.join(parts[2:])
        raise UnknownCommand(command)

    # === RIB operations ===
    if first == 'show':
        if len(parts) >= 2:
            if parts[1] == 'adj-rib':
                if len(parts) >= 3 and parts[2] in ('in', 'out'):
                    direction = parts[2]
                    remaining = ' '.join(parts[3:])
                    return rib_cmd.show_adj_rib, [], f'{direction} {remaining}'.strip()
            if parts[1] == 'neighbor':
                remaining = ' '.join(parts[2:])
                return neighbor_cmd.show_neighbor, [], remaining
        raise UnknownCommand(command)

    if first == 'flush':
        if len(parts) >= 3 and parts[1] == 'adj-rib' and parts[2] == 'out':
            peers = list(reactor.peers(service))
            if not peers:
                raise NoMatchingPeers(command)
            remaining = ' '.join(parts[3:])
            return rib_cmd.flush_adj_rib_out, peers, remaining
        raise UnknownCommand(command)

    if first == 'clear':
        if len(parts) >= 3 and parts[1] == 'adj-rib' and parts[2] in ('in', 'out'):
            peers = list(reactor.peers(service))
            if not peers:
                raise NoMatchingPeers(command)
            direction = parts[2]
            remaining = ' '.join(parts[3:])
            return rib_cmd.clear_adj_rib, peers, f'{direction} {remaining}'.strip()
        raise UnknownCommand(command)

    # === Peer management ===
    if first == 'create':
        if len(parts) >= 2 and parts[1] == 'neighbor':
            remaining = ' '.join(parts[2:])
            return peer_cmd.neighbor_create, [], remaining
        raise UnknownCommand(command)

    if first == 'delete':
        if len(parts) >= 2 and parts[1] == 'neighbor':
            # Extract selector and match peers
            # Convert to neighbor format for extract_neighbors
            selector_cmd = 'neighbor ' + ' '.join(parts[2:])
            descriptions, remaining = extract_neighbors(selector_cmd)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                raise NoMatchingPeers(command)
            return peer_cmd.peer_delete, peers, remaining
        raise UnknownCommand(command)

    if first == 'teardown':
        # v4: teardown <code> (affects all peers)
        peers = list(reactor.peers(service))
        if not peers:
            raise NoMatchingPeers(command)
        remaining = ' '.join(parts[1:])
        return neighbor_cmd.teardown, peers, remaining

    # === Announce (wildcard - all peers) ===
    if first == 'announce':
        if len(parts) >= 2 and parts[1] in ANNOUNCE_SUBCOMMANDS:
            peers = list(reactor.peers(service))
            if not peers:
                raise NoMatchingPeers(command)
            return _dispatch_announce_v4(command, parts, peers, announce_cmd, watchdog_cmd)
        raise UnknownCommand(command)

    # === Withdraw (wildcard - all peers) ===
    if first == 'withdraw':
        if len(parts) >= 2 and parts[1] in WITHDRAW_SUBCOMMANDS:
            peers = list(reactor.peers(service))
            if not peers:
                raise NoMatchingPeers(command)
            return _dispatch_withdraw_v4(command, parts, peers, announce_cmd, watchdog_cmd)
        raise UnknownCommand(command)

    # === Neighbor-prefixed commands ===
    if first == 'neighbor':
        return _dispatch_neighbor_v4(command, parts, reactor, service, neighbor_cmd, announce_cmd, watchdog_cmd)

    raise UnknownCommand(command)


def _dispatch_neighbor_v4(
    command: str,
    parts: list[str],
    reactor: 'Reactor',
    service: str,
    neighbor_cmd,
    announce_cmd,
    watchdog_cmd,
) -> tuple[Handler, list[str], str]:
    """Dispatch neighbor-prefixed v4 commands.

    Format: neighbor <ip> [selector-key value]... <action> [args...]
    """
    # Use extract_neighbors to parse selector and get remaining command
    descriptions, remaining = extract_neighbors(command)
    peers = match_neighbors(reactor.peers(service), descriptions)

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
        # remaining_parts: ['announce', '<type>', ...]
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
