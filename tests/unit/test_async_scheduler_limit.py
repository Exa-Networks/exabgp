"""The scheduler loses no callback at the end of its turn, and runs a command as a command.

Generators are advanced ASYNC.LIMIT steps per turn. The callback taken from the queue on
the last step was put back only if it was a generator: a coroutine there was dropped, never
awaited. And a coroutine met among generators ran without applying_commands, which tells
the peers to leave the RIB alone until what a helper wrote together has all been applied.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from exabgp.reactor.asynchronous import ASYNC


def steps(count: int) -> Iterator[bool]:
    for _ in range(count):
        yield False


@pytest.mark.asyncio
async def test_a_coroutine_taken_on_the_last_step_is_run_next_turn() -> None:
    scheduler = ASYNC()
    ran: list[str] = []

    async def command() -> None:
        ran.append('command')

    # the generator ends on the last step of the turn, which takes the coroutine after it
    scheduler.schedule('generator', 'generator', steps(ASYNC.LIMIT - 1))
    scheduler.schedule('command', 'command', command())

    await scheduler._run_async()
    assert ran == []
    assert not scheduler.ready(), 'the coroutine was taken off the queue and never run'

    await scheduler._run_async()
    assert ran == ['command']
    assert scheduler.ready()


@pytest.mark.asyncio
async def test_a_generator_not_finished_stays_queued() -> None:
    scheduler = ASYNC()
    scheduler.schedule('generator', 'generator', steps(ASYNC.LIMIT * 2))

    assert await scheduler._run_async()
    assert not scheduler.ready()
    await scheduler._run_async()
    assert not await scheduler._run_async()
    assert scheduler.ready()


@pytest.mark.asyncio
async def test_a_coroutine_among_generators_runs_as_a_command() -> None:
    scheduler = ASYNC()
    seen: list[bool] = []

    async def command() -> None:
        seen.append(scheduler.applying_commands)

    scheduler.schedule('generator', 'generator', steps(1))
    scheduler.schedule('command', 'command', command())

    await scheduler._run_async()
    assert seen == [True]
    assert not scheduler.applying_commands
