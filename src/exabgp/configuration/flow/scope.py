"""scope.py

Created by Stephane Litkowski on 2017-02-24.
"""

from __future__ import annotations

from typing import Any

from exabgp.configuration.core import Section
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error

from exabgp.configuration.flow.parser import interface_set


class ParseFlowScope(Section):
    definition: list[str] = ['interface-set transitive:input:1234:1234']

    joined: str = ';\\n  '.join(definition)
    syntax: str = f'scope {{\n  {joined};\n}}'

    known: dict[str | tuple[Any, ...], object] = {
        'interface-set': interface_set,
    }

    # 'community','extended-community'

    action: dict[str | tuple[Any, ...], str] = {
        'interface-set': 'attribute-add',
    }

    name: str = 'flow/scope'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        Section.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        return True

    def post(self) -> bool:
        return True
