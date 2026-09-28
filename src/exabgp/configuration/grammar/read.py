"""read.py

Read a configuration with the grammar.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.configuration.grammar.engine import Engine
from exabgp.configuration.grammar.lexer import lex_command, lex_file, lex_text
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


def read_command(section: str, text: str, announce: bool) -> list[Any]:
    """The routes of one API command, read as a statement of `section` (Configuration.partial)."""
    from exabgp.configuration.grammar.tree.static import ANNOUNCE, ROUTES

    block = _command_sections().get(section)
    assert block is not None, f'partial() reads no section {section}'
    engine = Engine(block)
    engine.context[ANNOUNCE] = announce
    engine.read(lex_command(text if text.endswith(';') or text.endswith('}') else text + ' ;'))
    routes: list[Any] = engine.context.get(ROUTES, [])
    return routes
