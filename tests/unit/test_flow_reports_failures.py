"""The flow helper must say when a flow did not make it onto the switch.

Two `except Exception: pass` handlers hid the only two ways this process fails at its
job. `_commit()` swallowed a cl-acltool which could not run, so exabgp announced flows
which filtered nothing. The main loop swallowed every message it could not read, so a
flowspec update became a dropped line with no rule, no error and no clue.

Both now write to stderr and both still carry on, which is what these tests pin.
"""

from __future__ import annotations

import io
import subprocess

import pytest

from exabgp.application import flow
from exabgp.application.flow import ACL


@pytest.fixture
def switch(tmp_path, monkeypatch):
    """A policy directory of our own, with nothing installed in it."""
    monkeypatch.setattr(ACL, 'path', f'{tmp_path}/')
    monkeypatch.setattr(ACL, '_known', {})
    monkeypatch.setattr(ACL, 'dry', False)
    return tmp_path


def test_a_reload_which_can_not_run_is_reported(switch, monkeypatch, capsys):
    """cl-acltool missing means no rule is programmed, and the operator must be told."""

    def refuse(*args, **kwargs):
        raise OSError('No such file or directory: cl-acltool')

    monkeypatch.setattr(subprocess, 'Popen', refuse)

    assert ACL._commit() is None, 'a failed reload still returns to its caller'

    reported = capsys.readouterr().err
    assert 'cl-acltool' in reported, 'the operator must be told which command failed'
    assert 'No such file' in reported, 'and why it failed'


def test_a_reload_which_works_is_quiet(switch, monkeypatch, capsys):
    """The report is for a failure only: a working reload says nothing."""

    class Reload:
        def communicate(self):
            return (b'', None)

    monkeypatch.setattr(subprocess, 'Popen', lambda *args, **kwargs: Reload())

    assert ACL._commit() == b''
    assert capsys.readouterr().err == '', 'a reload which worked has nothing to report'


def _drive(monkeypatch, lines):
    """Run the main loop over `lines` and return what it wrote to stderr."""
    monkeypatch.setattr(flow.signal, 'signal', lambda *args: None)
    monkeypatch.setattr('sys.stdin', io.StringIO(''.join(lines)))
    with pytest.raises(SystemExit):
        flow.main()


def test_a_message_which_can_not_be_processed_is_reported(switch, monkeypatch, capsys):
    """A malformed update is dropped, the loop survives, and the drop is named."""
    _drive(monkeypatch, ['{"type": "update", "neighbor": {}}\n', ''])

    reported = capsys.readouterr().err
    assert 'ignored a message' in reported, 'a message we could not read must be reported'
    assert 'message' in reported


def test_a_message_we_do_not_care_about_stays_quiet(switch, monkeypatch, capsys):
    """A well formed message of a type we skip is not an error and must not read as one."""
    _drive(monkeypatch, ['{"type": "keepalive", "neighbor": {}}\n', ''])

    assert 'ignored a message' not in capsys.readouterr().err
