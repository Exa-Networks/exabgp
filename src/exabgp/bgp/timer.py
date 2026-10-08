"""timer.py

Created by Thomas Mangin on 2012-07-21.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import random
import time

from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.holdtime import HoldTime

from exabgp.logger import log, lazymsg
from exabgp.bgp.message import Message
from exabgp.bgp.message import Notify

# RFC 4271 section 10: "The suggested default amount of jitter SHALL be determined by
# multiplying the base value of the appropriate timer by a random factor, which is uniformly
# distributed in the range from 0.75 to 1.0."
JITTER_LOWEST = 0.75
JITTER_HIGHEST = 1.0

# RFC 4271 section 4.4: keepalives "MUST NOT be sent more frequently than one per second",
# so jitter may not take a one second keepalive interval below it.
KEEPALIVE_INTERVAL_MINIMUM_SECONDS = 1.0


def jitter_factor() -> float:
    """A new factor for a timer, drawn each time the timer is set (RFC 4271 section 10)."""
    return random.uniform(JITTER_LOWEST, JITTER_HIGHEST)


# ================================================================ ReceiveTimer
# Track the time for keepalive updates


class ReceiveTimer:
    def __init__(
        self, session: Callable[[], str], holdtime: 'HoldTime', code: int, subcode: int, message: str = ''
    ) -> None:
        self.session = session

        self.holdtime = holdtime
        self.last_print = 0
        self.last_read = int(time.time())

        self.code = code
        self.subcode = subcode
        self.message = message

    # `message` is None when nothing was read: only a message received restarts the timer
    def check_ka_timer(self, message: Message | None = None) -> bool:
        if self.holdtime == 0:
            # RFC 4271 8.2.2: a KEEPALIVE restarts the hold timer "if the negotiated
            # HoldTime value is non-zero", and the session remains Established either way
            return True
        now = int(time.time())
        if message is not None:
            self.last_read = now
        elapsed = now - self.last_read
        if elapsed > int(self.holdtime):
            raise Notify(self.code, self.subcode, self.message)
        if self.last_print != now:
            left = int(self.holdtime) - elapsed
            log.debug(lazymsg('timer.receive seconds_left={left}', left=left), source='ka-' + self.session())
            self.last_print = now
        return True

    def check_ka(self, message: Message | None = None) -> None:
        self.check_ka_timer(message)


class SendTimer:
    def __init__(
        self, session: Callable[[], str], holdtime: 'HoldTime', jitter: Callable[[], float] = jitter_factor
    ) -> None:
        self.session = session
        self._jitter = jitter

        self.keepalive = holdtime.keepalive()
        self.interval_seconds = self._next_interval()
        self.last_print = int(time.time())
        self.last_sent = time.time()

    def _next_interval(self) -> float:
        """The keepalive interval jittered for its next run, never under one second."""
        if not self.keepalive:
            return 0.0
        factor = self._jitter()
        assert JITTER_LOWEST <= factor <= JITTER_HIGHEST, f'jitter factor {factor} is out of its range'
        return max(KEEPALIVE_INTERVAL_MINIMUM_SECONDS, self.keepalive * factor)

    def need_ka(self) -> bool:
        if not self.keepalive:
            return False

        now = time.time()
        left = self.last_sent + self.interval_seconds - now

        if int(now) != self.last_print:
            log.debug(lazymsg('timer.send seconds_left={left}', left=int(left)), source='ka-' + self.session())
            self.last_print = int(now)

        if left <= 0:
            self.last_sent = now
            self.interval_seconds = self._next_interval()
            return True
        return False
