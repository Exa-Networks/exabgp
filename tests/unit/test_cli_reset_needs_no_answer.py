#!/usr/bin/env python3
"""`exabgp cli` command dispatch: the reset short-circuit and the shortcut echo.

Both were compared against the argparse *list* rather than the joined string, so
`command == 'reset'` was never true and `sending != command` was always true.  The
result was a reset which waited five seconds and then told the user the reactor
might block, and a `command: ...` echo printed for every command including the ones
which needed no expansion.

The write-failure path is here too: `os.close(writer)` sat inside the try it skipped.
"""

from __future__ import annotations

import os

import pytest

from exabgp.application import cli


class Args:
    def __init__(self, command, pipename='testpipe'):
        self.command = command
        self.pipename = pipename


@pytest.fixture
def pipes(tmp_path, monkeypatch):
    """A pair of real fifos with the reader end of `.in` already open.

    `open_writer` opens the `.in` fifo O_WRONLY, which blocks until somebody holds
    the read end, so the test has to play the daemon that far.
    """
    folder = f'{tmp_path}/'
    pipename = 'testpipe'
    os.mkfifo(folder + pipename + '.in')
    os.mkfifo(folder + pipename + '.out')
    monkeypatch.setattr(cli, 'named_pipe', lambda root, name: [folder])
    daemon_side = os.open(folder + pipename + '.in', os.O_RDONLY | os.O_NONBLOCK)
    yield folder
    os.close(daemon_side)


def test_reset_does_not_warn_that_the_reactor_may_block(pipes, capsys):
    """reset expects no answer, so it must not wait for one and then complain."""
    with pytest.raises(SystemExit) as exit_info:
        cli.cmdline(Args(['reset']))
    captured = capsys.readouterr()
    assert exit_info.value.code == 0
    assert 'no end of command message' not in captured.err
    assert 'may cause exabgp reactor to block' not in captured.err


def test_a_command_needing_no_expansion_is_not_echoed(pipes, capsys, monkeypatch):
    """The comment says the echo is for changed commands; `help` is unchanged."""
    monkeypatch.setattr(cli, 'COMMAND_RESPONSE_TIMEOUT', 0.05)
    with pytest.raises(SystemExit):
        cli.cmdline(Args(['help']))
    assert 'command: help' not in capsys.readouterr().out


def test_a_shortcut_is_still_echoed(pipes, capsys, monkeypatch):
    """Control: an expansion the user did not type is still shown."""
    monkeypatch.setattr(cli, 'COMMAND_RESPONSE_TIMEOUT', 0.05)
    with pytest.raises(SystemExit):
        cli.cmdline(Args(['s', 'summary']))
    assert 'command: show summary' in capsys.readouterr().out


def test_a_failed_write_does_not_leak_the_descriptor(pipes, monkeypatch):
    opened = []
    real_open = os.open

    def remember(path, flags, *args):
        fd = real_open(path, flags, *args)
        if str(path).endswith('.in'):
            opened.append(fd)
        return fd

    def refuse(fd, data):
        raise OSError(5, 'Input/output error')

    monkeypatch.setattr(os, 'open', remember)
    monkeypatch.setattr(os, 'write', refuse)

    with pytest.raises(SystemExit) as exit_info:
        cli.cmdline(Args(['reset']))

    assert exit_info.value.code == 1
    assert opened, 'the writer fifo was never opened'
    with pytest.raises(OSError):
        os.fstat(opened[-1])


def test_reset_with_no_named_pipe_exits_non_zero(monkeypatch, capsys):
    """Control: 5.0 already refuses to claim success with no transport."""
    monkeypatch.setattr(cli, 'named_pipe', lambda root, name: [])
    with pytest.raises(SystemExit) as exit_info:
        cli.cmdline(Args(['reset']))
    assert exit_info.value.code == 1


def test_reset_with_an_unusable_fifo_exits_non_zero(tmp_path, monkeypatch):
    """Control: a plain file where the fifo should be is not a transport."""
    folder = f'{tmp_path}/'
    with open(folder + 'testpipe.in', 'w'):
        pass
    monkeypatch.setattr(cli, 'named_pipe', lambda root, name: [folder])
    with pytest.raises(SystemExit) as exit_info:
        cli.cmdline(Args(['reset']))
    assert exit_info.value.code == 1
