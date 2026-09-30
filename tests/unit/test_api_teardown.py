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

import os
from collections.abc import Iterator
from unittest.mock import patch

import pytest

from exabgp.bgp.fsm import FSM
from exabgp.bgp.message.notification import Notify
from exabgp.configuration.configuration import Configuration
from exabgp.reactor.api.command import neighbor
from exabgp.reactor.api.command.neighbor import teardown, teardown_notification
from exabgp.reactor.api.processes import Processes
from exabgp.reactor.loop import Reactor
from exabgp.reactor.peer import Peer
from tests import negotiation

CEASE = 6
ADMINISTRATIVE_SHUTDOWN = 2
ADMINISTRATIVE_RESET = 4


def wire(arguments: str) -> tuple[int, int, bytes]:
    notify = teardown_notification(arguments)
    return notify.code, notify.subcode, notify.data


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


class PipedHelper:
    """The Popen of the API client, as far as answering it goes: its stdin is a pipe."""

    def __init__(self) -> None:
        self._reader, writer = os.pipe()
        os.set_blocking(self._reader, False)
        self.stdin = os.fdopen(writer, 'wb')

    def lines(self) -> list[str]:
        try:
            return os.read(self._reader, 65536).decode('ascii').splitlines()
        except BlockingIOError:
            return []

    def close(self) -> None:
        os.close(self._reader)
        self.stdin.close()


@pytest.fixture
def client() -> Iterator[PipedHelper]:
    piped = PipedHelper()
    yield piped
    piped.close()


def handled(client: PipedHelper, arguments: str) -> tuple[bool, Peer]:
    """Run `teardown <arguments>` from `client` against one established peer, named 'peer'."""
    reactor = Reactor(Configuration([''], text=True))
    reactor.processes = Processes()
    reactor.processes._process['service'] = client  # type: ignore[assignment]
    reactor.processes._ack['service'] = True
    reactor.processes._ackjson['service'] = False
    peer = Peer(negotiation.neighbor(), reactor)
    peer.fsm.change(FSM.ESTABLISHED)
    reactor._peers['peer'] = peer
    return teardown(reactor.api, reactor, 'service', ['peer'], arguments, False), peer


def test_the_client_is_answered_with_an_error_and_nothing_is_torn_down(client: PipedHelper) -> None:
    """`teardown 300` used to reach the peer loop, where bytes([6, 300]) raised ValueError."""
    answered, peer = handled(client, '300')
    assert answered is False
    assert peer._teardown is None
    lines = client.lines()
    assert lines[-1] == 'error'
    assert lines[0].startswith('error: ')


def test_the_peer_is_handed_the_notification_the_client_asked_for(client: PipedHelper) -> None:
    answered, peer = handled(client, '3 1 testing')
    assert answered is True
    notify = peer._teardown
    assert notify is not None
    assert (notify.code, notify.subcode, notify.data) == (3, 1, b'testing')
    assert client.lines() == ['done']


def test_the_peer_raises_the_notification_it_was_handed() -> None:
    """A subcode of 0 used to be falsy, and `while not self._teardown` never saw it."""
    peer = Peer(negotiation.neighbor(), Reactor(Configuration([''], text=True)))
    notify = Notify(CEASE, 0)
    peer.teardown(notify, restart=False)

    assert peer._teardown is notify
    assert peer.stopping()
