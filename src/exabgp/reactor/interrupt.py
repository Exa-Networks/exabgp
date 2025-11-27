"""reactor/interrupt.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import signal
from typing import ClassVar, Dict
from types import FrameType

from exabgp.logger import log, lazymsg


class Signal:
    NONE: int = 0
    SHUTDOWN: int = -1
    RESTART: int = -2
    RELOAD: int = -4
    FULL_RELOAD: int = -8

    _names: ClassVar[Dict[int, str]] = {
        **dict(
            (k, v)
            for v, k in reversed(sorted(signal.__dict__.items()))
            if v.startswith('SIG') and not v.startswith('SIG_')
        ),
        NONE: 'none',
        SHUTDOWN: 'shutdown',
        RESTART: 'restart',
        RELOAD: 'reload',
        FULL_RELOAD: 'full reload',
        # some padding to make black format this as we like :-)
    }

    @classmethod
    def name(cls, received: int) -> str:
        return cls._names.get(received, 'unknown')

    def __init__(self) -> None:
        self.received: int = self.NONE
        self.number: int = 0
        self.rearm()

    def rearm(self) -> None:
        self.received = Signal.NONE
        self.number = 0

        signal.signal(signal.SIGTERM, self.sigterm)
        signal.signal(signal.SIGHUP, self.sighup)
        signal.signal(signal.SIGALRM, self.sigalrm)
        signal.signal(signal.SIGUSR1, self.sigusr1)
        signal.signal(signal.SIGUSR2, self.sigusr2)

    def sigterm(self, signum: int, frame: FrameType | None) -> None:
        log.critical(lazymsg('signal.received signal=SIGTERM'), 'reactor')
        if self.received:
            log.critical(lazymsg('signal.ignored reason=handling_previous'), 'reactor')
            return
        log.critical(lazymsg('signal.scheduling action=shutdown'), 'reactor')
        self.received = self.SHUTDOWN
        self.number = signum

    def sighup(self, signum: int, frame: FrameType | None) -> None:
        log.critical(lazymsg('signal.received signal=SIGHUP'), 'reactor')
        if self.received:
            log.critical(lazymsg('signal.ignored reason=handling_previous'), 'reactor')
            return
        log.critical(lazymsg('signal.scheduling action=shutdown'), 'reactor')
        self.received = self.SHUTDOWN
        self.number = signum

    def sigalrm(self, signum: int, frame: FrameType | None) -> None:
        log.critical(lazymsg('signal.received signal=SIGALRM'), 'reactor')
        if self.received:
            log.critical(lazymsg('signal.ignored reason=handling_previous'), 'reactor')
            return
        log.critical(lazymsg('signal.scheduling action=restart'), 'reactor')
        self.received = self.RESTART
        self.number = signum

    def sigusr1(self, signum: int, frame: FrameType | None) -> None:
        log.critical(lazymsg('signal.received signal=SIGUSR1'), 'reactor')
        if self.received:
            log.critical(lazymsg('signal.ignored reason=handling_previous'), 'reactor')
            return
        log.critical(lazymsg('signal.scheduling action=reload_config'), 'reactor')
        self.received = self.RELOAD
        self.number = signum

    def sigusr2(self, signum: int, frame: FrameType | None) -> None:
        log.critical(lazymsg('signal.received signal=SIGUSR2'), 'reactor')
        if self.received:
            log.critical(lazymsg('signal.ignored reason=handling_previous'), 'reactor')
            return
        log.critical(lazymsg('signal.scheduling action=full_reload'), 'reactor')
        self.received = self.FULL_RELOAD
        self.number = signum
