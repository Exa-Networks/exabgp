"""The routes an API helper announced go when it exits (issue #304).

A helper which dies leaves behind every route it announced, and nothing is left to
withdraw them: a crashed DDoS detector keeps its blackholes up for ever. The outgoing RIB
now records which helper announced a route, and when that helper exits, the reactor
withdraws them, unless the process is configured with `on-exit keep`.

A route which replaced one from the configuration gives the configured one back, so a
helper crash never takes a static route with it.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Iterator, cast
from unittest.mock import MagicMock, Mock, patch

import pytest

from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.med import MED
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.reactor.loop import Reactor
from exabgp.rib.outgoing import OutgoingRIB
from exabgp.rib.route import Route

FAMILY = (AFI.ipv4, SAFI.unicast)
PREFIX = '192.0.2.0/24'
OTHER = '198.51.100.0/24'


@pytest.fixture(autouse=True)
def _logger() -> Iterator[None]:
    """The RIB logs every insert and the logger is not initialised under pytest."""
    from exabgp.logger.option import option

    logger, formater = option.logger, option.formater
    option.logger = Mock()
    option.formater = Mock(return_value='formatted message')
    yield
    option.logger, option.formater = logger, formater


@pytest.fixture
def rib() -> OutgoingRIB:
    return OutgoingRIB(cache=True, families={FAMILY})


def route(prefix: str = PREFIX, med: int = 0) -> Route:
    address, mask = prefix.split('/')
    nlri = INET.from_cidr(CIDR.create_cidr(IP.pton(address), int(mask)), AFI.ipv4, SAFI.unicast)
    attributes = AttributeCollection()
    attributes.add(MED.from_int(med))
    return Route(nlri, attributes, nexthop=IP.from_string('192.0.2.1'))


def withdrawn(rib: OutgoingRIB) -> set[str]:
    return {str(nlri) for pending in rib._pending_withdraws.values() for nlri, _ in pending.values()}


def announced(rib: OutgoingRIB) -> dict[str, int]:
    return {str(entry.nlri): entry.attributes[MED.ID].med for entry in rib._new_nlri.values()}


# ==============================================================================
# The RIB knows who announced what
# ==============================================================================


def test_a_helper_owns_what_it_announced(rib: OutgoingRIB) -> None:
    rib.add_to_rib(route(), owner='helper')
    rib.add_to_rib(route(OTHER), owner='other')

    assert [str(r.nlri) for r in rib.owned('helper')] == [PREFIX]
    assert [str(r.nlri) for r in rib.owned('other')] == [OTHER]


def test_withdraw_owner_withdraws_only_that_helper(rib: OutgoingRIB) -> None:
    rib.add_to_rib(route(), owner='helper')
    rib.add_to_rib(route(OTHER), owner='other')

    assert rib.withdraw_owner('helper', []) == 1

    assert withdrawn(rib) == {PREFIX}
    assert rib.owned('helper') == []
    assert len(rib.owned('other')) == 1


def test_the_last_announcer_of_a_prefix_owns_it(rib: OutgoingRIB) -> None:
    rib.add_to_rib(route(), owner='helper')
    rib.add_to_rib(route(med=5), owner='other')

    assert rib.withdraw_owner('helper', []) == 0
    assert withdrawn(rib) == set()
    assert len(rib.owned('other')) == 1


def test_a_route_withdrawn_by_anyone_is_no_longer_owned(rib: OutgoingRIB) -> None:
    rib.add_to_rib(route(), owner='helper')
    rib.del_from_rib(route())

    assert rib.owned('helper') == []
    assert rib.withdraw_owner('helper', []) == 0


def test_a_configured_route_takes_the_prefix_back(rib: OutgoingRIB) -> None:
    rib.add_to_rib(route(), owner='helper')
    rib.add_to_rib(route(med=5), owner='')

    assert rib.owned('helper') == []


def test_a_replay_keeps_the_owner(rib: OutgoingRIB) -> None:
    # replace_restart re-adds the adj-rib-out on reconnect, with no owner given
    rib.add_to_rib(route(), owner='helper')
    rib.replace_restart([], [])

    assert len(rib.owned('helper')) == 1


def test_clear_forgets_every_owner(rib: OutgoingRIB) -> None:
    rib.add_to_rib(route(), owner='helper')
    rib.clear()

    assert rib.owned('helper') == []


# ==============================================================================
# A configured route comes back
# ==============================================================================


def test_the_configured_route_a_helper_replaced_is_restored(rib: OutgoingRIB) -> None:
    configured = route(med=9)
    rib.add_to_rib(configured, owner='')
    rib.add_to_rib(route(med=1), owner='helper')
    rib.add_to_rib(route(OTHER), owner='helper')

    assert rib.withdraw_owner('helper', [configured]) == 2

    assert announced(rib) == {PREFIX: 9}
    assert withdrawn(rib) == {OTHER}
    assert rib.owned('helper') == []


def test_a_configured_route_held_down_by_a_watchdog_is_not_restored(rib: OutgoingRIB) -> None:
    configured = route(med=9)
    rib._watchdog['dog'] = {'-': {configured.index(): configured}}
    rib.add_to_rib(route(med=1), owner='helper')

    rib.withdraw_owner('helper', [configured])

    assert withdrawn(rib) == {PREFIX}


# ==============================================================================
# on-exit in the process block
# ==============================================================================


def _process(on_exit: str) -> dict:
    line = f'    on-exit {on_exit};\n' if on_exit else ''
    c = Configuration([f'process helper {{\n    run /bin/cat;\n{line}}}\n'], text=True)
    assert c.reload(), c.error
    return c.processes['helper']


def test_on_exit_defaults_to_withdraw() -> None:
    assert _process('')['on-exit'] == 'withdraw'


def test_on_exit_keep_is_accepted() -> None:
    assert _process('keep')['on-exit'] == 'keep'


def test_on_exit_refuses_anything_else() -> None:
    c = Configuration(['process helper {\n    run /bin/cat;\n    on-exit forget;\n}\n'], text=True)
    assert not c.reload()


# ==============================================================================
# Processes tells the reactor, after the commands the helper sent
# ==============================================================================


@pytest.fixture
def processes():
    with patch('exabgp.reactor.api.processes.getenv') as getenv:
        environment = MagicMock()
        environment.api.respawn = False
        environment.api.terminate = False
        environment.api.ack = True
        environment.api.version = '5.0.0'
        getenv.return_value = environment

        from exabgp.reactor.api.processes import Processes

        with patch('exabgp.reactor.api.processes.log', MagicMock()):
            created = Processes()
            yield created
            for name in list(created._process):
                created._terminate(name)


def _start(processes, name: str, on_exit: str = 'withdraw') -> None:
    processes.start({name: {'run': ['/bin/cat'], 'encoder': 'text', 'respawn': False, 'on-exit': on_exit}}, False)
    assert name in processes._process


def test_an_exit_is_queued_after_the_commands_before_it(processes) -> None:
    _start(processes, 'helper')
    processes._command_queue.append(('helper', 'announce route 192.0.2.0/24 next-hop self'))

    processes._handle_problem('helper')

    assert [command for _, command in processes._command_queue] == [
        'announce route 192.0.2.0/24 next-hop self',
        processes.EXITED,
    ]


def test_on_exit_keep_queues_nothing(processes) -> None:
    _start(processes, 'helper', on_exit='keep')

    processes._handle_problem('helper')

    assert not processes._command_queue


def test_the_cli_helper_never_owns_routes(processes) -> None:
    from exabgp.configuration.cli_process import API_PREFIX

    name = f'{API_PREFIX}-socket-1'
    _start(processes, name)

    processes._handle_problem(name)

    assert not processes._command_queue


# ==============================================================================
# The reactor withdraws on every neighbour
# ==============================================================================


def test_the_reactor_withdraws_the_helper_routes_on_every_neighbour() -> None:
    ribs = [OutgoingRIB(cache=True, families={FAMILY}) for _ in range(2)]
    for each in ribs:
        each.add_to_rib(route(), owner='helper')
    neighbors = {
        f'n{index}': SimpleNamespace(rib=SimpleNamespace(outgoing=each), routes=[], resolve_self=lambda r: r)
        for index, each in enumerate(ribs)
    }
    scheduled = []
    reactor = SimpleNamespace(
        configuration=SimpleNamespace(neighbors=neighbors),
        asynchronous=SimpleNamespace(schedule=lambda uid, command, callback: scheduled.append((uid, callback))),
    )

    Reactor._withdraw_helper_routes(cast(Reactor, reactor), 'helper')
    assert [uid for uid, _ in scheduled] == ['helper']
    with patch('exabgp.reactor.loop.log', MagicMock()):
        asyncio.run(scheduled[0][1])

    assert [withdrawn(each) for each in ribs] == [{PREFIX}, {PREFIX}]
