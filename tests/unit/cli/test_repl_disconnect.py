"""The REPL tells a lost daemon from a Ctrl+C.

When the daemon goes away, the background thread of the persistent connection clears the
connection's running flag and interrupts input() with a KeyboardInterrupt. The REPL looked
at its own running flag, which nothing clears but its own quit, so it took the interrupt
for a Ctrl+C and sent `bye` down the dead connection.

Created by Thomas Mangin on 2026-10-27.
Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from unittest.mock import patch

from exabgp.application.cli import InteractiveCLI


def _run(connected: bool) -> list[str]:
    sent: list[str] = []

    def send(command: str) -> str:
        sent.append(command)
        return ''

    cli = InteractiveCLI(send_command=send, connected=lambda: connected)
    with patch('builtins.input', side_effect=KeyboardInterrupt):
        cli.run()
    return sent


def test_a_lost_daemon_ends_the_session_without_a_bye() -> None:
    assert _run(connected=False) == []


def test_a_ctrl_c_says_bye() -> None:
    assert _run(connected=True) == ['bye']
