# encoding: utf-8
"""
delay.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2017-2017 Exa Networks. All rights reserved.
"""

import time


# ======================================================================== Delay
# Exponential backup for outgoing connection


class Delay(object):
    def __init__(self):
        self._time = time.time()
        self._next = 0

    def reset(self):
        self._time = time.time()
        self._next = 0

    def increase(self):
        self._time = time.time() + self._next
        self._next = min(int(1 + self._next * 1.2), 60)

    def backoff(self):
        return self._time > time.time()
