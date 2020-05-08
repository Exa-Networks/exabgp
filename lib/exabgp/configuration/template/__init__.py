# encoding: utf-8
"""
template.py

Created by Thomas Mangin on 2015-06-16.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.configuration.core import Section
from exabgp.configuration.neighbor import ParseNeighbor

from exabgp.configuration.neighbor.api import ParseAPI


class ParseTemplate(Section):
    syntax = ''

    name = 'template'

    def __init__(self, tokeniser, scope, error, logger):
        Section.__init__(self, tokeniser, scope, error, logger)

    def clear(self):
        self._names = []

    def pre(self):
        return True

    def post(self):
        return True
