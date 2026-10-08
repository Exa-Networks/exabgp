"""RFC 4761 section 3.2.4: the Control Flags of the Layer2 Info Extended Community.

       0 1 2 3 4 5 6 7
      +-+-+-+-+-+-+-+-+
      |   MBZ     |C|S|

C is 0x02 and S is 0x01.  The six bits above them MUST be zero when we send the community,
and MUST be ignored when we receive it.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.extended.l2info import L2Info
from exabgp.configuration.grammar.types.bgp import extended_community

CONTROL_WORD = 0x02
SEQUENCED = 0x01


@pytest.mark.parametrize('control', [0, SEQUENCED, CONTROL_WORD, CONTROL_WORD | SEQUENCED])
@pytest.mark.rfc('rfc4761#3.2.4-l2info-control-flags-mbz')
def test_the_defined_control_flags_are_sent_as_configured(control: int) -> None:
    community = extended_community(f'l2info:19:{control}:1500:0')

    packed = bytes(community.pack_attribute(Negotiated.UNSET))
    assert packed == bytes([0x80, 0x0A, 19, control, 0x05, 0xDC, 0, 0])


@pytest.mark.parametrize('control', [0x04, 0x80, 0xFC, 0xFF])
@pytest.mark.rfc('rfc4761#3.2.4-l2info-control-flags-mbz', polarity='negative')
def test_a_configured_control_octet_with_an_mbz_bit_is_refused(control: int) -> None:
    with pytest.raises(ValueError, match='MBZ'):
        extended_community(f'l2info:19:{control}:1500:0')


@pytest.mark.parametrize('control', [0x04, 0x80, 0xFC, 0xFF])
@pytest.mark.rfc('rfc4761#3.2.4-l2info-control-flags-mbz', polarity='negative')
def test_received_mbz_bits_are_ignored(control: int) -> None:
    """Accepted, not refused, and reported with only the two bits RFC 4761 defines."""
    community = ExtendedCommunity.unpack_attribute(bytes([0x80, 0x0A, 19, control, 0x05, 0xDC, 0, 0]))

    assert isinstance(community, L2Info)
    assert community.control == control & (CONTROL_WORD | SEQUENCED)
    assert repr(community) == f'l2info:19:{control & 0x03}:1500:0'
