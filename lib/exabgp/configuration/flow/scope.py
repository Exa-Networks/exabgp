# encoding: utf-8
"""
scope.py

Created by Stephane Litkowski on 2017-02-24.
"""

from exabgp.configuration.core import Section

from exabgp.configuration.flow.parser import interface_set


class ParseFlowScope(Section):
    definition = ['interface-set transitive:input:1234:1234']

    syntax = 'scope {\n' '  %s;\n' '}' % ';\n  '.join(definition)

    known = {
        'interface-set': interface_set,
    }

    # 'community','extended-community'

    action = {
        'interface-set': 'attribute-add',
    }

    name = 'flow/scope'

    def __init__(self, tokeniser, scope, error, logger):
        Section.__init__(self, tokeniser, scope, error, logger)

    def clear(self):
        pass

    def pre(self):
        return True

    def post(self):
        return True
