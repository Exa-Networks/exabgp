"""command/neighbor.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
import json
import shlex
from typing import TYPE_CHECKING, Any

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.neighbor import NeighborTemplate
from exabgp.logger import lazymsg, log
from exabgp.util.intvalue import json_number

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor
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


_SHOW_MODES = ('summary', 'extensive', 'configuration', 'json', 'text')
# the words of the API 4 form which are not an address: `show neighbor [<ip>] <mode>`
_SHOW_WORDS = ('neighbor', 'peer', 'show')


def _selected(peers: list[str], address: str, name: str, peer_address: str) -> bool:
    """Whether `show` is about the neighbor called `name`, whose peer address is `peer_address`.

    A selector names its peers; without one, the API 4 form may end with an address, which
    is compared with the peer address. It was searched for in the whole name of the
    neighbor, so 10.0.0.1 matched 10.0.0.10 too, and any neighbor whose local address or
    router-id started with it.
    """
    if peers:
        return name in peers
    return not address or peer_address == address


async def _show_configuration(reactor: 'Reactor', service: str, peers: list[str], address: str) -> None:
    try:
        for name, neighbor in list(reactor.configuration.neighbors.items()):
            if not _selected(peers, address, name, str(neighbor.session.peer_address)):
                continue
            for line in str(neighbor).split('\n'):
                reactor.processes.write(service, line)
                await asyncio.sleep(0)
    except Exception as e:
        await reactor.processes.answer_error(service, str(e))
    else:
        await reactor.processes.answer_done(service)


def _neighbor_json(reactor: 'Reactor', name: str, neighbor: 'Neighbor') -> dict[str, Any]:
    """What the JSON of `show` says of a neighbor: the runtime data of its peer, if it has one."""
    if name in reactor.peers():
        return NeighborTemplate.as_dict(reactor.neighbor_cli_data(name))
    session = neighbor.session
    return {
        'peer-address': str(session.peer_address),
        'local-address': str(session.local_address) if session.local_address else None,
        'peer-as': session.peer_as,
        'local-as': session.local_as,
    }


async def _show_json(reactor: 'Reactor', service: str, peers: list[str], address: str) -> None:
    # every configured neighbor, connected or not, as tooling and completion want them
    shown = []
    try:
        for name, neighbor in list(reactor.configuration.neighbors.items()):
            if not _selected(peers, address, name, str(neighbor.session.peer_address)):
                continue
            try:
                shown.append(_neighbor_json(reactor, name, neighbor))
            except Exception as e:
                # one neighbor which can not be described does not hide the others
                reactor.processes.write(service, f'# Error processing neighbor {name}: {e}')
    except Exception as e:
        reactor.processes.write(service, f'# Error accessing neighbors: {e}')

    for line in json.dumps(shown, default=json_number).split('\n'):
        reactor.processes.write(service, line)
        await asyncio.sleep(0)
    await reactor.processes.answer_done(service)


def _show_extensive_down(reactor: 'Reactor', service: str, neighbor: 'Neighbor') -> None:
    """What `show extensive` says of a configured neighbor which has no peer."""
    session = neighbor.session
    peer_address = str(session.peer_address) if session.peer_address else 'not set'
    local_address = str(session.local_address) if session.local_address else 'not set'
    peer_as = session.peer_as if session.peer_as else 'not set'
    local_as = session.local_as if session.local_as else 'not set'

    reactor.processes.write(service, f'Neighbor {peer_address}')
    reactor.processes.write(service, '')
    reactor.processes.write(service, '    Session                         Local')
    reactor.processes.write(service, f'    {"local-address":<20} {local_address:>15}')
    reactor.processes.write(service, f'    {"state":<20} down (not connected)')
    reactor.processes.write(service, '')
    reactor.processes.write(service, '    Setup                           Local          Remote')
    reactor.processes.write(service, f'    {"AS":<20} {local_as:>15} {peer_as:>15}')
    reactor.processes.write(service, '')


async def _show_extensive(reactor: 'Reactor', service: str, peers: list[str], address: str) -> None:
    # every configured neighbor, connected or not, so one which never connects is seen
    try:
        for name, neighbor in list(reactor.configuration.neighbors.items()):
            if not _selected(peers, address, name, str(neighbor.session.peer_address)):
                continue
            if name not in reactor.peers():
                _show_extensive_down(reactor, service, neighbor)
                await asyncio.sleep(0)
                continue
            for line in NeighborTemplate.extensive(reactor.neighbor_cli_data(name)).split('\n'):
                if line:
                    reactor.processes.write(service, line)
                await asyncio.sleep(0)
    except Exception as e:
        await reactor.processes.answer_error(service, str(e))
    else:
        await reactor.processes.answer_done(service)


async def _show_summary(reactor: 'Reactor', service: str, peers: list[str], address: str) -> None:
    try:
        reactor.processes.write(service, NeighborTemplate.summary_header)
        for name in reactor.peers():
            if not _selected(peers, address, name, reactor.neighbor_ip(name)):
                continue
            cli_data = reactor.neighbor_cli_data(name)
            if not cli_data:
                continue
            for line in NeighborTemplate.summary(cli_data).split('\n'):
                if line:
                    reactor.processes.write(service, line)
                await asyncio.sleep(0)
    except Exception as e:
        await reactor.processes.answer_error(service, str(e))
    else:
        await reactor.processes.answer_done(service)


def show_neighbor(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool
) -> bool:
    """`peer [<selector>] show [summary|extensive|configuration]`, or `show neighbor [<ip>] ...`.

    An API 6 helper is answered in JSON whatever the mode; the text modes are for API 4.
    """
    modes = set(command.split()) & set(_SHOW_MODES)
    words = [word for word in command.split() if word not in _SHOW_MODES]
    address = words[-1] if words and words[-1] not in _SHOW_WORDS else ''

    if use_json:
        show = _show_json
    elif 'configuration' in modes:
        show = _show_configuration
    elif 'summary' in modes:
        show = _show_summary
    elif 'extensive' in modes:
        show = _show_extensive
    else:
        reactor.processes.write(service, 'usage: peer <ip> show [summary|extensive|configuration]')
        reactor.processes.answer_done_sync(service)
        return True

    reactor.asynchronous.schedule(service, command, show(reactor, service, peers, address))
    return True
