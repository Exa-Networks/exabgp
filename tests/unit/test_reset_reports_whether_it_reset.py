"""`exabgp cli reset` exited 0 whether or not the reset had happened.

`reset` is the one command which expects no answer from the daemon, and that was read as
"nothing here can fail". Every path through it ended at the same unconditional
`sys.exit(0)`:

  - no socket found in any of the search locations, so nothing was sent
  - no fifo found, or the path found was not a fifo
  - `connect` refused, or timed out, because the daemon is not running
  - `sendall` or `os.write` failed part way through

All four printed nothing and exited 0. A script or a CI job which runs `exabgp cli reset`
and checks the exit status was told the reset succeeded when no byte had left the process.
That is the "never report success you have not verified" rule: a command which returns 0
on a path it did not execute is lying to its caller.

There is no acknowledgement to wait for, so success here can only mean "the command was
handed to the transport". That is still worth distinguishing from "there was no transport
to hand it to", which is what these tests pin.
"""

from __future__ import annotations

import argparse
import os
from typing import Any

import pytest

from exabgp.application import run as run_module


def arguments() -> argparse.Namespace:
    return argparse.Namespace(command=['reset'], pipename=None, use_pipe=False, use_socket=True, batch_file=None)


def pipe_arguments() -> argparse.Namespace:
    return argparse.Namespace(command=['reset'], pipename=None, use_pipe=True, use_socket=False, batch_file=None)


class FakeSocket:
    """A unix socket whose connect and sendall the test decides."""

    sent: list[bytes] = []

    def __init__(self, fail_on: str = '') -> None:
        self._fail_on = fail_on
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

    def close(self) -> None:
        self.closed = True


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
    code = exit_code(monkeypatch, unix_socket=lambda root, name: [])

    assert code != 0, 'reset found no socket, sent nothing, and reported success'


def test_several_sockets_found_is_not_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ambiguous is not the same as delivered: the command still went nowhere."""
    code = exit_code(monkeypatch, unix_socket=lambda root, name: ['/one/', '/two/'])

    assert code != 0, 'reset could not choose a socket, sent nothing, and reported success'


def test_a_refused_connection_is_not_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """The daemon is not running. That is the commonest way for this to go wrong."""
    monkeypatch.setattr(run_module.sock, 'socket', lambda *a, **k: FakeSocket(fail_on='connect'))
    code = exit_code(monkeypatch, unix_socket=lambda root, name: ['/run/'])

    assert code != 0, 'reset could not connect and reported success'


def test_a_failed_send_is_not_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Connected, then the write failed. Still nothing reset."""
    monkeypatch.setattr(run_module.sock, 'socket', lambda *a, **k: FakeSocket(fail_on='sendall'))
    code = exit_code(monkeypatch, unix_socket=lambda root, name: ['/run/'])

    assert code != 0, 'reset failed to send and reported success'


def test_a_delivered_reset_is_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """The working path must still return zero, or every assertion above is trivial."""
    FakeSocket.sent = []
    monkeypatch.setattr(run_module.sock, 'socket', lambda *a, **k: FakeSocket())
    code = exit_code(monkeypatch, unix_socket=lambda root, name: ['/run/'])

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


def test_a_failed_pipe_write_closes_the_descriptor(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    """The write failure path leaked the writer: os.close sat inside the try it skipped."""
    opened: list[int] = []
    closed: list[int] = []

    def fake_open_writer(send: str) -> int:
        opened.append(7)
        return 7

    def failing_write(fd: int, data: bytes) -> int:
        raise OSError(32, 'Broken pipe')

    monkeypatch.setattr(os, 'close', lambda fd: closed.append(fd))
    monkeypatch.setattr(os, 'write', failing_write)

    code = exit_code(
        monkeypatch,
        named_pipe=lambda root, name: ['/run/'],
        check_fifo=lambda path: True,
        open_writer=fake_open_writer,
        _args=pipe_arguments(),
    )

    assert code != 0, 'the write failed and reset reported success'
    assert closed == opened, f'the writer was not closed on the failure path: opened={opened} closed={closed}'
