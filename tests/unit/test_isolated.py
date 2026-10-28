"""exabgp.util.isolated stops an Exception, and nothing which asks the work to stop.

Created by Thomas Mangin on 2026-10-28.
Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio

import pytest

from exabgp.util.isolated import isolated, isolated_async


def test_a_failure_is_reported_and_goes_no_further() -> None:
    reported: list[Exception] = []
    guard = isolated(reported.append)
    with guard:
        raise ValueError('broken')
    assert [str(each) for each in reported] == ['broken']
    assert guard.failed


def test_a_block_which_ends_is_not_reported() -> None:
    reported: list[Exception] = []
    guard = isolated(reported.append)
    with guard:
        pass
    assert reported == []
    assert not guard.failed


@pytest.mark.parametrize('stop', [KeyboardInterrupt, SystemExit, asyncio.CancelledError])
def test_a_request_to_stop_goes_through(stop: type[BaseException]) -> None:
    reported: list[Exception] = []
    with pytest.raises(stop), isolated(reported.append):
        raise stop()
    assert reported == []


def test_the_async_guard_awaits_its_report() -> None:
    reported: list[Exception] = []

    async def report(exc: Exception) -> None:
        await asyncio.sleep(0)
        reported.append(exc)

    async def run() -> bool:
        guard = isolated_async(report)
        async with guard:
            raise RuntimeError('broken')
        return guard.failed

    assert asyncio.run(run())
    assert [str(each) for each in reported] == ['broken']


def test_the_async_guard_lets_a_cancellation_through() -> None:
    async def report(exc: Exception) -> None:
        raise AssertionError('a cancellation is not a failure')

    async def run() -> None:
        async with isolated_async(report):
            raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())
