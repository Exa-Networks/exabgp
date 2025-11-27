"""command/neighbor.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
import json

from exabgp.bgp.neighbor import NeighborTemplate

from exabgp.reactor.api.command.limit import match_neighbor
from exabgp.reactor.api.command.limit import extract_neighbors

from exabgp.reactor.api.command.command import Command


def register_neighbor():
    pass


@Command.register('teardown', neighbor=True, json_support=True)
def teardown(self, reactor, service, line, use_json):
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
def show_neighbor(self, reactor, service, line, use_json):
    words = line.split()

    extensive = 'extensive' in words
    configuration = 'configuration' in words
    summary = 'summary' in words
    jason = 'json' in words
    text = 'text' in words

    if summary:
        words.remove('summary')
    if extensive:
        words.remove('extensive')
    if configuration:
        words.remove('configuration')
    if jason:
        words.remove('json')
    if text:
        words.remove('text')

    limit = words[-1] if words[-1] != 'neighbor' else ''

    async def callback_configuration():
        for neighbor_name in reactor.configuration.neighbors.keys():
            neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
            if not neighbor:
                continue
            if limit and limit not in neighbor_name:
                continue
            for line in str(neighbor).split('\n'):
                reactor.processes.write(service, line)
                await asyncio.sleep(0)  # Yield control after each line (matches original yield True)
        await reactor.processes.answer_done_async(service)

    async def callback_json():
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
                        'peer-address': str(neighbor['peer-address']),
                        'local-address': str(neighbor['local-address']) if neighbor.get('local-address') else None,
                        'peer-as': neighbor.get('peer-as'),
                        'local-as': neighbor.get('local-as'),
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

    async def callback_extensive():
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
                    peer_addr = str(neighbor['peer-address']) if neighbor['peer-address'] else 'not set'
                    local_addr = str(neighbor.get('local-address')) if neighbor.get('local-address') else 'not set'
                    peer_as = neighbor.get('peer-as', 'not set')
                    local_as = neighbor.get('local-as', 'not set')

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
            reactor.processes.write(service, f'# Error: {e}')
        await reactor.processes.answer_done_async(service)

    async def callback_summary():
        reactor.processes.write(service, NeighborTemplate.summary_header)
        for peer_name in reactor.peers():
            if limit and limit != str(reactor.neighbor_ip(peer_name)):
                continue
            for line in NeighborTemplate.summary(reactor.neighbor_cli_data(peer_name)).split('\n'):
                if line:
                    reactor.processes.write(service, line)
                await asyncio.sleep(0)  # Yield control after each line (matches original yield True)
        await reactor.processes.answer_done_async(service)

    if use_json:
        reactor.asynchronous.schedule(service, line, callback_json())
        return True

    if summary:
        reactor.asynchronous.schedule(service, line, callback_summary())
        return True

    if extensive:
        reactor.asynchronous.schedule(service, line, callback_extensive())
        return True

    if configuration:
        reactor.asynchronous.schedule(service, line, callback_configuration())
        return True

    reactor.processes.write(service, 'please specify summary, extensive or configuration')
    reactor.processes.write(service, 'you can filter by peer ip address adding it after the word neighbor')
    reactor.processes.answer_done(service)
