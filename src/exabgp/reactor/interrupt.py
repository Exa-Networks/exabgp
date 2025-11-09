
"""
reactor/interrupt.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import signal

from exabgp.logger import log


class Signal:
    NONE = 0
    SHUTDOWN = -1
    RESTART = -2
    RELOAD = -4
    FULL_RELOAD = -8

    _names = {
        **dict(
            (k, v)
            for v, k in reversed(sorted(signal.__dict__.items()))
            if v.startswith('SIG') and not v.startswith('SIG_')
        ),
        **{
            NONE: 'none',
            SHUTDOWN: 'shutdown',
            RESTART: 'restart',
            RELOAD: 'reload',
            FULL_RELOAD: 'full reload',
            # some padding to make black format this as we like :-)
        },
    }

    @classmethod
    def name(cls, received):
        return cls._names.get(received, 'unknown')

    def __init__(self):
        self.received = self.NONE
        self.number = 0
        self.rearm()

    def rearm(self):
        self.received = Signal.NONE
        self.number = 0

        signal.signal(signal.SIGTERM, self.sigterm)
        signal.signal(signal.SIGHUP, self.sighup)
        signal.signal(signal.SIGALRM, self.sigalrm)
        signal.signal(signal.SIGUSR1, self.sigusr1)
        signal.signal(signal.SIGUSR2, self.sigusr2)

    def sigterm(self, signum, frame):
        log.critical(lambda: 'SIGTERM received', 'reactor')
        if self.received:
            log.critical(lambda: 'ignoring - still handling previous signal', 'reactor')
            return
        log.critical(lambda: 'scheduling shutdown', 'reactor')
        self.received = self.SHUTDOWN
        self.number = signum

    def sighup(self, signum, frame):
        log.critical(lambda: 'SIGHUP received', 'reactor')
        if self.received:
            log.critical(lambda: 'ignoring - still handling previous signal', 'reactor')
            return
        log.critical(lambda: 'scheduling shutdown', 'reactor')
        self.received = self.SHUTDOWN
        self.number = signum

    def sigalrm(self, signum, frame):
        log.critical(lambda: 'SIGALRM received', 'reactor')
        if self.received:
            log.critical(lambda: 'ignoring - still handling previous signal', 'reactor')
            return
        log.critical(lambda: 'scheduling restart', 'reactor')
        self.received = self.RESTART
        self.number = signum

    def sigusr1(self, signum, frame):
        log.critical(lambda: 'SIGUSR1 received', 'reactor')
        if self.received:
            log.critical(lambda: 'ignoring - still handling previous signal', 'reactor')
            return
        log.critical(lambda: 'scheduling reload of configuration', 'reactor')
        self.received = self.RELOAD
        self.number = signum

    def sigusr2(self, signum, frame):
        log.critical(lambda: 'SIGUSR2 received', 'reactor')
        if self.received:
            log.critical(lambda: 'ignoring - still handling previous signal', 'reactor')
            return
        log.critical(lambda: 'scheduling reload of configuration and processes', 'reactor')
        self.received = self.FULL_RELOAD
        self.number = signum
