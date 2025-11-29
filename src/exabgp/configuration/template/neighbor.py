"""template.py

Created by Thomas Mangin on 2015-06-16.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.configuration.core.error import Error
    from exabgp.configuration.core.parser import Parser
    from exabgp.configuration.core.scope import Scope

from exabgp.configuration.core import Section
from exabgp.configuration.neighbor import ParseNeighbor


class ParseTemplateNeighbor(Section):
    syntax = 'neighbor {\n   <neighbor commands>\n}'

    known = ParseNeighbor.known
    action = ParseNeighbor.action
    default = ParseNeighbor.default

    name = 'template-neighbor'

    def __init__(self, parser: 'Parser', scope: 'Scope', error: 'Error') -> None:
        Section.__init__(self, parser, scope, error)

    def clear(self) -> None:
        self._names = []

    def pre(self) -> bool:
        named = self.parser.line[1]
        self.check_name(named)
        self.scope.enter(named)
        self.scope.to_context()
        return True

    def post(self) -> bool:
        routes = self.scope.pop_routes()
        self.scope.extend('routes', routes)
        self.scope.leave()
        return True
