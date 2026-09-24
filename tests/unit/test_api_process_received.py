"""What the sync reader does with everything a helper's pipe can present.

`Processes.received()` is the generator the sync reactor pulls API commands out of. Its
happy path is covered by test_process_read_stranding.py; almost none of the rest was.
That is the half which decides a helper is dead: a hang-up, an end of file, a command so
long it would grow the buffer without bound, and the three classes of read error.

These tests pin that behaviour before the function is taken apart. `_handle_problem` is
replaced by a recorder throughout, because what matters here is which conditions are
judged to be a problem, not what terminating a helper then does.
"""

from __future__ import annotations

import errno
import io
import os
import select
from typing import Any
from unittest.mock import patch

import pytest

from exabgp.environment import getenv
from exabgp.logger import log
from exabgp.reactor.api.processes import Processes
from exabgp.reactor.network.error import error

log.init(getenv())


class FakeProcess:
    """The parts of subprocess.Popen that received() touches."""

    def __init__(self, stdout: io.FileIO, returncode: int | None = None) -> None:
        self.stdout = stdout
        self.returncode = returncode

    def poll(self) -> int | None:
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
            # A test may close the writer itself to provoke a hang-up.
            pass


@pytest.fixture
def processes(pipe: Any) -> Any:
    read_fd, _ = pipe
    instance = Processes()
    instance._process['test'] = FakeProcess(io.FileIO(read_fd, 'rb', closefd=False))
    instance.problems: list[str] = []
    instance._handle_problem = instance.problems.append
    return instance


def exited(processes: Any, code: int = 0) -> None:
    """Make poll() report the helper has gone, as it does once the child is reaped."""
    processes._process['test'].returncode = code


class TestReading:
    def test_a_complete_line_becomes_a_command(self, processes: Any, pipe: Any) -> None:
        _, write_fd = pipe
        os.write(write_fd, b'announce route 10.0.0.0/24\n')

        assert list(processes.received()) == [('test', 'announce route 10.0.0.0/24')]
        assert processes.problems == []

    def test_a_debug_line_is_reported_but_not_executed(self, processes: Any, pipe: Any) -> None:
        """`debug ` is how a helper talks to the log, not to the API."""
        _, write_fd = pipe
        os.write(write_fd, b'debug helper says hello\nannounce route 10.0.0.0/24\n')

        assert list(processes.received()) == [('test', 'announce route 10.0.0.0/24')]

    def test_a_half_line_is_kept_for_the_next_read(self, processes: Any, pipe: Any) -> None:
        _, write_fd = pipe
        os.write(write_fd, b'announce rou')

        assert list(processes.received()) == []
        assert processes._buffer['test'] == 'announce rou'

        os.write(write_fd, b'te 10.0.0.0/24\n')
        assert list(processes.received()) == [('test', 'announce route 10.0.0.0/24')]

    def test_a_quiet_pipe_produces_nothing_and_no_complaint(self, processes: Any) -> None:
        assert list(processes.received()) == []
        assert processes.problems == []


class TestTheHelperGoingAway:
    def test_a_hung_up_pipe_alone_is_not_yet_a_problem(self, processes: Any, pipe: Any) -> None:
        """A closed writer reports POLLIN as well as POLLHUP, and POLLIN is tested first.

        So the hang-up is not what ends the helper: the empty read which follows is, and
        only once poll() has an exit code for the child. Until then this is a quiet turn.
        """
        _, write_fd = pipe
        os.close(write_fd)

        assert list(processes.received()) == []
        assert processes.problems == []

    def test_an_invalid_descriptor_is_a_problem(self, processes: Any) -> None:
        """POLLERR and POLLNVAL have no data behind them, so this is the branch they take."""
        with patch('exabgp.reactor.api.processes.select.poll') as poller:
            poller.return_value.poll.return_value = [(0, select.POLLNVAL)]
            assert list(processes.received()) == []

        assert processes.problems == ['test']

    def test_end_of_file_from_a_process_which_exited_is_a_problem(self, processes: Any, pipe: Any) -> None:
        """An empty read alone means nothing; an empty read from a reaped child means EOF."""
        _, write_fd = pipe
        os.write(write_fd, b'x')
        os.read(processes._process['test'].stdout.fileno(), 1)
        exited(processes)

        with patch('exabgp.reactor.api.processes.os.read', return_value=b''):
            with patch('exabgp.reactor.api.processes.select.poll') as poller:
                poller.return_value.poll.return_value = [(0, 1)]
                assert list(processes.received()) == []

        assert processes.problems == ['test']

    def test_a_process_which_exits_after_speaking_stops_the_sweep(self, processes: Any, pipe: Any) -> None:
        """Its last commands are still delivered; the sweep then returns rather than continuing."""
        _, write_fd = pipe
        os.write(write_fd, b'announce route 10.0.0.0/24\n')
        exited(processes)

        assert list(processes.received()) == [('test', 'announce route 10.0.0.0/24')]
        assert processes.problems == ['test']

    def test_a_process_removed_while_being_read_is_not_an_error(self, processes: Any, pipe: Any) -> None:
        """_handle_problem deletes the entry, and the sweep is iterating over a snapshot."""
        _, write_fd = pipe
        os.write(write_fd, b'announce route 10.0.0.0/24\n')
        stdout = processes._process['test'].stdout
        real_read = os.read

        def vanish(fd: int, size: int) -> bytes:
            del processes._process['test']
            return real_read(stdout.fileno(), size)

        with patch('exabgp.reactor.api.processes.os.read', side_effect=vanish):
            assert list(processes.received()) == [('test', 'announce route 10.0.0.0/24')]


class TestBounds:
    def test_a_command_which_never_ends_is_dropped_and_the_helper_given_up_on(self, processes: Any, pipe: Any) -> None:
        """Without the cap a helper which never sends a newline grows _buffer until OOM."""
        _, write_fd = pipe
        processes._buffer['test'] = 'x' * (processes.MAX_COMMAND_SIZE + 1)
        os.write(write_fd, b'y')

        assert list(processes.received()) == []

        assert 'test' not in processes._buffer
        assert processes.problems == ['test']

    def test_a_long_command_which_does_end_is_still_executed(self, processes: Any, pipe: Any) -> None:
        """The cap is on a line with no newline in it, not on a legitimately large one."""
        _, write_fd = pipe
        processes._buffer['test'] = 'announce attributes ' + 'z' * (processes.MAX_COMMAND_SIZE + 1)
        os.write(write_fd, b'\n')

        assert len(list(processes.received())) == 1
        assert processes.problems == []


class TestReadErrors:
    def test_a_fatal_errno_is_a_problem(self, processes: Any, pipe: Any) -> None:
        _, write_fd = pipe
        os.write(write_fd, b'x')
        fatal = sorted(error.fatal)[0]

        with patch('exabgp.reactor.api.processes.os.read', side_effect=OSError(fatal, 'fatal')):
            assert list(processes.received()) == []

        assert processes.problems == ['test']

    def test_errno_zero_is_a_problem(self, processes: Any, pipe: Any) -> None:
        """A helper exiting mid-read has been seen to surface as an IOError with errno 0."""
        _, write_fd = pipe
        os.write(write_fd, b'x')

        with patch('exabgp.reactor.api.processes.os.read', side_effect=OSError(0, 'nothing')):
            assert list(processes.received()) == []

        assert processes.problems == ['test']

    def test_a_recoverable_errno_is_left_for_the_next_turn(self, processes: Any, pipe: Any) -> None:
        """EINTR usually means the data is there; the next reactor cycle will collect it."""
        _, write_fd = pipe
        os.write(write_fd, b'x')
        block = sorted(error.block)[0]

        with patch('exabgp.reactor.api.processes.os.read', side_effect=OSError(block, 'again')):
            assert list(processes.received()) == []

        assert processes.problems == []

    def test_an_unclassified_errno_is_only_logged(self, processes: Any, pipe: Any) -> None:
        _, write_fd = pipe
        os.write(write_fd, b'x')
        unclassified = errno.EXDEV
        assert unclassified not in error.fatal and unclassified not in error.block

        with patch('exabgp.reactor.api.processes.os.read', side_effect=OSError(unclassified, 'odd')):
            assert list(processes.received()) == []

        assert processes.problems == []
