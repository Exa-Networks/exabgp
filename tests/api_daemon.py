"""A daemon an API helper talks to, for the tests of the API commands.

The objects are the ones ExaBGP runs: a Configuration parsed from text, a Reactor with a
Peer for each of its neighbors, and Processes answering a helper. Only the helper is not a
child process: its stdin is a pipe the test reads, so what a command answers is the lines
the helper would have read.

A command goes the way the reactor loop sends it (`Reactor._async_main_loop`): through
`API.process`, then whatever the handler scheduled is run, then the answers are flushed.

A client error has to be answered by the handler, never by an exception escaping it: the
reactor answers `error` for a coroutine which raised, so the client sees the same line
either way, and only the escape tells them apart. `Daemon.send` records every escape and
refuses one unless the test says it expects it.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from exabgp.bgp.fsm import FSM
from exabgp.configuration.configuration import Configuration
from exabgp.reactor.api.command import group
from exabgp.reactor.api.processes import Processes
from exabgp.reactor.loop import Reactor
from exabgp.reactor.peer import Peer

HELPER = 'helper'
# a pipe holds 64 KiB on macOS and Linux; no command of these tests answers more
PIPE_READ_SIZE = 1 << 16
# what a command schedules can schedule more; none of them goes this deep
SCHEDULING_ROUNDS = 100

FIRST = '127.0.0.1'
# a prefix of the other's address, so a filter matching text rather than an address shows
SECOND = '127.0.0.10'

# two neighbors, so a selector naming one can be seen to leave the other alone
CONFIGURATION = f"""
process {HELPER} {{
    run /usr/bin/true;
    encoder json;
}}

neighbor {FIRST} {{
    router-id 10.0.0.1;
    local-address 127.0.0.100;
    local-as 65000;
    peer-as 65001;
    family {{
        ipv4 unicast;
        ipv6 unicast;
        ipv4 flow;
        ipv4 mpls-vpn;
        l2vpn vpls;
    }}
    api {{
        processes [ {HELPER} ];
    }}
}}

neighbor {SECOND} {{
    router-id 10.0.0.1;
    local-address 127.0.0.100;
    local-as 65000;
    peer-as 65002;
    family {{
        ipv4 unicast;
    }}
    api {{
        processes [ {HELPER} ];
    }}
}}
"""


class PipedHelper:
    """The Popen of an API helper, as far as answering it goes: its stdin is a pipe."""

    def __init__(self) -> None:
        self._reader, writer = os.pipe()
        os.set_blocking(self._reader, False)
        self.stdin = os.fdopen(writer, 'wb')

    def lines(self) -> list[str]:
        """Every line written to the helper since the last call."""
        try:
            return os.read(self._reader, PIPE_READ_SIZE).decode('ascii').splitlines()
        except BlockingIOError:
            return []

    def close(self) -> None:
        os.close(self._reader)
        self.stdin.close()


class Daemon:
    """A Reactor running `configuration`, with one API helper, `HELPER`, talking to it."""

    def __init__(self, configuration: str = CONFIGURATION, encoder: str = 'json') -> None:
        parsed = Configuration([configuration], text=True)
        # not an assert: the optimised run of the suite (PYTHONOPTIMIZE) would not load it
        if not parsed.reload():
            raise AssertionError(str(parsed.error))
        self.configuration = parsed
        self.reactor = Reactor(parsed)
        self.reactor.processes = Processes()
        # the services whose coroutine raised, which Reactor.run_async answers error for
        self.escaped: list[str] = []
        self.reactor.asynchronous.set_error_handler(self._escaped)
        for key, neighbor in parsed.neighbors.items():
            self.reactor.register_peer(key, Peer(neighbor, self.reactor))

        self.helper = PipedHelper()
        processes = self.reactor.processes
        processes._process[HELPER] = self.helper  # type: ignore[assignment]
        # what Processes._start records for a helper configured with this encoder
        processes._configuration[HELPER] = {'encoder': encoder}
        processes._select_encoder(HELPER, {'encoder': encoder})
        processes._ackjson[HELPER] = False
        processes._ack[HELPER] = True

    def _escaped(self, service: str) -> None:
        self.escaped.append(service)
        self.reactor.processes.answer_error_sync(service)

    def key(self, address: str) -> str:
        """The name the reactor knows the neighbor with this peer address by."""
        found = [key for key in self.configuration.neighbors if key.split()[1] == address]
        if len(found) != 1:
            raise AssertionError(f'no single neighbor {address} in {list(self.configuration.neighbors)}')
        return found[0]

    def neighbor(self, address: str) -> Any:
        return self.configuration.neighbors[self.key(address)]

    def peer(self, address: str) -> Peer:
        return self.reactor._peers[self.key(address)]

    def establish(self, *addresses: str) -> None:
        """Put the sessions of these neighbors, or of all of them, in ESTABLISHED."""
        for address in addresses or (FIRST, SECOND):
            self.peer(address).fsm.change(FSM.ESTABLISHED)

    def send(self, command: str, escape: bool = False) -> list[str]:
        """Write `command` as the helper, run what it scheduled, and return what the helper read.

        An exception escaping the handler fails the test, unless `escape` says it is the point.
        """
        self.reactor.api.process(self.reactor, HELPER, command)
        asyncio.run(self._run_scheduled())
        if self.escaped and not escape:
            raise AssertionError(f'{command!r} raised through the reactor instead of answering')
        return self.helper.lines()

    async def _run_scheduled(self) -> None:
        for _ in range(SCHEDULING_ROUNDS):
            if not self.reactor.asynchronous._async:
                break
            await self.reactor.asynchronous._run_async()
        if self.reactor.asynchronous._async:
            raise AssertionError('a command kept scheduling work')
        await self.reactor.processes.flush_write_queue()

    def announced(self, address: str) -> list[str]:
        """The NLRI the outgoing RIB of a neighbor holds, sorted."""
        rib = self.neighbor(address).rib.outgoing
        return sorted(str(route.nlri) for route in rib.cached_routes(None))

    def close(self) -> None:
        for _, coroutine in self.reactor.asynchronous._async:
            coroutine.close()
        group.clear_group(HELPER)
        self.helper.close()


def failed(reason: str) -> str:
    """The line which says why a command failed, as an API 6 helper is written it."""
    return json.dumps({'error': reason})


def answer(lines: list[str]) -> list[Any]:
    """The JSON lines of an answer, decoded; the `done` or `error` closing it is left out."""
    return [json.loads(line) for line in lines if line not in ('done', 'error')]
