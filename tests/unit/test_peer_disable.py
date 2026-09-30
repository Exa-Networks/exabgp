"""A neighbour can be disabled and enabled, from the API or from the configuration.

    peer <selector> disable [<text>]     Cease / Administrative Shutdown, then stay down
    peer <selector> enable               connect again, straight away
    neighbor <ip> { shutdown true; }     start disabled

Issue #1013: an API process which loads its routes after the daemon starts had no way to
keep the session down until it was done, other than manual-eor.  teardown closes the
session but the peer reconnects after the backoff, and stop() removes the peer from the
reactor, so neither is a shutdown the operator can undo.
"""

from __future__ import annotations

import asyncio
import contextlib
import select
import socket
from typing import Any

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.environment import getenv
from exabgp.protocol.family import AFI
from exabgp.reactor.api.command.neighbor import disable, enable
from exabgp.reactor.api.dispatch.v4 import dispatch_v4
from exabgp.reactor.api.dispatch.v6 import dispatch_v6
from exabgp.reactor.loop import Reactor
from exabgp.reactor.network.incoming import Incoming
from exabgp.reactor.peer import Peer
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB
from tests import negotiation
from tests.wire_reader import tcp_socketpair

CEASE = 6
ADMINISTRATIVE_SHUTDOWN = 2
CONNECTION_REJECTED = 5

OPEN = 1
NOTIFICATION = 3

# the API process the command handlers answer
SERVICE = 'service'

# how long a scenario waits for what it expects before failing, rather than hanging
PATIENCE_SECONDS = 5.0


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Neighbor takes a RIB out of a process wide cache, so each test gets its own."""
    monkeypatch.setattr(RIB, '_cache', {})


def neighbour(shutdown: bool = False, peer_address: str = '127.0.0.2') -> Neighbor:
    neighbor = negotiation.api_asks(negotiation.neighbor(peer_address=peer_address))
    neighbor.api['processes'] = [SERVICE]
    neighbor.session.passive = False
    neighbor.shutdown = shutdown
    return neighbor


def peer(shutdown: bool = False, reactor: Reactor | None = None) -> Peer:
    neighbor = neighbour(shutdown)
    if reactor is None:
        reactor, _ = negotiation.reactor()
    return Peer(neighbor, reactor)


def incoming() -> tuple[Incoming, socket.socket]:
    """A real incoming connection, and the socket of the peer which made it."""
    accepted, connecting = tcp_socketpair()
    return Incoming(AFI.ipv4, '127.0.0.2', '127.0.0.1', accepted), connecting


def sent_to(theirs: socket.socket) -> list[tuple[int, bytes]]:
    """The BGP messages the peer end has received so far."""
    return negotiation.messages(negotiation.received(theirs))


async def cancelled(task: asyncio.Task[None], stopping: Peer) -> None:
    """End a peer task which is waiting on its session, and close that session."""
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    stopping.shutdown()


# ============================================================================
# the peer
# ============================================================================


def test_a_neighbour_configured_with_shutdown_starts_disabled() -> None:
    assert peer(shutdown=True).disabled()
    assert not peer(shutdown=False).disabled()


@pytest.mark.rfc('rfc4486#4-administrative-shutdown')
def test_disable_closes_the_session_with_an_administrative_shutdown() -> None:
    disabled = peer()
    notify = Notify(CEASE, ADMINISTRATIVE_SHUTDOWN, 'maintenance')

    disabled.disable(notify)

    assert disabled.disabled()
    assert disabled._teardown is notify
    assert not disabled.stopping(), 'a disabled peer stays in the reactor'


def test_enable_withdraws_a_disable_the_session_has_not_acted_on() -> None:
    """Otherwise the next session would be torn down as soon as it is established."""
    bounced = peer()
    bounced.disable(Notify(CEASE, ADMINISTRATIVE_SHUTDOWN))

    bounced.enable()

    assert not bounced.disabled()
    assert bounced._teardown is None


def test_enable_leaves_any_other_teardown_alone() -> None:
    reset = peer(shutdown=True)
    notify = Notify(CEASE, 4)
    reset.teardown(notify)

    reset.enable()

    assert reset._teardown is notify


@pytest.mark.rfc('rfc4486#4-connection-rejected')
def test_an_incoming_connection_is_rejected_while_disabled() -> None:
    connection, theirs = incoming()
    try:
        writing = peer(shutdown=True).handle_connection(connection)
        assert writing is not None, 'the connection was accepted'
        for _ in writing:
            pass

        # the NOTIFICATION crosses the loopback before it can be read, wait for it to arrive
        select.select([theirs], [], [], PATIENCE_SECONDS)
        ((kind, body),) = sent_to(theirs)
        assert kind == NOTIFICATION
        assert (body[0], body[1]) == (CEASE, CONNECTION_REJECTED)
    finally:
        connection.close()
        theirs.close()


def test_an_incoming_connection_is_accepted_once_enabled() -> None:
    enabled = peer(shutdown=True)
    enabled.enable()
    connection, theirs = incoming()
    try:
        assert enabled.handle_connection(connection) is None
        assert enabled.proto is not None
        assert enabled.proto.connection is connection
        assert sent_to(theirs) == [], 'the accepted connection was sent a message'
    finally:
        connection.close()
        theirs.close()


def test_a_disabled_peer_does_not_connect_until_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """The peer is pointed at a port the test listens on, so a connection is seen arrive."""
    # CLI encoding tests leave the global environment passive; this scenario opens a connection.
    monkeypatch.setattr(getenv().bgp, 'passive', False)
    with socket.create_server(('127.0.0.1', 0)) as listener:
        listener.setblocking(False)
        neighbor = neighbour(shutdown=True, peer_address='127.0.0.1')
        neighbor.session.connect = listener.getsockname()[1]
        built, _ = negotiation.reactor()
        waiting = Peer(neighbor, built)

        async def scenario() -> None:
            task = asyncio.create_task(waiting.run())
            try:
                await asyncio.sleep(0.3)
                with pytest.raises(BlockingIOError):
                    listener.accept()[0].close()  # a disabled peer connected
                waiting.enable()
                accepted, _ = await asyncio.wait_for(
                    asyncio.get_running_loop().sock_accept(listener), timeout=PATIENCE_SECONDS
                )
                accepted.close()
            finally:
                await cancelled(task, waiting)

        asyncio.run(scenario())


def test_a_disable_with_no_session_leaves_nothing_behind() -> None:
    """The teardown disable() set has nothing to close, and must not close the next one."""
    parked = peer()
    parked.disable(Notify(CEASE, ADMINISTRATIVE_SHUTDOWN))

    async def scenario() -> None:
        task = asyncio.create_task(parked.run())
        await asyncio.sleep(0.3)
        assert parked._teardown is None
        parked.stop()
        await asyncio.wait_for(task, timeout=PATIENCE_SECONDS)

    asyncio.run(scenario())


def test_a_reload_while_disabled_is_applied_without_a_session() -> None:
    """reestablish() leaves its Cease and the new neighbour for _reset, which only a session
    reaches.  A disabled peer has none, so the Cease closed the first session after enable,
    which was also opened with the neighbour the reload had replaced."""
    parked = peer(shutdown=True)
    replacement = neighbour(shutdown=True)
    parked.reestablish(replacement)

    async def scenario() -> None:
        task = asyncio.create_task(parked.run())
        await asyncio.sleep(0.3)
        assert parked._teardown is None
        assert parked.neighbor is replacement
        parked.stop()
        await asyncio.wait_for(task, timeout=PATIENCE_SECONDS)

    asyncio.run(scenario())


def test_a_connection_accepted_just_before_the_disable_is_not_parked() -> None:
    """It has to go on to the session, which the Cease is sent over: here its OPEN is seen."""
    accepted = peer()
    accepted.proto = Protocol(accepted)
    theirs = negotiation.connect(accepted.proto)
    accepted.disable(Notify(CEASE, ADMINISTRATIVE_SHUTDOWN))

    async def scenario() -> None:
        task = asyncio.create_task(accepted.run())
        seen: list[tuple[int, bytes]] = []
        # bounded: polls until the OPEN arrives or the patience runs out
        for _ in range(int(PATIENCE_SECONDS / 0.05)):
            seen += sent_to(theirs)
            if seen:
                break
            await asyncio.sleep(0.05)
        await cancelled(task, accepted)
        assert [kind for kind, _ in seen] == [OPEN], 'the accepted connection was parked'

    try:
        asyncio.run(scenario())
    finally:
        theirs.close()


def test_a_disabled_peer_removed_from_the_configuration_still_goes() -> None:
    """stop() has to end the loop a disabled peer waits in, or the reactor keeps it."""
    removed = peer(shutdown=True)
    removed.remove()

    asyncio.run(asyncio.wait_for(removed.run(), timeout=PATIENCE_SECONDS))


# ============================================================================
# the reactor
# ============================================================================


def reactor_with(**peers: Peer) -> Reactor:
    reactor, _ = negotiation.reactor()
    reactor._peers = dict(peers)
    return reactor


def test_a_disabled_peer_with_no_session_is_not_given_a_turn() -> None:
    """Its routes wait for it: a reload waiting for them to be sent would never happen."""
    reactor = reactor_with(disabled=peer(shutdown=True), enabled=peer())

    assert reactor.active_peers() == {'enabled'}


def test_a_disabled_peer_still_closing_its_session_is_given_a_turn() -> None:
    closing = peer()
    closing.proto = Protocol(closing)
    closing.disable(Notify(CEASE, ADMINISTRATIVE_SHUTDOWN))

    assert reactor_with(closing=closing).active_peers() == {'closing'}


@pytest.mark.parametrize(
    ('before', 'after', 'disabled'),
    [
        (False, True, True),
        (True, False, False),
    ],
)
def test_a_reload_applies_a_changed_shutdown(before: bool, after: bool, disabled: bool) -> None:
    reloaded = peer(shutdown=before)

    Reactor._reload_shutdown(reloaded, neighbour(shutdown=after))

    assert reloaded.disabled() is disabled


@pytest.mark.parametrize('shutdown', [False, True])
def test_a_reload_which_kept_shutdown_keeps_what_the_api_did(shutdown: bool) -> None:
    changed = peer(shutdown=shutdown)
    if shutdown:
        changed.enable()
    else:
        changed.disable(Notify(CEASE, ADMINISTRATIVE_SHUTDOWN))

    Reactor._reload_shutdown(changed, neighbour(shutdown=shutdown))

    assert changed.disabled() is not shutdown


# ============================================================================
# the API
# ============================================================================


class Answered:
    """A reactor holding one peer, and the lines its Processes answered SERVICE with.

    No helper runs: SERVICE is registered with the Processes in asynchronous mode, where
    a write is queued rather than sent, and the queue is what the test reads.
    """

    def __init__(self) -> None:
        self.reactor, _ = negotiation.reactor()
        self.peer = peer(reactor=self.reactor)
        self.reactor._peers = {'peer': self.peer}
        processes = self.reactor.processes
        processes._process[SERVICE] = None  # type: ignore[assignment]
        processes._ack[SERVICE] = True
        processes._ackjson[SERVICE] = False
        processes._async_mode = True

    def lines(self) -> list[str]:
        queued = self.reactor.processes._write_queue.get(SERVICE, [])
        return [line.decode('ascii').rstrip('\n') for line in queued]


def called(handler: Any, arguments: str) -> tuple[bool, Answered]:
    answered = Answered()
    return handler(answered.reactor.api, answered.reactor, SERVICE, ['peer'], arguments, False), answered


def test_disable_sends_the_text_as_the_shutdown_communication() -> None:
    answered, reactor = called(disable, '"back at 18:00"')

    assert answered is True
    notify = reactor.peer._disable
    assert notify is not None
    assert reactor.peer._teardown is notify
    assert (notify.code, notify.subcode, notify.data) == (CEASE, ADMINISTRATIVE_SHUTDOWN, b'\x0dback at 18:00')
    assert reactor.lines() == ['done']


def test_disable_with_no_text() -> None:
    _, reactor = called(disable, '')

    notify = reactor.peer._disable
    assert notify is not None
    assert notify.data == b''


def test_disable_refuses_an_unbalanced_quote() -> None:
    answered, reactor = called(disable, '"unbalanced')

    assert answered is False
    assert not reactor.peer.disabled()
    assert reactor.lines()[-1] == 'error'
    assert reactor.lines().count('error') == 1


def test_enable_is_passed_on() -> None:
    answered, reactor = called(enable, '')

    assert answered is True
    assert reactor.lines() == ['done']


def test_enable_is_passed_on_to_a_disabled_peer() -> None:
    answered = Answered()
    answered.peer.disable(Notify(CEASE, ADMINISTRATIVE_SHUTDOWN))

    assert enable(answered.reactor.api, answered.reactor, SERVICE, ['peer'], '', False) is True
    assert not answered.peer.disabled()


def test_enable_refuses_an_argument() -> None:
    answered = Answered()
    answered.peer.disable(Notify(CEASE, ADMINISTRATIVE_SHUTDOWN))

    assert enable(answered.reactor.api, answered.reactor, SERVICE, ['peer'], 'now', False) is False
    assert answered.peer.disabled()
    assert answered.lines()[-1] == 'error'


NAME = 'neighbor 127.0.0.1 local-ip 127.0.0.2 local-as 1 peer-as 1 router-id 1.1.1.1 family-allowed in-open'


def named_reactor() -> Reactor:
    """A reactor holding one peer, under the name the command selectors are matched against."""
    reactor, _ = negotiation.reactor()
    reactor._peers = {NAME: peer(reactor=reactor)}
    return reactor


@pytest.mark.parametrize(
    ('command', 'handler', 'arguments'),
    [
        ('peer 127.0.0.1 disable "back soon"', disable, '"back soon"'),
        ('peer * enable', enable, ''),
    ],
)
def test_the_v6_commands(command: str, handler: Any, arguments: str) -> None:
    assert dispatch_v6(command, named_reactor(), SERVICE) == (handler, [NAME], arguments)


@pytest.mark.parametrize(
    ('command', 'handler', 'arguments'),
    [
        ('neighbor 127.0.0.1 disable maintenance', disable, 'maintenance'),
        ('neighbor 127.0.0.1 enable', enable, ''),
    ],
)
def test_the_v4_commands(command: str, handler: Any, arguments: str) -> None:
    assert dispatch_v4(command, named_reactor(), SERVICE) == (handler, [NAME], arguments)


# ============================================================================
# the configuration
# ============================================================================


def configured(shutdown: str) -> bool:
    line = f'    shutdown {shutdown};\n' if shutdown else ''
    configuration = Configuration(
        [
            'neighbor 127.0.0.1 {\n'
            '    router-id 1.1.1.1;\n'
            '    local-address 127.0.0.2;\n'
            '    local-as 1;\n'
            '    peer-as 1;\n'
            f'{line}'
            '}\n'
        ],
        text=True,
    )
    assert configuration.reload(), configuration.error
    (neighbor,) = configuration.neighbors.values()
    return neighbor.shutdown


def test_the_configuration_default_is_enabled() -> None:
    assert configured('') is False


@pytest.mark.parametrize(('value', 'expected'), [('true', True), ('false', False)])
def test_the_configuration_sets_it(value: str, expected: bool) -> None:
    assert configured(value) is expected
