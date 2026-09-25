#!/usr/bin/env python3
"""`open_writer` telling the operator why it could not reach the daemon.

`open_writer` had two `except OSError` on one `try`.  Only the first could run, and it
printed 'could not communicate with ExaBGP' with the reason thrown away; the reason was in
the second, dead since Python 3.3 made `IOError` an alias of `OSError`.  A pipe we may not
open and a pipe which has gone away are the same sentence without it.
"""

from __future__ import annotations

import errno
import os
import signal

import pytest

from exabgp.application import cli


@pytest.fixture
def no_alarm():
    """open_writer arms SIGALRM and only disarms it on the path which succeeds.

    A test which takes the failing path would otherwise leave the alarm armed for whatever
    runs next in this interpreter, where the handler writes and exits.
    """
    previous = signal.getsignal(signal.SIGALRM)
    yield
    signal.alarm(0)
    signal.signal(signal.SIGALRM, previous)


def test_a_pipe_we_may_not_open_says_why(tmp_path, capsys, no_alarm):
    if os.geteuid() == 0:
        pytest.skip('root opens a fifo whatever its mode')
    name = str(tmp_path / 'exabgp.in')
    os.mkfifo(name, 0o000)

    with pytest.raises(SystemExit) as exit_info:
        cli.open_writer(name)

    assert exit_info.value.code == 1
    captured = capsys.readouterr().out
    assert 'could not communicate with ExaBGP' in captured
    assert 'Permission denied' in captured


def test_a_pipe_with_nobody_at_the_other_end_still_says_exabgp_is_not_running(tmp_path, monkeypatch, capsys, no_alarm):
    """Control: ENXIO keeps its own sentence, which is the one an operator acts on."""
    name = str(tmp_path / 'exabgp.in')
    os.mkfifo(name)
    real_open = os.open

    def refuse(path, flags, *args, **kwargs):
        if path == name:
            raise OSError(errno.ENXIO, 'Device not configured')
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, 'open', refuse)

    with pytest.raises(SystemExit) as exit_info:
        cli.open_writer(name)

    assert exit_info.value.code == 1
    assert 'ExaBGP is not running' in capsys.readouterr().out
