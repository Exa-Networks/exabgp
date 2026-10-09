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

    return Engine(ROOT, whole=True)


def read_file(path: str) -> ConfigurationSettings:
    settings = _engine().read(templates_first(lex_file(path)))
    assert isinstance(settings, ConfigurationSettings)
    return settings


def read_text(text: str) -> ConfigurationSettings:
    settings = _engine().read(templates_first(lex_text(text)))
    assert isinstance(settings, ConfigurationSettings)
    return settings


TEMPLATE = 'template'


def templates_first(statements: list[Statement]) -> list[Statement]:
    """The statements with the `template` sections first, each kept whole and in its order.

    A neighbor is made when its section closes, from the templates read by then: one
    inheriting a template written further down the file was given nothing from it.
    """
    templates: list[Statement] = []
    others: list[Statement] = []
    depth = 0
    taking = others
    for statement in statements:
        if not depth:
            starts_template = statement.end == '{' and bool(statement.words) and statement.words[0].word == TEMPLATE
            taking = templates if starts_template else others
        taking.append(statement)
        if statement.end == '{':
            depth += 1
        elif statement.end == '}':
            depth = max(depth - 1, 0)
    return templates + others


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
    from exabgp.configuration.grammar.tree.static import READING_COMMAND

    engine = Engine(block, ReadContext(announce=announce))
    statements = lex_command(text if text.endswith(';') or text.endswith('}') else text + ' ;')
    reading = READING_COMMAND.set(True)
    try:
        engine.read(statements)
    finally:
        READING_COMMAND.reset(reading)
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
ADVISORY = 'advisory'
QUOTED = ('"', "'")


def _advisory_text(words: list[str]) -> list[str]:
    """The words with the advisory, everything after its keyword, as one word without its quotes."""
    if ADVISORY not in words:
        return words
    index = words.index(ADVISORY)
    text = ' '.join(words[index + 1 :])
    if len(text) > 1 and text[0] in QUOTED and text[-1] == text[0]:
        text = text[1:-1]
    return [*words[: index + 1], text]


def read_operational(kind: str, words: list[str]) -> Any:
    """The operational message of an API command, None for a kind which is no message.

    The words are the command as the API splits it, on spaces. The advisory is the text after
    its keyword, a pair of quotes around it removed: `advisory "hello world"` sent `"hello`, the
    first word with its quote, and dropped the rest.
    """
    from exabgp.configuration.grammar.lexer import Token
    from exabgp.configuration.grammar.tree.operational import KINDS, OperationalLine
    from exabgp.configuration.grammar.words import Words

    found = KINDS.get(kind)
    if found is None:
        return None
    klass, parameters, _ = found
    words = _advisory_text(words) if ADVISORY in parameters else words
    tokens = tuple(Token(word, API_SOURCE, 1, index + 1) for index, word in enumerate(words))
    return OperationalLine(kind, klass, parameters).parse(Words(tokens, Token('', API_SOURCE, 1, len(words) + 1)))
