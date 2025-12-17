"""dispatch/v6.py

Dispatcher for v6 format API commands using tree-based routing.

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

from exabgp.configuration.core.parser import Tokeniser
from exabgp.reactor.api.dispatch.common import (
    SELECTOR_KEY,
    DispatchTree,
    Handler,
    NoMatchingPeers,
    dispatch,
)

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor


def _build_v6_tree() -> DispatchTree:
    """Build the v6 dispatch tree lazily to avoid circular imports."""
    from exabgp.reactor.api.command import announce as announce_cmd
    from exabgp.reactor.api.command import group as group_cmd
    from exabgp.reactor.api.command import neighbor as neighbor_cmd
    from exabgp.reactor.api.command import peer as peer_cmd
    from exabgp.reactor.api.command import reactor as reactor_cmd
    from exabgp.reactor.api.command import rib as rib_cmd
    from exabgp.reactor.api.command import route as route_cmd

    # Peer selector subtree (after selector is consumed)
    # v6_announce/v6_withdraw dispatch to specific handlers based on type token
    peer_selector_tree: DispatchTree = {
        'show': neighbor_cmd.show_neighbor,
        'teardown': neighbor_cmd.teardown,
        'announce': announce_cmd.v6_announce,
        'withdraw': announce_cmd.v6_withdraw,
        'group': group_cmd.group_inline,
        'routes': route_cmd.v6_routes,
    }

    tree: DispatchTree = {
        # Comment handling
        '#': reactor_cmd.comment,
        # Daemon commands
        'daemon': {
            'shutdown': reactor_cmd.shutdown,
            'reload': reactor_cmd.reload,
            'restart': reactor_cmd.restart,
            'status': reactor_cmd.status,
        },
        # Session commands
        'session': {
            'ack': {
                'enable': reactor_cmd.enable_ack,
                'disable': reactor_cmd.disable_ack,
                'silence': reactor_cmd.silence_ack,
            },
            'sync': {
                'enable': reactor_cmd.enable_sync,
                'disable': reactor_cmd.disable_sync,
            },
            'reset': reactor_cmd.reset,
            'ping': reactor_cmd.ping,
            'bye': reactor_cmd.bye,
        },
        # System commands
        'system': {
            'help': reactor_cmd.help_command,
            'version': reactor_cmd.version,
            'crash': reactor_cmd.crash,
            'queue-status': reactor_cmd.queue_status,
            'api': {
                'version': reactor_cmd.api_version_cmd,
            },
        },
        # RIB commands - handlers receive "in/out [options]"
        # Don't consume direction - let handler parse it from command
        'rib': {
            'show': rib_cmd.show_adj_rib,
            'flush': rib_cmd.flush_adj_rib_out,
            'clear': rib_cmd.clear_adj_rib,
        },
        # Peer commands
        'peer': {
            'list': neighbor_cmd.list_neighbor,
            'show': neighbor_cmd.show_neighbor,
            'create': peer_cmd.neighbor_create,
            'delete': peer_cmd.peer_delete,
            # Selector-based commands (*, IP, or [bracket])
            SELECTOR_KEY: peer_selector_tree,
        },
        # Group commands for batching multiple announcements
        'group': {
            'start': group_cmd.group_start,
            'end': group_cmd.group_end,
        },
    }

    return tree


# Lazy initialization of tree
_V6_TREE: DispatchTree | None = None


def _get_v6_tree() -> DispatchTree:
    """Get the v6 dispatch tree, building it lazily."""
    global _V6_TREE
    if _V6_TREE is None:
        _V6_TREE = _build_v6_tree()
    return _V6_TREE


def _v6_needs_peers() -> set[Handler]:
    """Return set of handlers that require peers if none specified."""
    from exabgp.reactor.api.command import announce as announce_cmd
    from exabgp.reactor.api.command import neighbor as neighbor_cmd
    from exabgp.reactor.api.command import rib as rib_cmd

    return {
        announce_cmd.v6_announce,
        announce_cmd.v6_withdraw,
        neighbor_cmd.teardown,
        rib_cmd.flush_adj_rib_out,
        rib_cmd.clear_adj_rib,
    }


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
        - remaining_command: Command portion after dispatch prefix stripped

    Raises:
        UnknownCommand: If the command cannot be routed
        NoMatchingPeers: If neighbor_support=True but no peers match
    """
    command = command.strip()

    # Create tokeniser with token list
    tokeniser = Tokeniser()
    token_list = command.split()
    tokeniser.replenish(token_list)

    # Special case: empty command or comment
    if not token_list or command.startswith('#'):
        from exabgp.reactor.api.command import reactor as reactor_cmd

        return reactor_cmd.comment, [], command

    tree = _get_v6_tree()
    handler, peers = dispatch(tree, tokeniser, reactor, service)

    # Some handlers require all peers if none specified
    if handler in _v6_needs_peers() and not peers:
        peers = list(reactor.peers(service))
        if not peers:
            raise NoMatchingPeers(command)

    return handler, peers, tokeniser.remaining_string()
