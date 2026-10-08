"""RFC 4271 section 10: jitter on the KeepaliveTimer and on the ConnectRetryTimer.

The random source is passed to the timers, so each test chooses the factor it wants and
the result does not depend on what the generator happened to draw.  The clock is the
time module's function, replaced, as in test_rfc4271_timers.py.

exabgp has no MinASOriginationIntervalTimer nor MinRouteAdvertisementIntervalTimer: an
UPDATE is sent when the API or the configuration asks for it.  The two timers it does run
from the list are the keepalive interval and the delay before it connects again.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator

import pytest

from exabgp.bgp.message.open import HoldTime
from exabgp.bgp.timer import JITTER_HIGHEST, JITTER_LOWEST, SendTimer, jitter_factor
from exabgp.reactor.delay import Delay

EPOCH = 1700000000.0


class Clock:
    def __init__(self, at: float) -> None:
        self._at = at

    def time(self) -> float:
        return self._at

    def advance(self, seconds: float) -> None:
        self._at += seconds

    def at(self, seconds: float) -> None:
        """Move to an offset from EPOCH, rather than add, so no rounding accumulates."""
        self._at = EPOCH + seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    frozen = Clock(EPOCH)
    monkeypatch.setattr(time, 'time', frozen.time)
    return frozen


def session() -> str:
    return 'rfc4271-jitter'


def factors(*values: float) -> Callable[[], float]:
    """A random source which returns the given factors in order, then the last one forever."""
    drawn: Iterator[float] = iter(values)
    last = [values[-1]]

    def draw() -> float:
        last[0] = next(drawn, last[0])
        return last[0]

    return draw


def keepalive_instants(timer: SendTimer, clock: Clock, seconds: float) -> list[float]:
    """When the timer asks for a keepalive, polled every tenth of a second."""
    asked = []
    for tenth in range(1, int(seconds * 10) + 1):
        clock.at(tenth / 10)
        if timer.need_ka():
            asked.append(round(clock.time() - EPOCH, 1))
    return asked


# ------------------------------------------------------------------ the KeepaliveTimer


@pytest.mark.rfc('rfc4271#10-jitter-timers')
@pytest.mark.rfc('rfc4271#10-jitter-new-value-each-time')
def test_each_keepalive_interval_is_scaled_by_a_new_factor(clock: Clock) -> None:
    """A 90 second hold time is a 30 second keepalive: 0.8 then 0.9 then 1.0 of it."""
    timer = SendTimer(session, HoldTime(90), jitter=factors(0.8, 0.9, 1.0))

    assert keepalive_instants(timer, clock, 85) == [24.0, 51.0, 81.0]


@pytest.mark.rfc('rfc4271#10-jitter-timers', polarity='negative')
def test_without_jitter_the_interval_is_the_whole_third(clock: Clock) -> None:
    """The factor 1.0 is the timer of before: a third of the hold time, exactly."""
    timer = SendTimer(session, HoldTime(90), jitter=factors(1.0))

    assert keepalive_instants(timer, clock, 95) == [30.0, 60.0, 90.0]


def test_jitter_never_brings_keepalives_below_one_second(clock: Clock) -> None:
    """Unmarked, the bound is 4.4's: a 3 second hold time is a 1 second keepalive, and
    0.75 of it would be two keepalives in the same second."""
    timer = SendTimer(session, HoldTime(3), jitter=factors(JITTER_LOWEST))

    assert keepalive_instants(timer, clock, 4.05) == [1.0, 2.0, 3.0, 4.0]


# ----------------------------------------------------------------- the ConnectRetryTimer


@pytest.mark.rfc('rfc4271#10-jitter-timers')
def test_the_connect_retry_delay_is_scaled_by_the_factor(clock: Clock) -> None:
    delay = Delay(jitter=factors(0.75))
    delay.increase()  # the first attempt waits for nothing
    delay.increase()  # the second waits one second, of which 0.75

    clock.advance(0.7)
    assert delay.backoff()
    clock.advance(0.1)
    assert not delay.backoff()


# --------------------------------------------------------------------- the default factor


@pytest.mark.rfc('rfc4271#10-jitter-default-range')
def test_the_default_factor_is_uniform_between_three_quarters_and_one() -> None:
    drawn = [jitter_factor() for _ in range(2000)]

    assert (JITTER_LOWEST, JITTER_HIGHEST) == (0.75, 1.0)
    assert all(JITTER_LOWEST <= factor <= JITTER_HIGHEST for factor in drawn)
    # Uniform over a quarter: both halves of the range are drawn, about equally.
    lower_half = sum(1 for factor in drawn if factor < 0.875)
    assert 800 < lower_half < 1200
