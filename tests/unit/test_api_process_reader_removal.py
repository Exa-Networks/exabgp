"""Taking an API process' stdout off the event loop must never raise.

`_async_reader_callback` is registered with `loop.add_reader`, so it runs as an asyncio
callback with nobody to catch what escapes it. Its first move on every error path is to
remove the reader, because a descriptor which raises on every read would otherwise have
the event loop call the callback again immediately, forever.

That removal used to be written out four times, each wrapped in its own try/except which
swallowed the failure. The duplication is what made it fragile: the copy in `_terminate`
guarded `process.stdout` and the copies in the error paths guarded `process_name in
self._process`, so each knew about a different way for the lookup to fail. They are now
one pair of methods, and these are the states those two have to survive.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from exabgp.reactor.api.processes import Processes


@pytest.fixture
def processes() -> Any:
    with patch('exabgp.reactor.api.processes.getenv') as getenv:
        environment = MagicMock()
        environment.api.respawn = False
        environment.api.terminate = False
        environment.api.ack = True
        getenv.return_value = environment
        instance = Processes()
    instance._async_mode = True
    instance._loop = MagicMock()
    return instance


def with_stdout(processes: Any, name: str, fileno: Any) -> Any:
    process = MagicMock()
    process.stdout.fileno = fileno
    processes._process[name] = process
    return process


def test_the_reader_is_removed_for_a_live_process(processes: Any) -> None:
    with_stdout(processes, 'watchdog', lambda: 11)

    processes._drop_reader('watchdog', 'terminating')

    processes._loop.remove_reader.assert_called_once_with(11)


def test_a_process_already_gone_is_not_looked_up(processes: Any) -> None:
    """_handle_problem deletes the entry, and both error paths can run after it."""
    processes._drop_reader('never-started', 'oserror')

    processes._loop.remove_reader.assert_not_called()


def test_a_process_without_stdout_is_not_looked_up(processes: Any) -> None:
    """Popen.stdout is None when the process was started without a pipe."""
    process = MagicMock()
    process.stdout = None
    processes._process['silent'] = process

    processes._drop_reader('silent', 'exception')

    processes._loop.remove_reader.assert_not_called()


def test_a_closed_stdout_does_not_escape(processes: Any) -> None:
    """fileno() on a closed file raises ValueError, and this runs as an asyncio callback."""

    def closed() -> int:
        raise ValueError('I/O operation on closed file')

    with_stdout(processes, 'closed', closed)

    processes._drop_reader('closed', 'oserror')

    processes._loop.remove_reader.assert_not_called()


@pytest.mark.parametrize('error', [ValueError('not registered'), OSError(9, 'Bad file descriptor')])
def test_a_refused_removal_does_not_escape(processes: Any, error: Exception) -> None:
    """Removing a reader twice is normal: the exit path and the error path both do it."""
    processes._loop.remove_reader.side_effect = error
    with_stdout(processes, 'twice', lambda: 12)

    processes._drop_reader('twice', 'exited')

    processes._loop.remove_reader.assert_called_once_with(12)


def test_nothing_is_removed_when_not_running_on_the_event_loop(processes: Any) -> None:
    """The poll based reader never registered one, so there is none to take off."""
    processes._async_mode = False
    with_stdout(processes, 'polled', lambda: 13)

    processes._drop_reader('polled', 'terminating')

    processes._loop.remove_reader.assert_not_called()


def test_the_callback_returns_when_the_process_is_already_gone(processes: Any) -> None:
    """The removed branch used to hold a try/except around a bare `pass`."""
    processes._async_reader_callback('never-started')

    processes._loop.remove_reader.assert_not_called()
