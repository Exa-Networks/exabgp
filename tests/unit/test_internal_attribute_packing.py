"""Internal attribute decisions must never be encoded onto the BGP wire."""

from unittest.mock import Mock

import pytest

from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection
from exabgp.bgp.message.update.attribute.attribute import Discard, TreatAsWithdraw


@pytest.mark.parametrize('attribute', [Discard(), TreatAsWithdraw()])
def test_internal_decisions_are_not_packed(attribute: Attribute) -> None:
    negotiated = Mock(local_as=65000, peer_as=65001)
    attributes = AttributeCollection()
    attributes.add(attribute)

    assert attributes.pack_attribute(negotiated, with_default=False) == b''
