#!/usr/bin/env python3
# encoding: utf-8

"""The next-hop of an MP_REACH must be read the way its family encodes it

Family.size drives both ends: which next-hop widths are accepted, and how many
bytes of route distinguisher sit in front of the address. A family missing from
that table is refused outright, however well its NLRI decodes.
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
from exabgp.protocol.family import AFI, SAFI

NODE = (
    b'\x03'
    + b'\x00' * 8
    + b'\x01\x00\x00\x18'
    + b'\x02\x00\x00\x04\x00\x00\xff\xfd'
    + b'\x02\x01\x00\x04\x00\x00\x00\x00'
    + b'\x02\x03\x00\x04\x0a\x71\x3f\xf0'
)


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


def bgpls_vpn(nexthop):
    body = b'\x00' * 8 + NODE
    nlri = pack('!HH', 1, len(body)) + body
    return pack('!HB', AFI.bgpls, SAFI.bgp_ls_vpn) + bytes([len(nexthop)]) + nexthop + b'\x00' + nlri


class TestBgpLsVpnNextHop:
    """RFC 7752 3.2.1: a VPN-IPv4 or VPN-IPv6 address with a zero RD"""

    @pytest.mark.parametrize(
        'nexthop,what',
        [
            (b'\x00' * 8 + b'\x0a\x00\x00\x09', 'VPN-IPv4, 12 bytes'),
            (b'\x00' * 8 + b'\x20\x01\x0d\xb8' + b'\x00' * 12, 'VPN-IPv6, 24 bytes'),
        ],
    )
    def test_the_documented_widths_decode(self, nexthop, what, session) -> None:
        # the family used to be absent from Family.size, so both were refused
        # with 'unsupported bgp-ls bgp-ls-vpn'
        attribute = MPRNLRI.unpack(bgpls_vpn(nexthop), Direction.IN, session)
        assert attribute.nlris

    def test_a_bare_address_is_refused(self, session) -> None:
        with pytest.raises(Notify):
            MPRNLRI.unpack(bgpls_vpn(b'\x0a\x00\x00\x09'), Direction.IN, session)


class TestTheRouteDistinguisherMustBeZero:
    """The check read a fixed slice and inspected only half the RD

    data[offset:8] with an offset of 4 covers the first FOUR bytes of an eight
    byte route distinguisher, and nothing at all had the offset ever passed 8.
    Every VPN family was half checked.
    """

    @pytest.mark.parametrize('position', range(0, 8))
    def test_a_non_zero_byte_anywhere_in_the_rd_is_refused(self, position, session) -> None:
        rd = bytearray(8)
        rd[position] = 1
        with pytest.raises(Notify):
            MPRNLRI.unpack(bgpls_vpn(bytes(rd) + b'\x0a\x00\x00\x09'), Direction.IN, session)

    def test_a_zero_rd_is_accepted(self, session) -> None:
        assert MPRNLRI.unpack(bgpls_vpn(b'\x00' * 8 + b'\x0a\x00\x00\x09'), Direction.IN, session).nlris

    @pytest.mark.parametrize('position', range(0, 8))
    def test_the_same_holds_for_mpls_vpn(self, position, session) -> None:
        rd = bytearray(8)
        rd[position] = 1
        nlri = bytes([88]) + b'\x00\x01\x01' + b'\x00' * 8 + bytes([10, 0, 0])
        data = pack('!HB', AFI.ipv4, SAFI.mpls_vpn) + bytes([12]) + bytes(rd) + b'\x0a\x00\x00\x09' + b'\x00' + nlri
        with pytest.raises(Notify):
            MPRNLRI.unpack(data, Direction.IN, session)
