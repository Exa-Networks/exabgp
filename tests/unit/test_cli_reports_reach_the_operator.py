"""A diagnostic goes to stderr, because in Control stdout is the pipe to the daemon.

`Control.loop()` hands the daemon its own stdout as the command channel: it writes
'session ack enable' and every later command through `sys.stdout.fileno()`. So anything
`check_fifo` wrote to stdout was written down that pipe and read by the daemon as a line of
command input, rather than by the operator as an error. `run.py`'s reset path already used
stderr for the same class of message; three sites were the outliers.

The second defect here is a handler which could never run. Python takes the first `except`
clause which matches, so `open_writer`'s second `except OSError` was unreachable, and it was
the one carrying the reason: the reachable clause printed 'could not communicate with ExaBGP'
with the exception discarded, so a pipe we may not open read exactly like one which had gone
away.
"""

from __future__ import annotations

import ast
import errno
import os
import pathlib
from typing import Any
from unittest.mock import patch

import pytest

from exabgp.application import pipe as pipe_module
from exabgp.application import run as run_module
from exabgp.application.pipe import check_fifo


@pytest.fixture
def fifo(tmp_path: Any) -> Any:
    name = tmp_path / 'exabgp.in'
    os.mkfifo(name)
    return name


def test_a_missing_pipe_is_reported_on_stderr(tmp_path: Any, capsys: Any) -> None:
    assert check_fifo(f'{tmp_path}/absent.in') is False

    captured = capsys.readouterr()
    assert 'could not access the named pipe' in captured.err
    assert captured.out == '', f'written to the daemon pipe: {captured.out!r}'


def test_a_plain_file_is_reported_on_stderr(tmp_path: Any, capsys: Any) -> None:
    plain = tmp_path / 'plain'
    plain.write_text('')

    assert check_fifo(str(plain)) is False

    captured = capsys.readouterr()
    assert 'is not a named pipe' in captured.err
    assert captured.out == ''


def test_an_unreadable_pipe_is_reported_on_stderr(tmp_path: Any, capsys: Any) -> None:
    name = tmp_path / 'unreadable.in'
    os.mkfifo(name, 0o000)

    assert check_fifo(str(name)) is False

    captured = capsys.readouterr()
    assert 'we can not read/write to it' in captured.err
    assert captured.out == ''


def test_a_usable_pipe_says_nothing_at_all(fifo: Any, capsys: Any) -> None:
    """The control: a working fifo must not report on either stream."""
    assert check_fifo(str(fifo)) is True

    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err == ''


def test_nothing_check_fifo_reports_reaches_the_daemon(tmp_path: Any, capsys: Any) -> None:
    """One `in` assertion per message would still pass if a copy went to stdout as well.

    stdout is the end that matters, so this asserts it is empty for every failing shape.
    """
    plain = tmp_path / 'plain'
    plain.write_text('')
    unreadable = tmp_path / 'unreadable.in'
    os.mkfifo(unreadable, 0o000)

    for name in (f'{tmp_path}/absent.in', str(plain), str(unreadable)):
        assert check_fifo(name) is False

        captured = capsys.readouterr()
        assert captured.out == '', f'{name} wrote to the daemon pipe: {captured.out!r}'
        assert captured.err != '', f'{name} reported nothing at all'


def test_an_unopenable_pipe_names_the_reason(fifo: Any, capsys: Any) -> None:
    """The unreachable handler's message, now on the path which actually runs."""
    refused = OSError(errno.EACCES, 'Permission denied')

    with patch.object(run_module.os, 'open', side_effect=refused):
        with pytest.raises(SystemExit):
            run_module.open_writer(str(fifo))

    captured = capsys.readouterr()
    assert 'could not communicate with ExaBGP' in captured.err
    assert 'Permission denied' in captured.err, 'the reason was discarded, as it used to be'
    assert captured.out == ''


def test_a_pipe_with_no_reader_still_says_exabgp_is_not_running(fifo: Any, capsys: Any) -> None:
    """ENXIO keeps its own sentence, which is the more useful one when it applies."""
    with patch.object(run_module.os, 'open', side_effect=OSError(errno.ENXIO, 'No such device')):
        with pytest.raises(SystemExit):
            run_module.open_writer(str(fifo))

    captured = capsys.readouterr()
    assert 'ExaBGP is not running' in captured.err
    assert captured.out == ''


def test_no_try_in_the_application_catches_one_name_twice() -> None:
    """The regression guard for the class, with a floor so an empty walk cannot pass."""
    root = pathlib.Path(run_module.__file__).parent
    offenders = []
    handlers = 0

    for path in root.rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Try):
                continue
            names = [h.type.id for h in node.handlers if isinstance(h.type, ast.Name)]
            handlers += len(names)
            repeated = {name for name in names if names.count(name) > 1}
            if repeated:
                offenders.append(f'{path.name}:{node.lineno} catches {sorted(repeated)} twice')

    assert handlers >= 20, f'only {handlers} named handlers walked, the scan is looking in the wrong place'
    assert not offenders, 'unreachable duplicate handlers: ' + '; '.join(offenders)


def test_check_fifo_writes_to_no_other_stream() -> None:
    """Read the source: the fault is a destination, and a destination is visible statically."""
    source = pathlib.Path(pipe_module.__file__).read_text()
    body = source[source.index('def check_fifo') : source.index('class Control')]

    # `sys.stdout.write`, not `sys.stdout`: the docstring names the stream it must not use,
    # and an assertion which cannot tell prose from code is not worth having.
    assert 'sys.stdout.write' not in body, 'check_fifo still writes to the pipe the daemon reads'
    assert body.count('sys.stderr.write') == 3
    assert body.count('sys.stderr.flush') == 3, 'a report which is not flushed can sit behind the next write'
