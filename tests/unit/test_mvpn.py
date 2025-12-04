"""Comprehensive tests for MVPN (Multicast VPN) NLRI types.

Tests cover all MVPN route types defined in RFC 6514:
- Route Type 5: Source Active A-D Route (SourceAD)
- Route Type 6: C-Multicast Shared Tree Join (SharedJoin)
- Route Type 7: C-Multicast Source Tree Join (SourceJoin)
"""

from unittest.mock import Mock

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.negotiated import Negotiated

import pytest
from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.mvpn.sourcead import SourceAD
from exabgp.bgp.message.update.nlri.mvpn.sharedjoin import SharedJoin
from exabgp.bgp.message.update.nlri.mvpn.sourcejoin import SourceJoin
from exabgp.bgp.message.update.nlri.mvpn.nlri import MVPN
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.nlri import Action


# ============================================================================
# MVPN Route Type 5: Source Active A-D Route (SourceAD)
# ============================================================================


def create_negotiated() -> Negotiated:
    """Create a Negotiated object with a mock neighbor for testing."""
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    return Negotiated(neighbor, Direction.OUT)


class TestSourceAD:
    """Tests for MVPN Route Type 5: Source Active A-D Route"""

    def test_sourcead_creation(self) -> None:
        """Test basic creation of SourceAD route"""
        rd = RouteDistinguisher.make_from_elements('1.2.3.4', 100)
        source = IP.create('192.168.1.1')
        group = IP.create('239.1.1.1')

        route = SourceAD.make_sourcead(rd, AFI.ipv4, source, group)

        assert route.CODE == 5
        assert route.NAME == 'Source Active A-D Route'
        assert route.SHORT_NAME == 'SourceAD'
        assert route.rd == rd
        assert route.source == source
        assert route.group == group

    def test_sourcead_pack_unpack_ipv4(self) -> None:
        """Test pack/unpack roundtrip for SourceAD with IPv4"""
        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 500)
        source = IP.create('192.168.1.1')
        group = IP.create('239.1.1.1')

        route = SourceAD.make_sourcead(rd, AFI.ipv4, source, group)
        packed = route.pack_nlri(create_negotiated())

        unpacked, leftover = MVPN.unpack_nlri(
            AFI.ipv4, SAFI.mcast_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 0
        assert isinstance(unpacked, SourceAD)
        assert unpacked.rd._str() == rd._str()
        assert str(unpacked.source) == str(source)
        assert str(unpacked.group) == str(group)

    def test_sourcead_pack_unpack_ipv6(self) -> None:
        """Test pack/unpack roundtrip for SourceAD with IPv6"""
        rd = RouteDistinguisher.make_from_elements('10.0.0.2', 100)
        source = IP.create('2001:db8:1::1')
        group = IP.create('ff0e::1')

        route = SourceAD.make_sourcead(rd, AFI.ipv6, source, group)
        packed = route.pack_nlri(create_negotiated())

        unpacked, leftover = MVPN.unpack_nlri(
            AFI.ipv6, SAFI.mcast_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 0
        assert isinstance(unpacked, SourceAD)
        assert unpacked.rd._str() == rd._str()
        assert str(unpacked.source) == str(source)
        assert str(unpacked.group) == str(group)

    def test_sourcead_equality(self) -> None:
        """Test equality comparison for SourceAD routes"""
        rd = RouteDistinguisher.make_from_elements('1.1.1.1', 10)
        source = IP.create('192.168.1.1')
        group = IP.create('239.1.1.1')

        route1 = SourceAD.make_sourcead(rd, AFI.ipv4, source, group)
        route2 = SourceAD.make_sourcead(rd, AFI.ipv4, source, group)

        assert route1 == route2
        assert not route1 != route2

    def test_sourcead_inequality(self) -> None:
        """Test inequality for different SourceAD routes"""
        rd = RouteDistinguisher.make_from_elements('1.1.1.1', 10)
        source1 = IP.create('192.168.1.1')
        source2 = IP.create('192.168.1.2')
        group = IP.create('239.1.1.1')

        route1 = SourceAD.make_sourcead(rd, AFI.ipv4, source1, group)
        route2 = SourceAD.make_sourcead(rd, AFI.ipv4, source2, group)

        assert route1 != route2
        assert not route1 == route2

    def test_sourcead_hash_consistency(self) -> None:
        """Test hash consistency for SourceAD routes"""
        rd = RouteDistinguisher.make_from_elements('2.2.2.2', 20)
        source = IP.create('192.168.2.1')
        group = IP.create('239.2.2.2')

        route1 = SourceAD.make_sourcead(rd, AFI.ipv4, source, group)
        route2 = SourceAD.make_sourcead(rd, AFI.ipv4, source, group)

        assert hash(route1) == hash(route2)

    def test_sourcead_string_representation(self) -> None:
        """Test string representation of SourceAD"""
        rd = RouteDistinguisher.make_from_elements('3.3.3.3', 30)
        source = IP.create('172.16.1.1')
        group = IP.create('239.3.3.3')

        route = SourceAD.make_sourcead(rd, AFI.ipv4, source, group)
        route_str = str(route)

        assert 'sourcead' in route_str.lower()
        assert '172.16.1.1' in route_str
        assert '239.3.3.3' in route_str

    def test_sourcead_json(self) -> None:
        """Test JSON serialization of SourceAD"""
        rd = RouteDistinguisher.make_from_elements('4.4.4.4', 40)
        source = IP.create('10.20.30.40')
        group = IP.create('239.4.4.4')

        route = SourceAD.make_sourcead(rd, AFI.ipv4, source, group)
        json_str = route.json()

        assert '"code": 5' in json_str
        assert 'Source Active A-D Route' in json_str
        assert '"source": "10.20.30.40"' in json_str
        assert '"group": "239.4.4.4"' in json_str

    def test_sourcead_invalid_length(self) -> None:
        """Test SourceAD with invalid length raises error"""
        # Create invalid packed data with wrong length (15 bytes instead of 18 or 42)
        rd = RouteDistinguisher.make_from_elements('1.1.1.1', 10)
        invalid_data = rd.pack_rd() + b'\x20\x01\x02\x03\x04\x20\x05'  # 15 bytes total

        # Pack into MVPN format: CODE=5, length, data
        packed = bytes([5, len(invalid_data)]) + invalid_data

        with pytest.raises(Notify):
            MVPN.unpack_nlri(AFI.ipv4, SAFI.mcast_vpn, packed, Action.UNSET, None, negotiated=create_negotiated())

    def test_sourcead_invalid_source_ip_length(self) -> None:
        """Test SourceAD with invalid source IP length raises error"""
        rd = RouteDistinguisher.make_from_elements('1.1.1.1', 10)
        # Create data with invalid source IP length (24 bits instead of 32 or 128)
        invalid_data = rd.pack_rd() + bytes([24]) + b'\x01\x02\x03' + bytes([32]) + b'\xef\x01\x01\x01'

        packed = bytes([5, len(invalid_data)]) + invalid_data

        with pytest.raises(Notify):
            MVPN.unpack_nlri(AFI.ipv4, SAFI.mcast_vpn, packed, Action.UNSET, None, negotiated=create_negotiated())

    def test_sourcead_multicast_addresses(self) -> None:
        """Test SourceAD with various multicast group addresses"""
        rd = RouteDistinguisher.make_from_elements('5.5.5.5', 50)
        source = IP.create('10.1.1.1')

        # Test various multicast groups
        multicast_groups = [
            '224.0.0.1',  # All hosts
            '239.255.255.255',  # Site-local
            '232.1.1.1',  # SSM range
        ]

        for group_str in multicast_groups:
            group = IP.create(group_str)
            route = SourceAD.make_sourcead(rd, AFI.ipv4, source, group)
            packed = route.pack_nlri(create_negotiated())
            unpacked, _ = MVPN.unpack_nlri(
                AFI.ipv4, SAFI.mcast_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
            )

            assert str(unpacked.group) == group_str


# ============================================================================
# MVPN Route Type 6: C-Multicast Shared Tree Join (SharedJoin)
# ============================================================================


class TestSharedJoin:
    """Tests for MVPN Route Type 6: C-Multicast Shared Tree Join"""

    def test_sharedjoin_creation(self) -> None:
        """Test basic creation of SharedJoin route"""
        rd = RouteDistinguisher.make_from_elements('1.2.3.4', 100)
        source = IP.create('192.168.1.1')
        group = IP.create('239.1.1.1')
        source_as = 65001

        route = SharedJoin.make_sharedjoin(rd, AFI.ipv4, source, group, source_as)

        assert route.CODE == 6
        assert route.NAME == 'C-Multicast Shared Tree Join route'
        assert route.SHORT_NAME == 'Shared-Join'
        assert route.rd == rd
        assert route.source == source
        assert route.group == group
        assert route.source_as == source_as

    def test_sharedjoin_pack_unpack_ipv4(self) -> None:
        """Test pack/unpack roundtrip for SharedJoin with IPv4"""
        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 500)
        source = IP.create('192.168.1.1')
        group = IP.create('239.1.1.1')
        source_as = 64512

        route = SharedJoin.make_sharedjoin(rd, AFI.ipv4, source, group, source_as)
        packed = route.pack_nlri(create_negotiated())

        unpacked, leftover = MVPN.unpack_nlri(
            AFI.ipv4, SAFI.mcast_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 0
        assert isinstance(unpacked, SharedJoin)
        assert unpacked.rd._str() == rd._str()
        assert str(unpacked.source) == str(source)
        assert str(unpacked.group) == str(group)
        assert unpacked.source_as == source_as

    def test_sharedjoin_pack_unpack_ipv6(self) -> None:
        """Test pack/unpack roundtrip for SharedJoin with IPv6"""
        rd = RouteDistinguisher.make_from_elements('10.0.0.2', 100)
        source = IP.create('2001:db8:1::1')
        group = IP.create('ff0e::1')
        source_as = 65000

        route = SharedJoin.make_sharedjoin(rd, AFI.ipv6, source, group, source_as)
        packed = route.pack_nlri(create_negotiated())

        unpacked, leftover = MVPN.unpack_nlri(
            AFI.ipv6, SAFI.mcast_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 0
        assert isinstance(unpacked, SharedJoin)
        assert unpacked.rd._str() == rd._str()
        assert str(unpacked.source) == str(source)
        assert str(unpacked.group) == str(group)
        assert unpacked.source_as == source_as

    def test_sharedjoin_equality(self) -> None:
        """Test equality comparison for SharedJoin routes"""
        rd = RouteDistinguisher.make_from_elements('1.1.1.1', 10)
        source = IP.create('192.168.1.1')
        group = IP.create('239.1.1.1')
        source_as = 65001

        route1 = SharedJoin.make_sharedjoin(rd, AFI.ipv4, source, group, source_as)
        route2 = SharedJoin.make_sharedjoin(rd, AFI.ipv4, source, group, source_as)

        assert route1 == route2
        assert not route1 != route2

    def test_sharedjoin_inequality(self) -> None:
        """Test inequality for different SharedJoin routes"""
        rd = RouteDistinguisher.make_from_elements('1.1.1.1', 10)
        source = IP.create('192.168.1.1')
        group = IP.create('239.1.1.1')

        route1 = SharedJoin.make_sharedjoin(rd, AFI.ipv4, source, group, 65001)
        route2 = SharedJoin.make_sharedjoin(rd, AFI.ipv4, source, group, 65002)

        # Different AS should not affect equality (only rd, source, group matter)
        assert route1 == route2  # AS not included in equality check

    def test_sharedjoin_hash_consistency(self) -> None:
        """Test hash consistency for SharedJoin routes"""
        rd = RouteDistinguisher.make_from_elements('2.2.2.2', 20)
        source = IP.create('192.168.2.1')
        group = IP.create('239.2.2.2')
        source_as = 65002

        route1 = SharedJoin.make_sharedjoin(rd, AFI.ipv4, source, group, source_as)
        route2 = SharedJoin.make_sharedjoin(rd, AFI.ipv4, source, group, source_as)

        assert hash(route1) == hash(route2)

    def test_sharedjoin_string_representation(self) -> None:
        """Test string representation of SharedJoin"""
        rd = RouteDistinguisher.make_from_elements('3.3.3.3', 30)
        source = IP.create('172.16.1.1')
        group = IP.create('239.3.3.3')
        source_as = 65003

        route = SharedJoin.make_sharedjoin(rd, AFI.ipv4, source, group, source_as)
        route_str = str(route)

        assert 'shared-join' in route_str.lower()
        assert '65003' in route_str
        assert '172.16.1.1' in route_str
        assert '239.3.3.3' in route_str

    def test_sharedjoin_json(self) -> None:
        """Test JSON serialization of SharedJoin"""
        rd = RouteDistinguisher.make_from_elements('4.4.4.4', 40)
        source = IP.create('10.20.30.40')
        group = IP.create('239.4.4.4')
        source_as = 65004

        route = SharedJoin.make_sharedjoin(rd, AFI.ipv4, source, group, source_as)
        json_str = route.json()

        assert '"code": 6' in json_str
        assert 'C-Multicast Shared Tree Join route' in json_str
        assert '"source-as": "65004"' in json_str
        assert '"source": "10.20.30.40"' in json_str
        assert '"group": "239.4.4.4"' in json_str

    def test_sharedjoin_invalid_length(self) -> None:
        """Test SharedJoin with invalid length raises error"""
        # Create invalid packed data with wrong length
        rd = RouteDistinguisher.make_from_elements('1.1.1.1', 10)
        invalid_data = rd.pack_rd() + b'\x00\x00\x00\x01\x20\x01\x02'  # Too short

        packed = bytes([6, len(invalid_data)]) + invalid_data

        with pytest.raises(Notify):
            MVPN.unpack_nlri(AFI.ipv4, SAFI.mcast_vpn, packed, Action.UNSET, None, negotiated=create_negotiated())

    def test_sharedjoin_various_as_numbers(self) -> None:
        """Test SharedJoin with various AS numbers"""
        rd = RouteDistinguisher.make_from_elements('5.5.5.5', 50)
        source = IP.create('10.1.1.1')
        group = IP.create('239.1.1.1')

        # Test various AS numbers
        as_numbers = [1, 64512, 65535, 4200000000]  # 2-byte and 4-byte AS

        for asn in as_numbers:
            route = SharedJoin.make_sharedjoin(rd, AFI.ipv4, source, group, asn)
            packed = route.pack_nlri(create_negotiated())
            unpacked, _ = MVPN.unpack_nlri(
                AFI.ipv4, SAFI.mcast_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
            )

            assert unpacked.source_as == asn


# ============================================================================
# MVPN Route Type 7: C-Multicast Source Tree Join (SourceJoin)
# ============================================================================


class TestSourceJoin:
    """Tests for MVPN Route Type 7: C-Multicast Source Tree Join"""

    def test_sourcejoin_creation(self) -> None:
        """Test basic creation of SourceJoin route"""
        rd = RouteDistinguisher.make_from_elements('1.2.3.4', 100)
        source = IP.create('192.168.1.1')
        group = IP.create('239.1.1.1')
        source_as = 65001

        route = SourceJoin.make_sourcejoin(rd, AFI.ipv4, source, group, source_as)

        assert route.CODE == 7
        assert route.NAME == 'C-Multicast Source Tree Join route'
        assert route.SHORT_NAME == 'Source-Join'
        assert route.rd == rd
        assert route.source == source
        assert route.group == group
        assert route.source_as == source_as

    def test_sourcejoin_pack_unpack_ipv4(self) -> None:
        """Test pack/unpack roundtrip for SourceJoin with IPv4"""
        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 500)
        source = IP.create('192.168.1.1')
        group = IP.create('239.1.1.1')
        source_as = 64512

        route = SourceJoin.make_sourcejoin(rd, AFI.ipv4, source, group, source_as)
        packed = route.pack_nlri(create_negotiated())

        unpacked, leftover = MVPN.unpack_nlri(
            AFI.ipv4, SAFI.mcast_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 0
        assert isinstance(unpacked, SourceJoin)
        assert unpacked.rd._str() == rd._str()
        assert str(unpacked.source) == str(source)
        assert str(unpacked.group) == str(group)
        assert unpacked.source_as == source_as

    def test_sourcejoin_pack_unpack_ipv6(self) -> None:
        """Test pack/unpack roundtrip for SourceJoin with IPv6"""
        rd = RouteDistinguisher.make_from_elements('10.0.0.2', 100)
        source = IP.create('2001:db8:1::1')
        group = IP.create('ff0e::1')
        source_as = 65000

        route = SourceJoin.make_sourcejoin(rd, AFI.ipv6, source, group, source_as)
        packed = route.pack_nlri(create_negotiated())

        unpacked, leftover = MVPN.unpack_nlri(
            AFI.ipv6, SAFI.mcast_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert len(leftover) == 0
        assert isinstance(unpacked, SourceJoin)
        assert unpacked.rd._str() == rd._str()
        assert str(unpacked.source) == str(source)
        assert str(unpacked.group) == str(group)
        assert unpacked.source_as == source_as

    def test_sourcejoin_equality(self) -> None:
        """Test equality comparison for SourceJoin routes"""
        rd = RouteDistinguisher.make_from_elements('1.1.1.1', 10)
        source = IP.create('192.168.1.1')
        group = IP.create('239.1.1.1')
        source_as = 65001

        route1 = SourceJoin.make_sourcejoin(rd, AFI.ipv4, source, group, source_as)
        route2 = SourceJoin.make_sourcejoin(rd, AFI.ipv4, source, group, source_as)

        assert route1 == route2
        assert not route1 != route2

    def test_sourcejoin_inequality(self) -> None:
        """Test inequality for different SourceJoin routes"""
        rd = RouteDistinguisher.make_from_elements('1.1.1.1', 10)
        source1 = IP.create('192.168.1.1')
        source2 = IP.create('192.168.1.2')
        group = IP.create('239.1.1.1')
        source_as = 65001

        route1 = SourceJoin.make_sourcejoin(rd, AFI.ipv4, source1, group, source_as)
        route2 = SourceJoin.make_sourcejoin(rd, AFI.ipv4, source2, group, source_as)

        assert route1 != route2
        assert not route1 == route2

    def test_sourcejoin_hash_consistency(self) -> None:
        """Test hash consistency for SourceJoin routes"""
        rd = RouteDistinguisher.make_from_elements('2.2.2.2', 20)
        source = IP.create('192.168.2.1')
        group = IP.create('239.2.2.2')
        source_as = 65002

        route1 = SourceJoin.make_sourcejoin(rd, AFI.ipv4, source, group, source_as)
        route2 = SourceJoin.make_sourcejoin(rd, AFI.ipv4, source, group, source_as)

        assert hash(route1) == hash(route2)

    def test_sourcejoin_string_representation(self) -> None:
        """Test string representation of SourceJoin"""
        rd = RouteDistinguisher.make_from_elements('3.3.3.3', 30)
        source = IP.create('172.16.1.1')
        group = IP.create('239.3.3.3')
        source_as = 65003

        route = SourceJoin.make_sourcejoin(rd, AFI.ipv4, source, group, source_as)
        route_str = str(route)

        assert 'source-join' in route_str.lower()
        assert '65003' in route_str
        assert '172.16.1.1' in route_str
        assert '239.3.3.3' in route_str

    def test_sourcejoin_json(self) -> None:
        """Test JSON serialization of SourceJoin"""
        rd = RouteDistinguisher.make_from_elements('4.4.4.4', 40)
        source = IP.create('10.20.30.40')
        group = IP.create('239.4.4.4')
        source_as = 65004

        route = SourceJoin.make_sourcejoin(rd, AFI.ipv4, source, group, source_as)
        json_str = route.json()

        assert '"code": 7' in json_str
        assert 'C-Multicast Source Tree Join route' in json_str
        assert '"source-as": "65004"' in json_str
        assert '"source": "10.20.30.40"' in json_str
        assert '"group": "239.4.4.4"' in json_str

    def test_sourcejoin_invalid_length(self) -> None:
        """Test SourceJoin with invalid length raises error"""
        # Create invalid packed data with wrong length
        rd = RouteDistinguisher.make_from_elements('1.1.1.1', 10)
        invalid_data = rd.pack_rd() + b'\x00\x00\x00\x01\x20\x01\x02'  # Too short

        packed = bytes([7, len(invalid_data)]) + invalid_data

        with pytest.raises(Notify):
            MVPN.unpack_nlri(AFI.ipv4, SAFI.mcast_vpn, packed, Action.UNSET, None, negotiated=create_negotiated())

    def test_sourcejoin_ssm_multicast(self) -> None:
        """Test SourceJoin with SSM (Source-Specific Multicast) addresses"""
        rd = RouteDistinguisher.make_from_elements('5.5.5.5', 50)
        source = IP.create('10.1.1.1')
        # SSM range: 232.0.0.0/8
        group = IP.create('232.1.1.1')
        source_as = 65005

        route = SourceJoin.make_sourcejoin(rd, AFI.ipv4, source, group, source_as)
        packed = route.pack_nlri(create_negotiated())
        unpacked, _ = MVPN.unpack_nlri(
            AFI.ipv4, SAFI.mcast_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert str(unpacked.group) == '232.1.1.1'


# ============================================================================
# Generic MVPN Tests
# ============================================================================


class TestMVPNGeneric:
    """Tests for generic MVPN functionality"""

    def test_mvpn_registration(self) -> None:
        """Test that all MVPN route types are registered"""
        assert 5 in MVPN.registered_mvpn  # SourceAD
        assert 6 in MVPN.registered_mvpn  # SharedJoin
        assert 7 in MVPN.registered_mvpn  # SourceJoin

    def test_mvpn_registered_classes(self) -> None:
        """Test that registered classes are correct"""
        assert MVPN.registered_mvpn[5] == SourceAD
        assert MVPN.registered_mvpn[6] == SharedJoin
        assert MVPN.registered_mvpn[7] == SourceJoin

    def test_mvpn_unpack_unknown_route_type(self) -> None:
        """Test unpacking unknown MVPN route type"""
        # Create a route with unknown code (99)
        rd = RouteDistinguisher.make_from_elements('1.1.1.1', 10)
        packed_rd = rd.pack_rd()

        # CODE=99, length=8 (just RD)
        packed = bytes([99, 8]) + packed_rd

        # Should return GenericMVPN
        unpacked, leftover = MVPN.unpack_nlri(
            AFI.ipv4, SAFI.mcast_vpn, packed, Action.UNSET, None, negotiated=create_negotiated()
        )

        assert unpacked.CODE == 99

    def test_mvpn_safi(self) -> None:
        """Test that MVPN routes use correct SAFI"""
        rd = RouteDistinguisher.make_from_elements('1.1.1.1', 10)
        source = IP.create('192.168.1.1')
        group = IP.create('239.1.1.1')

        route = SourceAD.make_sourcead(rd, AFI.ipv4, source, group)

        assert route.safi == SAFI.mcast_vpn

    def test_mvpn_route_distinction(self) -> None:
        """Test that different MVPN route types are distinct"""
        rd = RouteDistinguisher.make_from_elements('1.1.1.1', 10)
        source = IP.create('192.168.1.1')
        group = IP.create('239.1.1.1')
        source_as = 65001

        sourcead = SourceAD.make_sourcead(rd, AFI.ipv4, source, group)
        sharedjoin = SharedJoin.make_sharedjoin(rd, AFI.ipv4, source, group, source_as)
        sourcejoin = SourceJoin.make_sourcejoin(rd, AFI.ipv4, source, group, source_as)

        # Different route types should have different codes
        assert sourcead.CODE != sharedjoin.CODE
        assert sourcead.CODE != sourcejoin.CODE
        assert sharedjoin.CODE != sourcejoin.CODE

        # Should not be equal even with same data
        assert sourcead != sharedjoin
        assert sharedjoin != sourcejoin
