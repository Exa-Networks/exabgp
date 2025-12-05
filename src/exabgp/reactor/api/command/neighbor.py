"""command/neighbor.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from exabgp.bgp.neighbor import NeighborTemplate

from exabgp.reactor.api.command.limit import match_neighbor
from exabgp.reactor.api.command.limit import extract_neighbors

from exabgp.reactor.api.command.command import Command

if TYPE_CHECKING:
    from exabgp.reactor.api import API
    from exabgp.reactor.loop import Reactor


def register_neighbor() -> None:
    pass


@Command.register('teardown', neighbor=True, json_support=True)
def teardown(self: 'API', reactor: 'Reactor', service: str, line: str, use_json: bool) -> bool:
    try:
        descriptions, line = extract_neighbors(line)
        if ' ' not in line:
            reactor.processes.answer_error(service)
            return False
        _, code = line.split(' ', 1)
        if not code.isdigit():
            reactor.processes.answer_error(service)
            return False
        for key in reactor.established_peers():
            for description in descriptions:
                if match_neighbor(description, key):
                    reactor.teardown_peer(key, int(code))
                    desc_str = ' '.join(description)
                    self.log_message(f'teardown scheduled for {desc_str}')
        reactor.processes.answer_done(service)
        return True
    except ValueError:
        reactor.processes.answer_error(service)
        return False
    except IndexError:
        reactor.processes.answer_error(service)
        return False


@Command.register('show neighbor', False, ['summary', 'extensive', 'configuration'], True)
def show_neighbor(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    words = line.split()

    # Check if this is "peer list" command (defaults to summary)
    is_peer_list = 'list' in words

    extensive = 'extensive' in words
    configuration = 'configuration' in words
    summary = 'summary' in words or is_peer_list  # peer list defaults to summary
    jason = 'json' in words
    text = 'text' in words

    if 'list' in words:
        words.remove('list')
    if summary and 'summary' in words:
        words.remove('summary')
    if extensive:
        words.remove('extensive')
    if configuration:
        words.remove('configuration')
    if jason:
        words.remove('json')
    if text:
        words.remove('text')

    # Get IP filter from command
    # v4 syntax: show neighbor [<ip>] [options] - IP at end
    # v6 syntax: peer <ip> show [options] - IP at words[1]
    limit = ''
    if words:
        # Check v6 syntax first: peer <ip> show
        if len(words) >= 2 and words[0] == 'peer' and words[1] not in ('*', 'show', 'list'):
            limit = words[1]
        # Fall back to v4 syntax: last word if not a keyword
        elif words[-1] not in ('neighbor', 'peer', 'show'):
            limit = words[-1]

    async def callback_configuration() -> None:
        try:
            for neighbor_name in reactor.configuration.neighbors.keys():
                neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
                if not neighbor:
                    continue
                if limit and limit not in neighbor_name:
                    continue
                for line in str(neighbor).split('\n'):
                    reactor.processes.write(service, line)
                    await asyncio.sleep(0)  # Yield control after each line (matches original yield True)
        except Exception as e:
            await reactor.processes.answer_error_async(service, str(e))
        else:
            await reactor.processes.answer_done_async(service)

    async def callback_json() -> None:
        p = []
        # Include ALL configured neighbors (not just connected ones)
        # This is useful for tooling/completion even when neighbors are down
        try:
            for neighbor_name in reactor.configuration.neighbors.keys():
                neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
                if not neighbor:
                    continue

                # Build minimal neighbor info from configuration
                try:
                    neighbor_data = {
                        'peer-address': str(neighbor.session.peer_address),
                        'local-address': str(neighbor.session.local_address)
                        if neighbor.session.local_address
                        else None,
                        'peer-as': neighbor.session.peer_as,
                        'local-as': neighbor.session.local_as,
                    }

                    # If neighbor is also an active peer, get full runtime data
                    if neighbor_name in reactor.peers():
                        neighbor_data = NeighborTemplate.as_dict(reactor.neighbor_cli_data(neighbor_name))

                    p.append(neighbor_data)
                except Exception as e:
                    # Log error but continue with other neighbors
                    reactor.processes.write(service, f'# Error processing neighbor {neighbor_name}: {e}')
        except Exception as e:
            # Log error if configuration access fails
            reactor.processes.write(service, f'# Error accessing neighbors: {e}')

        for line in json.dumps(p).split('\n'):
            reactor.processes.write(service, line)
            await asyncio.sleep(0)  # Yield control after each line (matches original yield True)
        await reactor.processes.answer_done_async(service)

    async def callback_extensive() -> None:
        # Show ALL configured neighbors (both connected and disconnected)
        # This provides visibility into neighbors that are down/not connecting
        try:
            for neighbor_name in reactor.configuration.neighbors.keys():
                neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
                if not neighbor:
                    continue

                # Check if this neighbor matches the filter
                if limit and limit not in neighbor_name:
                    continue

                # If neighbor is connected, show full extensive output
                if neighbor_name in reactor.peers():
                    for line in NeighborTemplate.extensive(reactor.neighbor_cli_data(neighbor_name)).split('\n'):
                        if line:
                            reactor.processes.write(service, line)
                        await asyncio.sleep(0)
                else:
                    # Neighbor is configured but not connected - show minimal info
                    peer_addr = str(neighbor.session.peer_address) if neighbor.session.peer_address else 'not set'
                    local_addr = str(neighbor.session.local_address) if neighbor.session.local_address else 'not set'
                    peer_as = neighbor.session.peer_as if neighbor.session.peer_as else 'not set'
                    local_as = neighbor.session.local_as if neighbor.session.local_as else 'not set'

                    reactor.processes.write(service, f'Neighbor {peer_addr}')
                    reactor.processes.write(service, '')
                    reactor.processes.write(service, '    Session                         Local')
                    reactor.processes.write(service, f'    {"local-address":<20} {local_addr:>15}')
                    reactor.processes.write(service, f'    {"state":<20} down (not connected)')
                    reactor.processes.write(service, '')
                    reactor.processes.write(service, '    Setup                           Local          Remote')
                    reactor.processes.write(service, f'    {"AS":<20} {local_as:>15} {peer_as:>15}')
                    reactor.processes.write(service, '')
                    await asyncio.sleep(0)
        except Exception as e:
            await reactor.processes.answer_error_async(service, str(e))
        else:
            await reactor.processes.answer_done_async(service)

    async def callback_summary() -> None:
        try:
            reactor.processes.write(service, NeighborTemplate.summary_header)
            for peer_name in reactor.peers():
                if limit and limit != str(reactor.neighbor_ip(peer_name)):
                    continue
                cli_data = reactor.neighbor_cli_data(peer_name)
                if not cli_data:
                    continue
                for line in NeighborTemplate.summary(cli_data).split('\n'):
                    if line:
                        reactor.processes.write(service, line)
                    await asyncio.sleep(0)  # Yield control after each line (matches original yield True)
        except Exception as e:
            await reactor.processes.answer_error_async(service, str(e))
        else:
            await reactor.processes.answer_done_async(service)

    async def callback_list_json() -> None:
        """Simple peer list - just IP, AS, and state for each configured neighbor."""
        peers = []
        try:
            for neighbor_name in reactor.configuration.neighbors.keys():
                neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
                if not neighbor:
                    continue

                peer_addr = str(neighbor.session.peer_address) if neighbor.session.peer_address else None
                if not peer_addr:
                    continue

                peer_as = neighbor.session.peer_as

                # Check if connected and get state
                if neighbor_name in reactor.peers():
                    cli_data = reactor.neighbor_cli_data(neighbor_name)
                    state = cli_data.get('state', 'unknown') if cli_data else 'unknown'
                else:
                    state = None  # Not connected

                peers.append(
                    {
                        'peer-address': peer_addr,
                        'peer-as': peer_as,
                        'state': state,
                    }
                )

            for line in json.dumps(peers).split('\n'):
                reactor.processes.write(service, line)
                await asyncio.sleep(0)
        except Exception as e:
            await reactor.processes.answer_error_async(service, str(e))
        else:
            await reactor.processes.answer_done_async(service)

    # Explicit display options take priority over use_json default
    # (v6 API always has use_json=True, so we check explicit options first)
    if configuration:
        reactor.asynchronous.schedule(service, line, callback_configuration())
        return True

    if summary:
        reactor.asynchronous.schedule(service, line, callback_summary())
        return True

    if extensive:
        reactor.asynchronous.schedule(service, line, callback_extensive())
        return True

    # peer list: simple JSON list of peers
    if is_peer_list and use_json:
        reactor.asynchronous.schedule(service, line, callback_list_json())
        return True

    # Default: Full JSON output for peer <ip> show (no explicit option)
    if use_json:
        reactor.asynchronous.schedule(service, line, callback_json())
        return True

    reactor.processes.write(service, 'usage: peer <ip> show [summary|extensive|configuration]')
    reactor.processes.write(service, '       peer list')
    reactor.processes.answer_done(service)
    return True
