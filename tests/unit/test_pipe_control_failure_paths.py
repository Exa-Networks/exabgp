#!/usr/bin/env python3
"""`check_fifo` saying which failure it met, and `loop()` ending when it cannot read.

Two defects, one file.

`check_fifo` carried three `except OSError` clauses on one `try`.  Python takes the first
match, so the second and third could never run: two of its three messages had never
reached an operator, and both of those paths fell off the end returning `None` rather than
`False`.  The three messages named creating, deleting and writing on the pipe, none of
which the function does any more, so the conditions worth telling apart are the errno
values `os.stat` can come back with.  Each test below asserts the *specific* message,
because an unreachable message is exactly what was wrong.

`loop()` answered a failed `os.open(self.recv, ...)` with `self.terminate()`, which sets a
flag and cleans up but does not exit on its first call.  The loop then ran on with
`r_pipe` set to `None`: `read_on` skips a `None` descriptor, so it polled stdin for ever,
forwarded commands into the write fifo and never read an answer from anywhere.
"""

from __future__ import annotations

import errno
import os
import stat
import sys

import pytest

from exabgp.application import pipe


class LoopEntered(Exception):
    """Raised in place of `read_on` so the endless loop cannot hang the suite."""


@pytest.fixture
def standard_fds(monkeypatch):
    """Give `loop()` a stdin and a stdout which really have file descriptors.

    pytest's capture replaces `sys.stdin` with an object whose `fileno()` raises, and
    `loop()` reads both filenos before it reaches the loop, which would mask what it does
    next.  One pipe serves as both ends, so the `enable-ack` write comes straight back and
    the handshake needs no daemon and no timeout.
    """
    read_fd, write_fd = os.pipe()

    class Stream:
        def __init__(self, fd: int) -> None:
            self._fd = fd

        def fileno(self) -> int:
            return self._fd

        def write(self, text: str) -> int:
            return os.write(self._fd, text.encode())

        def flush(self) -> None:
            return None

    monkeypatch.setattr(sys, 'stdin', Stream(read_fd))
    # capsys re-installs its own sys.stdout when the call phase starts, which would undo
    # this; the loop tests use capfd, which captures the descriptor and leaves the object.
    monkeypatch.setattr(sys, 'stdout', Stream(write_fd))
    yield
    os.close(read_fd)
    os.close(write_fd)


def test_a_missing_pipe_says_it_is_missing(tmp_path, capsys):
    assert pipe.check_fifo(f'{tmp_path}/absent.in') is False
    assert 'could not find the named pipe' in capsys.readouterr().out


def test_a_pipe_we_may_not_reach_says_so(tmp_path, capsys):
    """A directory we may not search: os.stat raises PermissionError, not ENOENT."""
    if os.geteuid() == 0:
        pytest.skip('root searches a directory whatever its mode')
    closed = tmp_path / 'closed'
    closed.mkdir()
    os.chmod(closed, 0o000)
    try:
        assert pipe.check_fifo(str(closed / 'exabgp.in')) is False
    finally:
        os.chmod(closed, 0o700)
    assert 'not allowed to reach the named pipe' in capsys.readouterr().out


def test_any_other_errno_is_reported_with_its_reason(tmp_path, capsys):
    """Neither missing nor forbidden: the operator gets the errno's own words.

    A plain file where a run directory should be gives ENOTDIR, which is neither of the
    two named above, so it has to arrive with its strerror attached.
    """
    not_a_directory = tmp_path / 'run'
    not_a_directory.write_text('')
    with pytest.raises(NotADirectoryError) as raised:
        os.stat(not_a_directory / 'exabgp.in')
    assert raised.value.errno == errno.ENOTDIR

    assert pipe.check_fifo(str(not_a_directory / 'exabgp.in')) is False
    captured = capsys.readouterr().out
    assert 'could not check the named pipe' in captured
    assert 'Not a directory' in captured


def test_a_plain_file_says_it_is_not_a_pipe(tmp_path, capsys):
    plain = tmp_path / 'exabgp.in'
    plain.write_text('')
    assert pipe.check_fifo(str(plain)) is False
    assert 'is not a named pipe' in capsys.readouterr().out


def test_an_unreadable_pipe_says_it_cannot_be_read(tmp_path, capsys):
    if os.geteuid() == 0:
        pytest.skip('root reads a fifo whatever its mode')
    name = str(tmp_path / 'exabgp.in')
    os.mkfifo(name, 0o000)
    assert pipe.check_fifo(name) is False
    assert 'we can not read/write to it' in capsys.readouterr().out


def test_a_usable_pipe_is_accepted(tmp_path, capsys):
    name = str(tmp_path / 'exabgp.in')
    os.mkfifo(name)
    assert stat.S_ISFIFO(os.stat(name).st_mode)
    assert pipe.check_fifo(name) is True
    assert capsys.readouterr().out == ''


def test_loop_ends_when_the_answer_pipe_cannot_be_opened(tmp_path, monkeypatch, capfd, standard_fds):
    """The open fails, so there is nothing to read answers from: the loop must not start."""
    entered = []

    def spy(self, reading):
        entered.append(list(reading))
        raise LoopEntered

    monkeypatch.setattr(pipe.Control, 'read_on', spy)

    control = pipe.Control(f'{tmp_path}/')  # nothing was created, so os.open raises ENOENT

    with pytest.raises(SystemExit) as exit_info:
        control.loop()

    assert entered == [], f'loop() ran on with r_pipe {control.r_pipe!r}, polling {entered}'
    assert exit_info.value.code == 1
    assert control.terminating is True
    assert 'could not open the named pipe' in capfd.readouterr().err


def test_loop_runs_when_the_answer_pipe_opens(tmp_path, monkeypatch, standard_fds):
    """Control: with a fifo it can open, the same loop reaches read_on with a descriptor."""
    entered = []

    def spy(self, reading):
        entered.append(list(reading))
        raise LoopEntered

    monkeypatch.setattr(pipe.Control, 'read_on', spy)

    os.mkfifo(f'{tmp_path}/exabgp.in')
    control = pipe.Control(f'{tmp_path}/')

    with pytest.raises(LoopEntered):
        control.loop()

    assert control.r_pipe is not None
    assert entered == [[sys.stdin.fileno(), control.r_pipe]]
    os.close(control.r_pipe)
