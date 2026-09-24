"""The unit suite must not write in the home directory of whoever runs it.

Building an InteractiveCLI is enough to lose a developer's shell history: the constructor
picks ~/.exabgp_history, builds a HistoryTracker pointing at ~/.local/state/exabgp, and
registers an atexit handler which writes readline's (empty) in process history over the
file.  The isolate_home fixture in tests/unit/conftest.py is what stops that; this is the
test which goes red when it stops working.

Created by Thomas Mangin on 2026-09-24.
Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from pathlib import Path

from exabgp.application.cli import InteractiveCLI

READLINE_HISTORY = Path('.exabgp_history')
TRACKER_HISTORY = Path('.local') / 'state' / 'exabgp' / 'cli_history.json'


def _fingerprint(path: Path) -> tuple[int, bytes] | None:
    """Enough of a file to notice any rewrite of it, or None when it does not exist."""
    if not path.exists():
        return None
    return (path.stat().st_mtime_ns, path.read_bytes())


def test_building_a_cli_leaves_the_real_home_untouched(real_home: Path, isolate_home: Path) -> None:
    watched = [real_home / READLINE_HISTORY, real_home / TRACKER_HISTORY]
    before = [_fingerprint(path) for path in watched]

    cli = InteractiveCLI(send_command=lambda command: '')
    cli.history_tracker.record_command('show neighbor', success=True)
    # The atexit handler registered by the constructor calls exactly this, so running it
    # here is running what the end of the pytest process would have run.
    cli._save_history()

    history_file = Path(cli.history_file)
    assert not history_file.is_relative_to(real_home), f'the CLI aimed its history at {history_file}'
    assert history_file.is_relative_to(isolate_home)
    assert history_file.exists(), 'the history was written, it was written somewhere safe'

    if cli.history_tracker.enabled:
        tracker_path = cli.history_tracker._history_path
        assert tracker_path is not None
        assert tracker_path.is_relative_to(isolate_home)

    assert [_fingerprint(path) for path in watched] == before, 'a file in the real home was rewritten'


def test_the_isolated_home_is_where_the_tilde_now_points(real_home: Path, isolate_home: Path) -> None:
    # Both of the ways the CLI code resolves a home directory have to follow the fixture,
    # or only one of the two history files is protected.
    import os

    assert Path(os.path.expanduser('~')) == isolate_home
    assert Path.home() == isolate_home
    assert isolate_home != real_home
