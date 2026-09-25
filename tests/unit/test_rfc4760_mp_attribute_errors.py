#!/usr/bin/env python3
# encoding: utf-8

"""What RFC 4760 asks us to answer when an MP attribute is wrong

Section 3, on the octet between the next-hop and the NLRI: "Reserved: A 1 octet
field that MUST be set to 0, and SHOULD be ignored upon receipt."  We raised
Notify(3, 0) and ended the session over it, which cost the peer every route it
had announced in every family because one byte a future document may give
meaning to was not zero.  A reserved field eventually carrying something is what
reserved fields are for.  It is stepped over now.

Section 7: "if a BGP speaker determines that ... MP_REACH_NLRI or MP_UNREACH_NLRI
attribute is incorrect, it MUST ... send a NOTIFICATION message with the Error
Subcode set to Optional Attribute Error".  Every remaining raise in both decoders
said 3/0 Unspecific, which told the peer only that the session had ended and left
it to guess which attribute.  They are 3/9 now.

And two reads off the end of the buffer, which were not bugs main has: this
branch never checked that the attribute is long enough for the fields it reads,
so a three octet MP_REACH and a next-hop length the attribute cannot hold both
left the decoder by IndexError.  Attributes.parse re-raises IndexError for an
attribute which is not treat-as-withdraw, and MP_REACH is not, so it reached the
reactor as a crash rather than the peer as a NOTIFICATION.
"""

import importlib.util
import pathlib
from struct import pack

import pytest

from exabgp.bgp.message import Open
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open import ASN, HoldTime, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability, Negotiated
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
from exabgp.protocol.family import AFI, SAFI

OPTIONAL_ATTRIBUTE_ERROR = 9

# a SAFI IANA has not assigned, so no session can have negotiated it
UNASSIGNED_SAFI = 200

IPV4_NEXTHOP = b'\x0a\x00\x00\x09'
# 10.0.0.0/24, one IPv4 unicast NLRI
IPV4_NLRI = bytes([24, 10, 0, 0])


@pytest.fixture(scope='module')
def session():
    spec = importlib.util.spec_from_file_location('decode_fixtures', pathlib.Path(__file__).parent / 'test_decode.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    neighbor = module.FakeNeighbor()
    capabilities = Capabilities().new(neighbor, False)
    capabilities[Capability.CODE.MULTIPROTOCOL] = neighbor.families()
    negotiated = Negotiated(neighbor)
    negotiated.sent(Open(Version(4), ASN(neighbor['local-as']), HoldTime(180), RouterID('10.0.0.1'), capabilities))
    negotiated.received(Open(Version(4), ASN(neighbor['peer-as']), HoldTime(180), RouterID('10.0.0.2'), capabilities))
    return negotiated


def mp_reach(afi, safi, nexthop, nlri, reserved=0):
    return pack('!HB', afi, safi) + bytes([len(nexthop)]) + nexthop + bytes([reserved]) + nlri


class TestTheReservedOctetIsIgnored:
    """RFC 4760 3: "SHOULD be ignored upon receipt"."""

    @pytest.mark.parametrize('reserved', [0x01, 0x40, 0x80, 0xFF])
    def test_a_non_zero_reserved_octet_still_decodes(self, reserved, session) -> None:
        data = mp_reach(AFI.ipv4, SAFI.unicast, IPV4_NEXTHOP, IPV4_NLRI, reserved=reserved)

        attribute = MPRNLRI.unpack(data, Direction.IN, session)

        assert len(attribute.nlris) == 1

    def test_and_the_nlri_is_read_from_the_right_offset(self, session) -> None:
        # the byte is stepped over, not consumed as part of the NLRI
        one = MPRNLRI.unpack(mp_reach(AFI.ipv4, SAFI.unicast, IPV4_NEXTHOP, IPV4_NLRI), Direction.IN, session)
        other = MPRNLRI.unpack(
            mp_reach(AFI.ipv4, SAFI.unicast, IPV4_NEXTHOP, IPV4_NLRI, reserved=0xFF), Direction.IN, session
        )

        assert str(one.nlris[0]) == str(other.nlris[0])


class TestEveryRefusalIsOptionalAttributeError:
    """RFC 4760 7, rather than 3/0 Unspecific."""

    def test_a_family_which_was_not_negotiated(self, session) -> None:
        data = mp_reach(AFI.ipv4, UNASSIGNED_SAFI, IPV4_NEXTHOP, IPV4_NLRI)

        with pytest.raises(Notify) as excinfo:
            MPRNLRI.unpack(data, Direction.IN, session)

        assert 'non-negotiated' in str(excinfo.value)
        assert excinfo.value.subcode == OPTIONAL_ATTRIBUTE_ERROR

    def test_a_next_hop_length_the_family_does_not_use(self, session) -> None:
        data = mp_reach(AFI.ipv4, SAFI.unicast, b'\x0a\x00', IPV4_NLRI)

        with pytest.raises(Notify) as excinfo:
            MPRNLRI.unpack(data, Direction.IN, session)

        assert excinfo.value.subcode == OPTIONAL_ATTRIBUTE_ERROR

    def test_a_next_hop_route_distinguisher_which_is_not_zero(self, session) -> None:
        nexthop = b'\x00' * 7 + b'\x01' + IPV4_NEXTHOP
        data = mp_reach(AFI.ipv4, SAFI.mpls_vpn, nexthop, bytes([32, 0, 0, 1, 10, 0, 0]))

        with pytest.raises(Notify) as excinfo:
            MPRNLRI.unpack(data, Direction.IN, session)

        assert excinfo.value.subcode == OPTIONAL_ATTRIBUTE_ERROR

    def test_an_mp_reach_with_no_nlri_field(self, session) -> None:
        data = mp_reach(AFI.ipv4, SAFI.unicast, IPV4_NEXTHOP, b'')

        with pytest.raises(Notify) as excinfo:
            MPRNLRI.unpack(data, Direction.IN, session)

        assert excinfo.value.subcode == OPTIONAL_ATTRIBUTE_ERROR

    def test_an_mp_unreach_family_which_was_not_negotiated(self, session) -> None:
        with pytest.raises(Notify) as excinfo:
            MPURNLRI.unpack(pack('!HB', AFI.ipv4, UNASSIGNED_SAFI), Direction.IN, session)

        assert 'non-negotiated' in str(excinfo.value)
        assert excinfo.value.subcode == OPTIONAL_ATTRIBUTE_ERROR

    def test_an_mp_reach_too_short_for_its_own_header(self, session) -> None:
        with pytest.raises(Notify) as excinfo:
            MPRNLRI.unpack(pack('!HB', AFI.ipv4, SAFI.unicast), Direction.IN, session)

        assert excinfo.value.subcode == OPTIONAL_ATTRIBUTE_ERROR


class TestABufferIsNeverReadPastItsEnd:
    """The peer gets a NOTIFICATION, the reactor does not get an IndexError."""

    @pytest.mark.parametrize('truncated', [3, 4])
    def test_an_attribute_ending_at_the_next_hop_length(self, truncated, session) -> None:
        data = mp_reach(AFI.ipv4, SAFI.unicast, IPV4_NEXTHOP, IPV4_NLRI)[:truncated]

        with pytest.raises(Notify):
            MPRNLRI.unpack(data, Direction.IN, session)

    def test_a_next_hop_length_longer_than_the_attribute(self, session) -> None:
        # a four byte next-hop claimed, one byte of it present, no reserved octet
        data = pack('!HB', AFI.ipv4, SAFI.unicast) + bytes([4]) + b'\x0a'

        with pytest.raises(Notify):
            MPRNLRI.unpack(data, Direction.IN, session)

    def test_a_next_hop_which_fills_the_attribute_leaving_no_reserved_octet(self, session) -> None:
        data = pack('!HB', AFI.ipv4, SAFI.unicast) + bytes([4]) + IPV4_NEXTHOP

        with pytest.raises(Notify):
            MPRNLRI.unpack(data, Direction.IN, session)

    def test_an_mp_unreach_too_short_for_its_family(self, session) -> None:
        with pytest.raises(Notify):
            MPURNLRI.unpack(b'\x00\x01', Direction.IN, session)
