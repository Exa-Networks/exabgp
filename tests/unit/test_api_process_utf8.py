"""What a helper writes is read as UTF-8, a character cut by a read included.

A helper's output was decoded as ASCII. An octet above 127, a teardown whose Shutdown
Communication (RFC 9003) is UTF-8 text, raised UnicodeDecodeError: the helper was stopped
and every command of the read lost with it, and the NOTIFICATION never sent.
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
TEARDOWN = 'neighbor 127.0.0.1 teardown 2 "café fermé"\n'.encode()
ANNOUNCE = b'announce route 10.0.0.1/32 next-hop 1.2.3.4\n'


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
def processes(pipe: tuple[int, int]) -> Iterator[Processes]:
    loop = asyncio.new_event_loop()
    built = Processes()
    stdout = io.BufferedReader(io.FileIO(pipe[0], 'rb', closefd=False))
    built._process[HELPER] = cast(Any, Helper(stdout))
    built._async_mode = True
    built._loop = loop
    loop.add_reader(pipe[0], built._async_reader_callback, HELPER)
    yield built
    loop.remove_reader(pipe[0])
    loop.close()


def commands(processes: Processes) -> list[str]:
    return [command for _, command in processes._command_queue]


def test_a_utf8_teardown_text_is_read_with_the_commands_beside_it(pipe: tuple[int, int], processes: Processes) -> None:
    os.write(pipe[1], TEARDOWN + ANNOUNCE)
    processes._async_reader_callback(HELPER)

    assert HELPER in processes._process, 'the helper was stopped'
    assert commands(processes) == [TEARDOWN.decode().strip(), ANNOUNCE.decode().strip()]


def test_a_character_cut_by_a_read_is_completed_by_the_next(pipe: tuple[int, int], processes: Processes) -> None:
    cut = TEARDOWN.index('é'.encode()) + 1
    os.write(pipe[1], TEARDOWN[:cut])
    processes._async_reader_callback(HELPER)
    os.write(pipe[1], TEARDOWN[cut:])
    processes._async_reader_callback(HELPER)

    assert commands(processes) == [TEARDOWN.decode().strip()]


def test_an_octet_which_is_not_utf8_does_not_stop_the_helper(pipe: tuple[int, int], processes: Processes) -> None:
    os.write(pipe[1], b'neighbor 127.0.0.1 teardown 2 "\xff"\n' + ANNOUNCE)
    processes._async_reader_callback(HELPER)

    assert HELPER in processes._process, 'the helper was stopped'
    assert commands(processes) == ['neighbor 127.0.0.1 teardown 2 "�"', ANNOUNCE.decode().strip()]
