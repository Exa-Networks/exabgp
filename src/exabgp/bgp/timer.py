"""timer.py

Created by Thomas Mangin on 2012-07-21.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import time

from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.holdtime import HoldTime

from exabgp.logger import log, lazymsg
from exabgp.bgp.message import Message
from exabgp.bgp.message import Notify

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
    def __init__(self, session: Callable[[], str], holdtime: 'HoldTime') -> None:
        self.session = session

        self.keepalive = holdtime.keepalive()
        self.last_print = int(time.time())
        self.last_sent = int(time.time())

    def need_ka(self) -> bool:
        if not self.keepalive:
            return False

        now = int(time.time())
        left = self.last_sent + self.keepalive - now

        if now != self.last_print:
            log.debug(lazymsg('timer.send seconds_left={left}', left=left), source='ka-' + self.session())
            self.last_print = now

        if left <= 0:
            self.last_sent = now
            return True
        return False
