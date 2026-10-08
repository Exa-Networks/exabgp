"""The paths of Peer._main which no unit test reaches, and the order of one iteration.

Measured with branch coverage over the whole unit suite on 2026-09-29, `Peer._main` never
ran: a teardown already set when it starts, the ASM re-announce, a read which times out, a
ROUTE-REFRESH or a message neither handler takes, the loop leaving because a teardown was
set (either way it can leave), and everything after the loop, the Graceful Restart close
included.

These tests pin what the method does on each, and the order of the steps of one iteration,
which the functional suites depend on without saying so: the inbound handlers before
anything is sent, then operational, refresh, routes and End-of-RIB.

The session is a real one.  The Peer, its Protocol and its Reactor are the production
classes, the connection is one end of a socket pair, and the other end is the BGP peer:
what it sends is read by the production framing, and what exabgp writes is read back from
it.  They were recorders patched over the methods of the Peer, which the compiled build
(plan/wip-mypyc.md) does not allow, and a recorder pins what it records rather than what
the peer does.

The order is read off a Timeline: the API encoder of the Reactor, which each time exabgp
tells its API something (the session is up, a message was received) first takes whatever
exabgp wrote to the peer so far.  So every message sent is placed before or after every
message received, as it happened.  A KEEPALIVE from the peer is one message read, so a
peer which sends N of them up front drives N iterations, each opened by `told keepalive`.
"""

from __future__ import annotations

import asyncio
import socket
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest

from exabgp.bgp.fsm import FSM
from exabgp.bgp.message import KeepAlive, Notify, Operational, Update, UpdateCollection
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.operational import Advisory
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.neighbor import Neighbor
from exabgp.bgp.timer import ReceiveTimer
from exabgp.configuration.check import _negotiated
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB
from tests import negotiation

# what test_one_iteration_runs_in_this_order sends: an operational message and a refresh
SENDING_ALL = 'capability { route-refresh enable; operational enable; }'

# the name of each message type exabgp can write, as the timeline records it
SENT = {1: 'open', 2: 'update', 3: 'notification', 4: 'keepalive', 5: 'refresh', 6: 'operational'}

# RFC 4724 2: an IPv4 unicast End-of-RIB is an UPDATE with nothing in it, four octets of body
EOR_BODY = bytes(4)

# the API events a session is heard on: up, and every message received, parsed
HEARD = ('neighbor-changes', 'receive-parsed', 'receive-update', 'receive-refresh', 'receive-keepalive')

# how long a scenario waits for what it expects before failing, rather than hanging
PATIENCE_SECONDS = 5.0
POLL_SECONDS = 0.01

IPV4 = (AFI.ipv4, SAFI.unicast)
IPV6 = (AFI.ipv6, SAFI.unicast)


@pytest.fixture(autouse=True)
def fresh_rib_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


class Timeline(negotiation.Told):
    """The API encoder: each event told is placed after what had been written to the peer.

    `hooks` maps an event to what to do when it is told, the way a peer or an operator acts
    in the middle of an iteration.  A hook runs inside the read which told it.
    """

    def __init__(self, theirs: socket.socket) -> None:
        super().__init__()
        self.theirs = theirs
        self.events: list[str] = []
        self.written: list[tuple[int, bytes]] = []
        self.hooks: dict[str, Callable[[], None]] = {}
        self._pending = b''

    def drain(self) -> None:
        """Place on the timeline every message exabgp wrote to the peer since the last look."""
        self._pending += negotiation.received(self.theirs)
        # bounded: each pass removes one message of at least a 19 octet header
        while len(self._pending) >= 19:
            length = int.from_bytes(self._pending[16:18], 'big')
            if len(self._pending) < length:
                break
            kind, body = self._pending[18], self._pending[19:length]
            self._pending = self._pending[length:]
            self.written.append((kind, body))
            name = 'eor' if (kind, body) == (2, EOR_BODY) else SENT.get(kind, str(kind))
            self.events.append(f'sent {name}')

    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(name)

        def record(*args: Any) -> str:
            self.drain()
            self.calls.append((name, args))
            self.events.append(f'told {name}')
            hook = self.hooks.pop(f'told {name}', None)
            if hook is not None:
                hook()
            return ''

        return record


def configuration(extra: str = '', routes: int = 1) -> Configuration:
    statics = ''.join(f'route 10.0.{index}.0/24 next-hop 192.0.2.2 med {index};\n' for index in range(routes))
    config = Configuration(
        [
            f"""neighbor 192.0.2.1 {{
            router-id 192.0.2.2;
            local-address 192.0.2.2;
            local-as 65001;
            peer-as 65002;
            adj-rib-in true;
            family {{ ipv4 unicast; }}
            static {{ {statics} }}
            {extra}
        }}"""
        ],
        text=True,
    )
    assert config.reload(), str(config.error)
    return config


def neighbor(extra: str = '', routes: int = 1) -> Neighbor:
    configured: Neighbor = next(iter(configuration(extra, routes).neighbors.values()))
    # a route from the peer carries none of its AS in the path: RFC 4271 6.3 has its own tests
    configured.enforce_first_as = False
    return configured


class Session:
    """An established session of a real Peer, with the peer end of its connection."""

    def __init__(self, configured: Neighbor) -> None:
        negotiation.api_asks(configured, *HEARD)
        self.negotiated: Negotiated
        self.negotiated, _ = _negotiated(configured)
        self.peer, _ = negotiation.peer(configured)
        self.peer.proto = Protocol(self.peer)
        self.peer.proto.negotiated = self.negotiated
        self.theirs = negotiation.connect(self.peer.proto)
        self.timeline = Timeline(self.theirs)
        self.peer.reactor.processes._encoder[negotiation.PROCESS] = self.timeline
        connection = self.peer.proto.connection
        assert connection is not None
        self.peer.recv_timer = ReceiveTimer(connection.session, self.negotiated.holdtime, 4, 0)
        self.peer.fsm.change(FSM.ESTABLISHED)
        self.task: asyncio.Task[int] | None = None

    @property
    def events(self) -> list[str]:
        return self.timeline.events

    def send(self, *messages: Any) -> None:
        """The peer sends these messages."""
        for message in messages:
            self.theirs.sendall(message.pack_message(self.negotiated))

    def update(self, prefix: str = '10.9.0.0/24') -> Update:
        """An UPDATE from the peer, announcing `prefix`."""
        (route,) = configuration().parse_route_text(f'route {prefix} next-hop 192.0.2.1')
        collection = UpdateCollection([RoutedNLRI(route.nlri, route.nexthop)], [], route.attributes)
        (wire,) = collection.messages(self.negotiated)
        update = Update.unpack_message(wire[19:], self.negotiated)
        assert type(update) is Update
        return update

    async def until(self, done: Callable[[], bool]) -> None:
        """Wait, looking at the wire, until `done` holds."""
        # bounded: polls until the patience runs out
        for _ in range(int(PATIENCE_SECONDS / POLL_SECONDS)):
            self.timeline.drain()
            if done():
                return
            await asyncio.sleep(POLL_SECONDS)
        raise AssertionError(f'never happened, the timeline is {self.events}')

    async def sent(self, *events: str) -> None:
        """Wait until the timeline ends with `events`."""
        await self.until(lambda: self.events[-len(events) :] == list(events))

    def hang_up(self) -> None:
        """The peer closes the connection, which ends the session with a NetworkError."""
        if self.theirs.fileno() == -1:
            return
        self.timeline.drain()
        self.theirs.close()

    async def ended(self) -> None:
        """Wait until _main has ended."""
        await self.until(lambda: self.task is not None and self.task.done())

    async def run(self, drive: Callable[[Session], Any] | None = None) -> BaseException:
        """Run _main until it raises, while `drive` plays the peer, then hang up."""
        task = asyncio.create_task(self.peer._main())
        self.task = task
        try:
            if drive is not None:
                await drive(self)
            if not task.done():
                self.hang_up()
            await asyncio.wait_for(asyncio.shield(task), timeout=PATIENCE_SECONDS)
        except BaseException as raised:
            if task.done():
                return raised
            task.cancel()
            raise
        finally:
            self.hang_up()
        raise AssertionError('_main returned instead of raising')


def announced(body: bytes) -> list[str]:
    """The IPv4 prefixes in the NLRI field of an UPDATE body, as a.b.c.d/len."""
    withdrawn = int.from_bytes(body[0:2], 'big')
    attributes = int.from_bytes(body[2 + withdrawn : 4 + withdrawn], 'big')
    nlri = body[4 + withdrawn + attributes :]
    prefixes = []
    # bounded: each prefix takes at least its length octet
    while nlri:
        length = nlri[0]
        size = (length + 7) // 8
        address = bytes(nlri[1 : 1 + size]).ljust(4, b'\0')
        prefixes.append('.'.join(str(octet) for octet in address) + f'/{length}')
        nlri = nlri[1 + size :]
    return prefixes


def keepalive() -> KeepAlive:
    return KeepAlive.make_keepalive()


def refresh() -> RouteRefresh:
    return RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast)


def advisory(afi: AFI, text: str) -> Operational:
    return Advisory.ASM.make_advisory(afi, SAFI.unicast, text)


UP = 'told up'


@pytest.mark.asyncio
async def test_one_iteration_runs_in_this_order() -> None:
    """What was read is handled, then operational, refresh, routes and End-of-RIB go out."""
    configured = neighbor(SENDING_ALL)
    configured.messages.append(advisory(AFI.ipv4, 'queued'))
    configured.refresh.append(refresh())
    session = Session(configured)
    session.send(session.update())

    async def drive(session: Session) -> None:
        await session.sent('sent eor')

    raised = await session.run(drive)
    assert isinstance(raised, NetworkError)
    assert session.events == [
        UP,
        'told update',
        'sent operational',
        'sent refresh',
        'sent update',
        'sent eor',
    ]
    assert session.peer.stats['up'] == 1
    assert session.peer.neighbor.previous is None


@pytest.mark.asyncio
async def test_a_route_refresh_goes_to_its_handler_and_a_keepalive_to_none() -> None:
    session = Session(neighbor())

    async def drive(session: Session) -> None:
        await session.sent('sent eor')
        session.send(refresh(), keepalive())
        await session.sent('told keepalive')
        # one more iteration, to see the keepalive was given to nobody who sends anything
        session.send(keepalive())
        await session.sent('told keepalive', 'told keepalive')

    await session.run(drive)
    assert session.events == [
        UP,
        'sent update',
        'sent eor',
        'told refresh',
        # the handler resent the routes, without the RFC 7313 markers on a plain refresh
        'sent update',
        'told keepalive',
        'told keepalive',
    ]


@pytest.mark.asyncio
async def test_a_read_which_times_out_is_no_message() -> None:
    """The peer sends nothing: each read times out, and what is to send is still sent."""
    session = Session(neighbor())

    async def drive(session: Session) -> None:
        await session.sent('sent eor')

    raised = await session.run(drive)
    assert isinstance(raised, NetworkError)
    assert session.events == [UP, 'sent update', 'sent eor']


@pytest.mark.asyncio
async def test_the_handlers_share_one_context_built_from_the_session() -> None:
    """Both handlers act on this session: its neighbor's RIB, its statistics, a plain refresh."""
    session = Session(neighbor())
    session.send(session.update())

    async def drive(session: Session) -> None:
        await session.sent('sent eor')
        session.send(refresh())
        await session.sent('told refresh', 'sent update')

    await session.run(drive)
    stored = [str(route.nlri.cidr) for route in session.peer.neighbor.rib.incoming.cached_routes()]
    assert stored == ['10.9.0.0/24']
    assert session.peer.stats['receive-prefixes'] == 1
    # not enhanced: no Begin-of-RIB-Refresh (a ROUTE-REFRESH) was sent around the routes
    assert session.events.count('sent refresh') == 0


@pytest.mark.asyncio
async def test_the_outbound_state_is_carried_from_one_iteration_to_the_next() -> None:
    """Thirty routes at 25 an iteration: the second iteration carries on, then End-of-RIB."""
    session = Session(neighbor(routes=30))
    session.send(keepalive(), keepalive())

    async def drive(session: Session) -> None:
        await session.sent('sent eor')

    await session.run(drive)
    assert session.events == [
        UP,
        'told keepalive',
        *['sent update'] * 25,
        'told keepalive',
        *['sent update'] * 5,
        'sent eor',
    ]


@pytest.mark.asyncio
async def test_a_rate_limit_sends_one_route_per_iteration() -> None:
    configured = neighbor(routes=3)
    configured.rate_limit = 10
    configured.manual_eor = True
    session = Session(configured)
    session.send(keepalive(), keepalive(), keepalive())

    async def drive(session: Session) -> None:
        await session.until(lambda: session.events.count('sent update') == 3)

    await session.run(drive)
    assert session.events == [UP, *['told keepalive', 'sent update'] * 3]


@pytest.mark.asyncio
async def test_a_teardown_set_before_the_loop_is_raised_at_once() -> None:
    session = Session(neighbor())
    teardown = Notify(6, 3)
    session.peer._teardown = teardown
    session.send(keepalive())

    raised = await session.run()
    assert raised is teardown
    assert session.events == []
    assert session.peer.stats.get('up', 0) == 0


@pytest.mark.asyncio
async def test_asm_messages_of_negotiable_families_are_put_first() -> None:
    configured = neighbor('capability { operational enable; }', routes=0)
    assert IPV4 in configured.families()
    assert IPV6 not in configured.families()
    configured.asm[IPV4] = advisory(AFI.ipv4, 'asm ipv4')
    configured.asm[IPV6] = advisory(AFI.ipv6, 'asm ipv6')
    queued = advisory(AFI.ipv4, 'queued')
    configured.messages.append(queued)
    session = Session(configured)
    # one operational message goes out per iteration: three iterations would show a third
    session.send(keepalive(), keepalive(), keepalive())

    async def drive(session: Session) -> None:
        await session.until(lambda: session.events.count('told keepalive') == 3)

    await session.run(drive)
    operational = [body for kind, body in session.timeline.written if kind == 6]
    expected = [configured.asm[IPV4], queued]
    assert operational == [bytes(message.pack_message(session.negotiated)[19:]) for message in expected]


@pytest.mark.asyncio
async def test_a_reload_is_applied_by_the_loop_once() -> None:
    """A reload while established reaches the outgoing RIB once, and nothing is left pending.

    The replacement is read from a configuration naming the same neighbor, so it shares
    the RIB of the session, as it does in the daemon: its routes are those the session sent.
    """
    session = Session(neighbor(routes=1))
    replacement = negotiation.api_asks(neighbor(routes=2), *HEARD)
    replacement.previous = session.peer.neighbor

    async def drive(session: Session) -> None:
        await session.sent('sent eor')
        session.peer.reconfigure(replacement)
        await session.until(lambda: session.events.count('sent update') == 3)
        # more iterations, to see the reload is not applied a second time
        session.send(keepalive(), keepalive())
        await session.sent('told keepalive', 'told keepalive')

    await session.run(drive)
    assert session.events == [
        UP,
        'sent update',
        'sent update',
        'sent eor',
        'sent update',
        'told keepalive',
        'told keepalive',
    ]
    # the reload replayed the route the new configuration added, the other is where it was
    last = [body for kind, body in session.timeline.written if kind == 2][-1]
    assert announced(last) == ['10.0.1.0/24']
    assert session.peer._neighbor is None
    assert session.peer.neighbor is replacement
    assert replacement.previous is None


@pytest.mark.asyncio
async def test_a_teardown_with_no_pending_work_ends_the_loop_and_is_raised() -> None:
    """Nothing is read and nothing is left to send when the loop next looks."""
    session = Session(neighbor())
    teardown = Notify(6, 3)

    raised = await session.run(stop_after_teardown(teardown))
    assert raised is teardown
    assert session.events == [UP, 'sent update', 'sent eor']


def stop_after_teardown(teardown: Notify) -> Callable[[Session], Any]:
    """Wait until the routes are sent, then ask for `teardown`, and wait for _main to end."""

    async def drive(session: Session) -> None:
        await session.sent('sent eor')
        session.peer._teardown = teardown
        await session.ended()

    return drive


@pytest.mark.asyncio
async def test_a_teardown_with_pending_work_ends_the_loop_at_the_next_check() -> None:
    """A message was read, so there is work pending: the loop still ends, and reads no more."""
    session = Session(neighbor())
    teardown = Notify(6, 3)
    session.timeline.hooks['told keepalive'] = lambda: setattr(session.peer, '_teardown', teardown)

    async def drive(session: Session) -> None:
        await session.sent('sent eor')
        session.send(keepalive(), keepalive())
        await session.ended()

    raised = await session.run(drive)
    assert raised is teardown
    assert session.events == [UP, 'sent update', 'sent eor', 'told keepalive']


@pytest.mark.asyncio
async def test_graceful_restart_closes_without_a_notification() -> None:
    session = Session(neighbor(extra='capability { graceful-restart 120; }'))
    assert session.peer.neighbor.capability.graceful_restart

    raised = await session.run(stop_after_teardown(Notify(6, 3)))
    assert type(raised) is NetworkError
    assert str(raised) == 'closing'
    assert session.peer.proto is None, 'the session was not closed'
    assert session.peer.fsm == FSM.IDLE
    assert 'sent notification' not in session.events


def operator_asks(act: Callable[[Session], None]) -> Callable[[Session], Any]:
    """Wait until the routes are sent, then act as an operator would, and wait for _main to end."""

    async def drive(session: Session) -> None:
        await session.sent('sent eor')
        act(session)
        await session.ended()

    return drive


@pytest.mark.rfc('rfc4486#4-administrative-shutdown')
@pytest.mark.parametrize(
    'act,cease',
    [
        (lambda session: session.peer.teardown(Notify(6, 4, 'reset by the operator')), (6, 4)),
        (lambda session: session.peer.disable(Notify(6, 2, 'disabled by the operator')), (6, 2)),
    ],
    ids=['teardown', 'disable'],
)
@pytest.mark.asyncio
async def test_graceful_restart_does_not_silence_an_operator_teardown(
    act: Callable[[Session], None], cease: tuple[int, int]
) -> None:
    """RFC 4486 4: an operator ending the peering is a Cease, Graceful Restart or not.

    Closed quietly, as for a restart of ours, the peer kept our routes as stale for the
    whole Restart Time, routes the operator had just asked to take away.
    """
    session = Session(neighbor(extra='capability { graceful-restart 120; }'))
    assert session.peer.neighbor.capability.graceful_restart

    raised = await session.run(operator_asks(act))
    assert isinstance(raised, Notify)
    assert (raised.code, raised.subcode) == cease


@pytest.mark.asyncio
async def test_graceful_restart_keeps_a_restart_of_ours_quiet() -> None:
    """The documented exception: a session re-established for a restart closes without a word."""
    session = Session(neighbor(extra='capability { graceful-restart 120; }'))

    raised = await session.run(operator_asks(lambda session: session.peer.reestablish()))
    assert type(raised) is NetworkError
    assert 'sent notification' not in session.events


@pytest.mark.asyncio
async def test_a_network_error_is_logged_as_debug_and_raised_unchanged() -> None:
    session = Session(neighbor())

    async def drive(session: Session) -> None:
        await session.sent('sent eor')

    with patch('exabgp.reactor.peer.peer.log') as log:
        raised = await session.run(drive)
    assert isinstance(raised, NetworkError)
    assert not log.error.called
    assert log.debug.call_count >= 1


@pytest.mark.asyncio
async def test_any_other_exception_is_logged_as_an_error_and_raised_unchanged() -> None:
    """The API encoder failing while a message is read is an error the loop does not know."""
    session = Session(neighbor())
    broken = ValueError('broken')

    def fail() -> None:
        raise broken

    session.timeline.hooks['told keepalive'] = fail
    session.send(keepalive())

    with patch('exabgp.reactor.peer.peer.log') as log:
        raised = await session.run(lambda session: session.sent('told keepalive'))
    assert raised is broken
    assert log.error.call_count == 1


@pytest.mark.asyncio
async def test_a_notify_from_the_loop_is_raised_unchanged() -> None:
    """A malformed header, the marker not all ones: RFC 4271 6.1, Connection Not Synchronized."""
    session = Session(neighbor())
    session.theirs.sendall(bytes(16) + (19).to_bytes(2, 'big') + bytes([4]))

    raised = await session.run(Session.ended)
    assert isinstance(raised, Notify)
    assert (raised.code, raised.subcode) == (1, 1)


@pytest.mark.asyncio
async def test_no_pending_work_and_no_teardown_goes_round_again() -> None:
    session = Session(neighbor())

    async def drive(session: Session) -> None:
        await session.sent('sent eor')
        # idle iterations: every read times out and there is nothing to send
        await asyncio.sleep(0.3)
        session.send(keepalive())
        await session.sent('told keepalive')

    raised = await session.run(drive)
    assert isinstance(raised, NetworkError)
    assert session.events == [UP, 'sent update', 'sent eor', 'told keepalive']


@pytest.mark.asyncio
async def test_each_changed_statistic_is_logged_on_the_statistics_channel() -> None:
    session = Session(neighbor())
    session.send(keepalive())

    with patch('exabgp.reactor.peer.peer.log') as log:
        await session.run(lambda session: session.sent('sent eor'))
    channels = [call.args[1] for call in log.info.call_args_list]
    lines = [call.args[0]() for call in log.info.call_args_list if call.args[1] == 'statistics']
    # the session up and the keepalive read changed a counter each, and each was logged once
    assert channels.count('statistics') == len(lines) >= 2
    assert any('statistics for up ' in line for line in lines), lines
    assert any('statistics for receive-keepalive ' in line for line in lines), lines


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['stop', 'retry', 'ephemeral'])
async def test_run_observes_teardown_after_await_and_preserves_retries(mode: str) -> None:
    """Only a restartable, consumed Cease opens another session after run resumes."""
    session = Session(neighbor(routes=0))
    peer = session.peer
    peer.neighbor.ephemeral = mode == 'ephemeral'
    peer.fsm.change(FSM.IDLE)
    assert session.negotiated.received_open is not None
    session.send(session.negotiated.received_open, keepalive())
    task = asyncio.create_task(peer.run())
    try:
        await session.sent('sent eor')
        if mode == 'retry':
            peer.teardown(Notify(6, 4))
            await session.until(lambda: peer.proto is None)
            assert not task.done(), 'a restartable teardown ended run'
            assert peer._teardown is None
            assert [body for kind, body in session.timeline.written if kind == 3] == [bytes([6, 4])]
            session.hang_up()
            peer.proto = Protocol(peer)
            session.theirs = negotiation.connect(peer.proto)
            session.timeline.theirs = session.theirs
            peer._delay.reset()
            session.send(session.negotiated.received_open, keepalive())
            await session.until(lambda: peer.stats['up'] == 2)
        if mode == 'ephemeral':
            peer.teardown(Notify(6, 4))
        else:
            peer.stop()
        await asyncio.wait_for(asyncio.shield(task), timeout=PATIENCE_SECONDS)
        session.timeline.drain()
        notifications = [body for kind, body in session.timeline.written if kind == 3]
        expected = [bytes([6, 4])] if mode == 'ephemeral' else [bytes([6, 3])]
        assert notifications == ([bytes([6, 4])] if mode == 'retry' else []) + expected
        assert peer.proto is None
        assert peer.fsm == FSM.IDLE
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        peer.shutdown()
        session.hang_up()
