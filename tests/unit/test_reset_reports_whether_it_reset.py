"""`exabgp run reset` exits 0 only when the reset has happened.

On 5.x the daemon never answered `reset`, so the CLI sent it and exited at once. That was read
as "nothing here can fail", and every path ended at the same unconditional `sys.exit(0)`:

  - no socket found in any of the search locations, so nothing was sent
  - no fifo found, or the path found was not a fifo
  - `connect` refused, or timed out, because the daemon is not running
  - `sendall` or `os.write` failed part way through

A script or a CI job checking the status was told the reset succeeded when no byte had left
the process. 6.0 answers `session reset`, so `reset` now goes the way of every other command
and waits for that answer: zero means the daemon said it was done. These tests pin that the
four failures above are still failures on that common path, which had the last two holes too.

The compiled run.py calls unix_socket, named_pipe, check_fifo and open_writer directly,
so replacing them on the module changes nothing there. Where a test needs a transport to
be found, it is given a real one to find: a unix socket named by exabgp_api_socketpath, or
the two fifos under a ROOT of its own. The socket and os functions are looked up on their
module at each call, compiled or not, so those are still replaced.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import tempfile
from collections.abc import Iterator
from typing import Any

import pytest

from exabgp.application import run as run_module
from exabgp.environment import getenv


def arguments() -> argparse.Namespace:
    return argparse.Namespace(command=['reset'], pipename=None, use_pipe=False, use_socket=True, batch_file=None)


def pipe_arguments() -> argparse.Namespace:
    return argparse.Namespace(command=['reset'], pipename=None, use_pipe=True, use_socket=False, batch_file=None)


class FakeSocket:
    """A unix socket whose connect and sendall the test decides."""

    sent: list[bytes] = []

    def __init__(self, fail_on: str = '') -> None:
        self._fail_on = fail_on
        self._answer = b'asynchronous queue cleared\ndone\n'
        self.closed = False

    def settimeout(self, timeout: float) -> None:
        pass

    def connect(self, path: str) -> None:
        if self._fail_on == 'connect':
            raise OSError(61, 'Connection refused')

    def sendall(self, payload: bytes) -> None:
        if self._fail_on == 'sendall':
            raise OSError(32, 'Broken pipe')
        FakeSocket.sent.append(payload)

    def recv(self, size: int) -> bytes:
        # the daemon's answer to `session reset`, then the connection closes
        answer, self._answer = self._answer, b''
        return answer

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def listening(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A unix socket where exabgp_api_socketpath says the daemon's is, so unix_socket finds it.

    mkdtemp and not tmp_path: a unix socket path must fit in about a hundred bytes.
    """
    directory = tempfile.mkdtemp()
    path = os.path.join(directory, f'{getenv().api.socketname}.sock')
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    monkeypatch.setenv('exabgp_api_socketpath', path)
    # unix_socket records what it found here: registered so it is put back afterwards
    monkeypatch.delenv('exabgp_cli_socket', raising=False)
    try:
        yield path
    finally:
        server.close()
        shutil.rmtree(directory)


@pytest.fixture
def fifos(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The daemon's two fifos under a ROOT of our own, where named_pipe looks for them.

    A reader is held open on the .in fifo, as the daemon holds one: without it, opening
    the fifo to write would block.
    """
    root = tempfile.mkdtemp()
    location = os.path.join(root, 'run') + '/'
    os.mkdir(location)
    name = getenv().api.pipename
    os.mkfifo(location + name + '.in')
    os.mkfifo(location + name + '.out')
    reader = os.open(location + name + '.in', os.O_RDONLY | os.O_NONBLOCK)
    monkeypatch.setattr(run_module, 'ROOT', root)
    # named_pipe records what it found here: registered so it is put back afterwards
    monkeypatch.delenv('exabgp_cli_pipe', raising=False)
    alarm = signal.getsignal(signal.SIGALRM)
    try:
        yield location
    finally:
        # open_writer installs its own SIGALRM handler and leaves it
        signal.signal(signal.SIGALRM, alarm)
        os.close(reader)
        shutil.rmtree(root)


def exit_code(monkeypatch: pytest.MonkeyPatch, **patches: Any) -> int:
    """Run the reset command with the transport the caller describes, return its status."""
    args = patches.pop('_args', arguments())
    for name, value in patches.items():
        monkeypatch.setattr(run_module, name, value)
    try:
        run_module.cmdline(args)
    except SystemExit as exc:
        return int(exc.code or 0)
    raise AssertionError('cmdline returned without exiting')


def test_no_socket_found_is_not_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing was sent, so the reset did not happen, so this is not a zero."""
    FakeSocket.sent = []
    # should the search find a socket after all, nothing reaches whatever listens on it
    monkeypatch.setattr(run_module.sock, 'socket', lambda *a, **k: FakeSocket())
    code = exit_code(monkeypatch, unix_socket=lambda root, name: [])

    assert code != 0, 'reset found no socket, sent nothing, and reported success'
    assert FakeSocket.sent == []


def test_several_sockets_found_is_not_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ambiguous is not the same as delivered: the command still went nowhere."""
    code = exit_code(monkeypatch, unix_socket=lambda root, name: ['/one/', '/two/'])

    assert code != 0, 'reset could not choose a socket, sent nothing, and reported success'


def test_a_refused_connection_is_not_success(monkeypatch: pytest.MonkeyPatch, listening: str) -> None:
    """The daemon is not running. That is the commonest way for this to go wrong."""
    monkeypatch.setattr(run_module.sock, 'socket', lambda *a, **k: FakeSocket(fail_on='connect'))
    code = exit_code(monkeypatch)

    assert code != 0, 'reset could not connect and reported success'


def test_a_failed_send_is_not_success(monkeypatch: pytest.MonkeyPatch, listening: str) -> None:
    """Connected, then the write failed. Still nothing reset."""
    monkeypatch.setattr(run_module.sock, 'socket', lambda *a, **k: FakeSocket(fail_on='sendall'))
    code = exit_code(monkeypatch)

    assert code != 0, 'reset failed to send and reported success'


def test_a_delivered_reset_is_success(monkeypatch: pytest.MonkeyPatch, listening: str) -> None:
    """The daemon answered done: zero, or every assertion above is trivial."""
    FakeSocket.sent = []
    monkeypatch.setattr(run_module.sock, 'socket', lambda *a, **k: FakeSocket())
    code = exit_code(monkeypatch)

    assert code == 0, 'a delivered reset reported failure'
    assert FakeSocket.sent == [b'reset\n'], f'the command was not sent as expected: {FakeSocket.sent}'


def test_no_fifo_found_is_not_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """The pipe transport has the same hole and gets the same answer."""
    code = exit_code(
        monkeypatch,
        named_pipe=lambda root, name: [],
        _args=pipe_arguments(),
    )

    assert code != 0, 'reset found no fifo, sent nothing, and reported success'


def test_a_failed_pipe_write_closes_the_descriptor(monkeypatch: pytest.MonkeyPatch, fifos: str) -> None:
    """The write failure path leaked the writer: os.close sat inside the try it skipped."""
    opened: list[int] = []
    closed: list[int] = []
    real_open = os.open
    real_close = os.close

    def recording_open(path: str, flags: int, *args: Any) -> int:
        fd = real_open(path, flags, *args)
        opened.append(fd)
        return fd

    def recording_close(fd: int) -> None:
        closed.append(fd)
        real_close(fd)

    def failing_write(fd: int, data: bytes) -> int:
        raise OSError(32, 'Broken pipe')

    # undone before the fifos are removed, which opens and closes descriptors of its own
    with monkeypatch.context() as io:
        io.setattr(os, 'open', recording_open)
        io.setattr(os, 'close', recording_close)
        io.setattr(os, 'write', failing_write)

        code = exit_code(io, _args=pipe_arguments())

    assert code != 0, 'the write failed and reset reported success'
    assert opened, 'the fifo was never opened for writing, so this proves nothing'
    assert closed == opened, f'the writer was not closed on the failure path: opened={opened} closed={closed}'
