"""command/route.py

Route management API commands with index-based operations.

Commands:
    peer <selector> routes list [family]
    peer <selector> routes add <route-spec>
    peer <selector> routes remove <route-spec>
    peer <selector> routes remove index <hex>

Created on 2025-12-11.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from exabgp.configuration.static import ParseStaticRoute
from exabgp.protocol.family import AFI, SAFI

if TYPE_CHECKING:
    from exabgp.reactor.api import API
    from exabgp.reactor.loop import Reactor


def register_route() -> None:
    """Registration hook (currently unused)."""
    pass


# v6 routes dispatcher mapping
_V6_ROUTES_HANDLERS: dict[str, str] = {
    'list': 'routes_list',
    'add': 'routes_add',
    'remove': 'routes_remove',
}


def v6_routes(
    self: 'API',
    reactor: 'Reactor',
    service: str,
    peers: list[str],
    command: str,
    use_json: bool,
) -> bool:
    """v6 routes dispatcher - routes to list/add/remove handlers.

    Command formats:
        routes list
        routes ipv4 list
        routes ipv4 unicast list
        routes add <spec>
        routes ipv4 unicast add <spec>
        routes remove <spec>
        routes remove index <hex>
    """
    words = command.split()

    # Find action (list, add, remove) - may have AFI/SAFI prefix
    action = None
    action_idx = -1
    for i, word in enumerate(words):
        if word in _V6_ROUTES_HANDLERS:
            action = word
            action_idx = i
            break

    if not action:
        reactor.processes.answer_error(service, 'routes requires action: list, add, or remove')
        return False

    # Extract optional AFI/SAFI filter (words before action)
    afi_safi_words = words[:action_idx] if action_idx > 0 else []

    # Extract remaining command (words after action)
    remaining = ' '.join(words[action_idx + 1 :])

    handler = globals()[_V6_ROUTES_HANDLERS[action]]
    return handler(self, reactor, service, peers, afi_safi_words, remaining, use_json)


def _parse_family_filter(afi_safi_words: list[str]) -> tuple[AFI | None, SAFI | None]:
    """Parse optional AFI/SAFI filter from words.

    Args:
        afi_safi_words: List of 0, 1, or 2 words (e.g., [], ['ipv4'], ['ipv4', 'unicast'])

    Returns:
        Tuple of (AFI or None, SAFI or None)
    """
    afi = None
    safi = None

    if len(afi_safi_words) >= 1:
        afi = AFI.from_string(afi_safi_words[0])
        if afi == AFI.undefined:
            afi = None

    if len(afi_safi_words) >= 2:
        safi = SAFI.from_string(afi_safi_words[1])
        if safi == SAFI.undefined:
            safi = None

    return afi, safi


def routes_list(
    self: 'API',
    reactor: 'Reactor',
    service: str,
    peers: list[str],
    afi_safi_words: list[str],
    command: str,
    use_json: bool,
) -> bool:
    """List routes with their indexes.

    Command: peer <selector> routes [afi [safi]] list

    Response (JSON):
        [
            {"index": "0101180a000000", "route": "10.0.0.0/24 next-hop 1.2.3.4"},
            {"index": "0101200a010000", "route": "10.1.0.0/24 next-hop 1.2.3.4"}
        ]
    """

    async def callback() -> None:
        try:
            afi_filter, safi_filter = _parse_family_filter(afi_safi_words)

            routes_data = []
            for neighbor_name in peers:
                neighbor = reactor.configuration.neighbors.get(neighbor_name)
                if not neighbor:
                    continue

                # Get routes from RIB cache
                for route in neighbor.rib.outgoing.cached_routes(list(neighbor.families())):
                    # Apply family filter if specified
                    family = route.nlri.family()
                    if afi_filter and family.afi != afi_filter:
                        continue
                    if safi_filter and family.safi != safi_filter:
                        continue

                    routes_data.append(
                        {
                            'index': route.index().hex(),
                            'route': route.extensive(),
                            'neighbor': neighbor_name,
                        }
                    )

            await reactor.processes.answer_async(service, routes_data)
        except Exception as e:
            error_msg = f'Failed to list routes: {type(e).__name__}: {str(e)}'
            self.log_exception(error_msg, e)
            await reactor.processes.answer_error_async(service, error_msg)

    reactor.asynchronous.schedule(service, f'routes list {" ".join(afi_safi_words)}', callback())
    return True


def routes_add(
    self: 'API',
    reactor: 'Reactor',
    service: str,
    peers: list[str],
    afi_safi_words: list[str],
    command: str,
    use_json: bool,
) -> bool:
    """Add route and return its index.

    Command: peer <selector> routes [afi [safi]] add <route-spec>

    Response (JSON):
        {"index": "0101180a000000", "route": "10.0.0.0/24 next-hop 1.2.3.4", "success": true}
    """

    async def callback() -> None:
        try:
            if not command.strip():
                await reactor.processes.answer_error_async(service, 'routes add requires route specification')
                return

            # Parse route specification
            routes = self.api_route(command, 'announce')
            if not routes:
                error_msg = f'Could not parse route: {command}'
                self.log_failure(error_msg)
                await reactor.processes.answer_error_async(service, error_msg)
                return

            results = []
            for route in routes:
                if not ParseStaticRoute.check(route):
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'invalid route for {peer_list} : {route.extensive()}')
                    results.append(
                        {
                            'route': route.extensive(),
                            'success': False,
                            'error': 'invalid route',
                        }
                    )
                    continue

                # Use indexed injection to get index
                index, success = reactor.configuration.announce_route_indexed(peers, route)

                peer_list = ', '.join(peers) if peers else 'all peers'
                if success:
                    self.log_message(f'route added to {peer_list} : {route.extensive()}')
                else:
                    self.log_message(f'route added (no matching peers) : {route.extensive()}')

                results.append(
                    {
                        'index': index.hex(),
                        'route': route.extensive(),
                        'success': success,
                    }
                )
                await asyncio.sleep(0)

            # Return single result or list
            if len(results) == 1:
                await reactor.processes.answer_async(service, results[0])
            else:
                await reactor.processes.answer_async(service, results)

        except ValueError as e:
            error_msg = f'Failed to parse route: {str(e)}'
            self.log_failure(error_msg)
            await reactor.processes.answer_error_async(service, error_msg)
        except Exception as e:
            error_msg = f'Unexpected error: {type(e).__name__}: {str(e)}'
            self.log_exception(error_msg, e)
            await reactor.processes.answer_error_async(service, error_msg)

    reactor.asynchronous.schedule(service, f'routes add {command}', callback())
    return True


def routes_remove(
    self: 'API',
    reactor: 'Reactor',
    service: str,
    peers: list[str],
    afi_safi_words: list[str],
    command: str,
    use_json: bool,
) -> bool:
    """Remove route by specification or index.

    Commands:
        peer <selector> routes remove <route-spec>
        peer <selector> routes remove index <hex>

    Response (JSON):
        {"removed": true, "index": "0101180a000000"}
    """

    async def callback() -> None:
        try:
            if not command.strip():
                await reactor.processes.answer_error_async(service, 'routes remove requires route spec or index')
                return

            # Check if removing by index
            if command.strip().startswith('index '):
                index_hex = command.strip()[6:].strip()
                try:
                    index = bytes.fromhex(index_hex)
                except ValueError:
                    await reactor.processes.answer_error_async(service, f'Invalid hex index: {index_hex}')
                    return

                success = reactor.configuration.withdraw_route_by_index(peers, index)
                if success:
                    peer_list = ', '.join(peers) if peers else 'all peers'
                    self.log_message(f'route removed from {peer_list} by index: {index_hex}')
                else:
                    self.log_failure(f'route not found for index: {index_hex}')

                await reactor.processes.answer_async(
                    service,
                    {
                        'removed': success,
                        'index': index_hex,
                    },
                )
                return

            # Remove by route specification
            routes = self.api_route(command, 'withdraw')
            if not routes:
                error_msg = f'Could not parse route: {command}'
                self.log_failure(error_msg)
                await reactor.processes.answer_error_async(service, error_msg)
                return

            results = []
            for route in routes:
                success = reactor.configuration.withdraw_route(peers, route)

                peer_list = ', '.join(peers) if peers else 'all peers'
                if success:
                    self.log_message(f'route removed from {peer_list} : {route.extensive()}')
                else:
                    self.log_failure(f'route not found on {peer_list} : {route.extensive()}')

                results.append(
                    {
                        'removed': success,
                        'route': route.extensive(),
                        'index': route.index().hex(),
                    }
                )
                await asyncio.sleep(0)

            # Return single result or list
            if len(results) == 1:
                await reactor.processes.answer_async(service, results[0])
            else:
                await reactor.processes.answer_async(service, results)

        except ValueError as e:
            error_msg = f'Failed to parse route: {str(e)}'
            self.log_failure(error_msg)
            await reactor.processes.answer_error_async(service, error_msg)
        except Exception as e:
            error_msg = f'Unexpected error: {type(e).__name__}: {str(e)}'
            self.log_exception(error_msg, e)
            await reactor.processes.answer_error_async(service, error_msg)

    reactor.asynchronous.schedule(service, f'routes remove {command}', callback())
    return True
