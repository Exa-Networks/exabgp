"""answering.py

The guard of a command which has no API object to log through: what fails unhandled is
logged, and answered to the helper which sent the command (see exabgp.util.isolated).

Created by Thomas Mangin on 2026-10-28.
Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from exabgp.logger import lazyexc, log
from exabgp.util.isolated import isolated, isolated_async

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor


def answering(reactor: Reactor, service: str, failed: str = 'Unexpected error') -> isolated_async:
    """What fails inside is logged and answered to `service` as an error."""

    async def report(exc: Exception) -> None:
        message = f'{failed}: {type(exc).__name__}: {exc!s}'
        log.error(lazyexc('api.failure report={report} error={exc}', exc, report=message), 'processes')
        await reactor.processes.answer_error(service, message)

    return isolated_async(report)


def answering_sync(reactor: Reactor, service: str, failed: str = 'Unexpected error') -> isolated:
    """`answering`, for a command answered without awaiting."""

    def report(exc: Exception) -> None:
        message = f'{failed}: {type(exc).__name__}: {exc!s}'
        log.error(lazyexc('api.failure report={report} error={exc}', exc, report=message), 'processes')
        reactor.processes.answer_error_sync(service, message)

    return isolated(report)
