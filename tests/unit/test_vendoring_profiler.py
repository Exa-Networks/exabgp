"""The vendored memory profiler, typed and compiled with mypyc.

Nothing in ExaBGP imports it: it is kept to be pointed at a function by hand, through the
profile decorator, LineProfiler, memory_usage() and main(). These run each of them,
interpreted and against the compiled tree (PYTHONPATH=build/mypyc).
"""

from __future__ import annotations

import builtins
import io
import os
import subprocess
import sys
from pathlib import Path
from types import FrameType

import pytest

from exabgp.vendoring import profiler


def allocate(count: int) -> int:
    block = [0] * count
    return len(block)


def test_memory_usage_of_this_process() -> None:
    (sample,) = profiler.memory_usage()
    assert sample > 0


def test_memory_usage_samples_until_the_timeout() -> None:
    samples = profiler.memory_usage(os.getpid(), interval=0.01, timeout=0.05)
    assert len(samples) == 5
    assert all(sample > 0 for sample in samples)


@pytest.mark.timeout(30)
def test_memory_usage_of_a_pid_given_as_text_is_sampled_once() -> None:
    # The original looped forever on a PID given as a string without a timeout.
    (sample,) = profiler.memory_usage(str(os.getpid()))
    assert sample > 0


@pytest.mark.timeout(60)
def test_memory_usage_of_a_function_call() -> None:
    samples = profiler.memory_usage((allocate, (100_000,)), interval=0.01)
    assert samples
    assert all(sample > 0 for sample in samples)


def test_memory_usage_refuses_a_call_with_the_wrong_arguments() -> None:
    with pytest.raises(ValueError, match='expects 1 value'):
        profiler.memory_usage((allocate, ()))
    with pytest.raises(ValueError, match='a call is given as'):
        profiler.memory_usage((allocate, (1,), {}, 'extra'))


@pytest.mark.timeout(30)
def test_memory_usage_of_a_child_process_ends_with_it() -> None:
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(0.2)'])
    samples = profiler.memory_usage(child, interval=0.05)
    assert child.poll() is not None
    assert samples


def test_profile_decorator_reports_each_line(capsys: pytest.CaptureFixture[str]) -> None:
    stream = io.StringIO()
    measured = profiler.profile(allocate, stream=stream)
    assert measured(10_000) == 10_000
    report = stream.getvalue()
    assert f'Filename: {__file__}' in report
    assert 'Line #    Mem usage    Increment   Line Contents' in report
    assert 'block = [0] * count' in report
    assert ' MB ' in report


def other_tracer(frame: FrameType, event: str, arg: object) -> None:
    return None


def test_line_profiler_puts_back_the_tracer_it_displaced() -> None:
    # A coverage run traces with its own function: the original cleared it for good.
    before = sys.gettrace()
    sys.settrace(other_tracer)
    try:
        prof = profiler.LineProfiler()
        wrapped = prof(allocate)
        assert wrapped.__name__ == 'allocate'
        assert wrapped(100) == 100
        assert prof.runcall(allocate, 100) == 100
        with prof:
            allocate(100)
        assert sys.gettrace() is other_tracer
    finally:
        sys.settrace(before)
    (lines,) = prof.code_map.values()
    assert lines


def test_line_profiler_refuses_what_has_no_code() -> None:
    prof = profiler.LineProfiler()
    with pytest.warns(UserWarning, match='Could not extract a code object'):
        prof.add_function(len)
    assert prof.code_map == {}


def test_main_runs_a_script_and_reports_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = tmp_path / 'script.py'
    script.write_text(
        'import sys\n'
        '\n'
        '@profile\n'
        'def work():\n'
        '    block = [0] * 10000\n'
        '    return len(block)\n'
        '\n'
        'assert __name__ == "__main__"\n'
        'print("argv", sys.argv[1:])\n'
        'print("work", work())\n',
        encoding='utf-8',
    )
    monkeypatch.setattr(sys, 'argv', ['profiler'])
    monkeypatch.delattr(builtins, 'profile', raising=False)
    try:
        assert profiler.main(['--precision', '2', str(script), 'one', 'two']) == 0
    finally:
        monkeypatch.delattr(builtins, 'profile', raising=False)
    out = capsys.readouterr().out
    assert "argv ['one', 'two']" in out
    assert 'work 10000' in out
    assert f'Filename: {script}' in out
    assert 'block = [0] * 10000' in out


def test_main_without_arguments_prints_the_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert profiler.main([]) == 2
    assert 'usage:' in capsys.readouterr().out
