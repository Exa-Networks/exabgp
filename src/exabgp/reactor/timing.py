"""timing.py

Timing instrumentation for reactor performance analysis.
Enable with environment variable: exabgp_debug_timing=true

Created for async reactor debugging.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator

from exabgp.environment import getenv
from exabgp.logger import lazymsg, log


# Thresholds for slow operation warnings (milliseconds)
SLOW_THRESHOLD_MS = 50
VERY_SLOW_THRESHOLD_MS = 200


def timing_enabled() -> bool:
    """Check if timing instrumentation is enabled."""
    return getenv().debug.timing


@contextmanager
def timed_sync(name: str, warn_threshold_ms: float = SLOW_THRESHOLD_MS) -> Iterator[None]:
    """Context manager to log slow synchronous operations.

    Only logs if exabgp_debug_timing=true is set.

    Args:
        name: Operation name for logging
        warn_threshold_ms: Threshold in ms above which to log warning
    """
    if not timing_enabled():
        yield
        return

    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms > warn_threshold_ms:
            level = 'error' if elapsed_ms > VERY_SLOW_THRESHOLD_MS else 'warning'
            getattr(log, level)(
                lazymsg('timing.slow.sync operation={n} elapsed_ms={e:.1f}', n=name, e=elapsed_ms),
                'timing',
            )


@asynccontextmanager
async def timed_async(name: str, warn_threshold_ms: float = SLOW_THRESHOLD_MS) -> AsyncIterator[None]:
    """Context manager to log slow async operations.

    Only logs if exabgp_debug_timing=true is set.

    Args:
        name: Operation name for logging
        warn_threshold_ms: Threshold in ms above which to log warning
    """
    if not timing_enabled():
        yield
        return

    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms > warn_threshold_ms:
            level = 'error' if elapsed_ms > VERY_SLOW_THRESHOLD_MS else 'warning'
            getattr(log, level)(
                lazymsg('timing.slow.async operation={n} elapsed_ms={e:.1f}', n=name, e=elapsed_ms),
                'timing',
            )


class LoopTimer:
    """Tracks timing statistics for a repeatedly-executed loop.

    Usage:
        timer = LoopTimer('main_loop')
        while True:
            timer.start()
            # ... do work ...
            timer.stop()
            timer.log_if_slow()
    """

    def __init__(self, name: str, warn_threshold_ms: float = SLOW_THRESHOLD_MS) -> None:
        self.name = name
        self.warn_threshold_ms = warn_threshold_ms
        self._start: float = 0
        self._elapsed_ms: float = 0
        self._iteration: int = 0
        self._total_ms: float = 0
        self._max_ms: float = 0

    def start(self) -> None:
        """Start timing an iteration."""
        if timing_enabled():
            self._start = time.perf_counter()

    def stop(self) -> float:
        """Stop timing and return elapsed milliseconds."""
        if not timing_enabled():
            return 0

        self._elapsed_ms = (time.perf_counter() - self._start) * 1000
        self._iteration += 1
        self._total_ms += self._elapsed_ms
        if self._elapsed_ms > self._max_ms:
            self._max_ms = self._elapsed_ms
        return self._elapsed_ms

    def log_if_slow(self) -> None:
        """Log warning if last iteration was slow."""
        if not timing_enabled():
            return

        if self._elapsed_ms > self.warn_threshold_ms:
            level = 'error' if self._elapsed_ms > VERY_SLOW_THRESHOLD_MS else 'warning'
            getattr(log, level)(
                lazymsg(
                    'timing.slow.loop name={n} iteration={i} elapsed_ms={e:.1f} avg_ms={a:.1f} max_ms={m:.1f}',
                    n=self.name,
                    i=self._iteration,
                    e=self._elapsed_ms,
                    a=self._total_ms / self._iteration if self._iteration > 0 else 0,
                    m=self._max_ms,
                ),
                'timing',
            )

    def log_stats(self) -> None:
        """Log accumulated statistics."""
        if not timing_enabled() or self._iteration == 0:
            return

        log.info(
            lazymsg(
                'timing.stats name={n} iterations={i} total_ms={t:.1f} avg_ms={a:.1f} max_ms={m:.1f}',
                n=self.name,
                i=self._iteration,
                t=self._total_ms,
                a=self._total_ms / self._iteration,
                m=self._max_ms,
            ),
            'timing',
        )

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time of last iteration in milliseconds."""
        return self._elapsed_ms


class OperationTimer:
    """Simple timer for measuring individual operations.

    Usage:
        timer = OperationTimer()
        timer.start()
        # ... do work ...
        elapsed = timer.stop()
        if elapsed > 50:
            print(f"Operation took {elapsed}ms")
    """

    def __init__(self) -> None:
        self._start: float = 0
        self._elapsed_ms: float = 0

    def start(self) -> None:
        """Start the timer."""
        self._start = time.perf_counter()

    def stop(self) -> float:
        """Stop the timer and return elapsed milliseconds."""
        self._elapsed_ms = (time.perf_counter() - self._start) * 1000
        return self._elapsed_ms

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return self._elapsed_ms
