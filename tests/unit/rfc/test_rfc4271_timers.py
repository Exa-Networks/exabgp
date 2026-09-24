"""RFC 4271 sections 4.4, 6 and 6.5: what the hold time does once it has been negotiated.

Both timers read `time.time()` through the module global in `exabgp/bgp/timer.py`, so the
tests here replace that module with a clock they move by hand.  Sleeping would make the
suite take a minute to assert something about one second, and a test which sleeps for
"about" a second is a test which fails on a loaded machine.

Section 6.5 has no RFC 2119 keyword in it: it states that the notification is sent, it
does not say MUST.  The sentence which binds it is in the preamble of section 6, "If no
Error Subcode is specified, then a zero MUST be used", and Hold Timer Expired is an error
code with no subcodes.  That is what `rfc4271#6-zero-subcode-when-none-is-specified`
records, and its positive test is the hold timer expiring.
"""

from __future__ import annotations

import pytest

from exabgp.bgp import timer
from exabgp.bgp.message import KeepAlive, Notify, Open
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import ASN, Capabilities, HoldTime, RouterID, Version
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.neighbor import Neighbor
from exabgp.bgp.timer import ReceiveTimer, SendTimer
from exabgp.rib import RIB

HOLD_TIMER_EXPIRED = 4
UNSPECIFIC = 0
OPEN_MESSAGE_ERROR = 2
UNACCEPTABLE_HOLD_TIME = 6

# Any fixed point in time. The tests only ever move relative to it.
EPOCH = 1700000000.0


class Clock:
    """A stand-in for the time module, holding one instant which the test moves."""

    def __init__(self, at: float) -> None:
        self._at = at

    def time(self) -> float:
        return self._at

    def advance(self, seconds: float) -> None:
        self._at += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    frozen = Clock(EPOCH)
    monkeypatch.setattr(timer, 'time', frozen)
    return frozen


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Neighbor takes a RIB out of a process wide cache, so each test gets its own."""
    monkeypatch.setattr(RIB, '_cache', {})


def session() -> str:
    return 'rfc4271'


def sender(hold_time: int) -> SendTimer:
    return SendTimer(session, HoldTime(hold_time))


def receiver(hold_time: int) -> ReceiveTimer:
    """The receive timer the reactor builds: code 4, subcode 0, Hold Timer Expired."""
    return ReceiveTimer(session, HoldTime(hold_time), HOLD_TIMER_EXPIRED, UNSPECIFIC)


def negotiated_hold_time(ours: int, theirs: int) -> int:
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(65001)
    neighbor.session.peer_as = ASN(65002)
    neighbor.session.router_id = RouterID('192.0.2.1')

    negotiated = Negotiated.make_negotiated(neighbor, Direction.IN)
    negotiated.sent(Open.make_open(Version(4), ASN(65001), HoldTime(ours), RouterID('192.0.2.1'), Capabilities()))
    negotiated.received(Open.make_open(Version(4), ASN(65002), HoldTime(theirs), RouterID('192.0.2.2'), Capabilities()))
    return int(negotiated.holdtime)


# ------------------------------------------------------------- 4.4 how often we send one


@pytest.mark.rfc('rfc4271#4.4-keepalive-at-most-one-per-second')
def test_no_two_keepalives_fall_in_the_same_second(clock: Clock) -> None:
    """Three seconds is the smallest legal hold time, so one per second is our fastest."""
    timer_under_test = sender(3)
    seconds_asked = []

    for _ in range(40):
        clock.advance(0.25)
        if timer_under_test.need_ka():
            seconds_asked.append(int(clock.time()))

    assert seconds_asked, 'the timer never asked for a keepalive in ten seconds, so this proves nothing'
    assert len(seconds_asked) == len(set(seconds_asked)), (
        f'two keepalives were asked for in the same second: {seconds_asked}'
    )


# --------------------------------------------------------- 4.4 and when we send none at all


@pytest.mark.parametrize('elapsed', [1, 30, 600, 86400], ids=lambda value: f'after {value} seconds')
@pytest.mark.rfc('rfc4271#4.4-no-keepalive-when-holdtime-is-zero')
def test_a_zero_hold_time_asks_for_no_keepalive(clock: Clock, elapsed: int) -> None:
    timer_under_test = sender(0)
    clock.advance(elapsed)

    assert not timer_under_test.need_ka(), f'a keepalive was due {elapsed} seconds into a session with no hold time'


def test_a_non_zero_hold_time_does_ask_for_keepalives(clock: Clock) -> None:
    """Unmarked: the silence above has to be the rule and not a timer which never fires."""
    timer_under_test = sender(90)
    clock.advance(31)

    assert timer_under_test.need_ka()


def test_a_zero_hold_time_never_expires_the_session(clock: Clock) -> None:
    """Unmarked: the receive side of the same rule, so a peer which sends nothing survives."""
    timer_under_test = receiver(0)
    clock.advance(86400)

    timer_under_test.check_ka_timer()


# --------------------------------------- 6 the subcode when the error code has none, and 6.5


@pytest.mark.parametrize('hold_time', [3, 30, 90, 180], ids=lambda value: f'{value} second hold time')
@pytest.mark.rfc('rfc4271#6-zero-subcode-when-none-is-specified')
def test_the_hold_timer_expiring_uses_a_subcode_of_zero(clock: Clock, hold_time: int) -> None:
    """RFC 4271 6.5 names no subcode, and the Hold Timer Expired code has none to name."""
    timer_under_test = receiver(hold_time)
    clock.advance(hold_time + 1)

    with pytest.raises(Notify) as caught:
        timer_under_test.check_ka_timer()

    assert caught.value.code == HOLD_TIMER_EXPIRED
    assert caught.value.subcode == UNSPECIFIC


@pytest.mark.rfc('rfc4271#6-zero-subcode-when-none-is-specified', polarity='negative')
def test_an_error_whose_subcode_is_specified_keeps_it(clock: Clock) -> None:
    """A speaker which zeroed every subcode would pass the test above and say nothing.

    A keepalive on a session whose negotiated hold time is zero is the error the timer
    reports with a subcode of its own: 2/6, Unacceptable Hold Time.
    """
    timer_under_test = receiver(0)
    timer_under_test.check_ka(KeepAlive.make_keepalive())

    with pytest.raises(Notify) as caught:
        timer_under_test.check_ka(KeepAlive.make_keepalive())

    assert (caught.value.code, caught.value.subcode) == (OPEN_MESSAGE_ERROR, UNACCEPTABLE_HOLD_TIME)


# ----------------------------------------------- 6.2 the value the timer is actually run at


@pytest.mark.rfc('rfc4271#6.2-use-the-negotiated-hold-time')
def test_the_session_dies_at_the_negotiated_value_not_at_ours(clock: Clock) -> None:
    """We asked for 180 and the peer for 30, so silence has to kill us at 30."""
    negotiated = negotiated_hold_time(ours=180, theirs=30)
    assert negotiated == 30

    timer_under_test = receiver(negotiated)
    clock.advance(negotiated + 1)

    with pytest.raises(Notify) as caught:
        timer_under_test.check_ka_timer()

    assert caught.value.code == HOLD_TIMER_EXPIRED


@pytest.mark.parametrize('elapsed', [0, 1, 29, 30], ids=lambda value: f'{value} seconds of silence')
@pytest.mark.rfc('rfc4271#6.2-use-the-negotiated-hold-time', polarity='negative')
def test_the_session_survives_right_up_to_the_negotiated_value(clock: Clock, elapsed: int) -> None:
    """Thirty is the boundary: the RFC gives the peer the whole interval, not one less."""
    negotiated = negotiated_hold_time(ours=180, theirs=30)
    timer_under_test = receiver(negotiated)
    clock.advance(elapsed)

    timer_under_test.check_ka_timer()
