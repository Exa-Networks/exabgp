"""delay.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2017-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import time


# ======================================================================== Delay
# Exponential backup for outgoing connection


class Delay:
    def __init__(self) -> None:
        self._time: float = time.time()
        self._next: int = 0

    def reset(self) -> None:
        self._time = time.time()
        self._next = 0

    def increase(self) -> None:
        self._time = time.time() + self._next
        self._next = min(int(1 + self._next * 1.2), 60)

    def backoff(self) -> bool:
        return time.time() <= self._time
