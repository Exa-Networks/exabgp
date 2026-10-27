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
from collections.abc import Iterator
from unittest.mock import MagicMock, Mock, patch

import pytest

from exabgp.environment import Environment
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.med import MED
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.reactor.api.dispatch.version import API_AUTO, API_V4, API_V6
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


def test_on_exit_is_left_unset_for_the_api_version_to_decide() -> None:
    assert 'on-exit' not in _process('')


def test_on_exit_withdraw_is_accepted() -> None:
    assert _process('withdraw')['on-exit'] == 'withdraw'


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
        environment = Environment()
        environment.api.respawn = False
        environment.api.terminate = False
        environment.api.ack = True
        environment.api.version = 6
        getenv.return_value = environment

        from exabgp.reactor.api.processes import Processes

        with patch('exabgp.reactor.api.processes.log', MagicMock()):
            created = Processes()
            yield created
            for name in list(created._process):
                created._terminate(name)


def _start(processes, name: str, on_exit: str | None = 'withdraw') -> None:
    process = {'run': ['/bin/cat'], 'encoder': 'text', 'respawn': False}
    if on_exit is not None:
        process['on-exit'] = on_exit
    processes.start({name: process}, False)
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


@pytest.mark.parametrize(
    ('version', 'withdrawn'),
    [
        (API_V4, False),  # a helper written for 4.x and 5.x keeps the routes it leaves, as they did
        (API_V6, True),  # issue #304
        (API_AUTO, True),  # it never said which: the default of this release
    ],
)
def test_without_on_exit_the_api_version_decides(processes, version: int, withdrawn: bool) -> None:
    _start(processes, 'helper', on_exit=None)
    processes._api_version['helper'] = version

    processes._handle_problem('helper')

    assert (processes.EXITED in [command for _, command in processes._command_queue]) is withdrawn


@pytest.mark.parametrize('version', [API_V4, API_V6])
def test_on_exit_wins_over_the_api_version(processes, version: int) -> None:
    _start(processes, 'keeper', on_exit='keep')
    _start(processes, 'withdrawer', on_exit='withdraw')
    processes._api_version['keeper'] = version
    processes._api_version['withdrawer'] = version

    processes._handle_problem('keeper')
    processes._handle_problem('withdrawer')

    assert list(processes._command_queue) == [('withdrawer', processes.EXITED)]


def test_the_cli_helper_never_owns_routes(processes) -> None:
    from exabgp.configuration.cli_process import API_PREFIX

    name = f'{API_PREFIX}-socket-1'
    _start(processes, name)

    processes._handle_problem(name)

    assert not processes._command_queue


# ==============================================================================
# Reload applies the exiting helper's policy, not its replacement's
# ==============================================================================


@pytest.mark.parametrize('restart', [False, True])
@pytest.mark.parametrize(
    ('on_exit', 'version', 'withdraw'),
    [
        ('withdraw', API_V4, True),
        ('keep', API_V6, False),
        (None, API_V4, False),
        (None, API_V6, True),
        (None, API_AUTO, True),
    ],
)
def test_reload_removing_a_helper_applies_its_exit_policy(processes, restart, on_exit, version, withdraw) -> None:
    _start(processes, 'helper', on_exit=on_exit)
    processes._api_version['helper'] = version
    command = ('helper', 'announce route 192.0.2.0/24 next-hop self')
    processes._command_queue.append(command)

    processes.start({}, restart=restart)

    expected = [command, ('helper', processes.EXITED)] if withdraw else [command]
    assert list(processes.received_async()) == expected
    assert 'helper' not in processes._process


@pytest.mark.parametrize(
    ('old_policy', 'new_policy', 'version', 'withdraw'),
    [
        ('withdraw', 'keep', API_V4, True),
        ('keep', 'withdraw', API_V6, False),
        (None, None, API_V4, False),
        (None, None, API_V6, True),
    ],
)
def test_full_reload_uses_the_replaced_helpers_policy(processes, old_policy, new_policy, version, withdraw) -> None:
    original = {'run': ['/bin/cat'], 'encoder': 'text', 'respawn': True}
    if old_policy is not None:
        original['on-exit'] = old_policy
    processes.start({'helper': original})
    old_process = processes._process['helper']
    processes._api_version['helper'] = version
    command = ('helper', 'announce route 192.0.2.0/24 next-hop self')
    processes._command_queue.append(command)
    replacement = {'run': ['/bin/cat', '-u'], 'encoder': 'text', 'respawn': True}
    if new_policy is not None:
        replacement['on-exit'] = new_policy

    processes.start({'helper': replacement}, restart=True)
    successor = ('helper', 'announce route 198.51.100.0/24 next-hop self')
    processes._command_queue.append(successor)

    expected = [command, ('helper', processes.EXITED), successor] if withdraw else [command, successor]
    assert list(processes.received_async()) == expected
    assert processes._process['helper'] is not old_process


@pytest.mark.parametrize('restart', [False, True])
def test_reload_leaves_an_unchanged_helper_and_its_routes_alone(processes, restart) -> None:
    _start(processes, 'helper')
    original = processes._process['helper']
    configuration = dict(processes._configuration)

    processes.start(configuration, restart=restart)

    assert processes._process['helper'] is original
    assert list(processes.received_async()) == []


def test_plain_reload_keeps_a_running_helper_with_changed_arguments(processes) -> None:
    _start(processes, 'helper')
    original = processes._process['helper']
    replacement = dict(processes._configuration['helper'], run=['/bin/cat', '-u'])

    processes.start({'helper': replacement})

    assert processes._process['helper'] is original
    assert list(processes.received_async()) == []


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
    # the reactor only walks configuration.neighbors, and each neighbour's routes and rib
    reactor = Reactor(SimpleNamespace(neighbors=neighbors))

    reactor._withdraw_helper_routes('helper')
    scheduled = list(reactor.asynchronous._async)
    assert [uid for uid, _ in scheduled] == ['helper']
    with patch('exabgp.reactor.loop.log', MagicMock()):
        asyncio.run(scheduled[0][1])

    assert [withdrawn(each) for each in ribs] == [{PREFIX}, {PREFIX}]


@pytest.mark.asyncio
@pytest.mark.parametrize('policy', ['withdraw', 'keep'])
async def test_reload_removal_reaches_the_rib_without_a_final_helper_withdraw(processes, policy) -> None:
    neighbor_text = """neighbor 192.0.2.1 {
        router-id 192.0.2.2;
        local-address 192.0.2.2;
        local-as 65001;
        peer-as 65002;
        family { ipv4 unicast; }
        api { processes [ healthcheck other ]; }
    }"""
    other = 'process other { run /bin/cat; respawn false; }'
    healthcheck = f'process healthcheck {{ run /bin/cat; respawn false; on-exit {policy}; }}'
    configuration = Configuration(
        [healthcheck + other + neighbor_text, other + neighbor_text.replace('healthcheck other', 'other')],
        text=True,
    )
    reactor = Reactor(configuration)
    reactor._ips = []
    reactor.processes = processes
    assert reactor.reload(), configuration.error
    processes.start(configuration.processes)
    neighbor = next(iter(configuration.neighbors.values()))
    rib = neighbor.rib.outgoing
    rib.add_to_rib(route(), owner='healthcheck')
    rib.add_to_rib(route(OTHER), owner='other')
    list(rib.updates(grouped=False))

    assert reactor.reload(), configuration.error
    processes.start(configuration.processes)
    assert next(iter(configuration.neighbors.values())).rib.outgoing is rib
    for service, command in processes.received_async():
        assert command == processes.EXITED
        reactor._withdraw_helper_routes(service)
    await reactor.asynchronous._run_async()

    updates = list(rib.updates(grouped=False))
    expected_withdrawn = {PREFIX} if policy == 'withdraw' else set()
    expected_cached = {OTHER} if policy == 'withdraw' else {PREFIX, OTHER}
    assert {str(nlri) for update in updates for nlri in update.withdraws} == expected_withdrawn
    assert {str(entry.nlri) for entry in rib.cached_routes(None)} == expected_cached
    assert len(rib.owned('healthcheck')) == (0 if policy == 'withdraw' else 1)
    assert len(rib.owned('other')) == 1
    assert 'healthcheck' not in processes._process
    assert 'other' in processes._process


@pytest.mark.asyncio
async def test_full_reload_withdraws_before_the_successor_reannounces_the_same_prefix(processes, rib) -> None:
    configuration = {'run': ['/bin/cat'], 'encoder': 'text', 'respawn': True, 'on-exit': 'withdraw'}
    processes.start({'healthcheck': configuration})
    rib.add_to_rib(route(med=1), owner='healthcheck')
    rib.add_to_rib(route(OTHER), owner='healthcheck')
    list(rib.updates(grouped=False))
    neighbor = SimpleNamespace(rib=SimpleNamespace(outgoing=rib), routes=[], resolve_self=lambda r: r)
    reactor = Reactor(SimpleNamespace(neighbors={'n': neighbor}))
    reactor.processes = processes

    processes.start({'healthcheck': dict(configuration, run=['/bin/cat', '-u'])}, restart=True)
    for service, command in processes.received_async():
        assert command == processes.EXITED
        reactor._withdraw_helper_routes(service)

    async def announce_successor() -> None:
        rib.add_to_rib(route(med=9), owner='healthcheck')

    reactor.asynchronous.schedule('healthcheck', 'successor announcement', announce_successor())
    await reactor.asynchronous._run_async()

    assert [entry.attributes[MED.ID].med for entry in rib.owned('healthcheck')] == [9]
    assert [entry.attributes[MED.ID].med for entry in rib.cached_routes(None)] == [9]
