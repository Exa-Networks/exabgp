"""reactor/async.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
import inspect
from collections import deque
from typing import Any, Deque, Tuple

from exabgp.logger import log


class ASYNC:
    LIMIT: int = 50

    def __init__(self) -> None:
        self._async: Deque[Tuple[str, Any]] = deque()

    def ready(self) -> bool:
        return not self._async

    def _is_coroutine(self, callback: Any) -> bool:
        """Check if callback is a coroutine or coroutine function"""
        return inspect.iscoroutine(callback) or inspect.iscoroutinefunction(callback)

    def schedule(self, uid: str, command: str, callback: Any) -> None:
        """Schedule a callback (generator or coroutine) for execution

        Args:
            uid: Unique identifier
            command: Command string
            callback: Generator or coroutine to execute
        """
        log.debug(lambda: f'async | {uid} | {command}', 'reactor')
        self._async.append((uid, callback))

    def clear(self, deluid: str | None = None) -> None:
        if not self._async:
            return
        if deluid is None:
            # We could delete all the generators just to be safe
            self._async = deque()
            return
        running: deque = deque()
        for uid, generator in self._async:
            if uid != deluid:
                running.append((uid, generator))
        self._async = running

    def run(self) -> bool:
        """Execute scheduled callbacks (synchronous wrapper for backward compatibility)

        This method provides backward compatibility by calling the async version.
        For generators-only workload, this works synchronously.
        If coroutines are present, they will be executed in a new event loop.
        """
        # If no tasks, return immediately
        if not self._async:
            return False

        # Check if we have any coroutines in the queue
        has_coroutines: bool = any(self._is_coroutine(callback) for _, callback in self._async)

        if has_coroutines:
            # If we have coroutines, we need to run in async context
            try:
                # Try to get existing loop
                loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is already running, we can't use run_until_complete
                    # This shouldn't happen in normal operation
                    log.warning(lambda: 'async | Cannot run coroutines: event loop already running', 'reactor')
                    return False
                return loop.run_until_complete(self._run_async())
            except RuntimeError:
                # No event loop exists, create a new one
                return asyncio.run(self._run_async())
        else:
            # Only generators, run synchronously
            return asyncio.run(self._run_async())

    async def _run_async(self) -> bool:
        """Execute scheduled callbacks (supports both generators and coroutines)

        For generators: processes up to LIMIT iterations, then re-queues if not exhausted
        For coroutines: executes ALL pending coroutines until queue is empty
        """
        if not self._async:
            return False

        # Check if we have a mix of generators and coroutines
        first_uid, first_callback = self._async[0]

        if inspect.iscoroutine(first_callback) or inspect.iscoroutinefunction(first_callback):
            # Process ALL coroutines in the queue atomically
            # This ensures commands sent together (like "announce\nclear\n") are
            # executed atomically before peers read the RIB
            while self._async:
                uid, callback = self._async.popleft()
                try:
                    if inspect.iscoroutine(callback):
                        await callback
                    elif inspect.iscoroutinefunction(callback):
                        await callback()
                    else:
                        # Mixed queue - shouldn't happen, but handle gracefully
                        # Put it back and switch to generator processing
                        self._async.appendleft((uid, callback))
                        break
                except Exception as exc:
                    current_uid = uid
                    log.error(lambda: f'async | {current_uid} | problem with function', 'reactor')
                    for line in str(exc).split('\n'):
                        current_line = line
                        log.error(lambda: f'async | {current_uid} | {current_line}', 'reactor')
                    # Continue to next callback even if one fails
            return False  # All coroutines processed
        else:
            # Original generator processing logic
            # length = range(min(len(self._async),self.LIMIT))
            length = range(self.LIMIT)
            uid, callback = self._async.popleft()

            for _ in length:
                try:
                    # Check if current callback is a coroutine (mixed queue case)
                    if inspect.iscoroutine(callback) or inspect.iscoroutinefunction(callback):
                        # Found coroutine in generator processing - handle it
                        if inspect.iscoroutine(callback):
                            await callback
                        elif inspect.iscoroutinefunction(callback):
                            await callback()
                        # Coroutine completed - pop next callback
                        if not self._async:
                            return False
                        uid, callback = self._async.popleft()
                    elif inspect.isgenerator(callback):
                        # Old style: resume generator (may yield multiple times)
                        next(callback)
                    else:
                        # Fallback to generator behavior
                        next(callback)
                except StopIteration:
                    # Generator exhausted - pop next callback
                    if not self._async:
                        return False
                    uid, callback = self._async.popleft()
                except Exception as exc:
                    current_uid = uid
                    log.error(lambda: f'async | {current_uid} | problem with function', 'reactor')
                    for line in str(exc).split('\n'):
                        current_line = line
                        log.error(lambda: f'async | {current_uid} | {current_line}', 'reactor')
                    # Error occurred - pop next callback
                    if not self._async:
                        return False
                    uid, callback = self._async.popleft()

            # Only generators should be put back (they may not be exhausted)
            if inspect.isgenerator(callback):
                self._async.appendleft((uid, callback))
            return True
