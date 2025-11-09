
"""scope.py

Created by Stephane Litkowski on 2017-02-24.
"""

from __future__ import annotations

from exabgp.configuration.core import Section

from exabgp.configuration.flow.parser import interface_set


class ParseFlowScope(Section):
    definition = ['interface-set transitive:input:1234:1234']

    joined = ';\\n  '.join(definition)
    syntax = f'scope {{\n  {joined};\n}}'

    known = {
        'interface-set': interface_set,
    }

    # 'community','extended-community'

    action = {
        'interface-set': 'attribute-add',
    }

    name = 'flow/scope'

    def __init__(self, tokeniser, scope, error):
        Section.__init__(self, tokeniser, scope, error)

    def clear(self):
        pass

    def pre(self):
        return True

    def post(self):
        return True
