"""Comprehensive tests for BGP Community attributes.

These tests cover all three types of BGP communities:
1. Standard Communities (RFC 1997)
2. Extended Communities (RFC 4360, RFC 7153)
3. Large Communities (RFC 8092)

Test Coverage:
Phase 1: Standard Communities (tests 1-4)
  - Basic parsing and well-known communities
  - Multiple communities handling
  - Malformed data handling

Phase 2: Extended Communities - Route Target (tests 5-10)
  - RouteTargetASN2Number (Type 0x00)
  - RouteTargetIPNumber (Type 0x01)
  - RouteTargetASN4Number (Type 0x02)
  - Transitive flag handling

Phase 3: Extended Communities - Other Types (tests 11-22)
  - Route Origin
  - Bandwidth (Link Bandwidth)
  - Encapsulation (RFC 5512)
  - Traffic Engineering
  - L2 Info
  - MAC Mobility
  - FlowSpec Scope
  - MUP (Mobile User Plane)
  - Route Target Record

Phase 4: Large Communities (tests 23-26)
  - Basic parsing (RFC 8092)
  - Multiple large communities
  - Max size validation
  - Malformed data handling

Phase 5: Mixed Community Types (tests 27-30)
  - Multiple community types in one UPDATE
  - Community ordering
  - Community filtering
  - Set operations
"""

import struct
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.negotiated import Negotiated


def create_negotiated() -> Negotiated:
    """Create a Negotiated object with a mock neighbor for testing."""
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    return Negotiated(neighbor, Direction.OUT)


@pytest.fixture(autouse=True)
def mock_logger() -> Any:
    """Mock the logger to avoid initialization issues."""
    from exabgp.logger.option import option

    # Save original values
    original_logger = option.logger
    original_formater = option.formater

    # Create a mock logger with all required methods
    mock_option_logger = Mock()
    mock_option_logger.debug = Mock()
    mock_option_logger.info = Mock()
    mock_option_logger.warning = Mock()
    mock_option_logger.error = Mock()
    mock_option_logger.critical = Mock()

    # Create a mock formater that accepts all arguments
    mock_formater = Mock(return_value='formatted message')

    option.logger = mock_option_logger
    option.formater = mock_formater

    yield

    # Restore original values
    option.logger = original_logger
    option.formater = original_formater


# ==============================================================================
# Phase 1: Standard Communities (RFC 1997)
# ==============================================================================


def test_standard_community_parsing() -> None:
    """Test basic standard community parsing.

    Standard communities are 4 bytes: 2-byte ASN + 2-byte value.
    Format: ASN:VALUE (e.g., 65000:100)
    """
    from exabgp.bgp.message.update.attribute.community import Community

    # Create standard community: ASN 65000, value 100
    community_bytes = struct.pack('!HH', 65000, 100)
    community = Community(community_bytes)

    # Verify parsing
    assert len(community) == 4
    assert str(community) == '65000:100'

    # Verify pack round-trip
    negotiated = create_negotiated()
    assert community.pack_attribute(negotiated) == community_bytes


def test_standard_community_well_known() -> None:
    """Test well-known standard communities.

    Well-known communities (RFC 1997):
    - NO_EXPORT (0xFFFFFF01): Don't advertise to EBGP peers
    - NO_ADVERTISE (0xFFFFFF02): Don't advertise to any peer
    - NO_EXPORT_SUBCONFED (0xFFFFFF03): Don't advertise outside confederation
    - NO_PEER (0xFFFFFF04): Don't advertise to peers (RFC 3765)
    - BLACKHOLE (0xFFFF029A): Blackhole traffic (RFC 7999)
    """
    from exabgp.bgp.message.update.attribute.community import Community

    # Test NO_EXPORT
    no_export = Community(Community.NO_EXPORT)
    assert str(no_export) == 'no-export'
    assert len(no_export) == 4

    # Test NO_ADVERTISE
    no_advertise = Community(Community.NO_ADVERTISE)
    assert str(no_advertise) == 'no-advertise'

    # Test NO_EXPORT_SUBCONFED
    no_export_subconfed = Community(Community.NO_EXPORT_SUBCONFED)
    assert str(no_export_subconfed) == 'no-export-subconfed'

    # Test NO_PEER
    no_peer = Community(Community.NO_PEER)
    assert str(no_peer) == 'no-peer'

    # Test BLACKHOLE
    blackhole = Community(Community.BLACKHOLE)
    assert str(blackhole) == 'blackhole'

    # Verify caching works for well-known communities
    cached = Community.cached(Community.NO_EXPORT)
    assert cached is Community.cache[Community.NO_EXPORT]


def test_standard_community_multiple() -> None:
    """Test multiple standard communities in one attribute.

    The COMMUNITIES attribute can contain multiple 4-byte communities.
    """
    from exabgp.bgp.message.update.attribute.community import Community, Communities

    # Create multiple communities
    comm1_bytes = struct.pack('!HH', 65000, 100)
    comm2_bytes = struct.pack('!HH', 65001, 200)
    comm3_bytes = Community.NO_EXPORT

    comm1 = Community(comm1_bytes)
    comm2 = Community(comm2_bytes)
    comm3 = Community(comm3_bytes)

    # Create Communities attribute (collection)
    communities = Communities([comm1, comm2, comm3])

    # Verify all communities are present
    assert len(communities.communities) == 3
    assert comm1 in communities.communities
    assert comm2 in communities.communities
    assert comm3 in communities.communities


def test_standard_community_malformed() -> None:
    """Test handling of malformed standard community data.

    Test cases:
    - Truncated community (< 4 bytes)
    - Invalid community values
    """
    from exabgp.bgp.message.update.attribute.community import Community

    # Test with truncated data (2 bytes instead of 4)
    truncated = struct.pack('!H', 65000)
    with pytest.raises((struct.error, ValueError)):
        # This should fail because we can't unpack 2 bytes as !HH
        Community(truncated)

    # Test with valid but extreme values
    max_community = struct.pack('!HH', 0xFFFF, 0xFFFF)
    community = Community(max_community)
    assert len(community) == 4
    # Should parse as 65535:65535


# ==============================================================================
# Phase 2: Extended Communities - Route Target (RFC 4360, RFC 7153)
# ==============================================================================


def test_route_target_asn2_number() -> None:
    """Test Route Target with 2-byte ASN.

    Type 0x00, Subtype 0x02: 2-byte ASN + 4-byte number
    Format: target:ASN:NUMBER (e.g., target:65000:100)
    Most common RT format in MPLS VPNs.
    """
    from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetASN2Number
    from exabgp.bgp.message.open.asn import ASN

    negotiated = create_negotiated()
    # Create RT with 2-byte ASN
    asn = ASN(65000)
    number = 100
    rt = RouteTargetASN2Number(asn, number, transitive=True)

    # Verify representation
    assert str(rt) == 'target:65000:100'
    assert len(rt) == 8

    # Verify pack/unpack round-trip
    packed = rt.pack_attribute(negotiated)
    assert len(packed) == 8

    # Verify type and subtype
    assert (packed[0] & 0x0F) == 0x00  # Type 0x00
    assert packed[1] == 0x02  # Subtype 0x02

    # Unpack and verify
    unpacked = RouteTargetASN2Number.unpack_attribute(packed, None)  # type: ignore[arg-type]
    assert unpacked.asn == asn
    assert unpacked.number == number


def test_route_target_ip_number() -> None:
    """Test Route Target with IPv4 address.

    Type 0x01, Subtype 0x02: IPv4 address + 2-byte number
    Format: target:IP:NUMBER (e.g., target:192.0.2.1:100)
    Used when RT is based on router ID.
    """
    from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetIPNumber

    negotiated = create_negotiated()
    # Create RT with IPv4 address
    ip = '192.0.2.1'
    number = 100
    rt = RouteTargetIPNumber(ip, number, transitive=True)

    # Verify representation
    assert str(rt) == 'target:192.0.2.1:100'
    assert len(rt) == 8

    # Verify pack/unpack round-trip
    packed = rt.pack_attribute(negotiated)
    assert len(packed) == 8

    # Verify type and subtype
    assert (packed[0] & 0x0F) == 0x01  # Type 0x01
    assert packed[1] == 0x02  # Subtype 0x02

    # Unpack and verify
    unpacked = RouteTargetIPNumber.unpack_attribute(packed, None)  # type: ignore[arg-type]
    assert str(unpacked.ip) == ip
    assert unpacked.number == number


def test_route_target_asn4_number() -> None:
    """Test Route Target with 4-byte ASN.

    Type 0x02, Subtype 0x02: 4-byte ASN + 2-byte number
    Format: target:ASN:NUMBER (e.g., target:4200000000:100)
    Required for ASNs > 65535 (RFC 6793).
    """
    from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetASN4Number
    from exabgp.bgp.message.open.asn import ASN

    negotiated = create_negotiated()
    # Create RT with 4-byte ASN (>65535)
    asn = ASN(4200000000)
    number = 100
    rt = RouteTargetASN4Number(asn, number, transitive=True)

    # Verify representation
    assert str(rt) == 'target:4200000000:100'
    assert len(rt) == 8

    # Verify pack/unpack round-trip
    packed = rt.pack_attribute(negotiated)
    assert len(packed) == 8

    # Verify type and subtype
    assert (packed[0] & 0x0F) == 0x02  # Type 0x02
    assert packed[1] == 0x02  # Subtype 0x02

    # Unpack and verify
    unpacked = RouteTargetASN4Number.unpack_attribute(packed, None)  # type: ignore[arg-type]
    assert unpacked.asn == asn
    assert unpacked.number == number


def test_route_target_transitive_flag() -> None:
    """Test Route Target transitive flag handling.

    Extended communities have a transitive bit (bit 6):
    - 0: Transitive across ASes
    - 1: Non-transitive across ASes
    """
    from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetASN2Number
    from exabgp.bgp.message.open.asn import ASN

    negotiated = create_negotiated()
    # Create transitive RT
    rt_transitive = RouteTargetASN2Number(ASN(65000), 100, transitive=True)
    packed_trans = rt_transitive.pack_attribute(negotiated)
    # Transitive: bit 6 should be 0
    assert (packed_trans[0] & 0x40) == 0x00

    # Create non-transitive RT
    rt_non_transitive = RouteTargetASN2Number(ASN(65000), 100, transitive=False)
    packed_non_trans = rt_non_transitive.pack_attribute(negotiated)
    # Non-transitive: bit 6 should be 1
    assert (packed_non_trans[0] & 0x40) == 0x40


def test_extended_community_base_parsing() -> None:
    """Test base ExtendedCommunity parsing with unknown types.

    Unknown extended community types should still parse correctly,
    storing raw bytes for future processing.
    """
    from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

    negotiated = create_negotiated()
    # Create unknown extended community type
    # Type 0x0F (unknown), Subtype 0xFF (unknown)
    unknown_data = struct.pack('!BB', 0x0F, 0xFF) + b'\x00\x01\x02\x03\x04\x05'

    ec = ExtendedCommunity.unpack_attribute(unknown_data, None)  # type: ignore[arg-type]

    # Should store raw bytes
    assert len(ec) == 8
    assert ec.pack_attribute(negotiated) == unknown_data

    # Verify transitive check
    assert ec.transitive()  # bit 6 is 0


# ==============================================================================
# Phase 3: Extended Communities - Other Types
# ==============================================================================


def test_route_origin_community() -> None:
    """Test Route Origin extended community.

    Similar to Route Target but indicates route origin.
    Used in MPLS VPNs to mark route source.
    """
    from exabgp.bgp.message.update.attribute.community.extended.origin import OriginASN4Number
    from exabgp.bgp.message.open.asn import ASN

    negotiated = create_negotiated()
    # Create Route Origin
    asn = ASN(65000)
    number = 200
    ro = OriginASN4Number(asn, number, transitive=True)

    # Verify representation
    assert str(ro) == 'origin:65000:200'
    assert len(ro) == 8

    # Verify subtype (0x03 for origin vs 0x02 for target)
    packed = ro.pack_attribute(negotiated)
    assert packed[1] == 0x03


def test_bandwidth_community() -> None:
    """Test Link Bandwidth extended community.

    draft-ietf-idr-link-bandwidth-06
    Type 0x40, Subtype 0x04
    Contains 2-byte ASN + 4-byte float bandwidth (bytes/sec)
    """
    from exabgp.bgp.message.update.attribute.community.extended.bandwidth import Bandwidth

    negotiated = create_negotiated()
    # Create bandwidth community: ASN 65000, 1 Gbps = 125000000 bytes/sec
    asn = 65000
    speed = 125000000.0
    bw = Bandwidth(asn, speed)

    # Verify representation
    assert 'bandwith' in str(bw).lower()  # Note: typo in original code
    assert len(bw) == 8

    # Verify pack/unpack
    packed = bw.pack_attribute(negotiated)
    # Bandwidth.pack_attribute(negotiated) returns only the data (ASN + float), not full extended community
    assert len(packed) == 6

    # Unpack requires type/subtype prefix
    full_data = struct.pack('!BB', 0x40, 0x04) + packed
    unpacked = Bandwidth.unpack_attribute(full_data, create_negotiated())
    assert unpacked.asn == asn
    # Float comparison with small tolerance
    assert abs(unpacked.speed - speed) < 1.0


def test_encapsulation_community_vxlan() -> None:
    """Test Encapsulation extended community with VXLAN.

    RFC 5512: Tunnel Encapsulation Attribute
    Type 0x03, Subtype 0x0C
    Indicates tunnel type for NVO3/overlay networks.
    """
    from exabgp.bgp.message.update.attribute.community.extended.encapsulation import Encapsulation

    negotiated = create_negotiated()
    # Create VXLAN encapsulation
    encap = Encapsulation(Encapsulation.Type.VXLAN)

    # Verify representation
    assert str(encap) == 'encap:VXLAN'
    assert len(encap) == 8

    # Verify pack/unpack
    packed = encap.pack_attribute(negotiated)
    assert len(packed) == 8

    # Verify type and subtype
    assert packed[0] == 0x03
    assert packed[1] == 0x0C

    # Unpack and verify
    unpacked = Encapsulation.unpack_attribute(packed)
    assert unpacked.tunnel_type == Encapsulation.Type.VXLAN


def test_encapsulation_community_types() -> None:
    """Test various encapsulation types.

    IANA registry tunnel types:
    - GRE, IPIP, VXLAN, NVGRE, MPLS, etc.
    """
    from exabgp.bgp.message.update.attribute.community.extended.encapsulation import Encapsulation

    negotiated = create_negotiated()
    test_cases = [
        (Encapsulation.Type.GRE, 'encap:GRE'),
        (Encapsulation.Type.IPIP, 'encap:IP-in-IP'),
        (Encapsulation.Type.VXLAN, 'encap:VXLAN'),
        (Encapsulation.Type.MPLS, 'encap:MPLS'),
        (Encapsulation.Type.VXLAN_GPE, 'encap:VXLAN-GPE'),
    ]

    for tunnel_type, expected_str in test_cases:
        encap = Encapsulation(tunnel_type)
        assert str(encap) == expected_str

        # Verify round-trip
        packed = encap.pack_attribute(negotiated)
        unpacked = Encapsulation.unpack_attribute(packed)
        assert unpacked.tunnel_type == tunnel_type


def test_traffic_engineering_community() -> None:
    """Test Traffic Engineering extended community.

    Used for QoS and traffic engineering policies.
    """
    from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRate

    negotiated = create_negotiated()
    # Create traffic rate community
    # ASN 0 + 4-byte float rate (bytes/sec)
    asn = 0
    rate = 1000000.0  # 1 Mbps
    tr = TrafficRate(asn, rate)

    # Verify basic properties
    assert len(tr) == 8

    # Verify pack
    packed = tr.pack_attribute(negotiated)
    assert len(packed) == 8


def test_l2info_community() -> None:
    """Test L2 Info extended community.

    Used in EVPN for L2 attributes (MTU, etc.).
    """
    from exabgp.bgp.message.update.attribute.community.extended.l2info import L2Info

    negotiated = create_negotiated()
    # Create L2Info with common parameters
    # control_flags, mtu, reserved
    control = 0
    mtu = 1500
    reserved = 0

    encaps = 1
    l2info = L2Info(encaps, control, mtu, reserved)

    # Verify basic properties
    assert len(l2info) == 8
    assert l2info.mtu == mtu

    # Verify pack/unpack
    packed = l2info.pack_attribute(negotiated)
    unpacked = L2Info.unpack_attribute(packed, create_negotiated())
    assert unpacked.mtu == mtu


def test_mac_mobility_community() -> None:
    """Test MAC Mobility extended community.

    RFC 7432: Used in EVPN for MAC mobility tracking.
    Sequence number indicates how many times MAC has moved.
    """
    from exabgp.bgp.message.update.attribute.community.extended.mac_mobility import MacMobility

    negotiated = create_negotiated()
    # Create MAC mobility with sequence number
    flags = 0x01  # Static flag
    sequence = 5

    mac_mob = MacMobility(sequence, sticky=bool(flags))

    # Verify basic properties
    assert len(mac_mob) == 8
    assert mac_mob.sequence == sequence
    assert mac_mob.sticky == bool(flags)

    # Verify pack/unpack
    packed = mac_mob.pack_attribute(negotiated)
    unpacked = MacMobility.unpack_attribute(packed, create_negotiated())
    assert unpacked.sequence == sequence


def test_flowspec_redirect_community() -> None:
    """Test FlowSpec redirect extended community.

    Used with FlowSpec to redirect matching traffic to VRF.
    """
    from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetASN2Number
    from exabgp.bgp.message.open.asn import ASN

    # FlowSpec redirect uses Route Target format
    # Redirect to VRF identified by RT
    asn = ASN(65000)
    vrf_id = 999

    redirect = RouteTargetASN2Number(asn, vrf_id, transitive=True)

    # Verify it's a valid RT that can be used for redirect
    assert len(redirect) == 8
    assert str(redirect) == 'target:65000:999'


def test_rt_record_community() -> None:
    """Test Route Target Record extended community.

    RFC 4684: Records Route Targets in path.
    """
    from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetASN2Number

    # Create RT Record - format similar to Route Target
    data = struct.pack('!BB', 0x00, 0x13) + struct.pack('!HL', 65000, 100)

    rt_record = RouteTargetASN2Number.unpack_attribute(data, None)  # type: ignore[arg-type]

    # Verify basic properties
    assert len(rt_record) == 8


def test_mup_community() -> None:
    """Test MUP (Mobile User Plane) extended community.

    Recent draft for 5G mobile networks.
    """
    from exabgp.bgp.message.update.attribute.community.extended.mup import MUPExtendedCommunity

    # Create MUP community
    # Architecture Segment Identifier (ASI) and Segment Identifier (SI)
    sgid2 = 100
    sgid4 = 200
    mup = MUPExtendedCommunity(sgid2, sgid4, transitive=True)

    # Verify basic properties
    assert len(mup) == 8
    assert str(mup) == 'mup:100:200'


# ==============================================================================
# Phase 4: Large Communities (RFC 8092)
# ==============================================================================


def test_large_community_parsing() -> None:
    """Test Large Community basic parsing.

    RFC 8092: 12-byte communities (3 x 4-byte values)
    Format: GA:LD1:LD2
    - Global Administrator (4 bytes): Usually ASN
    - Local Data Part 1 (4 bytes): Operator defined
    - Local Data Part 2 (4 bytes): Operator defined
    """
    from exabgp.bgp.message.update.attribute.community.large.community import LargeCommunity

    negotiated = create_negotiated()
    # Create large community: 65000:100:200
    ga = 65000
    ld1 = 100
    ld2 = 200
    large_bytes = struct.pack('!LLL', ga, ld1, ld2)

    lc = LargeCommunity(large_bytes)

    # Verify parsing
    assert len(lc) == 12
    assert str(lc) == '65000:100:200'

    # Verify pack round-trip
    assert lc.pack_attribute(negotiated) == large_bytes


def test_large_community_multiple() -> None:
    """Test multiple Large Communities.

    LARGE_COMMUNITIES attribute can contain multiple 12-byte values.
    """
    from exabgp.bgp.message.update.attribute.community.large.community import LargeCommunity
    from exabgp.bgp.message.update.attribute.community.large.communities import LargeCommunities

    # Create multiple large communities
    lc1_bytes = struct.pack('!LLL', 65000, 100, 200)
    lc2_bytes = struct.pack('!LLL', 65001, 300, 400)
    lc3_bytes = struct.pack('!LLL', 4200000000, 500, 600)  # 4-byte ASN

    lc1 = LargeCommunity(lc1_bytes)
    lc2 = LargeCommunity(lc2_bytes)
    lc3 = LargeCommunity(lc3_bytes)

    # Create LargeCommunities attribute
    large_communities = LargeCommunities([lc1, lc2, lc3])

    # Verify all communities are present
    assert len(large_communities.communities) == 3


def test_large_community_max_values() -> None:
    """Test Large Community with maximum values.

    All three fields are 32-bit unsigned integers.
    Max value: 4294967295 (0xFFFFFFFF)
    """
    from exabgp.bgp.message.update.attribute.community.large.community import LargeCommunity

    # Create with max values
    max_val = 0xFFFFFFFF
    large_bytes = struct.pack('!LLL', max_val, max_val, max_val)

    lc = LargeCommunity(large_bytes)

    # Verify parsing
    assert len(lc) == 12
    assert str(lc) == f'{max_val}:{max_val}:{max_val}'


def test_large_community_malformed() -> None:
    """Test handling of malformed Large Community data.

    Large communities must be exactly 12 bytes.
    """
    from exabgp.bgp.message.update.attribute.community.large.community import LargeCommunity

    # Test with truncated data (8 bytes instead of 12)
    truncated = struct.pack('!LL', 65000, 100)
    with pytest.raises((struct.error, ValueError)):
        LargeCommunity(truncated)

    # Test with valid 12-byte data
    valid = struct.pack('!LLL', 65000, 100, 200)
    lc = LargeCommunity(valid)
    assert len(lc) == 12


# ==============================================================================
# Phase 5: Mixed Community Types and Operations
# ==============================================================================


def test_mixed_community_types() -> None:
    """Test handling multiple community attribute types together.

    A BGP UPDATE can contain:
    - COMMUNITIES (standard)
    - EXTENDED_COMMUNITIES
    - LARGE_COMMUNITIES
    All in the same message.
    """
    from exabgp.bgp.message.update.attribute.community import Community, Communities
    from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetASN2Number
    from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunities
    from exabgp.bgp.message.update.attribute.community.large.community import LargeCommunity
    from exabgp.bgp.message.update.attribute.community.large.communities import LargeCommunities
    from exabgp.bgp.message.open.asn import ASN

    # Create standard communities
    std_comm1 = Community(struct.pack('!HH', 65000, 100))
    std_comm2 = Community(Community.NO_EXPORT)
    std_communities = Communities([std_comm1, std_comm2])

    # Create extended communities
    ext_comm1 = RouteTargetASN2Number(ASN(65000), 200, transitive=True)
    ext_communities = ExtendedCommunities([ext_comm1])

    # Create large communities
    large_comm1 = LargeCommunity(struct.pack('!LLL', 65000, 300, 400))
    large_communities = LargeCommunities([large_comm1])

    # Verify all types parse correctly
    assert len(std_communities.communities) == 2
    assert len(ext_communities.communities) == 1
    assert len(large_communities.communities) == 1


def test_community_ordering() -> None:
    """Test that communities maintain order and can be sorted.

    Communities should be comparable for sorting/ordering.
    """
    from exabgp.bgp.message.update.attribute.community import Community

    # Create communities with different values
    comm1 = Community(struct.pack('!HH', 65000, 100))
    comm2 = Community(struct.pack('!HH', 65000, 200))
    comm3 = Community(struct.pack('!HH', 65001, 100))

    # Test comparisons
    assert comm1 < comm2
    assert comm1 < comm3
    assert comm2 > comm1

    # Test sorting
    communities = [comm3, comm1, comm2]
    sorted_communities = sorted(communities)
    assert sorted_communities[0] == comm1
    assert sorted_communities[1] == comm2
    assert sorted_communities[2] == comm3


def test_community_equality() -> None:
    """Test community equality and hashing.

    Same community values should be equal and hash identically.
    """
    from exabgp.bgp.message.update.attribute.community import Community
    from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetASN2Number
    from exabgp.bgp.message.open.asn import ASN

    # Standard communities
    comm1a = Community(struct.pack('!HH', 65000, 100))
    comm1b = Community(struct.pack('!HH', 65000, 100))
    comm2 = Community(struct.pack('!HH', 65000, 200))

    assert comm1a == comm1b
    assert comm1a != comm2

    # Extended communities
    rt1a = RouteTargetASN2Number(ASN(65000), 100, transitive=True)
    rt1b = RouteTargetASN2Number(ASN(65000), 100, transitive=True)
    rt2 = RouteTargetASN2Number(ASN(65000), 200, transitive=True)

    assert rt1a == rt1b
    assert rt1a != rt2

    # Hash equality
    assert hash(rt1a) == hash(rt1b)
    assert hash(rt1a) != hash(rt2)


def test_community_json_representation() -> None:
    """Test JSON representation of communities.

    Communities should be serializable to JSON for APIs.
    """
    from exabgp.bgp.message.update.attribute.community import Community
    from exabgp.bgp.message.update.attribute.community.large.community import LargeCommunity

    # Standard community JSON
    comm = Community(struct.pack('!HH', 65000, 100))
    json_str = comm.json()
    assert '65000' in json_str
    assert '100' in json_str

    # Large community JSON
    lc = LargeCommunity(struct.pack('!LLL', 65000, 100, 200))
    json_str = lc.json()
    assert '65000' in json_str
    assert '100' in json_str
    assert '200' in json_str
