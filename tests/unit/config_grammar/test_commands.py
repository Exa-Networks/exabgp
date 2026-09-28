"""The API route commands of the functional tests are the inputs of the frozen results (frozen.py)."""

from __future__ import annotations

from config_grammar.differential import COMMANDS, grammar_command


def test_the_commands_were_found() -> None:
    assert len(COMMANDS) > 100


def test_a_command_reads_to_routes_or_is_refused() -> None:
    for action, line in COMMANDS:
        found = grammar_command(action, line)
        assert found == 'rejected' or isinstance(found, list), line
