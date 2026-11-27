"""A reactor with nothing to do waits, instead of going round as fast as it can.

The main loop ended every pass with asyncio.sleep(0) and nothing in it blocked, so it
never let the event loop sleep: a daemon with a helper alive and its peer down sat at 98%
of a core for as long as it ran. Six of them, orphaned by a test harness, held six cores
for two and a half days.

What wakes the reactor early is what cannot wait for its next look: a helper writing a
command or going away, and a line queued for a helper, which only the reactor sends.
"""

from __future__ import annotations

import asyncio
import io
import os
import time
from typing import Any, cast

import pytest

from exabgp.environment import getenv
from exabgp.logger import log
from exabgp.reactor.api.processes import Processes
from exabgp.reactor.interrupt import Signal
from exabgp.reactor.loop import Reactor
from tests import negotiation

log.init(getenv())

# long enough that a reactor which stopped before it had not waited it out
NEVER_SECONDS = 60.0


def idle_reactor() -> Reactor:
    """A real Reactor with no peer, no helper and no listener: nothing to do."""
    reactor: Reactor
    reactor, _ = negotiation.reactor()
    return reactor


async def stop(reactor: Reactor, running: asyncio.Task[None]) -> None:
    reactor.signal.received = Signal.SHUTDOWN
    reactor.wake()
    await asyncio.wait_for(running, timeout=10)


def test_an_idle_reactor_leaves_the_cpu_alone() -> None:
    async def idle_for(seconds: float) -> float:
        reactor = idle_reactor()
        running = asyncio.create_task(reactor._async_main_loop())
        # let it start, so only the idling is measured
        await asyncio.sleep(0.1)
        before = time.process_time()
        await asyncio.sleep(seconds)
        used = time.process_time() - before
        await stop(reactor, running)
        return used

    waited = 1.0
    used = asyncio.run(idle_for(waited))

    assert used < waited / 4, f'an idle reactor used {used:.2f}s of CPU in {waited:.0f}s'


def test_a_wake_ends_the_wait_at_once() -> None:
    async def woken() -> float:
        reactor = idle_reactor()
        reactor.idle_wait_seconds = NEVER_SECONDS
        running = asyncio.create_task(reactor._async_main_loop())
        await asyncio.sleep(0.1)
        assert not running.done()
        before = time.monotonic()
        await stop(reactor, running)
        return time.monotonic() - before

    assert asyncio.run(woken()) < NEVER_SECONDS / 10


def test_a_shutdown_asked_for_during_a_pass_is_not_slept_on() -> None:
    """A helper found lost by a pass asks for the shutdown the next pass carries out.

    Nothing wakes the reactor for it, so the pass which asked must not be followed by a wait.
    """

    async def stopped() -> float:
        reactor = idle_reactor()
        reactor.idle_wait_seconds = NEVER_SECONDS
        reactor.processes.terminate_on_error = True
        reactor.processes._ended.append('helper')
        before = time.monotonic()
        await asyncio.wait_for(reactor._async_main_loop(), timeout=10)
        return time.monotonic() - before

    assert asyncio.run(stopped()) < NEVER_SECONDS / 10


class FakeProcess:
    """The parts of subprocess.Popen the async reader touches."""

    def __init__(self, stdout: io.FileIO) -> None:
        self.stdout = stdout
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        """The helper given up on has no child to stop."""

    def wait(self, timeout: float | None = None) -> int | None:
        return self.returncode


@pytest.fixture
def pipe() -> Any:
    read_fd, write_fd = os.pipe()
    os.set_blocking(read_fd, False)
    yield read_fd, write_fd
    for fd in (read_fd, write_fd):
        try:
            os.close(fd)
        except OSError:
            # A test closes the writer itself to make the helper go away.
            pass


class Woken:
    """Counts the times the reactor was asked to look."""

    def __init__(self) -> None:
        self.times = 0

    def __call__(self) -> None:
        self.times += 1


@pytest.fixture
def helper(pipe: Any) -> tuple[Processes, Woken]:
    read_fd, _ = pipe
    processes = Processes()
    processes._process['test'] = cast(Any, FakeProcess(io.FileIO(read_fd, 'rb', closefd=False)))
    processes.respawn_number = 0
    woken = Woken()
    processes.wake = woken
    return processes, woken


def test_a_command_from_a_helper_wakes_the_reactor(pipe: Any, helper: tuple[Processes, Woken]) -> None:
    processes, woken = helper
    _, write_fd = pipe
    os.write(write_fd, b'announce route 10.0.0.1/32 next-hop 1.2.3.4\n')

    processes._async_reader_callback('test')

    assert len(processes._command_queue) == 1
    assert woken.times == 1


def test_a_helper_going_away_wakes_the_reactor(pipe: Any, helper: tuple[Processes, Woken]) -> None:
    processes, woken = helper
    _, write_fd = pipe
    os.close(write_fd)
    cast(Any, processes._process['test']).returncode = 0

    processes._async_reader_callback('test')

    assert processes.lost() == ['test']
    assert woken.times == 1


def test_a_line_queued_for_a_helper_wakes_the_reactor(helper: tuple[Processes, Woken]) -> None:
    """A peer task queues what it tells a helper, and the reactor is what writes it."""
    processes, woken = helper
    processes._async_mode = True

    assert processes.write('test', 'neighbor 192.0.2.1 up')

    assert processes.waiting()
    assert woken.times == 1


def test_a_reactor_hears_its_helpers() -> None:
    """The reactor's own Processes wakes that reactor."""
    reactor = idle_reactor()
    reactor._listen_to_helpers()

    async def heard() -> bool:
        reactor.processes.wake()
        return reactor._wake.is_set()

    assert asyncio.run(heard())
