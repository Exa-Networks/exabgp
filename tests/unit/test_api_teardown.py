"""The API teardown command: what the client asks for is what the peer is sent.

    neighbor <ip> teardown                            Cease / Administrative Shutdown
    neighbor <ip> teardown <subcode> [<text>]         Cease / <subcode>, as it always was
    neighbor <ip> teardown <code> <subcode> [<text>]  any code and subcode

The documentation said the number was the error code, and the code always sent Cease with
the number as the subcode.  The single number keeps doing what scripts rely on, and the
two number form gives a client the rest: people testing another implementation need to
send codes and subcodes nobody would send in production, so those are warned about rather
than refused.  What is refused is what cannot be put on the wire, a value over 255, and
that used to raise inside the peer loop instead of answering the client.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.reactor.api.command import neighbor
from exabgp.reactor.api.command.neighbor import teardown, teardown_notification

CEASE = 6
ADMINISTRATIVE_SHUTDOWN = 2
ADMINISTRATIVE_RESET = 4


def wire(arguments: str) -> tuple[int, int, bytes]:
    notify = teardown_notification(arguments)
    return notify.code, notify.subcode, notify.raw_data


def test_no_argument_is_an_administrative_shutdown() -> None:
    assert wire('') == (CEASE, ADMINISTRATIVE_SHUTDOWN, b'')


@pytest.mark.parametrize('subcode', [1, 3, 4, 6, 8])
def test_one_number_is_a_cease_subcode_as_it_always_was(subcode: int) -> None:
    assert wire(str(subcode))[:2] == (CEASE, subcode)


def test_two_numbers_are_the_code_and_the_subcode() -> None:
    assert wire('3 1')[:2] == (3, 1)


def test_text_after_the_subcode_of_a_shutdown_is_the_rfc9003_communication() -> None:
    assert wire('6 2 back in 2h') == (CEASE, ADMINISTRATIVE_SHUTDOWN, b'\x0aback in 2h')


def test_text_after_a_single_number() -> None:
    assert wire('4 maintenance') == (CEASE, ADMINISTRATIVE_RESET, b'\x0bmaintenance')


def test_text_starting_with_a_digit_is_quoted() -> None:
    assert wire('4 "12 monkeys"') == (CEASE, ADMINISTRATIVE_RESET, b'\x0a12 monkeys')


def test_text_for_another_subcode_is_the_data_field() -> None:
    assert wire('3 1 testing') == (3, 1, b'testing')


def test_reserved_and_unassigned_values_are_sent_with_a_warning() -> None:
    with patch.object(neighbor.log, 'warning') as warning:
        assert wire('0 0')[:2] == (0, 0)
    warning.assert_called_once()


def test_an_assigned_value_is_not_warned_about() -> None:
    with patch.object(neighbor.log, 'warning') as warning:
        wire('6 4')
    warning.assert_not_called()


@pytest.mark.parametrize('arguments', ['256', '6 256', '256 1', '-1', 'shutdown', '6 2 "unbalanced'])
def test_what_cannot_be_put_on_the_wire_is_refused(arguments: str) -> None:
    with pytest.raises(ValueError):
        teardown_notification(arguments)


def handled(arguments: str) -> tuple[bool, Mock]:
    reactor = Mock()
    reactor.established_peers.return_value = ['peer']
    api = Mock()
    return teardown(api, reactor, 'service', ['peer'], arguments, False), reactor


def test_the_client_is_answered_with_an_error_and_nothing_is_torn_down() -> None:
    """`teardown 300` used to reach the peer loop, where bytes([6, 300]) raised ValueError."""
    answered, reactor = handled('300')
    assert answered is False
    reactor.teardown_peer.assert_not_called()
    reactor.processes.answer_error_sync.assert_called_once()


def test_the_peer_is_handed_the_notification_the_client_asked_for() -> None:
    answered, reactor = handled('3 1 testing')
    assert answered is True
    (name, notify), _ = reactor.teardown_peer.call_args
    assert name == 'peer'
    assert (notify.code, notify.subcode, notify.raw_data) == (3, 1, b'testing')


def test_the_peer_raises_the_notification_it_was_handed() -> None:
    """A subcode of 0 used to be falsy, and `while not self._teardown` never saw it."""
    from exabgp.reactor.peer import Peer

    neighbor_config = Mock()
    neighbor_config.uid = '1'
    neighbor_config.api = {'neighbor-changes': False, 'fsm': False}
    peer = Peer(neighbor_config, Mock())
    notify = Notify(CEASE, 0)
    peer.teardown(notify, restart=False)

    assert peer._teardown is notify
    assert peer.stopping()
