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
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.configuration.configuration import Configuration
from exabgp.reactor.api.command.neighbor import disable, enable
from exabgp.reactor.api.dispatch.v4 import dispatch_v4
from exabgp.reactor.api.dispatch.v6 import dispatch_v6
from exabgp.reactor.loop import Reactor
from exabgp.reactor.peer import Peer

CEASE = 6
ADMINISTRATIVE_SHUTDOWN = 2
CONNECTION_REJECTED = 5


def peer(shutdown: bool = False, reactor: Mock | None = None) -> Peer:
    neighbor = MagicMock()
    neighbor.uid = '1'
    neighbor.api = {'neighbor-changes': False, 'fsm': False}
    neighbor.rib = Mock()
    neighbor.session.passive = False
    neighbor.shutdown = shutdown
    if reactor is None:
        reactor = Mock()
        reactor.processes.broken.return_value = False
    return Peer(neighbor, reactor)


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
    connection = Mock()
    connection.notification = Mock(return_value='rejected')

    assert peer(shutdown=True).handle_connection(connection) == 'rejected'
    code, subcode, _ = connection.notification.call_args.args
    assert (code, subcode) == (CEASE, CONNECTION_REJECTED)


def test_an_incoming_connection_is_accepted_once_enabled() -> None:
    enabled = peer(shutdown=True)
    enabled.enable()
    connection = Mock()

    enabled.handle_connection(connection)

    connection.notification.assert_not_called()


def test_a_disabled_peer_does_not_connect_until_enabled() -> None:
    waiting = peer(shutdown=True)
    run = AsyncMock(side_effect=lambda: setattr(waiting, '_restart', False))
    waiting._run = run  # type: ignore[method-assign]

    async def scenario() -> None:
        task = asyncio.create_task(waiting.run())
        await asyncio.sleep(0.3)
        assert not run.called, 'a disabled peer connected'
        waiting.enable()
        await asyncio.wait_for(task, timeout=5)

    asyncio.run(scenario())
    run.assert_called_once()


def test_a_disable_with_no_session_leaves_nothing_behind() -> None:
    """The teardown disable() set has nothing to close, and must not close the next one."""
    parked = peer()
    parked.disable(Notify(CEASE, ADMINISTRATIVE_SHUTDOWN))

    async def scenario() -> None:
        task = asyncio.create_task(parked.run())
        await asyncio.sleep(0.3)
        assert parked._teardown is None
        parked.stop()
        await asyncio.wait_for(task, timeout=5)

    asyncio.run(scenario())


def test_a_reload_while_disabled_is_applied_without_a_session() -> None:
    """reestablish() leaves its Cease and the new neighbour for _reset, which only a session
    reaches.  A disabled peer has none, so the Cease closed the first session after enable,
    which was also opened with the neighbour the reload had replaced."""
    parked = peer(shutdown=True)
    replacement = MagicMock()
    parked.reestablish(replacement)

    async def scenario() -> None:
        task = asyncio.create_task(parked.run())
        await asyncio.sleep(0.3)
        assert parked._teardown is None
        assert parked.neighbor is replacement
        parked.stop()
        await asyncio.wait_for(task, timeout=5)

    asyncio.run(scenario())


def test_a_connection_accepted_just_before_the_disable_is_not_parked() -> None:
    """It has to reach _main, which sends it the Cease."""
    accepted = peer()
    accepted.proto = Mock()
    run = AsyncMock(side_effect=lambda: setattr(accepted, '_restart', False))
    accepted._run = run  # type: ignore[method-assign]
    accepted.disable(Notify(CEASE, ADMINISTRATIVE_SHUTDOWN))

    asyncio.run(asyncio.wait_for(accepted.run(), timeout=5))

    run.assert_called_once()


def test_a_disabled_peer_removed_from_the_configuration_still_goes() -> None:
    """stop() has to end the loop a disabled peer waits in, or the reactor keeps it."""
    removed = peer(shutdown=True)
    removed.remove()

    asyncio.run(asyncio.wait_for(removed.run(), timeout=5))


# ============================================================================
# the reactor
# ============================================================================


def reactor_with(**peers: Peer) -> Reactor:
    reactor = Reactor.__new__(Reactor)
    reactor._peers = dict(peers)
    return reactor


def test_a_disabled_peer_with_no_session_is_not_given_a_turn() -> None:
    """Its routes wait for it: a reload waiting for them to be sent would never happen."""
    reactor = reactor_with(disabled=peer(shutdown=True), enabled=peer())

    assert reactor.active_peers() == {'enabled'}


def test_a_disabled_peer_still_closing_its_session_is_given_a_turn() -> None:
    closing = peer()
    closing.proto = Mock()
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
    neighbor = Mock()
    neighbor.shutdown = after

    Reactor._reload_shutdown(reloaded, neighbor)

    assert reloaded.disabled() is disabled


@pytest.mark.parametrize('shutdown', [False, True])
def test_a_reload_which_kept_shutdown_keeps_what_the_api_did(shutdown: bool) -> None:
    changed = peer(shutdown=shutdown)
    if shutdown:
        changed.enable()
    else:
        changed.disable(Notify(CEASE, ADMINISTRATIVE_SHUTDOWN))
    neighbor = Mock()
    neighbor.shutdown = shutdown

    Reactor._reload_shutdown(changed, neighbor)

    assert changed.disabled() is not shutdown


# ============================================================================
# the API
# ============================================================================


def called(handler, arguments: str) -> tuple[bool, Mock]:  # type: ignore[no-untyped-def]
    reactor = Mock()
    return handler(Mock(), reactor, 'service', ['peer'], arguments, False), reactor


def test_disable_sends_the_text_as_the_shutdown_communication() -> None:
    answered, reactor = called(disable, '"back at 18:00"')

    assert answered is True
    (name, notify), _ = reactor.disable_peer.call_args
    assert name == 'peer'
    assert (notify.code, notify.subcode, notify.raw_data) == (CEASE, ADMINISTRATIVE_SHUTDOWN, b'\x0dback at 18:00')


def test_disable_with_no_text() -> None:
    _, reactor = called(disable, '')

    (_, notify), _ = reactor.disable_peer.call_args
    assert notify.raw_data == b''


def test_disable_refuses_an_unbalanced_quote() -> None:
    answered, reactor = called(disable, '"unbalanced')

    assert answered is False
    reactor.disable_peer.assert_not_called()
    reactor.processes.answer_error_sync.assert_called_once()


def test_enable_is_passed_on() -> None:
    answered, reactor = called(enable, '')

    assert answered is True
    reactor.enable_peer.assert_called_once_with('peer')


def test_enable_refuses_an_argument() -> None:
    answered, reactor = called(enable, 'now')

    assert answered is False
    reactor.enable_peer.assert_not_called()


NAME = 'neighbor 127.0.0.1 local-ip 127.0.0.2 local-as 1 peer-as 1 router-id 1.1.1.1 family-allowed in-open'


@pytest.mark.parametrize(
    ('command', 'handler', 'arguments'),
    [
        ('peer 127.0.0.1 disable "back soon"', disable, '"back soon"'),
        ('peer * enable', enable, ''),
    ],
)
def test_the_v6_commands(command: str, handler, arguments: str) -> None:  # type: ignore[no-untyped-def]
    reactor = Mock()
    reactor.peers.return_value = [NAME]

    assert dispatch_v6(command, reactor, 'service') == (handler, [NAME], arguments)


@pytest.mark.parametrize(
    ('command', 'handler', 'arguments'),
    [
        ('neighbor 127.0.0.1 disable maintenance', disable, 'maintenance'),
        ('neighbor 127.0.0.1 enable', enable, ''),
    ],
)
def test_the_v4_commands(command: str, handler, arguments: str) -> None:  # type: ignore[no-untyped-def]
    reactor = Mock()
    reactor.peers.return_value = [NAME]

    assert dispatch_v4(command, reactor, 'service') == (handler, [NAME], arguments)


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
