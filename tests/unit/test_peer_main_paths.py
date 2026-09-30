"""The paths of Peer._main which no unit test reaches, and the order of one iteration.

Measured with branch coverage over the whole unit suite on 2026-09-29, `Peer._main` never
ran: a teardown already set when it starts, the ASM re-announce, a read which times out, a
ROUTE-REFRESH or a message neither handler takes, the loop leaving because a teardown was
set (either way it can leave), and everything after the loop, the Graceful Restart close
included.  The tests which do drive it end the session by raising out of `read_message`.

These tests pin what the method does on each before it is split into helpers
(plan-large-function-decomposition), and pin the order of the steps of one iteration, which
the functional suites depend on without saying so: the reload before the read, the
keepalive after it, the inbound handlers before anything is sent, then operational,
refresh, routes, End-of-RIB and the yield.  Everything `_main` delegates to is replaced by
a recorder, so what is pinned is the sequencing and what is passed along, not what the
helpers do: they have their own tests.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from exabgp.bgp.fsm import FSM
from exabgp.bgp.message import Message, Notify
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.check import _negotiated
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.peer.context import PeerContext
from exabgp.reactor.peer.handlers import RouteRefreshHandler, UpdateHandler
from exabgp.reactor.peer.peer import Peer
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB
from exabgp.bgp.message.message import MessageCode

SLOW = object()  # a read which does not answer within the 0.1s _main waits for


class Received:
    """A message as read_message returns it: only its ID is looked at by _main."""

    def __init__(self, code: MessageCode, label: str) -> None:
        self.ID = code
        self.label = label

    def __repr__(self) -> str:
        return self.label


UPDATE = Received(Message.CODE.UPDATE, 'update')
REFRESH = Received(Message.CODE.ROUTE_REFRESH, 'route-refresh')
KEEPALIVE = Received(Message.CODE.KEEPALIVE, 'keepalive')


@pytest.fixture(autouse=True)
def fresh_rib_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def neighbor(extra: str = '') -> Neighbor:
    config = Configuration(
        [
            f"""neighbor 192.0.2.1 {{
            router-id 192.0.2.2;
            local-address 192.0.2.2;
            local-as 65001;
            peer-as 65002;
            family {{ ipv4 unicast; }}
            {extra}
        }}"""
        ],
        text=True,
    )
    assert config.reload(), str(config.error)
    configured: Neighbor = next(iter(config.neighbors.values()))
    return configured


def established(configured: Neighbor) -> Peer:
    negotiated, _ = _negotiated(configured)
    peer = Peer(configured, Mock())
    peer.proto = Protocol(peer)
    peer.proto.negotiated = negotiated
    peer.proto.connection = Mock()
    peer.recv_timer = Mock()
    peer.fsm.change(FSM.ESTABLISHED)
    return peer


class Run:
    """Runs Peer._main with every collaborator recording what it was asked, in order."""

    def __init__(self, peer: Peer, reads: list[Any], pending: bool = True) -> None:
        self.peer = peer
        self.reads = list(reads)
        self.pending = pending
        self.events: list[str] = []
        self.contexts: list[PeerContext] = []
        self.route_calls: list[tuple[Any, ...]] = []
        self.eor_calls: list[tuple[Any, ...]] = []
        self.generator = object()
        self.statistics_lines: list[str] = []

    async def read_message(self) -> Any:
        self.events.append('read')
        step = self.reads.pop(0) if self.reads else EOFError('script exhausted')
        if callable(step):
            step = step()
        if isinstance(step, BaseException):
            raise step
        if step is SLOW:
            await asyncio.sleep(1)
        return step

    def record(self, name: str, result: Any = None) -> Callable[..., Any]:
        def recorder(*args: Any, **kwargs: Any) -> Any:
            self.events.append(name)
            return result

        return recorder

    def handler(self, name: str) -> Callable[..., Any]:
        async def handle(_handler: Any, ctx: PeerContext, message: Received) -> None:
            self.events.append(f'{name} {message!r}')
            self.contexts.append(ctx)

        return handle

    async def routes(self, new_routes: Any, include_withdraw: bool, per_iteration: int) -> tuple[Any, bool]:
        self.events.append('routes')
        self.route_calls.append((new_routes, include_withdraw, per_iteration))
        return self.generator, True

    async def eors(self, send_eor: bool, new_routes: Any) -> bool:
        self.events.append('eor')
        self.eor_calls.append((send_eor, new_routes))
        return False

    def statistics(self) -> Iterator[str]:
        self.events.append('statistics')
        return iter(self.statistics_lines)

    def check_ka(self, message: Any = None) -> None:
        self.events.append(f'check_ka {message!r}')

    async def go(self) -> BaseException:
        peer = self.peer
        assert peer.proto is not None
        assert peer.recv_timer is not None
        # the RIB is compiled (plan/wip-mypyc.md) and its methods can not be patched, so the
        # peer methods which call replace_restart and replace_reload are wrapped instead
        restore, reload = peer._restore_outgoing_rib, peer._apply_reload

        def restored() -> None:
            self.events.append('replace_restart')
            restore()

        def reloaded() -> None:
            if peer._neighbor:
                self.events.append('replace_reload')
            reload()

        with (
            patch.object(peer.recv_timer, 'check_ka', side_effect=self.check_ka),
            patch.object(peer.proto, 'read_message', side_effect=self.read_message),
            patch.object(peer, '_resume_incoming', side_effect=self.record('resume')),
            patch.object(peer, '_announce_up_to_the_api', side_effect=self.record('api-up')),
            patch.object(peer, '_restore_outgoing_rib', side_effect=restored),
            patch.object(peer, '_apply_reload', side_effect=reloaded),
            patch('exabgp.reactor.peer.peer.KA.send_if_needed', new=AsyncMock(side_effect=self.record('send_ka'))),
            patch.object(peer.stats, 'changed_statistics', side_effect=self.statistics),
            patch.object(UpdateHandler, 'handle_async', new=self.handler('update-handler')),
            patch.object(RouteRefreshHandler, 'handle_async', new=self.handler('refresh-handler')),
            patch.object(peer, '_send_operational_messages', new=AsyncMock(side_effect=self.record('operational'))),
            patch.object(peer, '_send_refresh_messages', new=AsyncMock(side_effect=self.record('refresh'))),
            patch.object(peer, '_send_route_updates', side_effect=self.routes),
            patch.object(peer, '_send_eor_messages', side_effect=self.eors),
            patch.object(peer, '_has_pending_work', side_effect=self.record('pending', self.pending)),
            patch.object(peer, '_close', side_effect=self.record('close')),
        ):
            try:
                await peer._main()
            except BaseException as raised:
                return raised
        raise AssertionError('_main returned instead of raising')


ITERATION = ['statistics']
OUTBOUND = ['operational', 'refresh', 'routes', 'eor', 'pending']
START = ['resume', 'api-up', 'replace_restart']


@pytest.mark.asyncio
async def test_one_iteration_runs_in_this_order() -> None:
    peer = established(neighbor())
    run = Run(peer, [UPDATE])
    raised = await run.go()
    assert isinstance(raised, EOFError)
    assert run.events == [
        *START,
        'read',
        'check_ka update',
        'send_ka',
        'statistics',
        'update-handler update',
        *OUTBOUND,
        'read',
    ]
    assert peer.stats['up'] == 1
    assert peer.neighbor.previous is None


@pytest.mark.asyncio
async def test_a_route_refresh_goes_to_its_handler_and_a_keepalive_to_none() -> None:
    peer = established(neighbor())
    run = Run(peer, [REFRESH, KEEPALIVE])
    raised = await run.go()
    assert isinstance(raised, EOFError)
    assert run.events == [
        *START,
        'read',
        'check_ka route-refresh',
        'send_ka',
        'statistics',
        'refresh-handler route-refresh',
        *OUTBOUND,
        'read',
        'check_ka keepalive',
        'send_ka',
        'statistics',
        *OUTBOUND,
        'read',
    ]


@pytest.mark.asyncio
async def test_a_read_which_times_out_is_no_message() -> None:
    peer = established(neighbor())
    run = Run(peer, [SLOW])
    raised = await run.go()
    assert isinstance(raised, EOFError)
    assert run.events == [*START, 'read', 'check_ka None', 'send_ka', 'statistics', *OUTBOUND, 'read']


@pytest.mark.asyncio
async def test_the_handlers_share_one_context_built_from_the_session() -> None:
    peer = established(neighbor())
    run = Run(peer, [UPDATE, REFRESH])
    await run.go()
    first, second = run.contexts
    assert first is second
    assert first.proto is peer.proto
    assert first.neighbor is peer.neighbor
    assert peer.proto is not None
    assert first.negotiated is peer.proto.negotiated
    assert first.refresh_enhanced is False
    assert first.routes_per_iteration == 25
    assert first.peer_id == peer.id()
    assert first.stats is peer.stats


@pytest.mark.asyncio
async def test_the_outbound_state_is_carried_from_one_iteration_to_the_next() -> None:
    peer = established(neighbor())
    run = Run(peer, [None, None])
    await run.go()
    assert run.route_calls == [(None, False, 25), (run.generator, True, 25)]
    # send_eor starts as `not manual_eor`, then is what _send_eor_messages returned
    assert run.eor_calls == [(True, run.generator), (False, run.generator)]


@pytest.mark.asyncio
async def test_a_rate_limit_sends_one_route_per_iteration() -> None:
    configured = neighbor()
    configured.rate_limit = 10
    configured.manual_eor = True
    peer = established(configured)
    run = Run(peer, [UPDATE])
    await run.go()
    assert run.route_calls == [(None, False, 1)]
    assert run.eor_calls == [(False, run.generator)]
    assert run.contexts[0].routes_per_iteration == 1


@pytest.mark.asyncio
async def test_a_teardown_set_before_the_loop_is_raised_at_once() -> None:
    peer = established(neighbor())
    teardown = Notify(6, 3)
    peer._teardown = teardown
    run = Run(peer, [])
    raised = await run.go()
    assert raised is teardown
    assert run.events == []
    assert peer.stats.get('up', 0) == 0


@pytest.mark.asyncio
async def test_asm_messages_of_negotiable_families_are_put_first() -> None:
    configured = neighbor()
    ipv4 = (AFI.ipv4, SAFI.unicast)
    ipv6 = (AFI.ipv6, SAFI.unicast)
    assert ipv4 in configured.families()
    assert ipv6 not in configured.families()
    configured.asm[ipv4] = 'asm ipv4'  # type: ignore[assignment]
    configured.asm[ipv6] = 'asm ipv6'  # type: ignore[assignment]
    configured.messages.append('queued')  # type: ignore[arg-type]
    peer = established(configured)
    seen: list[list[Any]] = []

    def snapshot() -> BaseException:
        seen.append(list(peer.neighbor.messages))
        return EOFError('stop')

    run = Run(peer, [snapshot])
    await run.go()
    assert seen == [['asm ipv4', 'queued']]


@pytest.mark.asyncio
async def test_a_reload_is_applied_before_the_next_read() -> None:
    peer = established(neighbor())
    replacement = neighbor()
    replacement.previous = peer.neighbor

    def reload() -> None:
        peer._neighbor = replacement
        return None

    run = Run(peer, [reload, None])
    await run.go()
    after_first = run.events.index('pending') + 1
    assert run.events[after_first : after_first + 2] == ['replace_reload', 'read']
    assert run.events.count('replace_reload') == 1
    assert peer._neighbor is None
    assert replacement.previous is None


@pytest.mark.asyncio
async def test_a_teardown_with_no_pending_work_ends_the_loop_and_is_raised() -> None:
    peer = established(neighbor())
    teardown = Notify(6, 3)

    def stop() -> None:
        peer._teardown = teardown
        return None

    run = Run(peer, [stop], pending=False)
    raised = await run.go()
    assert raised is teardown
    assert run.events == [*START, 'read', 'check_ka None', 'send_ka', 'statistics', *OUTBOUND]


@pytest.mark.asyncio
async def test_a_teardown_with_pending_work_ends_the_loop_at_the_next_check() -> None:
    peer = established(neighbor())
    teardown = Notify(6, 3)

    def stop() -> None:
        peer._teardown = teardown
        return None

    run = Run(peer, [stop], pending=True)
    raised = await run.go()
    assert raised is teardown
    assert run.events == [*START, 'read', 'check_ka None', 'send_ka', 'statistics', *OUTBOUND]


@pytest.mark.asyncio
async def test_graceful_restart_closes_without_a_notification() -> None:
    peer = established(neighbor('capability { graceful-restart 120; }'))
    assert peer.neighbor.capability.graceful_restart

    def stop() -> None:
        peer._teardown = Notify(6, 3)
        return None

    run = Run(peer, [stop], pending=False)
    raised = await run.go()
    assert type(raised) is NetworkError
    assert str(raised) == 'closing'
    assert run.events[-1] == 'close'


@pytest.mark.asyncio
async def test_a_network_error_is_logged_as_debug_and_raised_unchanged() -> None:
    peer = established(neighbor())
    lost = NetworkError('lost')
    run = Run(peer, [lost])
    with patch('exabgp.reactor.peer.peer.log') as log:
        raised = await run.go()
    assert raised is lost
    assert not log.error.called
    assert log.debug.call_count >= 1


@pytest.mark.asyncio
async def test_any_other_exception_is_logged_as_an_error_and_raised_unchanged() -> None:
    peer = established(neighbor())
    broken = ValueError('broken')
    run = Run(peer, [broken])
    with patch('exabgp.reactor.peer.peer.log') as log:
        raised = await run.go()
    assert raised is broken
    assert log.error.call_count == 1


@pytest.mark.asyncio
async def test_a_notify_from_the_loop_is_raised_unchanged() -> None:
    peer = established(neighbor())
    notify = Notify(3, 1, 'malformed')
    run = Run(peer, [notify])
    raised = await run.go()
    assert raised is notify


@pytest.mark.asyncio
async def test_no_pending_work_and_no_teardown_goes_round_again() -> None:
    peer = established(neighbor())
    run = Run(peer, [None], pending=False)
    raised = await run.go()
    assert isinstance(raised, EOFError)
    assert run.events == [*START, 'read', 'check_ka None', 'send_ka', 'statistics', *OUTBOUND, 'read']


@pytest.mark.asyncio
async def test_each_changed_statistic_is_logged_on_the_statistics_channel() -> None:
    peer = established(neighbor())
    run = Run(peer, [None])
    run.statistics_lines = ['statistics for up counter 1', 'statistics for down counter 0']
    with patch('exabgp.reactor.peer.peer.log') as log:
        await run.go()
    channels = [call.args[1] for call in log.info.call_args_list]
    # one per line: the second iteration ends at its read, before the statistics
    assert channels.count('statistics') == 2
