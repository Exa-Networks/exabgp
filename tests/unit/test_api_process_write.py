"""What writing to an API helper's stdin does, pinned before the code is rearranged.

`Processes.write` and `Processes.flush_write_queue` carry the whole outbound half of the
API: every announce, every ACK and the shutdown message a helper is owed go through one
of them. Neither had a single unit test, and both are the paths which run when a helper
is slow or already dead, which is exactly when nobody is watching.

These tests say what the two do today, error paths included, so that moving the code
around cannot change it quietly. They are deliberately about observable effects, the
bytes that reach the descriptor and the state left in `_write_queue` and `_broken`,
rather than about how either function is structured inside.
"""

from __future__ import annotations

import asyncio
import collections
import errno
import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from exabgp.reactor.api.processes import ProcessError, Processes


@pytest.fixture(autouse=True)
def quiet_logger() -> Any:
    with patch('exabgp.reactor.api.processes.log') as logger:
        yield logger


@pytest.fixture
def processes() -> Any:
    with patch('exabgp.reactor.api.processes.getenv') as getenv:
        environment = MagicMock()
        environment.api.respawn = False
        environment.api.terminate = False
        environment.api.ack = True
        getenv.return_value = environment
        return Processes()


def with_stdin(processes: Any, name: str, fileno: int) -> Any:
    """Register a helper whose stdin is the descriptor given."""
    process = MagicMock()
    process.stdin.fileno.return_value = fileno
    processes._process[name] = process
    return process


@pytest.fixture
def pipe() -> Any:
    read_fd, write_fd = os.pipe()
    yield read_fd, write_fd
    for fd in (read_fd, write_fd):
        try:
            os.close(fd)
        except OSError:
            # The test may have closed the descriptor itself to provoke a failure.
            pass


class TestWrite:
    def test_nothing_to_say_is_not_an_error(self, processes: Any) -> None:
        """The encoders return None for an event a helper did not subscribe to."""
        assert processes.write('helper', None) is True

    def test_a_process_which_is_gone_reports_false(self, processes: Any) -> None:
        assert processes.write('helper', 'announce route') is False

    def test_the_line_reaches_stdin_with_a_newline(self, processes: Any, pipe: Any) -> None:
        read_fd, write_fd = pipe
        with_stdin(processes, 'helper', write_fd)

        assert processes.write('helper', 'announce route 10.0.0.0/24') is True

        assert os.read(read_fd, 4096) == b'announce route 10.0.0.0/24\n'

    def test_a_partial_write_is_resumed_until_the_whole_line_is_out(self, processes: Any) -> None:
        """os.write on a pipe may take fewer bytes than offered; none of them may be lost."""
        with_stdin(processes, 'helper', 7)
        written: list[bytes] = []

        def one_byte_at_a_time(fd: int, data: bytes) -> int:
            written.append(bytes(data[:1]))
            return 1

        with patch('exabgp.reactor.api.processes.os.write', side_effect=one_byte_at_a_time):
            assert processes.write('helper', 'ab') is True

        assert b''.join(written) == b'ab\n'

    def test_a_broken_pipe_marks_the_process_broken_and_raises(self, processes: Any) -> None:
        with_stdin(processes, 'helper', 7)

        with patch('exabgp.reactor.api.processes.os.write', side_effect=OSError(errno.EPIPE, 'broken pipe')):
            with pytest.raises(ProcessError):
                processes.write('helper', 'announce route')

        assert processes._broken == ['helper']

    def test_an_unexpected_errno_marks_the_process_broken_and_raises(self, processes: Any) -> None:
        with_stdin(processes, 'helper', 7)

        with patch('exabgp.reactor.api.processes.os.write', side_effect=OSError(errno.EIO, 'io error')):
            with pytest.raises(ProcessError):
                processes.write('helper', 'announce route')

        assert processes._broken == ['helper']

    def test_an_interrupted_write_is_retried_rather_than_lost(self, processes: Any) -> None:
        """EINTR says a signal arrived, not that the helper has a problem."""
        with_stdin(processes, 'helper', 7)
        attempts = [OSError(errno.EINTR, 'interrupted'), 3]

        def interrupted_once(fd: int, data: bytes) -> int:
            outcome = attempts.pop(0)
            if isinstance(outcome, OSError):
                raise outcome
            return outcome

        with patch('exabgp.reactor.api.processes.os.write', side_effect=interrupted_once):
            assert processes.write('helper', 'ab') is True

        assert attempts == []
        assert processes._broken == []

    def test_a_helper_which_never_drains_times_out_rather_than_blocking(self, processes: Any) -> None:
        """A full pipe returns False after the deadline: the reactor may not stall on it."""
        with_stdin(processes, 'helper', 7)
        poller = MagicMock()
        poller.poll.return_value = []

        with patch('exabgp.reactor.api.processes.os.write', side_effect=OSError(errno.EAGAIN, 'again')):
            with patch('exabgp.reactor.api.processes.select.poll', return_value=poller):
                assert processes.write('helper', 'announce route') is False

        # 5000ms of deadline at 100ms per poll, and the write is not treated as a failure.
        assert poller.poll.call_count == 50
        assert processes._broken == []

    def test_a_full_pipe_which_drains_completes_the_write(self, processes: Any) -> None:
        with_stdin(processes, 'helper', 7)
        attempts: list[Any] = [OSError(errno.EAGAIN, 'again'), 3]
        poller = MagicMock()
        poller.poll.return_value = [(7, 4)]

        def blocked_once(fd: int, data: bytes) -> int:
            outcome = attempts.pop(0)
            if isinstance(outcome, OSError):
                raise outcome
            return outcome

        with patch('exabgp.reactor.api.processes.os.write', side_effect=blocked_once):
            with patch('exabgp.reactor.api.processes.select.poll', return_value=poller):
                assert processes.write('helper', 'ab') is True

        assert attempts == []

    def test_in_async_mode_the_line_is_queued_and_not_written(self, processes: Any, pipe: Any) -> None:
        """The event loop must not be blocked, so write() only enqueues."""
        read_fd, write_fd = pipe
        with_stdin(processes, 'helper', write_fd)
        processes._async_mode = True

        assert processes.write('helper', 'announce route') is True

        assert list(processes._write_queue['helper']) == [b'announce route\n']


class TestFlushWriteQueue:
    def test_sync_mode_leaves_the_queue_alone(self, processes: Any) -> None:
        """Nothing enqueues in sync mode, and flushing would write behind write()'s back."""
        processes._write_queue['helper'] = collections.deque([b'stale\n'])

        asyncio.run(processes.flush_write_queue())

        assert list(processes._write_queue['helper']) == [b'stale\n']

    def test_queued_lines_reach_the_descriptor_in_order(self, processes: Any, pipe: Any) -> None:
        read_fd, write_fd = pipe
        with_stdin(processes, 'helper', write_fd)
        processes._async_mode = True
        processes.write('helper', 'first')
        processes.write('helper', 'second')

        asyncio.run(processes.flush_write_queue())

        assert os.read(read_fd, 4096) == b'first\nsecond\n'
        assert not processes._write_queue['helper']

    def test_only_ten_items_are_written_per_call(self, processes: Any, pipe: Any) -> None:
        """The batch cap is what keeps the reactor responsive under a flood of ACKs."""
        read_fd, write_fd = pipe
        with_stdin(processes, 'helper', write_fd)
        processes._async_mode = True
        for index in range(15):
            processes.write('helper', str(index))

        asyncio.run(processes.flush_write_queue())

        assert len(processes._write_queue['helper']) == 5
        assert list(processes._write_queue['helper'])[0] == b'10\n'

    def test_a_terminated_process_has_its_queue_dropped(self, processes: Any) -> None:
        """State belonging to a client which is gone must not outlive it."""
        processes._async_mode = True
        with_stdin(processes, 'helper', 7)
        processes.write('helper', 'orphan')
        del processes._process['helper']

        asyncio.run(processes.flush_write_queue())

        assert 'helper' not in processes._write_queue

    def test_a_closed_stdin_has_its_queue_dropped(self, processes: Any) -> None:
        processes._async_mode = True
        process = MagicMock()
        process.stdin.fileno.side_effect = ValueError('I/O operation on closed file')
        processes._process['helper'] = process
        processes._write_queue['helper'] = collections.deque([b'orphan\n'])

        asyncio.run(processes.flush_write_queue())

        assert 'helper' not in processes._write_queue

    def test_a_partial_write_puts_the_remainder_back_at_the_front(self, processes: Any) -> None:
        processes._async_mode = True
        with_stdin(processes, 'helper', 7)
        processes.write('helper', 'abcd')
        processes.write('helper', 'next')

        with patch('exabgp.reactor.api.processes.os.write', return_value=2):
            asyncio.run(processes.flush_write_queue())

        assert list(processes._write_queue['helper']) == [b'cd\n', b'next\n']

    def test_a_full_pipe_defers_the_line_without_losing_it(self, processes: Any) -> None:
        processes._async_mode = True
        with_stdin(processes, 'helper', 7)
        processes.write('helper', 'abcd')

        with patch('exabgp.reactor.api.processes.os.write', side_effect=OSError(errno.EAGAIN, 'again')):
            asyncio.run(processes.flush_write_queue())

        assert list(processes._write_queue['helper']) == [b'abcd\n']
        assert processes._broken == []

    def test_a_broken_pipe_marks_the_process_and_drops_its_queue(self, processes: Any) -> None:
        processes._async_mode = True
        with_stdin(processes, 'helper', 7)
        processes.write('helper', 'abcd')

        with patch('exabgp.reactor.api.processes.os.write', side_effect=OSError(errno.EPIPE, 'broken pipe')):
            asyncio.run(processes.flush_write_queue())

        assert processes._broken == ['helper']
        assert 'helper' not in processes._write_queue

    def test_an_unexpected_errno_marks_the_process_and_drops_its_queue(self, processes: Any) -> None:
        processes._async_mode = True
        with_stdin(processes, 'helper', 7)
        processes.write('helper', 'abcd')

        with patch('exabgp.reactor.api.processes.os.write', side_effect=OSError(errno.EIO, 'io error')):
            asyncio.run(processes.flush_write_queue())

        assert processes._broken == ['helper']
        assert 'helper' not in processes._write_queue

    def test_an_empty_queue_entry_is_kept_for_the_next_write(self, processes: Any, pipe: Any) -> None:
        """A helper with nothing pending is skipped, not forgotten."""
        read_fd, write_fd = pipe
        with_stdin(processes, 'helper', write_fd)
        processes._async_mode = True
        processes._write_queue['helper'] = collections.deque()

        asyncio.run(processes.flush_write_queue())

        assert 'helper' in processes._write_queue
