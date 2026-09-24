"""Two CLI handlers which swallowed an error and changed the outcome by doing so.

`check_exa_style` counts `except X: pass`, and most of what it counts in `exabgp/cli/`
is genuinely safe: a socket being abandoned, a completion ranking file nobody asked for,
Ctrl+C during teardown. These two are not.

1.  `PersistentSocketConnection._signal_shutdown` is the only way a background thread can
    end the session: it signals the main thread out of `input()`. Every caller has already
    written "Exiting gracefully" or "not responding" to the terminal before calling it. It
    swallowed `OSError` from `os.kill`, so a lost signal left the user reading that the
    session was over while it carried on, still connected, background threads still
    running. The one handler whose whole job is to end a session could fail to end it and
    say nothing.

    `os.kill(os.getpid(), SIGUSR1)` is not known to fail on any supported platform. The
    test pins the direction the handler fails in, and pins that the promise printed to the
    user is kept.

2.  `PersistentSocketConnection._handle_ping_response` parses a pong in JSON and falls
    back to the text form `pong <uuid> active=true`. A JSON frame which did not parse fell
    through to that fallback, which returns the second *word* of the frame as the daemon
    UUID. A truncated `{"pong": "...", "active": true` therefore announced a daemon restart
    that never happened and recorded a UUID no daemon has, so the next healthy pong looked
    like a second restart. A frame we cannot read is now counted as a failed health check,
    which is what the rest of the method already does with a reply it cannot make sense of.

    `_read_loop` only routes a frame here once it has parsed it, so the fallthrough is not
    reachable from the daemon today. The test holds the method to it directly.

And one report which was missing rather than wrong: `HistoryTracker.invalidate_cache`
deletes the history file on the user's request and swallowed the failure, leaving a file
they believe is gone to be read back by the next session.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from exabgp.cli.history import HistoryTracker
from exabgp.cli.persistent_connection import PersistentSocketConnection


def make_connection() -> PersistentSocketConnection:
    """Build a connection with no socket, no signal handler and no background threads."""
    with (
        patch('socket.socket'),
        patch('threading.Thread'),
        patch.object(PersistentSocketConnection, '_connect'),
        patch.object(PersistentSocketConnection, '_initial_ping'),
        patch.object(PersistentSocketConnection, '_setup_signal_handler'),
    ):
        return PersistentSocketConnection('/fake/path')


class TestSignalShutdown:
    def test_a_signal_which_cannot_be_sent_stops_the_threads_and_is_reported(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        connection = make_connection()
        assert connection.running is True

        with patch.object(os, 'kill', side_effect=OSError(1, 'Operation not permitted')):
            connection._signal_shutdown()

        # The main thread never woke up, so the session has to stop by the other route.
        assert connection.running is False
        captured = capsys.readouterr()
        assert 'could not stop this CLI session' in captured.err
        assert 'Operation not permitted' in captured.err

    def test_a_signal_which_is_sent_says_nothing(self, capsys: pytest.CaptureFixture[str]) -> None:
        connection = make_connection()

        with patch.object(os, 'kill') as kill:
            connection._signal_shutdown()

        assert kill.call_count == 1
        # The signal handler, not this method, decides what happens next.
        assert connection.running is True
        assert capsys.readouterr().err == ''


class TestPingResponseParsing:
    def test_an_unreadable_json_pong_is_not_a_daemon_restart(self, capsys: pytest.CaptureFixture[str]) -> None:
        connection = make_connection()
        connection.daemon_uuid = 'daemon-uuid-one'
        connection.consecutive_failures = 0

        # A pong frame cut short by a partial read.
        connection._handle_ping_response('{"pong": "daemon-uuid-one", "active": true')

        assert connection.daemon_uuid == 'daemon-uuid-one'
        assert connection.consecutive_failures == 1
        assert capsys.readouterr().err == ''

    def test_a_json_pong_is_still_read(self, capsys: pytest.CaptureFixture[str]) -> None:
        connection = make_connection()
        connection.daemon_uuid = 'daemon-uuid-one'
        connection.consecutive_failures = 2

        connection._handle_ping_response('{"pong": "daemon-uuid-one", "active": true}')

        assert connection.daemon_uuid == 'daemon-uuid-one'
        assert connection.consecutive_failures == 0
        assert capsys.readouterr().err == ''

    def test_a_text_pong_is_still_read(self, capsys: pytest.CaptureFixture[str]) -> None:
        connection = make_connection()
        connection.daemon_uuid = 'daemon-uuid-one'
        connection.consecutive_failures = 2

        connection._handle_ping_response('pong daemon-uuid-one active=true')

        assert connection.daemon_uuid == 'daemon-uuid-one'
        assert connection.consecutive_failures == 0
        assert capsys.readouterr().err == ''

    def test_a_json_pong_from_a_restarted_daemon_is_still_announced(self, capsys: pytest.CaptureFixture[str]) -> None:
        connection = make_connection()
        connection.daemon_uuid = 'daemon-uuid-one'
        connection.consecutive_failures = 0

        connection._handle_ping_response('{"pong": "daemon-uuid-two", "active": true}')

        assert connection.daemon_uuid == 'daemon-uuid-two'
        assert 'daemon restarted' in capsys.readouterr().err


class TestHistoryInvalidation:
    def test_a_history_file_which_cannot_be_removed_is_reported(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        history_path = tmp_path / 'cli_history.json'
        history_path.write_text('{"version": 1, "commands": {}}')

        tracker = HistoryTracker(enabled=False)
        tracker._history_path = history_path

        with patch.object(Path, 'unlink', side_effect=OSError(13, 'Permission denied')):
            tracker.invalidate_cache()

        captured = capsys.readouterr()
        assert 'could not remove the CLI history file' in captured.err
        assert str(history_path) in captured.err
        # The file the user asked to be rid of is still there, which is why they are told.
        assert history_path.exists()

    def test_a_history_file_which_is_removed_says_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        history_path = tmp_path / 'cli_history.json'
        history_path.write_text('{"version": 1, "commands": {}}')

        tracker = HistoryTracker(enabled=False)
        tracker._history_path = history_path

        tracker.invalidate_cache()

        assert not history_path.exists()
        assert capsys.readouterr().err == ''
