"""RFC 5307 1.2, through RFC 9552 Table 8: the Link Protection Type TLV (1093) of BGP-LS.

The ledger these tests are joined to is qa/rfc/rfc5307.toml.

The first octet is a bit vector, 0x01 Extra Traffic up to 0x20 Enhanced, and 0x40 and
0x80 reserved.  The second octet is reserved.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.update.attribute.bgpls.link.protection import LinkProtectionType
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

from rfc.community_wire import session

LINK_PROTECTION_TYPE = 1093

# RFC 5307 1.2, the bit each capability is carried on.  The JSON key of the first keeps
# the spelling exabgp has always published.
CAPABILITIES = {
    0x01: 'ExtraTrafic',
    0x02: 'Unprotected',
    0x04: 'Shared',
    0x08: 'Dedicated 1:1',
    0x10: 'Dedicated 1+1',
    0x20: 'Enhanced',
}


def protection(capability: int) -> dict[str, int]:
    value = bytes([capability, 0])
    attribute = LinkState.unpack_attribute(pack('!HH', LINK_PROTECTION_TYPE, len(value)) + value, session())
    assert isinstance(attribute, LinkState)
    (decoded,) = attribute.ls_attrs
    assert isinstance(decoded, LinkProtectionType)
    return decoded.flags


@pytest.mark.rfc('rfc5307#1.2-protection-capability-bits')
@pytest.mark.parametrize('bit', sorted(CAPABILITIES))
def test_each_capability_is_read_from_its_own_bit(bit: int) -> None:
    flags = protection(bit)
    assert flags[CAPABILITIES[bit]] == 1, f'{bit:#04x} is {CAPABILITIES[bit]}, RFC 5307 1.2'
    assert [name for name, value in flags.items() if value] == [CAPABILITIES[bit]]


@pytest.mark.rfc('rfc5307#1.2-protection-capability-bits', polarity='negative')
def test_the_reserved_bits_are_no_capability() -> None:
    flags = protection(0x80 | 0x40)
    assert not any(flags[name] for name in CAPABILITIES.values())
