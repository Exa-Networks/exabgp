"""command/neighbor.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
import json
import shlex
from typing import TYPE_CHECKING

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.neighbor import NeighborTemplate
from exabgp.logger import lazymsg, log
from exabgp.util.intvalue import json_number

if TYPE_CHECKING:
    from exabgp.reactor.api import API
    from exabgp.reactor.loop import Reactor


def register_neighbor() -> None:
    pass


def list_neighbor(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool
) -> bool:
    """List all configured neighbors - JSON only, no filtering."""

    async def callback() -> None:
        neighbors = []
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

                neighbors.append(
                    {
                        'peer-address': peer_addr,
                        'peer-as': peer_as,
                        'state': state,
                    }
                )

            for line in json.dumps(neighbors, default=json_number).split('\n'):
                reactor.processes.write(service, line)
                await asyncio.sleep(0)
        except Exception as e:
            await reactor.processes.answer_error(service, str(e))
        else:
            await reactor.processes.answer_done(service)

    reactor.asynchronous.schedule(service, command, callback())
    return True


# the default when the client names nothing: RFC 4486 Cease, Administrative Shutdown
_TEARDOWN_DEFAULT = (6, 2)
_OCTET_MAX = 255


def _octet(token: str) -> int:
    if not token.isdigit() or int(token) > _OCTET_MAX:
        raise ValueError(f'{token!r} is not a value from 0 to {_OCTET_MAX}')
    return int(token)


def teardown_notification(arguments: str) -> Notify:
    """The NOTIFICATION `teardown [<code>] [<subcode>] [<text>]` asks for.

    One number is a Cease subcode, which is what the command always sent whatever the
    documentation said; two are a code and a subcode.  Any value a wire octet can hold is
    accepted, for clients testing another implementation, and one IANA does not assign is
    warned about.  Text starting with a digit has to be quoted, or it reads as a number.
    """
    tokens = shlex.split(arguments)  # raises ValueError on an unbalanced quote
    numbers: list[int] = []
    while tokens and len(numbers) < len(_TEARDOWN_DEFAULT) and tokens[0].isdigit():
        numbers.append(_octet(tokens.pop(0)))
    if not numbers and tokens:
        raise ValueError(f'expected a code or a subcode, got {tokens[0]!r}')
    if not numbers:
        code, subcode = _TEARDOWN_DEFAULT
    elif len(numbers) == 1:
        code, subcode = 6, numbers[0]
    else:
        code, subcode = numbers
    if not Notify.is_assigned(code, subcode):
        log.warning(lazymsg('teardown.unassigned code={c} subcode={s}', c=code, s=subcode), 'api')
    return Notify(code, subcode, ' '.join(tokens))


def teardown(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    try:
        notify = teardown_notification(command)
    except ValueError as exc:
        reactor.processes.answer_error_sync(service, str(exc))
        return False
    for peer_key in peers:
        if peer_key in reactor.established_peers():
            reactor.teardown_peer(peer_key, notify)
            self.log_message(f'teardown scheduled for {peer_key}')
    reactor.processes.answer_done_sync(service)
    return True


def disable(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """`disable [<text>]`: close the session with Administrative Shutdown and keep it closed.

    The text is the RFC 9003 Shutdown Communication.  Unlike teardown, a peer which is not
    established is disabled too, so it does not connect until `enable` (issue #1013).
    """
    try:
        text = ' '.join(shlex.split(command))  # raises ValueError on an unbalanced quote
    except ValueError as exc:
        reactor.processes.answer_error_sync(service, str(exc))
        return False
    for peer_key in peers:
        reactor.disable_peer(peer_key, Notify(*_TEARDOWN_DEFAULT, text))
        self.log_message(f'disabled {peer_key}')
    reactor.processes.answer_done_sync(service)
    return True


def enable(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """`enable`: let a disabled peer connect again, straight away."""
    if command.strip():
        reactor.processes.answer_error_sync(service, f'enable takes no argument, got {command.strip()!r}')
        return False
    for peer_key in peers:
        reactor.enable_peer(peer_key)
        self.log_message(f'enabled {peer_key}')
    reactor.processes.answer_done_sync(service)
    return True


def show_neighbor(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool
) -> bool:
    words = command.split()

    summary = 'summary' in words
    extensive = 'extensive' in words
    configuration = 'configuration' in words
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

    # Get IP filter from peers list or command keywords
    # peers list may be empty for global commands like "peer show"
    limit = ''
    if peers and len(peers) == 1:
        # Single peer specified - use as filter
        # Extract IP from peer key (format: "neighbor 1.2.3.4 ...")
        peer_parts = peers[0].split()
        if len(peer_parts) >= 2:
            limit = peer_parts[1]
    elif words:
        # Fall back to parsing command for IP filter
        if words[-1] not in ('neighbor', 'peer', 'show', 'summary', 'extensive', 'configuration'):
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
            await reactor.processes.answer_error(service, str(e))
        else:
            await reactor.processes.answer_done(service)

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

        for line in json.dumps(p, default=json_number).split('\n'):
            reactor.processes.write(service, line)
            await asyncio.sleep(0)  # Yield control after each line (matches original yield True)
        await reactor.processes.answer_done(service)

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
            await reactor.processes.answer_error(service, str(e))
        else:
            await reactor.processes.answer_done(service)

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
            await reactor.processes.answer_error(service, str(e))
        else:
            await reactor.processes.answer_done(service)

    # JSON output takes priority in v6 API (use_json=True)
    # This ensures consistent JSON responses for all commands

    # Full JSON output for peer <ip> show (default in v6 API)
    if use_json:
        reactor.asynchronous.schedule(service, command, callback_json())
        return True

    # Text output modes (only for v4 API or explicit text request)
    if configuration:
        reactor.asynchronous.schedule(service, command, callback_configuration())
        return True

    if summary:
        reactor.asynchronous.schedule(service, command, callback_summary())
        return True

    if extensive:
        reactor.asynchronous.schedule(service, command, callback_extensive())
        return True

    # Fallback
    reactor.processes.write(service, 'usage: peer <ip> show [summary|extensive|configuration]')
    reactor.processes.answer_done_sync(service)
    return True
