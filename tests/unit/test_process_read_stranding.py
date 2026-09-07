#!/usr/bin/env python3
# encoding: utf-8

"""The process readers must read the kernel fd, never the BufferedReader over it

Both readers decide whether a helper process has anything to say by asking the
kernel about the pipe: `received()` calls `select.poll(0)` on the file descriptor,
and `_async_reader_callback` is driven by `loop.add_reader`, which is level
triggered on that same descriptor. If the read which follows goes through the
`BufferedReader` that `subprocess.Popen` wraps the pipe in, the two disagree:
`BufferedReader.read(n)` can drain more from the pipe than it hands back, and the
excess sits in a user-space buffer neither poll nor the event loop can see.

Mid-batch that is harmless, the writer's next flush makes the fd readable again
and the hidden bytes come out. At the tail of a batch nothing follows, so the last
commands are stranded and silently never executed. See issue #1421: the bug
arrived in 2017 when an unbounded `read()` (which could not strand anything)
became `read(16384)`, and it is why the symptom is flaky.

`os.read(fd, n)` never consumes more than it returns, so the readable check and
the read agree. Both readers use it, and these tests are what stops a future
cleanup from quietly putting the buffered call back.
"""

import collections
import io
import os
import select

import pytest

from exabgp.environment import getenv
from exabgp.logger import log
from exabgp.reactor.api.processes import Processes

log.init(getenv())


class _InjectingRaw(io.FileIO):
    """A pipe whose writer flushes between the BufferedReader's two raw reads

    This is the kernel scheduling which makes the bug appear, made deterministic:
    CPython's buffered read asks the raw object twice when the first answer is
    short, and real data landing between those two calls is what ends up hidden.
    """

    def __init__(self, read_fd: int, write_fd: int, second: bytes) -> None:
        super().__init__(read_fd, 'rb', closefd=False)
        self._write_fd = write_fd
        self._second = second
        self.calls = 0

    def readinto(self, buffer) -> int:  # type: ignore[override]
        read = super().readinto(buffer)
        self.calls += 1
        if self.calls == 1 and self._second:
            os.write(self._write_fd, self._second)
            self._second = b''
        return read


class _RefusingReader(io.BufferedReader):
    """A stdout which fails loudly if anything reads it instead of its fd"""

    def read(self, size: int | None = -1) -> bytes:
        raise AssertionError('the reader must use the raw fd, not the BufferedReader over it')

    def read1(self, size: int = -1) -> bytes:
        raise AssertionError('the reader must use the raw fd, not the BufferedReader over it')


class _FakeProcess:
    """The parts of subprocess.Popen which the readers touch"""

    def __init__(self, stdout: io.BufferedReader) -> None:
        self.stdout = stdout

    def poll(self):
        return None


@pytest.fixture
def pipe():
    read_fd, write_fd = os.pipe()
    os.set_blocking(read_fd, False)
    yield read_fd, write_fd
    os.close(read_fd)
    os.close(write_fd)


@pytest.fixture
def processes(pipe):
    read_fd, _ = pipe
    processes = Processes()
    stdout = _RefusingReader(io.FileIO(read_fd, 'rb', closefd=False), buffer_size=8192)
    processes._process['test'] = _FakeProcess(stdout)  # type: ignore[assignment]
    processes._command_queue = collections.deque()
    return processes


class TestTheTrap:
    """Why the raw fd is not a matter of taste"""

    def test_a_buffered_read_can_hide_bytes_from_poll(self, pipe) -> None:
        read_fd, write_fd = pipe
        raw = _InjectingRaw(read_fd, write_fd, b'y' * 5000)
        reader = io.BufferedReader(raw, buffer_size=8192)

        os.write(write_fd, b'x' * 12000)
        assert len(reader.read(16384)) == 16384
        assert raw.calls == 2, 'the two-phase buffered read did not happen, the test no longer proves anything'

        poller = select.poll()
        poller.register(read_fd, select.POLLIN)
        assert poller.poll(0) == [], 'the kernel pipe should look empty'
        with pytest.raises(BlockingIOError):
            os.read(read_fd, 16384)

        assert len(reader.read(16384)) == 616, 'these are the bytes the reader would have stranded'

    def test_reading_the_raw_fd_hides_nothing(self, pipe) -> None:
        read_fd, write_fd = pipe
        os.write(write_fd, b'x' * 17000)

        assert len(os.read(read_fd, 16384)) == 16384

        poller = select.poll()
        poller.register(read_fd, select.POLLIN)
        assert poller.poll(0) != [], 'poll must still see what has not been read'
        assert len(os.read(read_fd, 16384)) == 616


class TestTheAsyncReader:
    """_async_reader_callback, the reader the reactor actually runs"""

    def test_it_does_not_read_the_buffered_object(self, pipe, processes) -> None:
        _, write_fd = pipe
        os.write(write_fd, b'announce route 10.0.0.1/32 next-hop 1.2.3.4\n')

        processes._async_reader_callback('test')

        assert [process for process, _ in processes._command_queue] == ['test']

    def test_it_queues_every_command_written_before_the_writer_went_quiet(self, pipe, processes) -> None:
        _, write_fd = pipe
        # a batch larger than one read, so the tail can only arrive on a later cycle
        expected = [f'announce route 10.0.0.{index // 256}.{index % 256}/32 next-hop 1.2.3.4' for index in range(400)]
        os.write(write_fd, ('\n'.join(expected) + '\n').encode('ascii'))

        for _ in range(10):
            processes._async_reader_callback('test')
            if len(processes._command_queue) == len(expected):
                break

        assert len(processes._command_queue) == len(expected), 'commands were stranded'


class TestTheSyncReader:
    """received() is not wired to the reactor, but must not carry the bad pattern"""

    def test_it_does_not_read_the_buffered_object(self, pipe, processes) -> None:
        _, write_fd = pipe
        os.write(write_fd, b'announce route 10.0.0.1/32 next-hop 1.2.3.4\n')

        assert [process for process, _ in processes.received()] == ['test']
