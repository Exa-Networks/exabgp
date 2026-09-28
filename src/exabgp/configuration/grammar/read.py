"""read.py

Read a configuration with the grammar.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.configuration.grammar.context import ReadContext
from exabgp.configuration.grammar.engine import Engine
from exabgp.configuration.grammar.lexer import Statement, lex_command, lex_file, lex_text
from exabgp.configuration.settings import ConfigurationSettings


def _engine() -> Engine:
    from exabgp.configuration.grammar.tree.root import ROOT

    return Engine(ROOT)


def read_file(path: str) -> ConfigurationSettings:
    settings = _engine().read(lex_file(path))
    assert isinstance(settings, ConfigurationSettings)
    return settings


def read_text(text: str) -> ConfigurationSettings:
    settings = _engine().read(lex_text(text))
    assert isinstance(settings, ConfigurationSettings)
    return settings


def _command_sections() -> dict[str, Any]:
    from exabgp.configuration.grammar.tree.announce import IPV4, IPV6, L2VPN, STATIC
    from exabgp.configuration.grammar.tree.flow import FLOW

    return {'static': STATIC, 'ipv4': IPV4, 'ipv6': IPV6, 'flow': FLOW, 'l2vpn': L2VPN}


def read_command(section: str, text: str, announce: bool) -> tuple[list[Any], int]:
    """The routes of one API command, read as a statement of `section` (Configuration.partial),
    and how many of the sections it opens it leaves open.
    """
    block = _command_sections().get(section)
    assert block is not None, f'partial() reads no section {section}'
    engine = Engine(block, ReadContext(announce=announce))
    statements = lex_command(text if text.endswith(';') or text.endswith('}') else text + ' ;')
    engine.read(statements)
    return list(engine.context.routes), left_open(statements)


def left_open(statements: list[Statement]) -> int:
    """The sections still open when the statements end, as the engine reads them."""
    depth = 0
    for statement in statements:
        if statement.end == '{':
            depth += 1
        elif statement.end == '}':
            if not depth:
                break  # legacy: a `}` with nothing open ends the text, the rest is not read
            depth -= 1
    return depth


API_SOURCE = 'api'  # where the words of an API command come from, for its errors


def read_operational(kind: str, words: list[str]) -> Any:
    """The operational message of an API command, None for a kind which is no message.

    The words are the command as the API splits it, on spaces: a quote stays in the word,
    as it did when the legacy parser read them.
    """
    from exabgp.configuration.grammar.lexer import Token
    from exabgp.configuration.grammar.tree.operational import KINDS, OperationalLine
    from exabgp.configuration.grammar.words import Words

    found = KINDS.get(kind)
    if found is None:
        return None
    klass, parameters, _ = found
    tokens = tuple(Token(word, API_SOURCE, 1, index + 1) for index, word in enumerate(words))
    return OperationalLine(kind, klass, parameters).parse(Words(tokens, Token('', API_SOURCE, 1, len(words) + 1)))
