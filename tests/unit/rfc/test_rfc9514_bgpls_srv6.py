"""RFC 9514 3.1: the Flags of the SRv6 Capabilities TLV (1038) of the BGP-LS Attribute.

The ledger these tests are joined to is qa/rfc/rfc9514.toml.

The flags are the IGP's: RFC 9352 section 2 puts the O-flag on bit 1 of a two octet field,
0x4000, and has every other bit ignored on receipt.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.update.attribute.bgpls.link.srv6capabilities import Srv6Capabilities
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

from rfc.community_wire import session

SRV6_CAPABILITIES = 1038
O_FLAG = 0x4000


def capabilities(flags: int, reserved: int = 0) -> Srv6Capabilities:
    value = pack('!HH', flags, reserved)
    attribute = LinkState.unpack_attribute(pack('!HH', SRV6_CAPABILITIES, len(value)) + value, session())
    assert isinstance(attribute, LinkState)
    (decoded,) = attribute.ls_attrs
    assert isinstance(decoded, Srv6Capabilities)
    return decoded


@pytest.mark.rfc('rfc9514#3.1-capabilities-flags-from-the-igp')
def test_the_o_flag_is_bit_one_of_the_field() -> None:
    assert capabilities(O_FLAG).flags == {'O': 1}


@pytest.mark.rfc('rfc9514#3.1-capabilities-flags-from-the-igp')
def test_the_o_flag_is_written_on_bit_one() -> None:
    packed = bytes(Srv6Capabilities.make_srv6_capabilities({'O': 1})._packed)
    assert packed == pack('!HH', O_FLAG, 0)
    assert bytes(Srv6Capabilities.make_srv6_capabilities({'O': 0})._packed) == bytes(4)


@pytest.mark.rfc('rfc9514#3.1-capabilities-flags-from-the-igp', polarity='negative')
def test_every_other_bit_of_the_field_is_ignored() -> None:
    assert capabilities(0xFFFF ^ O_FLAG).flags == {'O': 0}
    assert capabilities(0x0040).flags == {'O': 0}, 'bit 9 is reserved, not the O-flag'


@pytest.mark.rfc('rfc9514#3.1-capabilities-reserved-zero-and-ignored')
def test_the_reserved_field_is_originated_as_zero() -> None:
    packed = bytes(Srv6Capabilities.make_srv6_capabilities({'O': 1})._packed)
    assert packed[2:] == b'\x00\x00'


@pytest.mark.rfc('rfc9514#3.1-capabilities-reserved-zero-and-ignored', polarity='negative')
def test_a_reserved_field_which_is_not_zero_is_ignored() -> None:
    assert capabilities(O_FLAG, reserved=0xFFFF).flags == {'O': 1}
