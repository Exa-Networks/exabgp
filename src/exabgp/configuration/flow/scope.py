"""scope.py

Created by Stephane Litkowski on 2017-02-24.
"""

from __future__ import annotations

from typing import Callable, Dict, Generator, List

from exabgp.configuration.core import Section
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error

from exabgp.bgp.message.update.attribute.community.extended import InterfaceSet
from exabgp.configuration.flow.parser import interface_set


class ParseFlowScope(Section):
    definition: List[str] = ['interface-set transitive:input:1234:1234']

    joined: str = ';\\n  '.join(definition)
    syntax: str = f'scope {{\n  {joined};\n}}'

    known: Dict[str, Callable[[Tokeniser], Generator[InterfaceSet, None, None]]] = {  # type: ignore[dict-item]
        'interface-set': interface_set,
    }

    # 'community','extended-community'

    action: Dict[str, str] = {
        'interface-set': 'attribute-add',
    }

    name: str = 'flow/scope'

    def __init__(self, tokeniser: Tokeniser, scope: Scope, error: Error) -> None:
        Section.__init__(self, tokeniser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        return True

    def post(self) -> bool:
        return True
