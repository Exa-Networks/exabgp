"""RFC 4271 sections 4.4, 6 and 6.5: what the hold time does once it has been negotiated.

Both timers call `time.time()`, so the tests here replace that function of the time module
with a clock they move by hand.  Sleeping would make the suite take a minute to assert
something about one second, and a test which sleeps for "about" a second is a test which
fails on a loaded machine.  It is the function which is replaced, not the `time` global of
`exabgp/bgp/timer.py`: the compiled module holds the time module itself and never reads
its own global, but it does look `time` up on that module at each call.

Section 6.5 has no RFC 2119 keyword in it: it states that the notification is sent, it
does not say MUST.  The sentence which binds it is in the preamble of section 6, "If no
Error Subcode is specified, then a zero MUST be used", and Hold Timer Expired is an error
code with no subcodes.  That is what `rfc4271#6-zero-subcode-when-none-is-specified`
records, and its positive test is the hold timer expiring.
"""

from __future__ import annotations

import time

import pytest

from exabgp.bgp.message import KeepAlive, Notify, Open
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import ASN, Capabilities, HoldTime, RouterID, Version
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.neighbor import Neighbor
from exabgp.bgp.timer import ReceiveTimer, SendTimer
from exabgp.protocol.family import AFI, SAFI
from exabgp.rib import RIB
from tests import negotiation

HOLD_TIMER_EXPIRED = 4
UNSPECIFIC = 0
OPEN_MESSAGE_ERROR = 2
UNACCEPTABLE_HOLD_TIME = 6

# Any fixed point in time. The tests only ever move relative to it.
EPOCH = 1700000000.0


class Clock:
    """A stand-in for time.time(), holding one instant which the test moves."""

    def __init__(self, at: float) -> None:
        self._at = at

    def time(self) -> float:
        return self._at

    def advance(self, seconds: float) -> None:
        self._at += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    frozen = Clock(EPOCH)
    monkeypatch.setattr(time, 'time', frozen.time)
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
def test_an_error_whose_subcode_is_specified_keeps_it() -> None:
    """A speaker which zeroed every subcode would pass the test above and say nothing.

    A hold time of one second is the timer error RFC 4271 6.2 gives a subcode of its own:
    2/6, Unacceptable Hold Time. This used to be a second keepalive on a zero hold time
    session, which is no error at all (see the 8.2.2 test below).
    """
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(65001)
    neighbor.session.peer_as = ASN(65002)
    neighbor.session.router_id = RouterID('192.0.2.1')
    negotiated = Negotiated.make_negotiated(neighbor, Direction.IN)
    negotiated.sent(Open.make_open(Version(4), ASN(65001), HoldTime(180), RouterID('192.0.2.1'), Capabilities()))
    negotiated.received(Open.make_open(Version(4), ASN(65002), HoldTime(1), RouterID('192.0.2.2'), Capabilities()))

    error = negotiated.validate(neighbor)

    assert error is not None
    assert (error[0], error[1]) == (OPEN_MESSAGE_ERROR, UNACCEPTABLE_HOLD_TIME)


# --------------------------------------------- 8.2.2 a KEEPALIVE in Established


def test_keepalives_on_a_zero_hold_time_session_keep_it_established(clock: Clock) -> None:
    """Unmarked, 8.2.2 has no keyword: a KEEPALIVE "restarts its HoldTimer, if the
    negotiated HoldTime value is non-zero, and remains in the Established state".

    The second one raised Notify(2, 6) and closed a session whose peer only sent a
    keepalive more than the zero hold time asked for.
    """
    timer_under_test = receiver(0)

    for _ in range(5):
        clock.advance(60)
        timer_under_test.check_ka(KeepAlive.make_keepalive())


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


# ----------------------------------------------- 8.2.2 no OPEN arrives while in OpenSent


@pytest.mark.asyncio
async def test_waiting_too_long_for_the_open_is_hold_timer_expired() -> None:
    """RFC 4271 8.2.2, OpenSent: "If the HoldTimer_Expires (Event 10), the local system:
    - sends a NOTIFICATION message with the error code Hold Timer Expired".

    exabgp sent (5, 1), Receive Unexpected Message in OpenSent State, which RFC 6608 keeps
    for a message which did arrive.  Here nothing arrived at all.
    """
    from exabgp.environment import getenv
    from tests import negotiation

    # a real session over a socket pair, whose peer end is connected and never writes
    proto, _ = negotiation.protocol()
    theirs = negotiation.connect(proto)
    peer = proto.peer
    peer.proto = proto
    monkeypatch = pytest.MonkeyPatch()
    # openwait is whole seconds (the compiled build refuses a float): none at all expires at once
    monkeypatch.setattr(getenv().bgp, 'openwait', 0)
    try:
        with pytest.raises(Notify) as caught:
            await peer._read_open()
    finally:
        monkeypatch.undo()
        proto.close()
        theirs.close()

    assert (caught.value.code, caught.value.subcode) == (HOLD_TIMER_EXPIRED, UNSPECIFIC)


# ------------------------------------------- 8.2.2 sending an UPDATE restarts the KeepaliveTimer


def steady_sender(hold_time: int) -> SendTimer:
    """A timer whose jitter factor is 1.0, so its keepalive falls a whole interval after a restart."""
    return SendTimer(session, HoldTime(hold_time), jitter=lambda: 1.0)


@pytest.mark.rfc('rfc4271#8.2.2-sending-restarts-the-keepalive-timer')
def test_a_restart_puts_the_next_keepalive_a_whole_interval_later(clock: Clock) -> None:
    timer_under_test = steady_sender(90)
    clock.advance(20)
    timer_under_test.restart()

    clock.advance(25)
    assert not timer_under_test.need_ka(), 'a keepalive was due 25 seconds after an UPDATE restarted the timer'
    clock.advance(5)
    assert timer_under_test.need_ka()


@pytest.mark.rfc('rfc4271#10-jitter-new-value-each-time')
def test_each_restart_draws_a_new_jitter_factor(clock: Clock) -> None:
    factors = iter([1.0, 0.75, 0.9])
    timer_under_test = SendTimer(session, HoldTime(90), jitter=lambda: next(factors))
    timer_under_test.restart()
    assert timer_under_test.interval_seconds == 30 * 0.75
    timer_under_test.restart()
    assert timer_under_test.interval_seconds == 30 * 0.9


@pytest.mark.rfc('rfc4271#8.2.2-sending-restarts-the-keepalive-timer', polarity='negative')
def test_a_zero_hold_time_has_no_keepalive_timer_to_restart(clock: Clock) -> None:
    timer_under_test = steady_sender(0)
    timer_under_test.restart()
    clock.advance(86400)

    assert not timer_under_test.need_ka()


def update_on_the_wire() -> bytes:
    from exabgp.bgp.message.update.eor import EOR

    return EOR.make_eor(*IPV4_UNICAST).pack_message(Negotiated.UNSET)


IPV4_UNICAST = (AFI.ipv4, SAFI.unicast)


@pytest.mark.rfc('rfc4271#8.2.2-sending-restarts-the-keepalive-timer')
@pytest.mark.asyncio
async def test_an_update_the_session_sends_restarts_its_keepalive_timer(clock: Clock) -> None:
    proto, _ = negotiation.protocol()
    theirs = negotiation.connect(proto)
    proto.keepalive_timer = steady_sender(90)
    clock.advance(20)

    await proto.send(update_on_the_wire())

    clock.advance(25)
    assert not proto.keepalive_timer.need_ka(), 'the UPDATE sent 25 seconds ago did not restart the keepalive timer'
    theirs.close()


@pytest.mark.rfc('rfc4271#8.2.2-sending-restarts-the-keepalive-timer')
@pytest.mark.asyncio
async def test_an_update_written_as_a_message_restarts_it_too(clock: Clock) -> None:
    """The End-of-RIB goes out through write(), not send()."""
    proto, _ = negotiation.protocol()
    theirs = negotiation.connect(proto)
    proto.keepalive_timer = steady_sender(90)
    clock.advance(20)

    await proto.new_eor(AFI.ipv4, SAFI.unicast)

    clock.advance(25)
    assert not proto.keepalive_timer.need_ka()
    theirs.close()


@pytest.mark.rfc('rfc4271#8.2.2-sending-restarts-the-keepalive-timer', polarity='negative')
@pytest.mark.asyncio
async def test_a_notification_does_not_restart_the_keepalive_timer(clock: Clock) -> None:
    proto, _ = negotiation.protocol()
    theirs = negotiation.connect(proto)
    proto.keepalive_timer = steady_sender(90)
    clock.advance(20)

    await proto.new_notification(Notify(6, 2, 'shutdown'))

    clock.advance(10)
    assert proto.keepalive_timer.need_ka(), 'a NOTIFICATION is not one of the messages which restart it'
    theirs.close()
