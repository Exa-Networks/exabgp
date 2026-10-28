"""The one place a failure nobody foresaw is caught whole.

One process serves every peer and every helper. A command which fails in a way nobody
wrote a handler for, a scheduled callback, a peer's task, a CLI line: none of them may take
the others down with it (EXA_STYLE.md 1.2: an API client gets an error answer, never an
exception through the reactor). Each of those boundaries wraps its work in `isolated`,
and says what to do with the failure: log it, answer the helper, reset the peer.

Everywhere else catches the exceptions it expects by name. Catching `Exception` anywhere
but here is what ruff BLE001 refuses, so a new boundary is a new use of this module, not
a new blind `except`.

Only an Exception is stopped. KeyboardInterrupt, SystemExit and asyncio's CancelledError
are not failures of the work but a request to stop it, and go on as they would have.

Created by Thomas Mangin on 2026-10-28.
Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from types import TracebackType


class isolated:
    """`with isolated(report):` runs the block; a failure is given to `report` and goes no further.

    A class, not a contextmanager: __exit__ says it returns bool, which is what tells mypy
    the block may end here, and that the line after the `with` can be reached. `failed`
    says, after the block, whether it was cut short, for a loop which then has to stop.
    """

    __slots__ = ('_report', 'failed')

    def __init__(self, report: Callable[[Exception], None]) -> None:
        self._report = report
        self.failed = False

    def __enter__(self) -> None:
        return None

    def __exit__(
        self, kind: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> bool:
        # the test `except Exception` makes, which is the one this boundary exists to make
        if not isinstance(exc, Exception):
            return False
        self.failed = True
        self._report(exc)
        return True


class isolated_async:
    """`async with isolated_async(report):`, for a block which awaits, with a report which may await."""

    __slots__ = ('_report', 'failed')

    def __init__(self, report: Callable[[Exception], Awaitable[None]]) -> None:
        self._report = report
        self.failed = False

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self, kind: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> bool:
        if not isinstance(exc, Exception):
            return False
        self.failed = True
        await self._report(exc)
        return True
