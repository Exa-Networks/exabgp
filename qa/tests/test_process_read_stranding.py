#!/usr/bin/env python3
# encoding: utf-8

"""The process reader must read the kernel fd, never the BufferedReader over it

`Processes.received()` decides whether a helper process has anything to say by
calling `select.poll(0)` on the process' stdout file descriptor. That asks the
kernel about the pipe. If the read which follows goes through the `BufferedReader`
which `subprocess.Popen` wraps the pipe in, the two disagree: `BufferedReader.read(n)`
can drain more from the pipe than it hands back, and the excess sits in a user-space
buffer that `poll()` can not see.

Mid-batch that is harmless, the writer's next flush makes poll ready again and the
hidden bytes come out. At the tail of a batch nothing follows, so the last commands
are stranded and silently never executed. See issue #1421: the bug arrived in 2017
when an unbounded `read()` (which could not strand anything) became `read(16384)`.

`os.read(fd, n)` never consumes more than it returns, so poll and the read agree.
"""

import io
import os
import select

import pytest

from exabgp.configuration.setup import environment
from exabgp.reactor.api.processes import Processes

environment.setup('')


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

    def read(self, size=-1):
        raise AssertionError('received() must read the raw fd, not the BufferedReader over it')

    def read1(self, size=-1):
        raise AssertionError('received() must read the raw fd, not the BufferedReader over it')


class _FakeProcess:
    """The parts of subprocess.Popen which received() touches"""

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
        assert poller.poll(0) == [], 'the kernel pipe should be empty'
        with pytest.raises(BlockingIOError):
            os.read(read_fd, 16384)

        assert len(reader.read(16384)) == 616, 'these are the bytes received() would have stranded'

    def test_reading_the_raw_fd_hides_nothing(self, pipe) -> None:
        read_fd, write_fd = pipe
        os.write(write_fd, b'x' * 17000)

        first = os.read(read_fd, 16384)
        assert len(first) == 16384

        poller = select.poll()
        poller.register(read_fd, select.POLLIN)
        assert poller.poll(0) != [], 'poll must still see what has not been read'
        assert len(os.read(read_fd, 16384)) == 616


class TestReceived:
    """The reader in Processes.received()"""

    def test_it_does_not_read_the_buffered_object(self, pipe) -> None:
        read_fd, write_fd = pipe
        processes = Processes()
        processes._process['test'] = _FakeProcess(
            _RefusingReader(io.FileIO(read_fd, 'rb', closefd=False), buffer_size=8192)
        )

        os.write(write_fd, b'announce route 10.0.0.1/32 next-hop 1.2.3.4\n')

        commands = list(processes.received())
        assert [process for process, _ in commands] == ['test']

    def test_it_returns_every_command_written_before_the_writer_went_quiet(self, pipe) -> None:
        read_fd, write_fd = pipe
        processes = Processes()
        processes._process['test'] = _FakeProcess(
            _RefusingReader(io.FileIO(read_fd, 'rb', closefd=False), buffer_size=8192)
        )

        # a batch larger than one read, so the tail can only arrive on a later cycle
        expected = [f'announce route 10.0.0.{index // 256}.{index % 256}/32 next-hop 1.2.3.4' for index in range(400)]
        os.write(write_fd, ('\n'.join(expected) + '\n').encode('ascii'))

        seen = []
        for _ in range(10):
            seen.extend(command for _, command in processes.received())
            if len(seen) == len(expected):
                break

        assert len(seen) == len(expected), 'commands were stranded'
