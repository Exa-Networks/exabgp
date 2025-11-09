
"""
reactor/async.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
import inspect
from collections import deque

from exabgp.logger import log


class ASYNC:
    LIMIT = 50

    def __init__(self):
        self._async = deque()

    def ready(self):
        return not self._async

    def _is_coroutine(self, callback):
        """Check if callback is a coroutine or coroutine function"""
        return inspect.iscoroutine(callback) or inspect.iscoroutinefunction(callback)

    def schedule(self, uid, command, callback):
        """
        Schedule a callback (generator or coroutine) for execution

        Args:
            uid: Unique identifier
            command: Command string
            callback: Generator or coroutine to execute
        """
        log.debug(lambda: f'async | {uid} | {command}', 'reactor')
        self._async.append((uid, callback))

    def clear(self, deluid=None):
        if not self._async:
            return
        if deluid is None:
            # We could delete all the generators just to be safe
            self._async = deque()
            return
        running = deque()
        for uid, generator in self._async:
            if uid != deluid:
                running.append((uid, generator))
        self._async = running

    def run(self):
        """
        Execute scheduled callbacks (synchronous wrapper for backward compatibility)

        This method provides backward compatibility by calling the async version.
        For generators-only workload, this works synchronously.
        If coroutines are present, they will be executed in a new event loop.
        """
        # If no tasks, return immediately
        if not self._async:
            return False

        # Check if we have any coroutines in the queue
        has_coroutines = any(
            self._is_coroutine(callback) for _, callback in self._async
        )

        if has_coroutines:
            # If we have coroutines, we need to run in async context
            try:
                # Try to get existing loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is already running, we can't use run_until_complete
                    # This shouldn't happen in normal operation
                    log.warning(lambda: 'async | Cannot run coroutines: event loop already running', 'reactor')
                    return False
                else:
                    return loop.run_until_complete(self._run_async())
            except RuntimeError:
                # No event loop exists, create a new one
                return asyncio.run(self._run_async())
        else:
            # Only generators, run synchronously
            return asyncio.run(self._run_async())

    async def _run_async(self):
        """Execute scheduled callbacks (supports both generators and coroutines)"""
        if not self._async:
            return False

        # length = range(min(len(self._async),self.LIMIT))
        length = range(self.LIMIT)
        uid, callback = self._async.popleft()

        for _ in length:
            try:
                # Support both old (generator) and new (coroutine) style
                if inspect.isgenerator(callback):
                    # Old style: resume generator
                    next(callback)
                elif inspect.iscoroutine(callback):
                    # New style: await coroutine
                    await callback
                elif inspect.iscoroutinefunction(callback):
                    # Coroutine function that needs to be called first
                    await callback()
                else:
                    # Fallback to generator behavior
                    next(callback)
            except StopIteration:
                if not self._async:
                    return False
                uid, callback = self._async.popleft()
            except Exception as exc:
                log.error(lambda uid=uid: f'async | {uid} | problem with function', 'reactor')
                for line in str(exc).split('\n'):
                    log.error(lambda line=line, uid=uid: f'async | {uid} | {line}', 'reactor')
                if not self._async:
                    return False
                uid, callback = self._async.popleft()

        self._async.appendleft((uid, callback))
        return True
