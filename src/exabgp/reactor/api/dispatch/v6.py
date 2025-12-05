"""dispatch/v6.py

Dispatcher for v6 format API commands.

v6 format: target-first syntax
- daemon shutdown
- session ack enable
- peer <selector> announce route ...
- rib show in

Created on 2025-12-05.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from exabgp.reactor.api.command.limit import extract_neighbors, match_neighbors
from exabgp.reactor.api.dispatch.common import Handler, InvalidCommand, NoMatchingPeers, UnknownCommand

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor


def dispatch_v6(
    command: str,
    reactor: 'Reactor',
    service: str,
) -> tuple[Handler, list[str], str]:
    """Dispatch v6 format command.

    Args:
        command: The v6 format command string
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
    from exabgp.reactor.api.command import announce as announce_cmd
    from exabgp.reactor.api.command import neighbor as neighbor_cmd
    from exabgp.reactor.api.command import peer as peer_cmd
    from exabgp.reactor.api.command import reactor as reactor_cmd
    from exabgp.reactor.api.command import rib as rib_cmd
    from exabgp.reactor.api.command import watchdog as watchdog_cmd

    # Comment - always handle
    if command.startswith('#'):
        return reactor_cmd.comment, [], command

    # Split command for prefix matching
    parts = command.split()
    if not parts:
        raise UnknownCommand(command)

    prefix = parts[0]

    # === Daemon commands (no neighbor support) ===
    if prefix == 'daemon':
        if len(parts) < 2:
            raise UnknownCommand(command)
        action = parts[1]
        remaining = ' '.join(parts[2:])
        if action == 'shutdown':
            return reactor_cmd.shutdown, [], remaining
        if action == 'reload':
            return reactor_cmd.reload, [], remaining
        if action == 'restart':
            return reactor_cmd.restart, [], remaining
        if action == 'status':
            return reactor_cmd.status, [], remaining
        raise UnknownCommand(command)

    # === Session commands (no neighbor support) ===
    if prefix == 'session':
        if len(parts) < 2:
            raise UnknownCommand(command)
        action = parts[1]
        if action == 'ack':
            if len(parts) < 3:
                raise UnknownCommand(command)
            sub = parts[2]
            remaining = ' '.join(parts[3:])
            if sub == 'enable':
                return reactor_cmd.enable_ack, [], remaining
            if sub == 'disable':
                return reactor_cmd.disable_ack, [], remaining
            if sub == 'silence':
                return reactor_cmd.silence_ack, [], remaining
            raise UnknownCommand(command)
        if action == 'sync':
            if len(parts) < 3:
                raise UnknownCommand(command)
            sub = parts[2]
            remaining = ' '.join(parts[3:])
            if sub == 'enable':
                return reactor_cmd.enable_sync, [], remaining
            if sub == 'disable':
                return reactor_cmd.disable_sync, [], remaining
            raise UnknownCommand(command)
        remaining = ' '.join(parts[2:])
        if action == 'reset':
            return reactor_cmd.reset, [], remaining
        if action == 'ping':
            return reactor_cmd.ping, [], remaining
        if action == 'bye':
            return reactor_cmd.bye, [], remaining
        raise UnknownCommand(command)

    # === System commands ===
    if prefix == 'system':
        if len(parts) < 2:
            raise UnknownCommand(command)
        action = parts[1]
        remaining = ' '.join(parts[2:])
        if action == 'help':
            return reactor_cmd.help_command, [], remaining
        if action == 'version':
            return reactor_cmd.version, [], remaining
        if action == 'crash':
            # crash has neighbor_support=True but typically used without selector
            return reactor_cmd.crash, [], remaining
        if action == 'queue-status':
            return reactor_cmd.queue_status, [], remaining
        if action == 'api':
            # system api version [4|6]
            remaining = ' '.join(parts[3:]) if len(parts) > 3 else ''
            return reactor_cmd.api_version_cmd, [], remaining
        raise UnknownCommand(command)

    # === RIB commands ===
    if prefix == 'rib':
        if len(parts) < 3:
            raise UnknownCommand(command)
        action = parts[1]
        direction = parts[2]
        remaining = ' '.join(parts[3:])
        if action == 'show':
            if direction in ('in', 'out'):
                return rib_cmd.show_adj_rib, [], f'{direction} {remaining}'.strip()
            raise UnknownCommand(command)
        if action == 'flush':
            if direction == 'out':
                # flush has neighbor_support - extract peers
                peers = list(reactor.peers(service))
                if not peers:
                    raise NoMatchingPeers(command)
                return rib_cmd.flush_adj_rib_out, peers, remaining
            raise UnknownCommand(command)
        if action == 'clear':
            # clear has neighbor_support - extract peers
            peers = list(reactor.peers(service))
            if not peers:
                raise NoMatchingPeers(command)
            return rib_cmd.clear_adj_rib, peers, f'{direction} {remaining}'.strip()
        raise UnknownCommand(command)

    # === Peer commands ===
    if prefix == 'peer':
        return _dispatch_peer_v6(command, parts, reactor, service, neighbor_cmd, peer_cmd, announce_cmd, watchdog_cmd)

    raise UnknownCommand(command)


def _dispatch_peer_v6(
    command: str,
    parts: list[str],
    reactor: 'Reactor',
    service: str,
    neighbor_cmd,
    peer_cmd,
    announce_cmd,
    watchdog_cmd,
) -> tuple[Handler, list[str], str]:
    """Dispatch peer-prefixed v6 commands.

    Handles:
    - peer list
    - peer show [summary|extensive|configuration]
    - peer <selector> show [summary|extensive|configuration]
    - peer <selector> teardown <code>
    - peer create <ip> ...
    - peer delete <selector>
    - peer <selector> announce <type> ...
    - peer <selector> withdraw <type> ...
    """
    if len(parts) < 2:
        raise UnknownCommand(command)

    # Check for immediate action words at parts[1]
    action = parts[1]

    # peer list - list all peers (no selector)
    if action == 'list':
        if len(parts) != 2:
            raise InvalidCommand(command)
        return neighbor_cmd.list_neighbor, [], command

    # peer show - show all peers (no selector)
    if action == 'show':
        remaining = ' '.join(parts[2:])
        return neighbor_cmd.show_neighbor, [], remaining

    # peer create - create peer (no selector needed)
    if action == 'create':
        # Pass full command for parsing
        remaining = ' '.join(parts[2:])
        return peer_cmd.neighbor_create, [], remaining

    # peer delete - delete peer (has selector)
    if action == 'delete':
        # Extract selector and match peers
        descriptions, remaining = extract_neighbors(command)
        peers = match_neighbors(reactor.peers(service), descriptions)
        if not peers:
            raise NoMatchingPeers(command)
        return peer_cmd.peer_delete, peers, remaining

    # Commands with selector: peer <selector> <action> ...
    # selector can be: *, IP, or [bracket syntax]
    return _dispatch_peer_with_selector_v6(command, parts, reactor, service, neighbor_cmd, announce_cmd, watchdog_cmd)


def _dispatch_peer_with_selector_v6(
    command: str,
    parts: list[str],
    reactor: 'Reactor',
    service: str,
    neighbor_cmd,
    announce_cmd,
    watchdog_cmd,
) -> tuple[Handler, list[str], str]:
    """Dispatch peer command with selector."""
    # Extract neighbors from command
    descriptions, remaining = extract_neighbors(command)

    # Find action word in remaining command
    remaining_parts = remaining.split()
    if not remaining_parts:
        raise UnknownCommand(command)

    action = remaining_parts[0]
    action_args = ' '.join(remaining_parts[1:])

    # Match peers
    peers = match_neighbors(reactor.peers(service), descriptions)

    if action == 'show':
        # show doesn't require peers to match (can show config for unconfigured)
        return neighbor_cmd.show_neighbor, peers if peers else [], action_args

    if action == 'teardown':
        if not peers:
            raise NoMatchingPeers(command)
        return neighbor_cmd.teardown, peers, action_args

    if action == 'announce':
        if not peers:
            raise NoMatchingPeers(command)
        return _dispatch_announce_v6(command, remaining_parts, peers, announce_cmd, watchdog_cmd)

    if action == 'withdraw':
        if not peers:
            raise NoMatchingPeers(command)
        return _dispatch_withdraw_v6(command, remaining_parts, peers, announce_cmd, watchdog_cmd)

    raise UnknownCommand(command)


def _dispatch_announce_v6(
    command: str,
    parts: list[str],
    peers: list[str],
    announce_cmd,
    watchdog_cmd,
) -> tuple[Handler, list[str], str]:
    """Dispatch announce subcommand."""
    # parts[0] is 'announce', parts[1] is type
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


def _dispatch_withdraw_v6(
    command: str,
    parts: list[str],
    peers: list[str],
    announce_cmd,
    watchdog_cmd,
) -> tuple[Handler, list[str], str]:
    """Dispatch withdraw subcommand."""
    # parts[0] is 'withdraw', parts[1] is type
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
