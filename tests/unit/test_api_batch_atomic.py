"""The commands a helper writes together reach the outgoing RIB before a peer reads it

A helper which writes "announce A\\nwithdraw B\\n" in one go has handed the daemon both
before either could be sent, so the peer has to see them as one change: the withdraw
goes out first (outgoing.py orders a batch that way), and it never holds A without B
having gone. The reactor used to apply one command per loop pass, and a peer whose read
timeout expired in between flushed the announce on its own, so which of the two reached
the wire first came down to a timer (qa/encoding/conf-announce-withdraw.ci, test 2).

Two things close it, and each has its test here:
- the reactor takes every command queued since the last pass, not one
- a peer does not start a new batch, nor send an End-of-RIB, while those commands are
  being applied, unless one of them is waiting for that flush (the sync keyword)
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.environment import Environment
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.reactor.asynchronous import ASYNC
from exabgp.reactor.peer import Peer
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB
from exabgp.rib.route import Route
from tests import negotiation


@pytest.fixture
def processes():
    with patch('exabgp.reactor.api.processes.getenv') as getenv:
        environment = Environment()
        environment.api.respawn = False
        environment.api.terminate = False
        environment.api.ack = True
        environment.api.version = 6
        getenv.return_value = environment

        from exabgp.reactor.api.processes import Processes

        with patch('exabgp.reactor.api.processes.log', MagicMock()):
            yield Processes()


# ==============================================================================
# The reactor takes every queued command in one pass
# ==============================================================================


def test_every_queued_command_is_handed_out_in_one_pass(processes) -> None:
    processes._command_queue.append(('helper', 'announce route 2001:db8:2::/64 next-hop 2001:db8::1'))
    processes._command_queue.append(('helper', 'withdraw route 2001:db8:1::/64 next-hop 2001:db8::1'))

    assert [command.split()[0] for _, command in processes.received_async()] == ['announce', 'withdraw']
    assert not processes._command_queue


def test_a_pass_is_bounded(processes) -> None:
    limit = processes.MAX_COMMANDS_PER_PASS
    for index in range(limit + 1):
        processes._command_queue.append(('helper', f'announce route 10.0.{index // 256}.{index % 256}/32'))

    assert len(list(processes.received_async())) == limit
    assert len(processes._command_queue) == 1


# ==============================================================================
# The scheduler says when it is applying commands
# ==============================================================================


@pytest.mark.asyncio
async def test_commands_are_applying_while_their_coroutines_run() -> None:
    scheduler = ASYNC()
    seen: list[bool] = []

    async def command() -> None:
        seen.append(scheduler.applying_commands)
        await asyncio.sleep(0)
        seen.append(scheduler.applying_commands)

    scheduler.schedule('helper', 'announce', command())
    assert not scheduler.applying_commands
    await scheduler._run_async()

    assert seen == [True, True]
    assert not scheduler.applying_commands


@pytest.mark.asyncio
async def test_a_failing_command_does_not_leave_the_peers_held() -> None:
    scheduler = ASYNC()

    async def command() -> None:
        raise RuntimeError('broken command')

    scheduler.schedule('helper', 'announce', command())
    with patch('exabgp.reactor.asynchronous.log', MagicMock()):
        await scheduler._run_async()

    assert not scheduler.applying_commands


# ==============================================================================
# A peer waits for the commands to be applied
# ==============================================================================
#
# Real objects throughout: under mypyc (the compiled suite of test_everything) Peer,
# Protocol and OutgoingRIB are native classes, which refuse both Peer.__new__ and a mock
# in a typed slot.


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Neighbor takes a RIB out of a process wide cache, so each test gets its own."""
    monkeypatch.setattr(RIB, '_cache', {})


def _route() -> Route:
    nlri = INET.from_cidr(CIDR.create_cidr(IP.pton('192.0.2.0'), 24), AFI.ipv4, SAFI.unicast)
    return Route(nlri, AttributeCollection(), nexthop=IP.from_string('192.0.2.1'))


def _peer(applying: bool) -> Peer:
    """A peer with a route waiting in its RIB, while commands are, or are not, applied."""
    peer, _ = negotiation.peer()
    peer.proto = Protocol(peer)
    peer.reactor.asynchronous.applying_commands = applying
    # the neighbor of tests/negotiation.py comes with its RIB off and no family
    outgoing = peer.neighbor.rib.outgoing
    outgoing.enabled = True
    outgoing.families = {(AFI.ipv4, SAFI.unicast)}
    outgoing.add_to_rib(_route())
    assert peer.neighbor.rib.outgoing.pending()
    return peer


@pytest.mark.asyncio
async def test_a_peer_holds_while_commands_are_applied() -> None:
    assert _peer(applying=True)._holding_for_commands()
    assert not _peer(applying=False)._holding_for_commands()


@pytest.mark.asyncio
async def test_a_command_waiting_for_the_flush_is_not_held() -> None:
    # "announce ... sync" waits inside the batch for this very flush: holding the peer
    # would leave both waiting on each other
    peer = _peer(applying=True)
    peer.neighbor.rib.outgoing.register_flush_callback()

    assert not peer._holding_for_commands()


@pytest.mark.asyncio
async def test_a_peer_does_not_start_a_batch_while_commands_are_applied() -> None:
    peer = _peer(applying=True)

    new_routes, _ = await peer._send_route_updates(None, True, 25)

    assert new_routes is None
    assert peer.neighbor.rib.outgoing.pending(), 'the route is still waiting for the batch'


@pytest.mark.asyncio
async def test_no_end_of_rib_overtakes_the_commands_being_applied() -> None:
    peer = _peer(applying=True)
    manual = SimpleNamespace(afi=AFI.ipv4, safi=SAFI.unicast)

    assert await peer._send_eor_messages(True, None) is True
    peer.neighbor.eor.append(manual)
    assert await peer._send_eor_messages(False, None) is False

    assert list(peer.neighbor.eor) == [manual]
    assert not peer._end_of_rib_sent
