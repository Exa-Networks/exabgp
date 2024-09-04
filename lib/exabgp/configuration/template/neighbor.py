# encoding: utf-8
"""
template.py

Created by Thomas Mangin on 2015-06-16.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.configuration.core import Section
from exabgp.configuration.neighbor import ParseNeighbor


class ParseTemplateNeighbor(Section):
    syntax = 'neighbor {\n' '   <neighbor commands>\n' '}'

    known = ParseNeighbor.known
    action = ParseNeighbor.action
    default = ParseNeighbor.default

    name = 'template-neighbor'

    def __init__(self, tokeniser, scope, error, logger):
        Section.__init__(self, tokeniser, scope, error, logger)

    def clear(self):
        self._names = []

    def pre(self):
        named = self.tokeniser.line[1]
        self.check_name(named)
        self.scope.enter(named)
        self.scope.to_context()
        return True

    def post(self):
        routes = self.scope.pop_routes()
        self.scope.extend('routes', routes)
        self.scope.leave()
        return True
