# From https://git.geekli.st/daveyoon/khan-academy-lite/blob/14ab3615f66bcdd737909e7951a250da8a10646b/python-packages/memory_profiler.py
# LICENCE: MIT

"""Profile the memory usage of a Python program"""

# Changed for ExaBGP: typed for mypy --strict and compiled with mypyc. The IPython magics
# (%mprun, %memit) are gone: they registered with ip.define_magic(), which IPython 1.0
# removed in 2013, so they could not load on any IPython Python 3.12 runs. The sampling
# process is a function run by multiprocessing rather than a Process subclass, and the
# command line uses argparse rather than optparse.

from __future__ import annotations

__version__ = '0.26'

_CMD_USAGE = 'python -m memory_profiler script_file.py'

import argparse  # noqa: E402
import builtins  # noqa: E402
import functools  # noqa: E402
import importlib  # noqa: E402
import importlib.util  # noqa: E402
import os  # noqa: E402
import pdb  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
import types  # noqa: E402
import warnings  # noqa: E402
import linecache  # noqa: E402
import inspect  # noqa: E402
import subprocess  # noqa: E402
from collections.abc import Callable  # noqa: E402
from collections.abc import Mapping  # noqa: E402
from collections.abc import Sequence  # noqa: E402
from multiprocessing import Pipe  # noqa: E402
from multiprocessing import Process  # noqa: E402
from multiprocessing.connection import Connection  # noqa: E402
from typing import TYPE_CHECKING  # noqa: E402
from typing import Any  # noqa: E402
from typing import ParamSpec  # noqa: E402
from typing import TextIO  # noqa: E402
from typing import TypeVar  # noqa: E402

if TYPE_CHECKING:
    from _typeshed import TraceFunction

P = ParamSpec('P')
R = TypeVar('R')

# How long memory_usage() waits for the sampling process to report it is running.
SAMPLER_START_SECONDS = 30.0

MEGABYTE = 1024**2

# psutil is a development dependency, not a runtime one: without it the memory is read
# from ps, one process spawned per sample, which is why the warning says it is slow.
_HAS_PSUTIL = importlib.util.find_spec('psutil') is not None

if not _HAS_PSUTIL:
    warnings.warn('psutil module not found. memory_profiler will be slow')
    if os.name != 'posix':
        raise NotImplementedError('The psutil module is required for non-unix platforms')


def _get_memory(pid: int) -> float:
    """The resident memory of process pid, in MB, or -1 when it cannot be read."""
    if not _HAS_PSUTIL:
        return _get_memory_from_ps(pid)
    # Imported by name: psutil has no type information, and is not always installed.
    psutil = importlib.import_module('psutil')
    try:
        return float(psutil.Process(pid).memory_info()[0]) / MEGABYTE
    except psutil.AccessDenied:
        return -1.0


def _get_memory_from_ps(pid: int) -> float:
    # .. memory usage in MB ..
    # .. this should work on both Mac and Linux ..
    out = subprocess.run(['ps', 'v', '-p', str(pid)], stdout=subprocess.PIPE, check=False).stdout.split(b'\n')
    try:
        vsz_index = out[0].split().index(b'RSS')
        return float(out[1].split()[vsz_index]) / 1024
    except (ValueError, IndexError):
        # No RSS column, or no line for the process: it has gone, or is not ours to read.
        return -1.0


def _sample_memory(monitor_pid: int, interval: float, pipe: Connection) -> None:
    """Fetch memory consumption over a time interval, until pipe says to stop.

    Run in its own process by memory_usage(), while the function measured runs in this one.
    """
    timings = [_get_memory(monitor_pid)]
    pipe.send(0)  # we're ready
    while not pipe.poll(interval):
        timings.append(_get_memory(monitor_pid))
    pipe.send(timings)


def memory_usage(proc: object = -1, interval: float = 0.1, timeout: float | None = None) -> list[float]:
    """
    Return the memory usage of a process or piece of code

    Parameters
    ----------
    proc : {int, string, tuple, subprocess.Popen}, optional
        The process to monitor. Can be given by an integer/string
        representing a PID, by a Popen object or by a tuple
        representing a Python function. The tuple contains three
        values (f, args, kw) and specifies to run the function
        f(*args, **kw).
        Set to -1 (default) for current process.

    interval : float, optional
        Interval at which measurements are collected.

    timeout : float, optional
        Maximum amount of time (in seconds) to wait before returning.
        A function is always run to its end.

    Returns
    -------
    mem_usage : list of floating-poing values
        memory usage, in MB. It's length is always < timeout / interval
    """
    if callable(proc):
        return _memory_of_call(proc, (), {}, interval)
    if isinstance(proc, (list, tuple)):
        function, args, kw = _unpack_call(proc)
        return _memory_of_call(function, args, kw, interval)
    if isinstance(proc, subprocess.Popen):
        return _memory_of_popen(proc, interval, timeout)
    if isinstance(proc, (int, str)):
        pid = os.getpid() if proc == -1 else int(proc)
        # An external process is measured once, unless a timeout asks for more. The
        # original looped forever on a PID given as a string without a timeout.
        samples = int(timeout / interval) if timeout is not None else 1
        return _memory_of_pid(pid, interval, samples)
    raise TypeError('cannot measure the memory of %r' % (proc,))


def _unpack_call(
    proc: list[Any] | tuple[Any, ...],
) -> tuple[Callable[..., object], Sequence[object], Mapping[str, object]]:
    """The function, arguments and keyword arguments of a call given as (f,), (f, args) or (f, args, kw)."""
    if not 1 <= len(proc) <= 3:
        raise ValueError('a call is given as (f,), (f, args) or (f, args, kw), not %d items' % len(proc))
    function = proc[0]
    if not callable(function):
        raise TypeError('%r is not callable' % (function,))
    args = proc[1] if len(proc) > 1 else ()
    kw = proc[2] if len(proc) > 2 else {}
    return function, args, kw


def _memory_of_call(
    function: Callable[..., object], args: Sequence[object], kw: Mapping[str, object], interval: float
) -> list[float]:
    aspec = inspect.getfullargspec(function)
    n_args = len(aspec.args)
    if aspec.defaults is not None:
        n_args -= len(aspec.defaults)
    if n_args != len(args):
        raise ValueError('Function expects %s value(s) but %s where given' % (n_args, len(args)))

    child_conn, parent_conn = Pipe()  # this will store the sampler's results
    sampler = Process(target=_sample_memory, args=(os.getpid(), interval, child_conn))
    sampler.start()
    # A sampler which cannot start (it could not import this module) never answers.
    if not parent_conn.poll(SAMPLER_START_SECONDS):
        sampler.kill()
        raise RuntimeError('the memory sampling process did not start')
    parent_conn.recv()  # wait until we start getting memory
    function(*args, **kw)
    parent_conn.send(0)  # finish timing
    timings: list[float] = parent_conn.recv()
    sampler.join(5 * interval)
    return timings


def _memory_of_popen(proc: subprocess.Popen[Any], interval: float, timeout: float | None) -> list[float]:
    """Sample an external process launched from Python, until it ends or the timeout passes."""
    timings: list[float] = []
    remaining = int(timeout / interval) if timeout is not None else None
    # Without a timeout the loop lasts as long as the process does.
    while True:
        timings.append(_get_memory(proc.pid))
        time.sleep(interval)
        if remaining is not None:
            remaining -= 1
            # The original tested == 0, and a timeout under one interval never ended.
            if remaining <= 0:
                break
        if proc.poll() is not None:
            break
    return timings


def _memory_of_pid(pid: int, interval: float, samples: int) -> list[float]:
    timings: list[float] = []
    for _ in range(samples):
        timings.append(_get_memory(pid))
        time.sleep(interval)
    return timings


# ..
# .. utility functions for line-by-line ..


def _find_script(script_name: str) -> str:
    """Find the script.

    If the input is not a file, then $PATH will be searched.
    """
    if os.path.isfile(script_name):
        return script_name
    path = os.getenv('PATH', os.defpath).split(os.pathsep)
    for folder in path:
        if folder == '':
            continue
        fn = os.path.join(folder, script_name)
        if os.path.isfile(fn):
            return fn

    sys.stderr.write('Could not find script {0}\n'.format(script_name))
    raise SystemExit(1)


class LineProfiler:
    """A profiler that records the amount of memory for each line"""

    def __init__(self, max_mem: float | None = None) -> None:
        self.functions: list[Callable[..., object]] = []
        self.code_map: dict[types.CodeType, dict[int, list[float]]] = {}
        self.enable_count = 0
        self.max_mem = max_mem
        self.previous_trace: TraceFunction | None = None

    def __call__(self, func: Callable[P, R]) -> Callable[P, R]:
        self.add_function(func)
        return self.wrap_function(func)

    def add_function(self, func: Callable[..., object]) -> None:
        """Record line profiling information for the given Python function."""
        # A builtin, or a function compiled by mypyc, has no code object to trace.
        code = getattr(func, '__code__', None)
        if not isinstance(code, types.CodeType):
            warnings.warn('Could not extract a code object for the object %r' % (func,))
            return
        if code not in self.code_map:
            self.code_map[code] = {}
            self.functions.append(func)

    def wrap_function(self, func: Callable[P, R]) -> Callable[P, R]:
        """Wrap a function to profile it."""

        @functools.wraps(func)
        def f(*args: P.args, **kwds: P.kwargs) -> R:
            self.enable_by_count()
            try:
                return func(*args, **kwds)
            finally:
                self.disable_by_count()

        return f

    def run(self, cmd: str) -> LineProfiler:
        """Profile a single executable statment in the main namespace."""
        import __main__

        main_dict = __main__.__dict__
        return self.runctx(cmd, main_dict, main_dict)

    def runctx(self, cmd: str, globals: dict[str, Any], locals: Mapping[str, object]) -> LineProfiler:
        """Profile a single executable statement in the given namespaces."""
        self.enable_by_count()
        try:
            exec(cmd, globals, locals)
        finally:
            self.disable_by_count()
        return self

    def runcall(self, func: Callable[P, R], *args: P.args, **kw: P.kwargs) -> R:
        """Profile a single function call."""
        self.enable_by_count()
        try:
            return func(*args, **kw)
        finally:
            self.disable_by_count()

    def enable_by_count(self) -> None:
        """Enable the profiler if it hasn't been enabled before."""
        if self.enable_count == 0:
            self.enable()
        self.enable_count += 1

    def disable_by_count(self) -> None:
        """Disable the profiler if the number of disable requests matches the
        number of enable requests.
        """
        if self.enable_count > 0:
            self.enable_count -= 1
            if self.enable_count == 0:
                self.disable()

    def trace_memory_usage(self, frame: types.FrameType, event: str, arg: object) -> TraceFunction:
        """Callback for sys.settrace"""
        if event in ('line', 'return') and frame.f_code in self.code_map:
            lineno = frame.f_lineno
            if event == 'return':
                lineno += 1
            entry = self.code_map[frame.f_code].setdefault(lineno, [])
            entry.append(_get_memory(os.getpid()))

        return self.trace_memory_usage

    def trace_max_mem(self, frame: types.FrameType, event: str, arg: object) -> TraceFunction:
        # run into PDB as soon as memory is higher than MAX_MEM
        assert self.max_mem is not None, 'enable() only traces the maximum when there is one'
        if event in ('line', 'return') and frame.f_code in self.code_map:
            c = _get_memory(os.getpid())
            if c >= self.max_mem:
                t = 'Current memory {0:.2f} MB exceeded the maximum '.format(c) + 'of {0:.2f} MB\n'.format(self.max_mem)
                sys.stdout.write(t)
                sys.stdout.write('Stepping into the debugger \n')
                # The original also moved frame.f_lineno two lines back, to show the line
                # which allocated. Python 3 only lets a trace function jump on a 'line'
                # event, and a jump re-runs the code it skips back over: the debugger
                # now stops where the maximum was found.
                debugger = pdb.Pdb()
                debugger.set_trace(frame)
                return debugger.trace_dispatch

        return self.trace_max_mem

    def __enter__(self) -> None:
        self.enable_by_count()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self.disable_by_count()

    def enable(self) -> None:
        # The tracer this one displaces (a coverage run's) is put back by disable(): the
        # original cleared it, and whatever was measuring stopped for good.
        self.previous_trace = sys.gettrace()
        if self.max_mem is not None:
            sys.settrace(self.trace_max_mem)
        else:
            sys.settrace(self.trace_memory_usage)

    def disable(self) -> None:
        sys.settrace(self.previous_trace)
        self.previous_trace = None


def show_results(prof: LineProfiler, stream: TextIO | None = None, precision: int = 3) -> None:
    out = sys.stdout if stream is None else stream
    for code, lines in prof.code_map.items():
        if not lines:
            # .. measurements are empty ..
            continue
        filename = code.co_filename
        out.write('Filename: ' + filename + '\n\n')
        if not os.path.exists(filename):
            out.write('ERROR: Could not find file ' + filename + '\n')
            continue
        _show_code(out, code, lines, int(precision))


_TEMPLATE = '{0:>6} {1:>12} {2:>12}   {3:<}'


def _show_code(out: TextIO, code: types.CodeType, lines: dict[int, list[float]], precision: int) -> None:
    """Write the source of code, each line beside the memory it was measured using."""
    all_lines = linecache.getlines(code.co_filename)
    sub_lines = inspect.getblock(all_lines[code.co_firstlineno - 1 :])
    linenos = range(code.co_firstlineno, code.co_firstlineno + len(sub_lines))
    lines_normalized = _normalize(lines)

    header = _TEMPLATE.format('Line #', 'Mem usage', 'Increment', 'Line Contents')
    out.write(header + '\n')
    out.write('=' * len(header) + '\n')

    first_line = min(lines_normalized)
    mem_old = max(lines_normalized[first_line])
    template_mem = '{{0:{0}.{1}'.format(precision + 6, precision) + 'f} MB'
    for idx, line in enumerate(linenos):
        mem_text = ''
        inc_text = ''
        if line in lines_normalized:
            mem = max(lines_normalized[line])
            inc = mem - mem_old
            mem_old = mem
            mem_text = template_mem.format(mem)
            inc_text = template_mem.format(inc)
        out.write(_TEMPLATE.format(line, mem_text, inc_text, sub_lines[idx]))
    out.write('\n\n')


def _normalize(lines: dict[int, list[float]]) -> dict[int, list[float]]:
    """Move every measurement one line up: the trace sees a line before it runs.

    As in the original, the measurement lists are shared with the profiler, and the
    samples taken past the length of the previous line's are replaced with -1.
    """
    lines_normalized: dict[int, list[float]] = {}
    keys = sorted(lines.keys())

    k_old = keys[0] - 1
    lines_normalized[keys[0] - 1] = lines[keys[0]]
    for i in range(1, len(lines_normalized[keys[0] - 1])):
        lines_normalized[keys[0] - 1][i] = -1.0
    k = keys.pop(0)
    while keys:
        lines_normalized[k] = lines[keys[0]]
        for i in range(len(lines_normalized[k_old]), len(lines_normalized[k])):
            lines_normalized[k][i] = -1.0
        k_old = k
        k = keys.pop(0)
    return lines_normalized


def profile(func: Callable[P, R], stream: TextIO | None = None) -> Callable[P, R]:
    """
    Decorator that will run the function and print a line-by-line profile
    """

    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        prof = LineProfiler()
        val = prof(func)(*args, **kwargs)
        show_results(prof, stream=stream)
        return val

    return wrapper


def main(argv: list[str] | None = None) -> int:
    """Run a script with its functions decorated @profile measured, line by line."""
    parser = argparse.ArgumentParser(usage=_CMD_USAGE)
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument(
        '--pdb-mmem',
        dest='max_mem',
        metavar='MAXMEM',
        type=float,
        help='step into the debugger when memory exceeds MAXMEM',
    )
    parser.add_argument(
        '--precision',
        type=int,
        default=3,
        help='precision of memory output in number of significant digits',
    )
    parser.add_argument('script', help='the script to run')
    parser.add_argument('arguments', nargs=argparse.REMAINDER, help='the arguments of the script')

    arguments = sys.argv[1:] if argv is None else argv
    if not arguments:
        parser.print_help()
        return 2
    options = parser.parse_args(arguments)

    script = _find_script(options.script)
    # The script sees its own name and arguments, as if it had been run directly. The
    # original deleted only argv[0], leaving the profiler's options in front of them.
    sys.argv[:] = [options.script, *options.arguments]
    prof = LineProfiler(max_mem=options.max_mem)
    setattr(builtins, 'profile', prof)
    namespace: dict[str, Any] = {'__name__': '__main__', '__file__': script, '__builtins__': builtins}
    try:
        with open(script) as source:
            code = compile(source.read(), script, 'exec')
        exec(code, namespace)
    finally:
        show_results(prof, precision=options.precision)
    return 0


if __name__ == '__main__':
    sys.exit(main())
