"""State-transition tests for the functional runner's Exec process owner."""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path
import time
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
Exec: Any = runpy.run_path(str(ROOT / 'qa/bin/functional'))['Exec']


def test_new_exec_is_not_ready() -> None:
    execution = Exec()

    assert execution.ready() is False


def test_collected_exec_is_ready_and_reusable() -> None:
    execution = Exec()

    execution.run([sys.executable, '-c', "print('first')"], env=os.environ.copy())
    execution.collect()

    assert execution.ready() is True
    assert execution.code == 0
    assert execution.stdout == b'first\n'
    assert execution._process is None
    assert execution._stdout_file is None
    assert execution._stderr_file is None
    assert execution._process_group is None

    execution.run([sys.executable, '-c', "print('second')"], env=os.environ.copy())
    execution.collect()

    assert execution.code == 0
    assert execution.stdout == b'second\n'


def test_run_refuses_to_replace_an_owned_process() -> None:
    execution = Exec().run([sys.executable, '-c', 'import time; time.sleep(10)'], env=os.environ.copy())
    try:
        with pytest.raises(RuntimeError, match='must be collected or terminated'):
            execution.run([sys.executable, '-c', 'pass'], env=os.environ.copy())
    finally:
        execution.terminate()


def test_collect_releases_process_state_when_file_close_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    execution = Exec().run([sys.executable, '-c', 'pass'], env=os.environ.copy())
    close_files = execution._close_temp_files

    def close_then_raise() -> None:
        close_files()
        raise OSError('close failed')

    monkeypatch.setattr(execution, '_close_temp_files', close_then_raise)

    with pytest.raises(OSError, match='close failed'):
        execution.collect()

    assert execution._process is None
    assert execution._collected is True


def test_output_limit_fails_and_truncates_the_process(monkeypatch: pytest.MonkeyPatch) -> None:
    execution = Exec()
    monkeypatch.setattr(execution, 'MAX_OUTPUT_BYTES', 8)
    execution.run([sys.executable, '-c', "print('output larger than eight bytes')"], env=os.environ.copy())

    for _ in range(100):
        if execution.ready():
            break
        time.sleep(0.01)
    else:
        execution.terminate()
        raise AssertionError('process did not become ready')

    execution.collect()

    assert execution.code != 0
    assert len(execution.stdout) <= execution.MAX_OUTPUT_BYTES
    assert 'output exceeded' in execution.message


def test_collect_does_not_signal_a_process_group_which_already_emptied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The usual case is a process which left nothing behind.

    Sweeping unconditionally cost a SIGTERM, a tenth of a second of sleep and a SIGKILL
    on every collect, on the harness's own thread, for a group the parent already took
    with it. Signal zero answers whether anything is left without disturbing it.
    """
    if os.name != 'posix':
        pytest.skip('process groups require POSIX')

    execution = Exec().run([sys.executable, '-c', 'pass'], env=os.environ.copy())

    delivered: list[int] = []
    real_killpg = os.killpg

    def recording_killpg(group: int, number: int) -> None:
        delivered.append(number)
        real_killpg(group, number)

    monkeypatch.setattr(os, 'killpg', recording_killpg)

    execution.collect()

    assert execution.code == 0
    assert execution._process_group is None
    assert delivered == [0], f'a signal was delivered to an empty process group: {delivered}'


def test_collect_kills_descendants_left_by_a_completed_parent() -> None:
    if os.name != 'posix':
        pytest.skip('process groups require POSIX')

    child_code = 'import time; time.sleep(30)'
    parent_code = (
        'import subprocess, sys; '
        f'child = subprocess.Popen([sys.executable, "-c", {child_code!r}]); '
        'print(child.pid, flush=True)'
    )
    execution = Exec().run([sys.executable, '-c', parent_code], env=os.environ.copy())

    execution.collect()
    child_pid = int(execution.stdout.strip())

    for _ in range(100):
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.01)
    else:
        raise AssertionError(f'descendant process {child_pid} survived collection')

    assert execution._process_group is None
