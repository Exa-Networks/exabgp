"""scope.py

Created by Stephane Litkowski on 2017-02-24.
"""

from __future__ import annotations

from typing import Any

from exabgp.configuration.core import Section
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget, Container, Leaf, ValueType

from exabgp.configuration.flow.parser import interface_set


class ParseFlowScope(Section):
    # Schema definition for FlowSpec scope
    schema = Container(
        description='FlowSpec scope configuration',
        children={
            'interface-set': Leaf(
                type=ValueType.STRING,
                description='Interface set (transitive:input:local_id:interface_id)',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
        },
    )
    definition: list[str] = ['interface-set transitive:input:1234:1234']

    joined: str = ';\\n  '.join(definition)
    syntax: str = f'scope {{\n  {joined};\n}}'

    known: dict[str | tuple[Any, ...], object] = {
        'interface-set': interface_set,
    }

    # action dict removed - derived from schema

    name: str = 'flow/scope'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        Section.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        return True

    def post(self) -> bool:
        return True
