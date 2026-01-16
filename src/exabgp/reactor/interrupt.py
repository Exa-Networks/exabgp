
"""reactor/interrupt.py

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

            NONE: 'none',
            SHUTDOWN: 'shutdown',
            RESTART: 'restart',
            RELOAD: 'reload',
            FULL_RELOAD: 'full reload'
            # some padding to make black format this as we like :-)
        ,
    }

    @classmethod
    def name(cls, received):
        return cls._names.get(received, 'unknown')

    def __init__(self):
        self.received = self.NONE
        self.number = 0
        self._ready = False
        self._pending = []
        self.rearm()

    def mark_ready(self):
        """Mark the signal handler as ready to process signals.

        If signals were received before ready, the first one will be processed now.
        Remaining signals will be processed after each rearm() call.
        """
        self._ready = True
        if self._pending:
            log.critical(lambda: f'processing {len(self._pending)} deferred signal(s)', 'reactor')
            self.received, self.number = self._pending.pop(0)

    def rearm(self):
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

    def _defer_or_schedule(self, action, signum, action_name):
        """Common logic for signal handlers - defer if not ready, schedule if ready."""
        if not self._ready:
            # Deduplicate by action type
            if any(a == action for a, _ in self._pending):
                log.critical(lambda: f'signal deferred (not ready, duplicate): {action_name}', 'reactor')
                return
            log.critical(lambda: f'signal deferred (not ready): {action_name}', 'reactor')
            self._pending.append((action, signum))
            return
        if self.received:
            log.critical(lambda: 'ignoring - still handling previous signal', 'reactor')
            return
        log.critical(lambda: f'scheduling {action_name}', 'reactor')
        self.received = action
        self.number = signum

    def sigterm(self, signum, frame):
        log.critical(lambda: 'SIGTERM received', 'reactor')
        self._defer_or_schedule(self.SHUTDOWN, signum, 'shutdown')

    def sighup(self, signum, frame):
        log.critical(lambda: 'SIGHUP received', 'reactor')
        self._defer_or_schedule(self.SHUTDOWN, signum, 'shutdown')

    def sigalrm(self, signum, frame):
        log.critical(lambda: 'SIGALRM received', 'reactor')
        self._defer_or_schedule(self.RESTART, signum, 'restart')

    def sigusr1(self, signum, frame):
        log.critical(lambda: 'SIGUSR1 received', 'reactor')
        self._defer_or_schedule(self.RELOAD, signum, 'reload')

    def sigusr2(self, signum, frame):
        log.critical(lambda: 'SIGUSR2 received', 'reactor')
        self._defer_or_schedule(self.FULL_RELOAD, signum, 'full_reload')
