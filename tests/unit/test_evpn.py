"""Comprehensive tests for EVPN (Ethernet VPN) NLRI types.

Tests cover all EVPN route types defined in RFC 7432:
- Route Type 1: Ethernet Auto-Discovery (EthernetAD)
- Route Type 2: MAC/IP Advertisement (MAC)
- Route Type 3: Inclusive Multicast Ethernet Tag (Multicast)
- Route Type 4: Ethernet Segment (EthernetSegment)
- Route Type 5: IP Prefix Advertisement (Prefix)
"""

import pytest
from unittest.mock import Mock

from exabgp.protocol.ip import IP
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import ESI
from exabgp.bgp.message.update.nlri.qualifier import EthernetTag
from exabgp.bgp.message.update.nlri.qualifier import MAC as MACQUAL
from exabgp.bgp.message.update.nlri.evpn.ethernetad import EthernetAD
from exabgp.bgp.message.update.nlri.evpn.mac import MAC
from exabgp.bgp.message.update.nlri.evpn.multicast import Multicast
from exabgp.bgp.message.update.nlri.evpn.segment import EthernetSegment
from exabgp.bgp.message.update.nlri.evpn.prefix import Prefix
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.nlri import Action


def create_negotiated() -> Negotiated:
    """Create a Negotiated object with a mock neighbor for testing."""
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    return Negotiated(neighbor, Direction.OUT)


# ============================================================================
# EVPN Route Type 1: Ethernet Auto-Discovery (EthernetAD)
# ============================================================================


class TestEthernetAD:
    """Tests for EVPN Route Type 1: Ethernet Auto-Discovery"""

    def test_ethernetad_creation(self) -> None:
        """Test basic creation of EthernetAD route"""
        rd = RouteDistinguisher.make_from_elements('1.2.3.4', 100)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(200)
        label = Labels.make_labels([300], True)

        route = EthernetAD(rd, esi, etag, label)

        assert route.CODE == 1
        assert route.NAME == 'Ethernet Auto-Discovery'
        assert route.rd == rd
        assert route.esi == esi
        assert route.etag == etag
        assert route.label == label

    def test_ethernetad_pack_unpack(self) -> None:
        """Test pack/unpack roundtrip for EthernetAD"""
        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 500)
        esi = ESI(bytes([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
        etag = EthernetTag.make_etag(1000)
        label = Labels.make_labels([100], True)

        route = EthernetAD(rd, esi, etag, label)
        packed = route.pack_nlri(create_negotiated())

        unpacked, leftover = EVPN.unpack_nlri(AFI.l2vpn, SAFI.evpn, packed, Action.UNSET, None, create_negotiated())

        assert len(leftover) == 0
        assert isinstance(unpacked, EthernetAD)
        assert unpacked.rd._str() == rd._str()
        assert unpacked.etag == etag
        assert len(unpacked.label.labels) == 1
        assert unpacked.label.labels[0] == 100

    def test_ethernetad_equality(self) -> None:
        """Test equality comparison for EthernetAD routes"""
        rd = RouteDistinguisher.make_from_elements('1.1.1.1', 10)
        etag = EthernetTag.make_etag(100)

        route1 = EthernetAD(rd, ESI.make_default(), etag, Labels.make_labels([50], True))
        route2 = EthernetAD(rd, ESI.make_default(), etag, Labels.make_labels([60], True))

        # Same RD and etag should be equal (ESI and label not part of comparison)
        assert route1 == route2
        assert not route1 != route2

    def test_ethernetad_hash_consistency(self) -> None:
        """Test hash consistency - ESI and label should not affect hash"""
        rd = RouteDistinguisher.make_from_elements('2.2.2.2', 20)
        etag = EthernetTag.make_etag(200)

        route1 = EthernetAD(rd, ESI.make_default(), etag, Labels.make_labels([100], True))
        route2 = EthernetAD(rd, ESI(bytes([1] * 10)), etag, Labels.make_labels([200], True))

        assert hash(route1) == hash(route2)

    def test_ethernetad_string_representation(self) -> None:
        """Test string representation of EthernetAD"""
        rd = RouteDistinguisher.make_from_elements('3.3.3.3', 30)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(300)
        label = Labels.make_labels([400], True)

        route = EthernetAD(rd, esi, etag, label)
        str_repr = str(route)

        assert '3.3.3.3:30' in str_repr
        assert 'ethernetad' in str_repr.lower() or 'ethernet' in str_repr.lower()

    def test_ethernetad_json(self) -> None:
        """Test JSON serialization of EthernetAD"""
        rd = RouteDistinguisher.make_from_elements('4.4.4.4', 40)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(400)
        label = Labels.make_labels([500], True)

        route = EthernetAD(rd, esi, etag, label)
        json_str = route.json()

        assert '"code": 1' in json_str
        assert '"name": "Ethernet Auto-Discovery"' in json_str
        assert '"parsed": true' in json_str


# ============================================================================
# EVPN Route Type 2: MAC/IP Advertisement (MAC)
# ============================================================================


class TestMAC:
    """Tests for EVPN Route Type 2: MAC/IP Advertisement"""

    def test_mac_creation_with_ipv4(self) -> None:
        """Test creation of MAC route with IPv4 address"""
        rd = RouteDistinguisher.make_from_elements('5.5.5.5', 50)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(500)
        mac = MACQUAL('aa:bb:cc:dd:ee:ff')
        maclen = 48
        label = Labels.make_labels([600], True)
        ip = IP.create('192.168.1.1')

        route = MAC(rd, esi, etag, mac, maclen, label, ip)

        assert route.CODE == 2
        assert route.NAME == 'MAC/IP advertisement'
        assert route.rd == rd
        assert route.mac == mac
        assert route.maclen == maclen
        assert route.ip == ip

    def test_mac_creation_without_ip(self) -> None:
        """Test creation of MAC route without IP address"""
        rd = RouteDistinguisher.make_from_elements('6.6.6.6', 60)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(600)
        mac = MACQUAL('11:22:33:44:55:66')
        maclen = 48
        label = Labels.make_labels([700], True)

        route = MAC(rd, esi, etag, mac, maclen, label, None)

        assert route.CODE == 2
        assert route.ip is None

    def test_mac_pack_unpack_with_ipv4(self) -> None:
        """Test pack/unpack roundtrip for MAC route with IPv4"""
        rd = RouteDistinguisher.make_from_elements('7.7.7.7', 70)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(700)
        mac = MACQUAL('aa:bb:cc:dd:ee:ff')
        maclen = 48
        label = Labels.make_labels([800], True)
        ip = IP.create('10.1.1.1')

        route = MAC(rd, esi, etag, mac, maclen, label, ip)
        packed = route.pack_nlri(create_negotiated())

        unpacked, leftover = EVPN.unpack_nlri(AFI.l2vpn, SAFI.evpn, packed, Action.UNSET, None, create_negotiated())

        assert len(leftover) == 0
        assert isinstance(unpacked, MAC)
        assert unpacked.rd._str() == rd._str()
        assert unpacked.mac == mac
        assert unpacked.maclen == maclen
        assert unpacked.ip == ip

    def test_mac_pack_unpack_without_ip(self) -> None:
        """Test pack/unpack roundtrip for MAC route without IP"""
        rd = RouteDistinguisher.make_from_elements('8.8.8.8', 80)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(800)
        mac = MACQUAL('12:34:56:78:9a:bc')
        maclen = 48
        label = Labels.make_labels([900], True)

        route = MAC(rd, esi, etag, mac, maclen, label, None)
        packed = route.pack_nlri(create_negotiated())

        unpacked, leftover = EVPN.unpack_nlri(AFI.l2vpn, SAFI.evpn, packed, Action.UNSET, None, create_negotiated())

        assert len(leftover) == 0
        assert isinstance(unpacked, MAC)
        assert unpacked.rd._str() == rd._str()
        assert unpacked.mac == mac
        assert unpacked.ip is None

    def test_mac_pack_unpack_with_ipv6(self) -> None:
        """Test pack/unpack roundtrip for MAC route with IPv6"""
        rd = RouteDistinguisher.make_from_elements('9.9.9.9', 90)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(900)
        mac = MACQUAL('fe:dc:ba:98:76:54')
        maclen = 48
        label = Labels.make_labels([1000], True)
        ip = IP.create('2001:db8::1')

        route = MAC(rd, esi, etag, mac, maclen, label, ip)
        packed = route.pack_nlri(create_negotiated())

        unpacked, leftover = EVPN.unpack_nlri(AFI.l2vpn, SAFI.evpn, packed, Action.UNSET, None, create_negotiated())

        assert len(leftover) == 0
        assert isinstance(unpacked, MAC)
        assert unpacked.rd._str() == rd._str()
        assert unpacked.mac == mac
        assert unpacked.ip == ip

    def test_mac_equality(self) -> None:
        """Test equality comparison for MAC routes"""
        rd = RouteDistinguisher.make_from_elements('10.10.10.10', 100)
        etag = EthernetTag.make_etag(1000)
        mac = MACQUAL('aa:bb:cc:dd:ee:ff')
        ip = IP.create('192.168.1.1')

        route1 = MAC(rd, ESI.make_default(), etag, mac, 48, Labels.make_labels([100], True), ip)
        route2 = MAC(rd, ESI.make_default(), etag, mac, 48, Labels.make_labels([200], True), ip)

        # ESI and label should not affect equality
        assert route1 == route2

    def test_mac_hash_consistency(self) -> None:
        """Test hash consistency - ESI and label should not affect hash"""
        rd = RouteDistinguisher.make_from_elements('11.11.11.11', 110)
        etag = EthernetTag.make_etag(1100)
        mac = MACQUAL('11:22:33:44:55:66')
        ip = IP.create('10.0.0.1')

        route1 = MAC(rd, ESI.make_default(), etag, mac, 48, Labels.make_labels([100], True), ip)
        route2 = MAC(rd, ESI(bytes([1] * 10)), etag, mac, 48, Labels.make_labels([200], True), ip)

        assert hash(route1) == hash(route2)

    def test_mac_invalid_maclen(self) -> None:
        """Test that invalid MAC length raises error"""
        rd = RouteDistinguisher.make_from_elements('12.12.12.12', 120)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(1200)
        mac = MACQUAL('aa:bb:cc:dd:ee:ff')

        # Create packed data with invalid MAC length
        packed = rd.pack_rd() + esi.pack_esi() + etag.pack_etag() + bytes([64])  # Invalid: > 48

        with pytest.raises(Notify):
            MAC.unpack_evpn_route(packed + mac.pack_mac() + bytes([0]) + Labels.make_labels([100], True).pack_labels())

    def test_mac_string_representation(self) -> None:
        """Test string representation of MAC route"""
        rd = RouteDistinguisher.make_from_elements('13.13.13.13', 130)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(1300)
        mac = MACQUAL('aa:bb:cc:dd:ee:ff')
        ip = IP.create('192.168.1.1')
        label = Labels.make_labels([1400], True)

        route = MAC(rd, esi, etag, mac, 48, label, ip)
        str_repr = str(route)

        assert '13.13.13.13:130' in str_repr
        assert '192.168.1.1' in str_repr
        # MAC address may be uppercase or lowercase
        assert 'AA:BB:CC:DD:EE:FF' in str_repr or 'aa:bb:cc:dd:ee:ff' in str_repr

    def test_mac_json(self) -> None:
        """Test JSON serialization of MAC route"""
        rd = RouteDistinguisher.make_from_elements('14.14.14.14', 140)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(1400)
        mac = MACQUAL('11:22:33:44:55:66')
        ip = IP.create('10.1.1.1')
        label = Labels.make_labels([1500], True)

        route = MAC(rd, esi, etag, mac, 48, label, ip)
        json_str = route.json()

        assert '"code": 2' in json_str
        assert '"name": "MAC/IP advertisement"' in json_str
        assert '"ip": "10.1.1.1"' in json_str


# ============================================================================
# EVPN Route Type 3: Inclusive Multicast Ethernet Tag (Multicast)
# ============================================================================


class TestMulticast:
    """Tests for EVPN Route Type 3: Inclusive Multicast Ethernet Tag"""

    def test_multicast_creation_ipv4(self) -> None:
        """Test creation of Multicast route with IPv4"""
        rd = RouteDistinguisher.make_from_elements('15.15.15.15', 150)
        etag = EthernetTag.make_etag(1500)
        ip = IP.create('192.168.1.1')

        route = Multicast(rd, etag, ip)

        assert route.CODE == 3
        assert route.NAME == 'Inclusive Multicast Ethernet Tag'
        assert route.rd == rd
        assert route.etag == etag
        assert route.ip == ip

    def test_multicast_creation_ipv6(self) -> None:
        """Test creation of Multicast route with IPv6"""
        rd = RouteDistinguisher.make_from_elements('16.16.16.16', 160)
        etag = EthernetTag.make_etag(1600)
        ip = IP.create('2001:db8::1')

        route = Multicast(rd, etag, ip)

        assert route.CODE == 3
        assert route.ip == ip

    def test_multicast_pack_unpack_ipv4(self) -> None:
        """Test pack/unpack roundtrip for Multicast route with IPv4"""
        rd = RouteDistinguisher.make_from_elements('17.17.17.17', 170)
        etag = EthernetTag.make_etag(1700)
        ip = IP.create('10.0.0.1')

        route = Multicast(rd, etag, ip)
        packed = route.pack_nlri(create_negotiated())

        unpacked, leftover = EVPN.unpack_nlri(AFI.l2vpn, SAFI.evpn, packed, Action.UNSET, None, create_negotiated())

        assert len(leftover) == 0
        assert isinstance(unpacked, Multicast)
        assert unpacked.rd._str() == rd._str()
        assert unpacked.etag == etag
        assert unpacked.ip == ip

    def test_multicast_pack_unpack_ipv6(self) -> None:
        """Test pack/unpack roundtrip for Multicast route with IPv6"""
        rd = RouteDistinguisher.make_from_elements('18.18.18.18', 180)
        etag = EthernetTag.make_etag(1800)
        ip = IP.create('fe80::1')

        route = Multicast(rd, etag, ip)
        packed = route.pack_nlri(create_negotiated())

        unpacked, leftover = EVPN.unpack_nlri(AFI.l2vpn, SAFI.evpn, packed, Action.UNSET, None, create_negotiated())

        assert len(leftover) == 0
        assert isinstance(unpacked, Multicast)
        assert unpacked.rd._str() == rd._str()
        assert unpacked.etag == etag
        assert unpacked.ip == ip

    def test_multicast_hash(self) -> None:
        """Test hash calculation for Multicast route"""
        rd = RouteDistinguisher.make_from_elements('19.19.19.19', 190)
        etag = EthernetTag.make_etag(1900)
        ip = IP.create('192.168.1.1')

        route = Multicast(rd, etag, ip)
        hash_val = hash(route)

        assert isinstance(hash_val, int)

    def test_multicast_string_representation(self) -> None:
        """Test string representation of Multicast route"""
        rd = RouteDistinguisher.make_from_elements('20.20.20.20', 200)
        etag = EthernetTag.make_etag(2000)
        ip = IP.create('192.168.1.1')

        route = Multicast(rd, etag, ip)
        str_repr = str(route)

        assert '20.20.20.20:200' in str_repr
        assert '192.168.1.1' in str_repr

    def test_multicast_json(self) -> None:
        """Test JSON serialization of Multicast route"""
        rd = RouteDistinguisher.make_from_elements('21.21.21.21', 210)
        etag = EthernetTag.make_etag(2100)
        ip = IP.create('10.1.1.1')

        route = Multicast(rd, etag, ip)
        json_str = route.json()

        assert '"code": 3' in json_str
        assert '"name": "Inclusive Multicast Ethernet Tag"' in json_str
        assert '"ip": "10.1.1.1"' in json_str


# ============================================================================
# EVPN Route Type 4: Ethernet Segment (EthernetSegment)
# ============================================================================


class TestEthernetSegment:
    """Tests for EVPN Route Type 4: Ethernet Segment"""

    def test_segment_creation_ipv4(self) -> None:
        """Test creation of EthernetSegment route with IPv4"""
        rd = RouteDistinguisher.make_from_elements('22.22.22.22', 220)
        esi = ESI(bytes([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
        ip = IP.create('192.168.1.1')

        route = EthernetSegment(rd, esi, ip)

        assert route.CODE == 4
        assert route.NAME == 'Ethernet Segment'
        assert route.rd == rd
        assert route.esi == esi
        assert route.ip == ip

    def test_segment_creation_ipv6(self) -> None:
        """Test creation of EthernetSegment route with IPv6"""
        rd = RouteDistinguisher.make_from_elements('23.23.23.23', 230)
        esi = ESI(bytes([10, 9, 8, 7, 6, 5, 4, 3, 2, 1]))
        ip = IP.create('2001:db8::1')

        route = EthernetSegment(rd, esi, ip)

        assert route.CODE == 4
        assert route.ip == ip

    def test_segment_pack_unpack_ipv4(self) -> None:
        """Test pack/unpack roundtrip for EthernetSegment with IPv4"""
        rd = RouteDistinguisher.make_from_elements('24.24.24.24', 240)
        esi = ESI(bytes([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
        ip = IP.create('10.0.0.1')

        route = EthernetSegment(rd, esi, ip)
        packed = route.pack_nlri(create_negotiated())

        unpacked, leftover = EVPN.unpack_nlri(AFI.l2vpn, SAFI.evpn, packed, Action.UNSET, None, create_negotiated())

        assert len(leftover) == 0
        assert isinstance(unpacked, EthernetSegment)
        assert unpacked.rd._str() == rd._str()
        assert unpacked.ip == ip

    def test_segment_pack_unpack_ipv6(self) -> None:
        """Test pack/unpack roundtrip for EthernetSegment with IPv6"""
        rd = RouteDistinguisher.make_from_elements('25.25.25.25', 250)
        esi = ESI(bytes([5, 5, 5, 5, 5, 5, 5, 5, 5, 5]))
        ip = IP.create('fe80::1')

        route = EthernetSegment(rd, esi, ip)
        packed = route.pack_nlri(create_negotiated())

        unpacked, leftover = EVPN.unpack_nlri(AFI.l2vpn, SAFI.evpn, packed, Action.UNSET, None, create_negotiated())

        assert len(leftover) == 0
        assert isinstance(unpacked, EthernetSegment)
        assert unpacked.rd._str() == rd._str()
        assert unpacked.ip == ip

    def test_segment_equality(self) -> None:
        """Test equality comparison for EthernetSegment routes"""
        rd = RouteDistinguisher.make_from_elements('26.26.26.26', 260)
        ip = IP.create('192.168.1.1')

        route1 = EthernetSegment(rd, ESI.make_default(), ip)
        route2 = EthernetSegment(rd, ESI(bytes([1] * 10)), ip)

        # ESI should not affect equality
        assert route1 == route2

    def test_segment_hash_consistency(self) -> None:
        """Test hash consistency - ESI should not affect hash"""
        rd = RouteDistinguisher.make_from_elements('27.27.27.27', 270)
        ip = IP.create('10.0.0.1')

        route1 = EthernetSegment(rd, ESI.make_default(), ip)
        route2 = EthernetSegment(rd, ESI(bytes([1] * 10)), ip)

        assert hash(route1) == hash(route2)

    def test_segment_invalid_iplen(self) -> None:
        """Test that invalid IP length raises error"""
        rd = RouteDistinguisher.make_from_elements('28.28.28.28', 280)
        esi = ESI.make_default()

        # Create packed data with invalid IP length
        packed = rd.pack_rd() + esi.pack_esi() + bytes([64])  # Invalid: not 32 or 128

        with pytest.raises(Notify):
            EthernetSegment.unpack_evpn_route(packed + bytes([0] * 8))

    def test_segment_string_representation(self) -> None:
        """Test string representation of EthernetSegment route"""
        rd = RouteDistinguisher.make_from_elements('29.29.29.29', 290)
        esi = ESI.make_default()
        ip = IP.create('192.168.1.1')

        route = EthernetSegment(rd, esi, ip)
        str_repr = str(route)

        assert '29.29.29.29:290' in str_repr
        assert '192.168.1.1' in str_repr

    def test_segment_json(self) -> None:
        """Test JSON serialization of EthernetSegment route"""
        rd = RouteDistinguisher.make_from_elements('30.30.30.30', 300)
        esi = ESI.make_default()
        ip = IP.create('10.1.1.1')

        route = EthernetSegment(rd, esi, ip)
        json_str = route.json()

        assert '"code": 4' in json_str
        assert '"name": "Ethernet Segment"' in json_str
        assert '"ip": "10.1.1.1"' in json_str


# ============================================================================
# EVPN Route Type 5: IP Prefix Advertisement (Prefix)
# ============================================================================


class TestPrefix:
    """Tests for EVPN Route Type 5: IP Prefix Advertisement"""

    def test_prefix_creation_ipv4(self) -> None:
        """Test creation of Prefix route with IPv4"""
        rd = RouteDistinguisher.make_from_elements('31.31.31.31', 310)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(3100)
        label = Labels.make_labels([3200], True)
        ip = IP.create('10.1.1.0')
        iplen = 24
        gwip = IP.create('10.1.1.1')

        route = Prefix(rd, esi, etag, label, ip, iplen, gwip)

        assert route.CODE == 5
        assert route.NAME == 'IP Prefix Advertisement'
        assert route.rd == rd
        assert route.ip == ip
        assert route.iplen == iplen
        assert route.gwip == gwip

    def test_prefix_creation_ipv6(self) -> None:
        """Test creation of Prefix route with IPv6"""
        rd = RouteDistinguisher.make_from_elements('32.32.32.32', 320)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(3200)
        label = Labels.make_labels([3300], True)
        ip = IP.create('2001:db8::')
        iplen = 64
        gwip = IP.create('2001:db8::1')

        route = Prefix(rd, esi, etag, label, ip, iplen, gwip)

        assert route.CODE == 5
        assert route.ip == ip
        assert route.iplen == iplen

    def test_prefix_pack_unpack_ipv4(self) -> None:
        """Test pack/unpack roundtrip for Prefix route with IPv4"""
        rd = RouteDistinguisher.make_from_elements('33.33.33.33', 330)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(3300)
        label = Labels.make_labels([3400], True)
        ip = IP.create('192.168.1.0')
        iplen = 24
        gwip = IP.create('192.168.1.1')

        route = Prefix(rd, esi, etag, label, ip, iplen, gwip)
        packed = route.pack_nlri(create_negotiated())

        unpacked, leftover = EVPN.unpack_nlri(AFI.l2vpn, SAFI.evpn, packed, Action.UNSET, None, create_negotiated())

        assert len(leftover) == 0
        assert isinstance(unpacked, Prefix)
        assert unpacked.rd._str() == rd._str()
        assert unpacked.ip == ip
        assert unpacked.iplen == iplen
        assert unpacked.gwip == gwip

    def test_prefix_pack_unpack_ipv6(self) -> None:
        """Test pack/unpack roundtrip for Prefix route with IPv6"""
        rd = RouteDistinguisher.make_from_elements('34.34.34.34', 340)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(3400)
        label = Labels.make_labels([3500], True)
        ip = IP.create('2001:db8:1::')
        iplen = 48
        gwip = IP.create('2001:db8:1::1')

        route = Prefix(rd, esi, etag, label, ip, iplen, gwip)
        packed = route.pack_nlri(create_negotiated())

        unpacked, leftover = EVPN.unpack_nlri(AFI.l2vpn, SAFI.evpn, packed, Action.UNSET, None, create_negotiated())

        assert len(leftover) == 0
        assert isinstance(unpacked, Prefix)
        assert unpacked.rd._str() == rd._str()
        assert unpacked.ip == ip
        assert unpacked.iplen == iplen
        assert unpacked.gwip == gwip

    def test_prefix_equality(self) -> None:
        """Test equality comparison for Prefix routes"""
        rd = RouteDistinguisher.make_from_elements('35.35.35.35', 350)
        etag = EthernetTag.make_etag(3500)
        ip = IP.create('10.1.1.0')
        iplen = 24
        label = Labels.make_labels([100], True)
        gwip = IP.create('10.1.1.1')

        # Create two identical routes
        route1 = Prefix(rd, ESI.make_default(), etag, label, ip, iplen, gwip)
        route2 = Prefix(rd, ESI.make_default(), etag, label, ip, iplen, gwip)

        # Routes should be equal when all parameters match
        assert route1 == route2

        # Test that different gwip makes them unequal (via NLRI.index())
        route3 = Prefix(rd, ESI.make_default(), etag, label, ip, iplen, IP.create('10.1.1.2'))
        assert route1 != route3

    def test_prefix_hash_consistency(self) -> None:
        """Test hash consistency - ESI, label, and gwip should not affect hash"""
        rd = RouteDistinguisher.make_from_elements('36.36.36.36', 360)
        etag = EthernetTag.make_etag(3600)
        ip = IP.create('10.2.2.0')
        iplen = 24

        route1 = Prefix(rd, ESI.make_default(), etag, Labels.make_labels([100], True), ip, iplen, IP.create('10.2.2.1'))
        route2 = Prefix(
            rd, ESI(bytes([1] * 10)), etag, Labels.make_labels([200], True), ip, iplen, IP.create('10.2.2.2')
        )

        assert hash(route1) == hash(route2)

    def test_prefix_string_representation(self) -> None:
        """Test string representation of Prefix route"""
        rd = RouteDistinguisher.make_from_elements('37.37.37.37', 370)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(3700)
        label = Labels.make_labels([3800], True)
        ip = IP.create('10.3.3.0')
        iplen = 24
        gwip = IP.create('10.3.3.1')

        route = Prefix(rd, esi, etag, label, ip, iplen, gwip)
        str_repr = str(route)

        assert '37.37.37.37:370' in str_repr
        assert '10.3.3.0' in str_repr
        assert '/24' in str_repr

    def test_prefix_json(self) -> None:
        """Test JSON serialization of Prefix route"""
        rd = RouteDistinguisher.make_from_elements('38.38.38.38', 380)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(3800)
        label = Labels.make_labels([3900], True)
        ip = IP.create('10.4.4.0')
        iplen = 24
        gwip = IP.create('10.4.4.1')

        route = Prefix(rd, esi, etag, label, ip, iplen, gwip)
        json_str = route.json()

        assert '"code": 5' in json_str
        assert '"name": "IP Prefix Advertisement"' in json_str
        assert '"ip": "10.4.4.0"' in json_str
        assert '"iplen": 24' in json_str
        assert '"gateway": "10.4.4.1"' in json_str


# ============================================================================
# EVPN NLRI Integration Tests
# ============================================================================


class TestEVPNIntegration:
    """Integration tests for EVPN NLRI parsing and handling"""

    def test_evpn_route_type_codes(self) -> None:
        """Test that all EVPN route types have correct CODE values"""
        assert EthernetAD.CODE == 1
        assert MAC.CODE == 2
        assert Multicast.CODE == 3
        assert EthernetSegment.CODE == 4
        assert Prefix.CODE == 5

    def test_evpn_route_type_names(self) -> None:
        """Test that all EVPN route types have descriptive names"""
        assert EthernetAD.NAME == 'Ethernet Auto-Discovery'
        assert MAC.NAME == 'MAC/IP advertisement'
        assert Multicast.NAME == 'Inclusive Multicast Ethernet Tag'
        assert EthernetSegment.NAME == 'Ethernet Segment'
        assert Prefix.NAME == 'IP Prefix Advertisement'

    def test_evpn_multiple_labels(self) -> None:
        """Test handling of multiple MPLS labels"""
        rd = RouteDistinguisher.make_from_elements('39.39.39.39', 390)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(3900)
        labels = Labels.make_labels([100, 200], True)

        route = EthernetAD(rd, esi, etag, labels)

        assert len(route.label.labels) == 2
        assert route.label.labels[0] == 100
        assert route.label.labels[1] == 200

    def test_evpn_nolabel(self) -> None:
        """Test handling of routes with no labels"""
        rd = RouteDistinguisher.make_from_elements('40.40.40.40', 400)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(4000)

        route = EthernetAD(rd, esi, etag, None)

        assert route.label == Labels.NOLABEL

    def test_prefix_different_iplen_values(self) -> None:
        """Test Prefix routes with different prefix lengths"""
        rd = RouteDistinguisher.make_from_elements('41.41.41.41', 410)
        esi = ESI.make_default()
        etag = EthernetTag.make_etag(4100)
        label = Labels.make_labels([4200], True)
        gwip = IP.create('10.5.5.1')

        for iplen in [8, 16, 24, 32]:
            ip = IP.create('10.5.5.0')
            route = Prefix(rd, esi, etag, label, ip, iplen, gwip)
            assert route.iplen == iplen

    def test_evpn_with_addpath(self) -> None:
        """Test EVPN routes with ADD-PATH support via unpack_nlri"""
        rd = RouteDistinguisher.make_from_elements('42.42.42.42', 420)
        etag = EthernetTag.make_etag(4200)
        ip = IP.create('192.168.1.1')

        route = Multicast(rd, etag, ip)
        packed = route.pack_nlri(create_negotiated())

        # addpath is set during unpacking
        unpacked, leftover = EVPN.unpack_nlri(AFI.l2vpn, SAFI.evpn, packed, Action.UNSET, 12345, create_negotiated())

        assert len(leftover) == 0
        # addpath is stored during unpack_nlri
        assert hasattr(unpacked, 'addpath')

    def test_evpn_with_nexthop(self) -> None:
        """Test EVPN routes with next hop"""
        rd = RouteDistinguisher.make_from_elements('43.43.43.43', 430)
        etag = EthernetTag.make_etag(4300)
        ip = IP.create('192.168.1.1')
        nexthop = IP.create('192.168.1.254')

        route = Multicast(rd, etag, ip, nexthop=nexthop)

        assert route.nexthop == nexthop
