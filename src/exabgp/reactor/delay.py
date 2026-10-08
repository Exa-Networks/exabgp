"""delay.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2017-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import time

from typing import Callable

from exabgp.bgp.timer import jitter_factor


# ======================================================================== Delay
# Exponential backup for outgoing connection


class Delay:
    def __init__(self, jitter: Callable[[], float] = jitter_factor) -> None:
        self._jitter = jitter
        self._time: float = time.time()
        self._next: int = 0

    def reset(self) -> None:
        self._time = time.time()
        self._next = 0

    def increase(self) -> None:
        # RFC 4271 section 10: jitter SHOULD be applied to the ConnectRetryTimer, with a new
        # factor each time it is set, so that peers restarted together do not reconnect together.
        self._time = time.time() + self._next * self._jitter()
        self._next = min(int(1 + self._next * 1.2), 60)

    def backoff(self) -> bool:
        return time.time() <= self._time
