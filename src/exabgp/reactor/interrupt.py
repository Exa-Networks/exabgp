"""reactor/interrupt.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import signal
from typing import ClassVar
from types import FrameType

from exabgp.logger import log, lazymsg


class Signal:
    NONE: int = 0
    SHUTDOWN: int = -1
    RESTART: int = -2
    RELOAD: int = -4
    FULL_RELOAD: int = -8

    _names: ClassVar[dict[int, str]] = {
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
        self._ready: bool = False
        self._pending: list[tuple[int, int]] = []
        self.rearm()

    def mark_ready(self) -> None:
        """Mark the signal handler as ready to process signals.

        If signals were received before ready, the first one will be processed now.
        Remaining signals will be processed after each rearm() call.
        """
        self._ready = True
        if self._pending:
            log.critical(lazymsg('signal.processing_deferred count={c}', c=len(self._pending)), 'reactor')
            self.received, self.number = self._pending.pop(0)

    def rearm(self) -> None:
        self.received = Signal.NONE
        self.number = 0

        # Process next queued signal if any
        if self._pending:
            self.received, self.number = self._pending.pop(0)

        signal.signal(signal.SIGTERM, self.sigterm)
        signal.signal(signal.SIGHUP, self.sighup)
        signal.signal(signal.SIGALRM, self.sigalrm)
        signal.signal(signal.SIGUSR1, self.sigusr1)
        signal.signal(signal.SIGUSR2, self.sigusr2)

    def _defer_or_schedule(self, action: int, signum: int, action_name: str) -> None:
        """Common logic for signal handlers - defer if not ready, schedule if ready."""
        if not self._ready:
            # Deduplicate by action type
            if any(a == action for a, _ in self._pending):
                log.critical(
                    lazymsg('signal.deferred reason=not_ready action={a} status=duplicate', a=action_name), 'reactor'
                )
                return
            log.critical(lazymsg('signal.deferred reason=not_ready action={a} status=queued', a=action_name), 'reactor')
            self._pending.append((action, signum))
            return
        if self.received:
            log.critical(lazymsg('signal.ignored reason=handling_previous'), 'reactor')
            return
        log.critical(lazymsg('signal.scheduling action={a}', a=action_name), 'reactor')
        self.received = action
        self.number = signum

    def sigterm(self, signum: int, frame: FrameType | None) -> None:
        log.critical(lazymsg('signal.received signal=SIGTERM'), 'reactor')
        self._defer_or_schedule(self.SHUTDOWN, signum, 'shutdown')

    def sighup(self, signum: int, frame: FrameType | None) -> None:
        log.critical(lazymsg('signal.received signal=SIGHUP'), 'reactor')
        self._defer_or_schedule(self.SHUTDOWN, signum, 'shutdown')

    def sigalrm(self, signum: int, frame: FrameType | None) -> None:
        log.critical(lazymsg('signal.received signal=SIGALRM'), 'reactor')
        self._defer_or_schedule(self.RESTART, signum, 'restart')

    def sigusr1(self, signum: int, frame: FrameType | None) -> None:
        log.critical(lazymsg('signal.received signal=SIGUSR1'), 'reactor')
        self._defer_or_schedule(self.RELOAD, signum, 'reload_config')

    def sigusr2(self, signum: int, frame: FrameType | None) -> None:
        log.critical(lazymsg('signal.received signal=SIGUSR2'), 'reactor')
        self._defer_or_schedule(self.FULL_RELOAD, signum, 'full_reload')
