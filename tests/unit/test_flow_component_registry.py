"""Every FlowSpec component class is in the registry the decoder reads.

flow.COMPONENTS names them, where the module used to find them by walking its own dir()
and globals(), which a compiled module does not have (plan/wip-mypyc.md). A component
added to the module and not to the list would be refused on the wire as a type the family
does not define.
"""

from __future__ import annotations

import exabgp.bgp.message.update.nlri.flow as flow
from exabgp.protocol.family import AFI


def defined_components() -> set[type]:
    found = set()
    for name in dir(flow):
        value = getattr(flow, name)
        if isinstance(value, type) and issubclass(value, flow.IComponent) and getattr(value, 'ID', None):
            found.add(value)
    return found


def test_every_component_class_is_registered() -> None:
    assert defined_components() == set(flow.COMPONENTS)


def test_both_families_decode_their_components() -> None:
    for afi in (AFI.ipv4, AFI.ipv6):
        assert flow.decode[afi], f'no {afi} flow component is registered'
        assert set(flow.decode[afi]) == set(flow.factory[afi])
