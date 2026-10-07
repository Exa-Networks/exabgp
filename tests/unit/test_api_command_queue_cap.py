"""The commands read from the helpers and not yet applied are capped.

A helper writing faster than the reactor applies its commands grew _command_queue without
limit. Past MAX_QUEUED_COMMANDS the helper is no longer read, so the pipe fills and the
helper waits on its writes, and it is read again once the reactor has caught up.
"""

from __future__ import annotations

import asyncio
import io
import os
from collections.abc import Iterator
from typing import Any, cast

import pytest

from exabgp.environment import getenv
from exabgp.logger import log
from exabgp.reactor.api.processes import Processes

log.init(getenv())

HELPER = 'helper'
LINE = b'announce route 10.0.0.1/32 next-hop 1.2.3.4\n'


class Helper:
    """The parts of subprocess.Popen the reader touches: a running process and its stdout."""

    def __init__(self, stdout: io.BufferedReader) -> None:
        self.stdout = stdout

    def poll(self) -> int | None:
        return None


@pytest.fixture
def pipe() -> Iterator[tuple[int, int]]:
    read_fd, write_fd = os.pipe()
    os.set_blocking(read_fd, False)
    yield read_fd, write_fd
    os.close(read_fd)
    os.close(write_fd)


@pytest.fixture
def loop() -> Iterator[asyncio.AbstractEventLoop]:
    created = asyncio.new_event_loop()
    yield created
    created.close()


@pytest.fixture
def processes(pipe: tuple[int, int], loop: asyncio.AbstractEventLoop, monkeypatch: pytest.MonkeyPatch) -> Processes:
    monkeypatch.setattr(Processes, 'MAX_COMMANDS_PER_PASS', 2)
    # raising=False: the cap is what is under test, a tree without it fails the test, not the fixture
    monkeypatch.setattr(Processes, 'MAX_QUEUED_COMMANDS', 6, raising=False)
    built = Processes()
    stdout = io.BufferedReader(io.FileIO(pipe[0], 'rb', closefd=False))
    built._process[HELPER] = cast(Any, Helper(stdout))
    built._async_mode = True
    built._loop = loop
    loop.add_reader(pipe[0], built._async_reader_callback, HELPER)
    return built


def read_by_the_loop(loop: asyncio.AbstractEventLoop, fd: int, processes: Processes) -> bool:
    """Whether the event loop reads the helper, putting the reader back as it was."""
    registered = loop.remove_reader(fd)
    if registered:
        loop.add_reader(fd, processes._async_reader_callback, HELPER)
    return registered


def test_a_full_queue_stops_reading_the_helper(
    pipe: tuple[int, int], loop: asyncio.AbstractEventLoop, processes: Processes
) -> None:
    read_fd, write_fd = pipe
    os.write(write_fd, LINE * 8)
    processes._async_reader_callback(HELPER)

    assert len(processes._command_queue) == 8
    assert not read_by_the_loop(loop, read_fd, processes), 'a helper is still read past the cap'


def test_a_queue_under_the_cap_keeps_reading(
    pipe: tuple[int, int], loop: asyncio.AbstractEventLoop, processes: Processes
) -> None:
    read_fd, write_fd = pipe
    os.write(write_fd, LINE * 3)
    processes._async_reader_callback(HELPER)

    assert len(processes._command_queue) == 3
    assert read_by_the_loop(loop, read_fd, processes)


def test_the_helper_is_read_again_once_the_reactor_caught_up(
    pipe: tuple[int, int], loop: asyncio.AbstractEventLoop, processes: Processes
) -> None:
    read_fd, write_fd = pipe
    os.write(write_fd, LINE * 8)
    processes._async_reader_callback(HELPER)

    applied = 0
    # bounded: each pass takes MAX_COMMANDS_PER_PASS commands off a queue of eight
    for _ in range(10):
        if read_by_the_loop(loop, read_fd, processes):
            break
        applied += len(list(processes.received_async()))
    else:
        raise AssertionError('the helper was never read again')

    # read again with room for a pass more, not before
    assert len(processes._command_queue) <= Processes.MAX_QUEUED_COMMANDS - Processes.MAX_COMMANDS_PER_PASS
    assert applied + len(processes._command_queue) == 8, 'no command was lost while it waited'


def test_a_helper_gone_while_paused_is_not_read_again(
    pipe: tuple[int, int], loop: asyncio.AbstractEventLoop, processes: Processes
) -> None:
    read_fd, write_fd = pipe
    os.write(write_fd, LINE * 8)
    processes._async_reader_callback(HELPER)
    del processes._process[HELPER]

    # bounded: the queue of eight drains in four passes
    for _ in range(10):
        list(processes.received_async())

    assert not processes._command_queue
    assert not read_by_the_loop(loop, read_fd, processes)
    assert not processes._paused
