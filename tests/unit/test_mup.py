"""Comprehensive tests for MUP (Mobile User Plane) NLRI types.

Tests cover all MUP route types defined in draft-mpmz-bess-mup-safi:
- Route Type 1: Interwork Segment Discovery (ISD)
- Route Type 2: Direct Segment Discovery (DSD)
- Route Type 3: Type 1 Session Transformed (T1ST)
- Route Type 4: Type 2 Session Transformed (T2ST)
"""

import pytest
from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.mup.isd import InterworkSegmentDiscoveryRoute
from exabgp.bgp.message.update.nlri.mup.dsd import DirectSegmentDiscoveryRoute
from exabgp.bgp.message.update.nlri.mup.t1st import Type1SessionTransformedRoute
from exabgp.bgp.message.update.nlri.mup.t2st import Type2SessionTransformedRoute
from exabgp.bgp.message.update.nlri.mup.nlri import MUP
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.nlri import Action


# ============================================================================
# MUP Route Type 1: Interwork Segment Discovery (ISD)
# ============================================================================

class TestInterworkSegmentDiscoveryRoute:
    """Tests for MUP Route Type 1: Interwork Segment Discovery"""

    def test_isd_creation(self) -> None:
        """Test basic creation of ISD route"""
        rd = RouteDistinguisher.fromElements('1.2.3.4', 100)
        prefix_ip = IP.create('10.0.0.0')
        prefix_ip_len = 24

        route = InterworkSegmentDiscoveryRoute(rd, prefix_ip_len, prefix_ip, AFI.ipv4)

        assert route.ARCHTYPE == 1
        assert route.CODE == 1
        assert route.NAME == 'InterworkSegmentDiscoveryRoute'
        assert route.SHORT_NAME == 'ISD'
        assert route.rd == rd
        assert route.prefix_ip_len == prefix_ip_len
        assert route.prefix_ip == prefix_ip

    def test_isd_pack_unpack_ipv4(self) -> None:
        """Test pack/unpack roundtrip for ISD with IPv4"""
        rd = RouteDistinguisher.fromElements('10.0.0.1', 500)
        prefix_ip = IP.create('192.168.1.0')
        prefix_ip_len = 24

        route = InterworkSegmentDiscoveryRoute(rd, prefix_ip_len, prefix_ip, AFI.ipv4)
        packed = route.pack_nlri()

        unpacked, leftover = MUP.unpack_nlri(AFI.ipv4, SAFI.mup, packed, Action.UNSET, None)

        assert len(leftover) == 0
        assert isinstance(unpacked, InterworkSegmentDiscoveryRoute)
        assert unpacked.rd._str() == rd._str()
        assert unpacked.prefix_ip_len == prefix_ip_len
        assert str(unpacked.prefix_ip) == str(prefix_ip)

    def test_isd_pack_unpack_ipv6(self) -> None:
        """Test pack/unpack roundtrip for ISD with IPv6"""
        rd = RouteDistinguisher.fromElements('10.0.0.2', 100)
        prefix_ip = IP.create('2001:db8:1:2::')
        prefix_ip_len = 64

        route = InterworkSegmentDiscoveryRoute(rd, prefix_ip_len, prefix_ip, AFI.ipv6)
        packed = route.pack_nlri()

        unpacked, leftover = MUP.unpack_nlri(AFI.ipv6, SAFI.mup, packed, Action.UNSET, None)

        assert len(leftover) == 0
        assert isinstance(unpacked, InterworkSegmentDiscoveryRoute)
        assert unpacked.rd._str() == rd._str()
        assert unpacked.prefix_ip_len == prefix_ip_len
        assert str(unpacked.prefix_ip) == str(prefix_ip)

    def test_isd_equality(self) -> None:
        """Test equality comparison for ISD routes"""
        rd = RouteDistinguisher.fromElements('1.1.1.1', 10)
        prefix_ip = IP.create('10.0.0.0')
        prefix_ip_len = 24

        route1 = InterworkSegmentDiscoveryRoute(rd, prefix_ip_len, prefix_ip, AFI.ipv4)
        route2 = InterworkSegmentDiscoveryRoute(rd, prefix_ip_len, prefix_ip, AFI.ipv4)

        assert route1 == route2
        assert not route1 != route2

    def test_isd_inequality(self) -> None:
        """Test inequality for different ISD routes"""
        rd1 = RouteDistinguisher.fromElements('1.1.1.1', 10)
        rd2 = RouteDistinguisher.fromElements('2.2.2.2', 20)
        prefix_ip = IP.create('10.0.0.0')

        route1 = InterworkSegmentDiscoveryRoute(rd1, 24, prefix_ip, AFI.ipv4)
        route2 = InterworkSegmentDiscoveryRoute(rd2, 24, prefix_ip, AFI.ipv4)

        assert route1 != route2
        assert not route1 == route2

    def test_isd_hash_consistency(self) -> None:
        """Test hash consistency for ISD routes"""
        rd = RouteDistinguisher.fromElements('2.2.2.2', 20)
        prefix_ip = IP.create('10.1.0.0')
        prefix_ip_len = 16

        route1 = InterworkSegmentDiscoveryRoute(rd, prefix_ip_len, prefix_ip, AFI.ipv4)
        route2 = InterworkSegmentDiscoveryRoute(rd, prefix_ip_len, prefix_ip, AFI.ipv4)

        assert hash(route1) == hash(route2)

    def test_isd_string_representation(self) -> None:
        """Test string representation of ISD"""
        rd = RouteDistinguisher.fromElements('3.3.3.3', 30)
        prefix_ip = IP.create('172.16.0.0')
        prefix_ip_len = 12

        route = InterworkSegmentDiscoveryRoute(rd, prefix_ip_len, prefix_ip, AFI.ipv4)
        route_str = str(route)

        assert 'isd' in route_str.lower()
        assert '172.16.0.0' in route_str
        assert '/12' in route_str

    def test_isd_json(self) -> None:
        """Test JSON serialization of ISD"""
        rd = RouteDistinguisher.fromElements('4.4.4.4', 40)
        prefix_ip = IP.create('10.20.30.0')
        prefix_ip_len = 24

        route = InterworkSegmentDiscoveryRoute(rd, prefix_ip_len, prefix_ip, AFI.ipv4)
        json_str = route.json()

        assert 'InterworkSegmentDiscoveryRoute' in json_str
        assert '"arch": 1' in json_str
        assert '"code": 1' in json_str
        assert '"prefix_ip_len": 24' in json_str

    def test_isd_variable_prefix_lengths(self) -> None:
        """Test ISD with various prefix lengths"""
        rd = RouteDistinguisher.fromElements('5.5.5.5', 50)

        for prefix_len in [8, 16, 24, 32]:
            prefix_ip = IP.create('10.0.0.0')
            route = InterworkSegmentDiscoveryRoute(rd, prefix_len, prefix_ip, AFI.ipv4)
            packed = route.pack_nlri()
            unpacked, _ = MUP.unpack_nlri(AFI.ipv4, SAFI.mup, packed, Action.UNSET, None)

            assert unpacked.prefix_ip_len == prefix_len


# ============================================================================
# MUP Route Type 2: Direct Segment Discovery (DSD)
# ============================================================================

class TestDirectSegmentDiscoveryRoute:
    """Tests for MUP Route Type 2: Direct Segment Discovery"""

    def test_dsd_creation(self) -> None:
        """Test basic creation of DSD route"""
        rd = RouteDistinguisher.fromElements('1.2.3.4', 100)
        ip = IP.create('10.0.0.1')

        route = DirectSegmentDiscoveryRoute(rd, ip, AFI.ipv4)

        assert route.ARCHTYPE == 1
        assert route.CODE == 2
        assert route.NAME == 'DirectSegmentDiscoveryRoute'
        assert route.SHORT_NAME == 'DSD'
        assert route.rd == rd
        assert route.ip == ip

    def test_dsd_pack_unpack_ipv4(self) -> None:
        """Test pack/unpack roundtrip for DSD with IPv4"""
        rd = RouteDistinguisher.fromElements('10.0.0.1', 500)
        ip = IP.create('192.168.1.1')

        route = DirectSegmentDiscoveryRoute(rd, ip, AFI.ipv4)
        packed = route.pack_nlri()

        unpacked, leftover = MUP.unpack_nlri(AFI.ipv4, SAFI.mup, packed, Action.UNSET, None)

        assert len(leftover) == 0
        assert isinstance(unpacked, DirectSegmentDiscoveryRoute)
        assert unpacked.rd._str() == rd._str()
        assert str(unpacked.ip) == str(ip)

    def test_dsd_pack_unpack_ipv6(self) -> None:
        """Test pack/unpack roundtrip for DSD with IPv6"""
        rd = RouteDistinguisher.fromElements('10.0.0.2', 100)
        ip = IP.create('2001:db8:1:2::1')

        route = DirectSegmentDiscoveryRoute(rd, ip, AFI.ipv6)
        packed = route.pack_nlri()

        unpacked, leftover = MUP.unpack_nlri(AFI.ipv6, SAFI.mup, packed, Action.UNSET, None)

        assert len(leftover) == 0
        assert isinstance(unpacked, DirectSegmentDiscoveryRoute)
        assert unpacked.rd._str() == rd._str()
        assert str(unpacked.ip) == str(ip)

    def test_dsd_equality(self) -> None:
        """Test equality comparison for DSD routes"""
        rd = RouteDistinguisher.fromElements('1.1.1.1', 10)
        ip = IP.create('10.0.0.1')

        route1 = DirectSegmentDiscoveryRoute(rd, ip, AFI.ipv4)
        route2 = DirectSegmentDiscoveryRoute(rd, ip, AFI.ipv4)

        assert route1 == route2
        assert not route1 != route2

    def test_dsd_inequality(self) -> None:
        """Test inequality for different DSD routes"""
        rd = RouteDistinguisher.fromElements('1.1.1.1', 10)
        ip1 = IP.create('10.0.0.1')
        ip2 = IP.create('10.0.0.2')

        route1 = DirectSegmentDiscoveryRoute(rd, ip1, AFI.ipv4)
        route2 = DirectSegmentDiscoveryRoute(rd, ip2, AFI.ipv4)

        assert route1 != route2
        assert not route1 == route2

    def test_dsd_hash_consistency(self) -> None:
        """Test hash consistency for DSD routes"""
        rd = RouteDistinguisher.fromElements('2.2.2.2', 20)
        ip = IP.create('10.1.0.1')

        route1 = DirectSegmentDiscoveryRoute(rd, ip, AFI.ipv4)
        route2 = DirectSegmentDiscoveryRoute(rd, ip, AFI.ipv4)

        assert hash(route1) == hash(route2)

    def test_dsd_string_representation(self) -> None:
        """Test string representation of DSD"""
        rd = RouteDistinguisher.fromElements('3.3.3.3', 30)
        ip = IP.create('172.16.0.1')

        route = DirectSegmentDiscoveryRoute(rd, ip, AFI.ipv4)
        route_str = str(route)

        assert 'dsd' in route_str.lower()
        assert '172.16.0.1' in route_str

    def test_dsd_json(self) -> None:
        """Test JSON serialization of DSD"""
        rd = RouteDistinguisher.fromElements('4.4.4.4', 40)
        ip = IP.create('10.20.30.40')

        route = DirectSegmentDiscoveryRoute(rd, ip, AFI.ipv4)
        json_str = route.json()

        assert 'DirectSegmentDiscoveryRoute' in json_str
        assert '"arch": 1' in json_str
        assert '"code": 2' in json_str
        assert '"ip": "10.20.30.40"' in json_str

    def test_dsd_invalid_ip_size(self) -> None:
        """Test DSD with invalid IP size raises error"""
        # Create invalid packed data with wrong IP size (3 bytes instead of 4 or 16)
        rd = RouteDistinguisher.fromElements('1.1.1.1', 10)
        packed_rd = rd.pack()
        invalid_data = packed_rd + b'\x01\x02\x03'  # 3 bytes - invalid

        # Pack into MUP format
        packed = b'\x01\x00\x02' + bytes([len(invalid_data)]) + invalid_data

        with pytest.raises(Notify):
            MUP.unpack_nlri(AFI.ipv4, SAFI.mup, packed, Action.UNSET, None)


# ============================================================================
# MUP Route Type 3: Type 1 Session Transformed (T1ST)
# ============================================================================

class TestType1SessionTransformedRoute:
    """Tests for MUP Route Type 3: Type 1 Session Transformed"""

    def test_t1st_creation(self) -> None:
        """Test basic creation of T1ST route"""
        rd = RouteDistinguisher.fromElements('1.2.3.4', 100)
        prefix_ip = IP.create('10.0.0.0')
        endpoint_ip = IP.create('192.168.1.1')
        source_ip = IP.create('192.168.2.1')

        route = Type1SessionTransformedRoute(
            rd=rd,
            prefix_ip_len=24,
            prefix_ip=prefix_ip,
            teid=12345,
            qfi=5,
            endpoint_ip_len=32,
            endpoint_ip=endpoint_ip,
            source_ip_len=32,
            source_ip=source_ip,
            afi=AFI.ipv4,
        )

        assert route.ARCHTYPE == 1
        assert route.CODE == 3
        assert route.NAME == 'Type1SessionTransformedRoute'
        assert route.SHORT_NAME == 'T1ST'
        assert route.rd == rd
        assert route.teid == 12345
        assert route.qfi == 5

    def test_t1st_pack_unpack_ipv4_with_source(self) -> None:
        """Test pack/unpack roundtrip for T1ST with IPv4 and source address"""
        rd = RouteDistinguisher.fromElements('10.0.0.1', 500)
        prefix_ip = IP.create('192.168.1.0')
        endpoint_ip = IP.create('10.1.1.1')
        source_ip = IP.create('10.2.2.2')

        route = Type1SessionTransformedRoute(
            rd=rd,
            prefix_ip_len=24,
            prefix_ip=prefix_ip,
            teid=99999,
            qfi=9,
            endpoint_ip_len=32,
            endpoint_ip=endpoint_ip,
            source_ip_len=32,
            source_ip=source_ip,
            afi=AFI.ipv4,
        )
        packed = route.pack_nlri()

        unpacked, leftover = MUP.unpack_nlri(AFI.ipv4, SAFI.mup, packed, Action.UNSET, None)

        assert len(leftover) == 0
        assert isinstance(unpacked, Type1SessionTransformedRoute)
        assert unpacked.rd._str() == rd._str()
        assert unpacked.teid == 99999
        assert unpacked.qfi == 9
        assert str(unpacked.endpoint_ip) == str(endpoint_ip)
        assert str(unpacked.source_ip) == str(source_ip)

    def test_t1st_pack_unpack_ipv4_without_source(self) -> None:
        """Test pack/unpack roundtrip for T1ST with IPv4 without source address"""
        rd = RouteDistinguisher.fromElements('10.0.0.1', 500)
        prefix_ip = IP.create('192.168.1.0')
        endpoint_ip = IP.create('10.1.1.1')

        route = Type1SessionTransformedRoute(
            rd=rd,
            prefix_ip_len=24,
            prefix_ip=prefix_ip,
            teid=55555,
            qfi=3,
            endpoint_ip_len=32,
            endpoint_ip=endpoint_ip,
            source_ip_len=0,
            source_ip=b'',
            afi=AFI.ipv4,
        )
        packed = route.pack_nlri()

        unpacked, leftover = MUP.unpack_nlri(AFI.ipv4, SAFI.mup, packed, Action.UNSET, None)

        assert len(leftover) == 0
        assert isinstance(unpacked, Type1SessionTransformedRoute)
        assert unpacked.teid == 55555
        assert unpacked.source_ip_len == 0

    def test_t1st_pack_unpack_ipv6(self) -> None:
        """Test pack/unpack roundtrip for T1ST with IPv6"""
        rd = RouteDistinguisher.fromElements('10.0.0.2', 100)
        prefix_ip = IP.create('2001:db8:1::')
        endpoint_ip = IP.create('2001:db8:2::1')
        source_ip = IP.create('2001:db8:3::1')

        route = Type1SessionTransformedRoute(
            rd=rd,
            prefix_ip_len=64,
            prefix_ip=prefix_ip,
            teid=77777,
            qfi=7,
            endpoint_ip_len=128,
            endpoint_ip=endpoint_ip,
            source_ip_len=128,
            source_ip=source_ip,
            afi=AFI.ipv6,
        )
        packed = route.pack_nlri()

        unpacked, leftover = MUP.unpack_nlri(AFI.ipv6, SAFI.mup, packed, Action.UNSET, None)

        assert len(leftover) == 0
        assert isinstance(unpacked, Type1SessionTransformedRoute)
        assert unpacked.teid == 77777
        assert unpacked.qfi == 7

    def test_t1st_equality(self) -> None:
        """Test equality comparison for T1ST routes"""
        rd = RouteDistinguisher.fromElements('1.1.1.1', 10)
        prefix_ip = IP.create('10.0.0.0')
        endpoint_ip = IP.create('192.168.1.1')
        source_ip = IP.create('192.168.2.1')

        route1 = Type1SessionTransformedRoute(
            rd, 24, prefix_ip, 12345, 5, 32, endpoint_ip, 32, source_ip, AFI.ipv4,
        )
        route2 = Type1SessionTransformedRoute(
            rd, 24, prefix_ip, 12345, 5, 32, endpoint_ip, 32, source_ip, AFI.ipv4,
        )

        assert route1 == route2
        assert not route1 != route2

    def test_t1st_hash_consistency(self) -> None:
        """Test hash consistency for T1ST routes"""
        rd = RouteDistinguisher.fromElements('2.2.2.2', 20)
        prefix_ip = IP.create('10.1.0.0')
        endpoint_ip = IP.create('192.168.1.1')

        route1 = Type1SessionTransformedRoute(
            rd, 24, prefix_ip, 11111, 1, 32, endpoint_ip, 0, b'', AFI.ipv4,
        )
        route2 = Type1SessionTransformedRoute(
            rd, 24, prefix_ip, 11111, 1, 32, endpoint_ip, 0, b'', AFI.ipv4,
        )

        assert hash(route1) == hash(route2)

    def test_t1st_string_representation(self) -> None:
        """Test string representation of T1ST"""
        rd = RouteDistinguisher.fromElements('3.3.3.3', 30)
        prefix_ip = IP.create('172.16.0.0')
        endpoint_ip = IP.create('10.1.1.1')

        route = Type1SessionTransformedRoute(
            rd, 12, prefix_ip, 12345, 5, 32, endpoint_ip, 0, b'', AFI.ipv4,
        )
        route_str = str(route)

        assert 't1st' in route_str.lower()
        assert '12345' in route_str  # TEID

    def test_t1st_json(self) -> None:
        """Test JSON serialization of T1ST"""
        rd = RouteDistinguisher.fromElements('4.4.4.4', 40)
        prefix_ip = IP.create('10.20.30.0')
        endpoint_ip = IP.create('10.1.1.1')

        route = Type1SessionTransformedRoute(
            rd, 24, prefix_ip, 88888, 8, 32, endpoint_ip, 0, b'', AFI.ipv4,
        )
        json_str = route.json()

        assert 'Type1SessionTransformedRoute' in json_str
        assert '"arch": 1' in json_str
        assert '"code": 3' in json_str
        assert '"teid": "88888"' in json_str
        assert '"qfi": "8"' in json_str

    def test_t1st_invalid_endpoint_length(self) -> None:
        """Test T1ST with invalid endpoint IP length raises error"""
        rd = RouteDistinguisher.fromElements('1.1.1.1', 10)
        prefix_ip = IP.create('10.0.0.0')

        # Create packed data with invalid endpoint length (33 bits)
        packed_rd = rd.pack()
        packed_prefix = bytes([24]) + prefix_ip.pack()[:3]  # 24-bit prefix
        packed_teid_qfi = b'\x00\x00\x30\x39\x05'  # TEID=12345, QFI=5
        packed_endpoint = bytes([33])  # Invalid: not 32 or 128

        invalid_data = packed_rd + packed_prefix + packed_teid_qfi + packed_endpoint
        packed = b'\x01\x00\x03' + bytes([len(invalid_data)]) + invalid_data

        with pytest.raises(RuntimeError):
            MUP.unpack_nlri(AFI.ipv4, SAFI.mup, packed, Action.UNSET, None)

    def test_t1st_variable_prefix_lengths(self) -> None:
        """Test T1ST with various prefix lengths"""
        rd = RouteDistinguisher.fromElements('5.5.5.5', 50)
        endpoint_ip = IP.create('10.1.1.1')

        for prefix_len in [8, 16, 24, 32]:
            prefix_ip = IP.create('10.0.0.0')
            route = Type1SessionTransformedRoute(
                rd, prefix_len, prefix_ip, 1000, 1, 32, endpoint_ip, 0, b'', AFI.ipv4,
            )
            packed = route.pack_nlri()
            unpacked, _ = MUP.unpack_nlri(AFI.ipv4, SAFI.mup, packed, Action.UNSET, None)

            assert unpacked.prefix_ip_len == prefix_len


# ============================================================================
# MUP Route Type 4: Type 2 Session Transformed (T2ST)
# ============================================================================

class TestType2SessionTransformedRoute:
    """Tests for MUP Route Type 4: Type 2 Session Transformed"""

    def test_t2st_creation(self) -> None:
        """Test basic creation of T2ST route"""
        rd = RouteDistinguisher.fromElements('1.2.3.4', 100)
        endpoint_ip = IP.create('192.168.1.1')

        route = Type2SessionTransformedRoute(
            rd=rd,
            endpoint_len=32,
            endpoint_ip=endpoint_ip,
            teid=0,
            afi=AFI.ipv4,
        )

        assert route.ARCHTYPE == 1
        assert route.CODE == 4
        assert route.NAME == 'Type2SessionTransformedRoute'
        assert route.SHORT_NAME == 'T2ST'
        assert route.rd == rd
        assert route.endpoint_len == 32
        assert route.teid == 0

    def test_t2st_pack_unpack_ipv4_no_teid(self) -> None:
        """Test pack/unpack roundtrip for T2ST with IPv4 without TEID"""
        rd = RouteDistinguisher.fromElements('10.0.0.1', 500)
        endpoint_ip = IP.create('192.168.1.1')

        route = Type2SessionTransformedRoute(rd, 32, endpoint_ip, 0, AFI.ipv4)
        packed = route.pack_nlri()

        unpacked, leftover = MUP.unpack_nlri(AFI.ipv4, SAFI.mup, packed, Action.UNSET, None)

        assert len(leftover) == 0
        assert isinstance(unpacked, Type2SessionTransformedRoute)
        assert unpacked.rd._str() == rd._str()
        assert unpacked.endpoint_len == 32
        assert str(unpacked.endpoint_ip) == str(endpoint_ip)
        assert unpacked.teid == 0

    def test_t2st_pack_unpack_ipv4_with_teid(self) -> None:
        """Test pack/unpack roundtrip for T2ST with IPv4 with TEID"""
        rd = RouteDistinguisher.fromElements('10.0.0.1', 500)
        endpoint_ip = IP.create('192.168.1.1')
        # endpoint_len = 32 (IP) + 32 (TEID bits) = 64
        teid = 0xABCDEF12

        route = Type2SessionTransformedRoute(rd, 64, endpoint_ip, teid, AFI.ipv4)
        packed = route.pack_nlri()

        unpacked, leftover = MUP.unpack_nlri(AFI.ipv4, SAFI.mup, packed, Action.UNSET, None)

        assert len(leftover) == 0
        assert isinstance(unpacked, Type2SessionTransformedRoute)
        assert unpacked.teid == teid

    def test_t2st_pack_unpack_ipv6_no_teid(self) -> None:
        """Test pack/unpack roundtrip for T2ST with IPv6 without TEID"""
        rd = RouteDistinguisher.fromElements('10.0.0.2', 100)
        endpoint_ip = IP.create('2001:db8:1::1')

        route = Type2SessionTransformedRoute(rd, 128, endpoint_ip, 0, AFI.ipv6)
        packed = route.pack_nlri()

        unpacked, leftover = MUP.unpack_nlri(AFI.ipv6, SAFI.mup, packed, Action.UNSET, None)

        assert len(leftover) == 0
        assert isinstance(unpacked, Type2SessionTransformedRoute)
        assert unpacked.endpoint_len == 128
        assert unpacked.teid == 0

    def test_t2st_pack_unpack_ipv6_with_teid(self) -> None:
        """Test pack/unpack roundtrip for T2ST with IPv6 with TEID"""
        rd = RouteDistinguisher.fromElements('10.0.0.2', 100)
        endpoint_ip = IP.create('2001:db8:1::1')
        # endpoint_len = 128 (IP) + 16 (TEID bits) = 144
        teid = 0x1234

        route = Type2SessionTransformedRoute(rd, 144, endpoint_ip, teid, AFI.ipv6)
        packed = route.pack_nlri()

        unpacked, leftover = MUP.unpack_nlri(AFI.ipv6, SAFI.mup, packed, Action.UNSET, None)

        assert len(leftover) == 0
        assert isinstance(unpacked, Type2SessionTransformedRoute)
        assert unpacked.teid == teid

    def test_t2st_equality(self) -> None:
        """Test equality comparison for T2ST routes"""
        rd = RouteDistinguisher.fromElements('1.1.1.1', 10)
        endpoint_ip = IP.create('192.168.1.1')

        route1 = Type2SessionTransformedRoute(rd, 32, endpoint_ip, 0, AFI.ipv4)
        route2 = Type2SessionTransformedRoute(rd, 32, endpoint_ip, 0, AFI.ipv4)

        assert route1 == route2
        assert not route1 != route2

    def test_t2st_inequality(self) -> None:
        """Test inequality for different T2ST routes"""
        rd = RouteDistinguisher.fromElements('1.1.1.1', 10)
        endpoint_ip = IP.create('192.168.1.1')

        route1 = Type2SessionTransformedRoute(rd, 32, endpoint_ip, 0, AFI.ipv4)
        route2 = Type2SessionTransformedRoute(rd, 64, endpoint_ip, 12345, AFI.ipv4)

        # Different TEID should make them unequal
        assert route1 != route2

    def test_t2st_hash_consistency(self) -> None:
        """Test hash consistency for T2ST routes"""
        rd = RouteDistinguisher.fromElements('2.2.2.2', 20)
        endpoint_ip = IP.create('10.1.1.1')

        route1 = Type2SessionTransformedRoute(rd, 32, endpoint_ip, 0, AFI.ipv4)
        route2 = Type2SessionTransformedRoute(rd, 32, endpoint_ip, 0, AFI.ipv4)

        assert hash(route1) == hash(route2)

    def test_t2st_string_representation(self) -> None:
        """Test string representation of T2ST"""
        rd = RouteDistinguisher.fromElements('3.3.3.3', 30)
        endpoint_ip = IP.create('172.16.0.1')

        route = Type2SessionTransformedRoute(rd, 32, endpoint_ip, 0, AFI.ipv4)
        route_str = str(route)

        assert 't2st' in route_str.lower()
        assert '172.16.0.1' in route_str

    def test_t2st_json(self) -> None:
        """Test JSON serialization of T2ST"""
        rd = RouteDistinguisher.fromElements('4.4.4.4', 40)
        endpoint_ip = IP.create('10.20.30.40')

        route = Type2SessionTransformedRoute(rd, 64, endpoint_ip, 99999, AFI.ipv4)
        json_str = route.json()

        assert 'Type2SessionTransformedRoute' in json_str
        assert '"arch": 1' in json_str
        assert '"code": 4' in json_str
        assert '"endpoint_len": 64' in json_str
        assert '"teid": "99999"' in json_str

    def test_t2st_teid_too_large(self) -> None:
        """Test T2ST with TEID that's too large raises error"""
        rd = RouteDistinguisher.fromElements('1.1.1.1', 10)
        endpoint_ip = IP.create('192.168.1.1')

        # endpoint_len = 32 (IP) + 33 (TEID bits) = 65 - too large!
        with pytest.raises(Exception):
            route = Type2SessionTransformedRoute(rd, 65, endpoint_ip, 0xFFFFFFFF, AFI.ipv4)
            route.pack_nlri()  # This should raise when packing

    def test_t2st_various_teid_sizes(self) -> None:
        """Test T2ST with various TEID sizes"""
        rd = RouteDistinguisher.fromElements('5.5.5.5', 50)
        endpoint_ip = IP.create('10.1.1.1')

        # Test different TEID bit sizes: 0, 8, 16, 24, 32
        for teid_bits in [0, 8, 16, 24, 32]:
            endpoint_len = 32 + teid_bits
            teid_value = (1 << teid_bits) - 1 if teid_bits > 0 else 0

            route = Type2SessionTransformedRoute(rd, endpoint_len, endpoint_ip, teid_value, AFI.ipv4)
            packed = route.pack_nlri()
            unpacked, _ = MUP.unpack_nlri(AFI.ipv4, SAFI.mup, packed, Action.UNSET, None)

            assert unpacked.endpoint_len == endpoint_len


# ============================================================================
# Generic MUP Tests
# ============================================================================

class TestMUPGeneric:
    """Tests for generic MUP functionality"""

    def test_mup_registration(self) -> None:
        """Test that all MUP route types are registered"""
        assert '1:1' in MUP.registered  # ISD
        assert '1:2' in MUP.registered  # DSD
        assert '1:3' in MUP.registered  # T1ST
        assert '1:4' in MUP.registered  # T2ST

    def test_mup_registered_classes(self) -> None:
        """Test that registered classes are correct"""
        assert MUP.registered['1:1'] == InterworkSegmentDiscoveryRoute
        assert MUP.registered['1:2'] == DirectSegmentDiscoveryRoute
        assert MUP.registered['1:3'] == Type1SessionTransformedRoute
        assert MUP.registered['1:4'] == Type2SessionTransformedRoute

    def test_mup_unpack_unknown_route_type(self) -> None:
        """Test unpacking unknown MUP route type"""
        # Create a route with unknown code (99)
        rd = RouteDistinguisher.fromElements('1.1.1.1', 10)
        packed_rd = rd.pack()

        # ARCHTYPE=1, CODE=99, length=8 (just RD)
        packed = b'\x01\x00\x63\x08' + packed_rd

        # Should return GenericMUP
        unpacked, leftover = MUP.unpack_nlri(AFI.ipv4, SAFI.mup, packed, Action.UNSET, None)

        assert unpacked.CODE == 99
        assert unpacked.ARCHTYPE == 1

    def test_mup_safi(self) -> None:
        """Test that MUP routes use correct SAFI"""
        rd = RouteDistinguisher.fromElements('1.1.1.1', 10)
        ip = IP.create('10.0.0.1')

        route = DirectSegmentDiscoveryRoute(rd, ip, AFI.ipv4)

        assert route.safi == SAFI.mup
