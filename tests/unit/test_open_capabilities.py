#!/usr/bin/env python3
# encoding: utf-8
"""test_open_capabilities.py

Comprehensive tests for BGP OPEN message capabilities (RFC 5492)

Tests various capability scenarios for BGP OPEN messages:
- Multiprotocol Extensions (RFC 4760)
- Route Refresh (RFC 2918)
- 4-Byte AS Numbers (RFC 6793)
- Graceful Restart (RFC 4724)
- ADD-PATH (RFC 7911)
- Extended Message (RFC 8654)

Created for ExaBGP testing framework
License: 3-clause BSD
"""

from unittest.mock import Mock
from exabgp.bgp.message import Message
from exabgp.bgp.message.open import Open
from exabgp.bgp.message.open import Version, ASN, RouterID, HoldTime
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability import RouteRefresh
from exabgp.bgp.message.open.capability.graceful import Graceful
from exabgp.bgp.message.open.capability.addpath import AddPath
from exabgp.bgp.message.open.capability.extended import ExtendedMessage
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.protocol.family import AFI, SAFI


# ==============================================================================
# Test Helper Functions
# ==============================================================================


def create_negotiated() -> Negotiated:
    """Create a Negotiated object with a mock neighbor for testing."""
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    return Negotiated.make_negotiated(neighbor, Direction.OUT)


def make_inet(prefix: str, afi: AFI = AFI.ipv4, safi: SAFI = SAFI.unicast, path_id: int = 0) -> INET:
    """Helper to create INET NLRI for tests."""
    import socket
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo

    ip_str, mask_str = prefix.split('/')
    if afi == AFI.ipv4:
        packed_ip = socket.inet_pton(socket.AF_INET, ip_str)
    else:
        packed_ip = socket.inet_pton(socket.AF_INET6, ip_str)
    cidr = CIDR.create_cidr(packed_ip, int(mask_str))
    if path_id:
        pi = PathInfo.make_from_integer(path_id)
    else:
        pi = PathInfo.DISABLED
    return INET.from_cidr(cidr, afi, safi, pi)


# ==============================================================================
# Phase 1: Basic OPEN Message Creation and Validation
# ==============================================================================


def test_open_creation_basic() -> None:
    """Test basic OPEN message creation.

    RFC 4271 Section 4.2:
    OPEN message contains: Version, ASN, Hold Time, Router ID, Capabilities
    """
    capabilities = Capabilities()
    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert open_msg.version == 4
    assert open_msg.asn == 65500
    assert open_msg.hold_time == 180
    assert open_msg.router_id == RouterID('192.0.2.1')
    assert open_msg.capabilities == {}


def test_open_creation_with_2byte_asn() -> None:
    """Test OPEN message with 2-byte ASN.

    ASNs 1-65535 are 2-byte ASNs.
    """
    capabilities = Capabilities()
    open_msg = Open.make_open(Version(4), ASN(64512), HoldTime(90), RouterID('10.0.0.1'), capabilities)

    assert open_msg.asn == 64512


def test_open_message_id() -> None:
    """Test OPEN message ID.

    RFC 4271: OPEN message type code is 1.
    """
    assert Open.ID == 1
    assert Open.ID == Message.CODE.OPEN


def test_open_message_type_bytes() -> None:
    """Test OPEN TYPE byte representation."""
    assert Open.TYPE == b'\x01'


# ==============================================================================
# Phase 2: Multiprotocol Capability (RFC 4760)
# ==============================================================================


def test_open_with_multiprotocol_ipv4_unicast() -> None:
    """Test OPEN message with Multiprotocol capability for IPv4 Unicast.

    RFC 4760: Multiprotocol Extensions for BGP-4
    """
    capabilities = Capabilities()
    capabilities[Capability.CODE.MULTIPROTOCOL] = [(AFI.ipv4, SAFI.unicast)]

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert Capability.CODE.MULTIPROTOCOL in open_msg.capabilities
    assert (AFI.ipv4, SAFI.unicast) in open_msg.capabilities[Capability.CODE.MULTIPROTOCOL]


def test_open_with_multiprotocol_ipv6_unicast() -> None:
    """Test OPEN with IPv6 Unicast capability."""
    capabilities = Capabilities()
    capabilities[Capability.CODE.MULTIPROTOCOL] = [(AFI.ipv6, SAFI.unicast)]

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert (AFI.ipv6, SAFI.unicast) in open_msg.capabilities[Capability.CODE.MULTIPROTOCOL]


def test_open_with_multiple_multiprotocol_families() -> None:
    """Test OPEN with multiple address families.

    Common scenario: IPv4 Unicast + IPv6 Unicast
    """
    capabilities = Capabilities()
    capabilities[Capability.CODE.MULTIPROTOCOL] = [
        (AFI.ipv4, SAFI.unicast),
        (AFI.ipv6, SAFI.unicast),
    ]

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    mp_caps = open_msg.capabilities[Capability.CODE.MULTIPROTOCOL]
    assert (AFI.ipv4, SAFI.unicast) in mp_caps
    assert (AFI.ipv6, SAFI.unicast) in mp_caps


def test_open_with_vpnv4_capability() -> None:
    """Test OPEN with VPNv4 capability (MPLS VPN).

    RFC 4364: BGP/MPLS IP VPNs
    """
    capabilities = Capabilities()
    capabilities[Capability.CODE.MULTIPROTOCOL] = [(AFI.ipv4, SAFI.mpls_vpn)]

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert (AFI.ipv4, SAFI.mpls_vpn) in open_msg.capabilities[Capability.CODE.MULTIPROTOCOL]


def test_open_with_multicast_capability() -> None:
    """Test OPEN with multicast capabilities."""
    capabilities = Capabilities()
    capabilities[Capability.CODE.MULTIPROTOCOL] = [
        (AFI.ipv4, SAFI.multicast),
        (AFI.ipv6, SAFI.multicast),
    ]

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    mp_caps = open_msg.capabilities[Capability.CODE.MULTIPROTOCOL]
    assert (AFI.ipv4, SAFI.multicast) in mp_caps
    assert (AFI.ipv6, SAFI.multicast) in mp_caps


# ==============================================================================
# Phase 3: Route Refresh Capability (RFC 2918)
# ==============================================================================


def test_open_with_route_refresh_capability() -> None:
    """Test OPEN with Route Refresh capability.

    RFC 2918: Route Refresh Capability for BGP-4
    """
    capabilities = Capabilities()
    capabilities[Capability.CODE.ROUTE_REFRESH] = RouteRefresh()

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert Capability.CODE.ROUTE_REFRESH in open_msg.capabilities


def test_open_with_enhanced_route_refresh() -> None:
    """Test OPEN with Enhanced Route Refresh capability.

    RFC 7313: Enhanced Route Refresh Capability for BGP-4
    """
    capabilities = Capabilities()
    capabilities[Capability.CODE.ENHANCED_ROUTE_REFRESH] = RouteRefresh()

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert Capability.CODE.ENHANCED_ROUTE_REFRESH in open_msg.capabilities


# ==============================================================================
# Phase 4: 4-Byte ASN Capability (RFC 6793)
# ==============================================================================


def test_open_with_4byte_asn_capability() -> None:
    """Test OPEN with 4-byte ASN capability.

    RFC 6793: BGP Support for Four-Octet Autonomous System (AS) Number Space
    """
    capabilities = Capabilities()
    asn4_value = 4200000000  # Large ASN requiring 4 bytes
    capabilities[Capability.CODE.FOUR_BYTES_ASN] = asn4_value

    open_msg = Open.make_open(Version(4), ASN(23456), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    # When using 4-byte ASN, the 2-byte ASN field should be AS_TRANS (23456)
    assert open_msg.asn == 23456
    assert Capability.CODE.FOUR_BYTES_ASN in open_msg.capabilities
    assert open_msg.capabilities[Capability.CODE.FOUR_BYTES_ASN] == asn4_value


def test_open_with_various_4byte_asns() -> None:
    """Test OPEN with various 4-byte ASN values."""
    test_asns = [
        65536,  # First 4-byte ASN
        100000,  # Mid-range
        4200000000,  # High value
        4294967294,  # Max valid ASN (2^32 - 2)
    ]

    for asn4 in test_asns:
        capabilities = Capabilities()
        capabilities[Capability.CODE.FOUR_BYTES_ASN] = asn4

        open_msg = Open.make_open(Version(4), ASN(23456), HoldTime(180), RouterID('192.0.2.1'), capabilities)

        assert open_msg.capabilities[Capability.CODE.FOUR_BYTES_ASN] == asn4


# ==============================================================================
# Phase 5: Graceful Restart Capability (RFC 4724)
# ==============================================================================


def test_open_with_graceful_restart_basic() -> None:
    """Test OPEN with basic Graceful Restart capability.

    RFC 4724: Graceful Restart Mechanism for BGP
    """
    capabilities = Capabilities()

    # Create Graceful Restart capability
    graceful = Graceful()
    graceful.set(
        restart_flag=0,
        restart_time=120,
        protos=[
            (AFI.ipv4, SAFI.unicast, 0x80),  # IPv4 unicast with forwarding state
        ],
    )

    capabilities[Capability.CODE.GRACEFUL_RESTART] = graceful

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert Capability.CODE.GRACEFUL_RESTART in open_msg.capabilities


def test_open_with_graceful_restart_multiple_families() -> None:
    """Test Graceful Restart with multiple address families."""
    capabilities = Capabilities()

    graceful = Graceful()
    graceful.set(
        restart_flag=0,
        restart_time=180,
        protos=[
            (AFI.ipv4, SAFI.unicast, 0x80),
            (AFI.ipv6, SAFI.unicast, 0x80),
            (AFI.ipv4, SAFI.mpls_vpn, 0x80),
        ],
    )

    capabilities[Capability.CODE.GRACEFUL_RESTART] = graceful

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    gr_cap = open_msg.capabilities[Capability.CODE.GRACEFUL_RESTART]
    assert (AFI.ipv4, SAFI.unicast) in gr_cap
    assert (AFI.ipv6, SAFI.unicast) in gr_cap
    assert (AFI.ipv4, SAFI.mpls_vpn) in gr_cap


def test_open_with_graceful_restart_flags() -> None:
    """Test Graceful Restart with restart flags."""
    capabilities = Capabilities()

    graceful = Graceful()
    graceful.set(
        restart_flag=Graceful.RESTART_STATE,  # Restart state flag set
        restart_time=240,
        protos=[
            (AFI.ipv4, SAFI.unicast, Graceful.FORWARDING_STATE),
        ],
    )

    capabilities[Capability.CODE.GRACEFUL_RESTART] = graceful

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    gr_cap = open_msg.capabilities[Capability.CODE.GRACEFUL_RESTART]
    assert gr_cap.restart_flag == Graceful.RESTART_STATE


# ==============================================================================
# Phase 6: ADD-PATH Capability (RFC 7911)
# ==============================================================================


def test_open_with_addpath_receive() -> None:
    """Test OPEN with ADD-PATH capability (receive mode).

    RFC 7911: Advertisement of Multiple Paths in BGP
    """
    capabilities = Capabilities()

    addpath = AddPath()
    addpath.add_path(AFI.ipv4, SAFI.unicast, 1)  # 1 = receive

    capabilities[Capability.CODE.ADD_PATH] = addpath

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert Capability.CODE.ADD_PATH in open_msg.capabilities


def test_open_with_addpath_send() -> None:
    """Test OPEN with ADD-PATH capability (send mode)."""
    capabilities = Capabilities()

    addpath = AddPath()
    addpath.add_path(AFI.ipv4, SAFI.unicast, 2)  # 2 = send

    capabilities[Capability.CODE.ADD_PATH] = addpath

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    ap_cap = open_msg.capabilities[Capability.CODE.ADD_PATH]
    assert (AFI.ipv4, SAFI.unicast) in ap_cap


def test_open_with_addpath_send_receive() -> None:
    """Test OPEN with ADD-PATH capability (send/receive mode)."""
    capabilities = Capabilities()

    addpath = AddPath()
    addpath.add_path(AFI.ipv4, SAFI.unicast, 3)  # 3 = send/receive
    addpath.add_path(AFI.ipv6, SAFI.unicast, 3)

    capabilities[Capability.CODE.ADD_PATH] = addpath

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    ap_cap = open_msg.capabilities[Capability.CODE.ADD_PATH]
    assert (AFI.ipv4, SAFI.unicast) in ap_cap
    assert (AFI.ipv6, SAFI.unicast) in ap_cap


# ==============================================================================
# Phase 7: Extended Message Capability (RFC 8654)
# ==============================================================================


def test_open_with_extended_message_capability() -> None:
    """Test OPEN with Extended Message capability.

    RFC 8654: Extended Message Support for BGP
    Allows BGP messages larger than 4096 bytes.
    """
    capabilities = Capabilities()
    capabilities[Capability.CODE.EXTENDED_MESSAGE] = ExtendedMessage()

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert Capability.CODE.EXTENDED_MESSAGE in open_msg.capabilities


# ==============================================================================
# Phase 8: Multiple Capabilities Combined
# ==============================================================================


def test_open_with_multiple_capabilities() -> None:
    """Test OPEN with multiple capabilities combined.

    Realistic scenario: Modern BGP router with multiple features.
    """
    capabilities = Capabilities()

    # Multiprotocol for IPv4 and IPv6
    capabilities[Capability.CODE.MULTIPROTOCOL] = [
        (AFI.ipv4, SAFI.unicast),
        (AFI.ipv6, SAFI.unicast),
    ]

    # Route Refresh
    capabilities[Capability.CODE.ROUTE_REFRESH] = RouteRefresh()

    # 4-Byte ASN
    capabilities[Capability.CODE.FOUR_BYTES_ASN] = 4200000000

    open_msg = Open.make_open(Version(4), ASN(23456), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert Capability.CODE.MULTIPROTOCOL in open_msg.capabilities
    assert Capability.CODE.ROUTE_REFRESH in open_msg.capabilities
    assert Capability.CODE.FOUR_BYTES_ASN in open_msg.capabilities


def test_open_with_full_capability_set() -> None:
    """Test OPEN with comprehensive set of capabilities."""
    capabilities = Capabilities()

    # Multiprotocol
    capabilities[Capability.CODE.MULTIPROTOCOL] = [
        (AFI.ipv4, SAFI.unicast),
        (AFI.ipv6, SAFI.unicast),
        (AFI.ipv4, SAFI.mpls_vpn),
    ]

    # Route Refresh
    capabilities[Capability.CODE.ROUTE_REFRESH] = RouteRefresh()

    # 4-Byte ASN
    capabilities[Capability.CODE.FOUR_BYTES_ASN] = 4200000000

    # Graceful Restart
    graceful = Graceful()
    graceful.set(0, 120, [(AFI.ipv4, SAFI.unicast, 0x80)])
    capabilities[Capability.CODE.GRACEFUL_RESTART] = graceful

    # ADD-PATH
    addpath = AddPath()
    addpath.add_path(AFI.ipv4, SAFI.unicast, 3)
    capabilities[Capability.CODE.ADD_PATH] = addpath

    # Extended Message
    capabilities[Capability.CODE.EXTENDED_MESSAGE] = ExtendedMessage()

    open_msg = Open.make_open(Version(4), ASN(23456), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    # Verify all capabilities are present
    assert len(open_msg.capabilities) == 6


# ==============================================================================
# Phase 9: OPEN Message Encoding
# ==============================================================================


def test_open_message_encoding_basic() -> None:
    """Test basic OPEN message encoding.

    Wire format:
    - Marker: 16 bytes (all 0xFF)
    - Length: 2 bytes
    - Type: 1 byte (0x01 = OPEN)
    - Version: 1 byte
    - My AS: 2 bytes
    - Hold Time: 2 bytes
    - BGP Identifier: 4 bytes
    - Optional Parameters Length: 1 byte
    - Optional Parameters: variable
    """
    capabilities = Capabilities()
    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    msg = open_msg.pack_message(create_negotiated())

    # Should start with BGP marker
    assert msg[0:16] == b'\xff' * 16

    # Message type should be OPEN (0x01)
    assert msg[18] == 0x01

    # Message should be at least 29 bytes (minimum OPEN size)
    assert len(msg) >= 29


def test_open_message_encoding_with_capabilities() -> None:
    """Test OPEN message encoding with capabilities."""
    from exabgp.bgp.message.open.capability.mp import MultiProtocol

    capabilities = Capabilities()

    # Create MultiProtocol capability properly
    mp = MultiProtocol()
    mp.append((AFI.ipv4, SAFI.unicast))
    capabilities[Capability.CODE.MULTIPROTOCOL] = mp

    capabilities[Capability.CODE.ROUTE_REFRESH] = RouteRefresh()

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    msg = open_msg.pack_message(create_negotiated())

    # Should be larger than minimum due to capabilities
    assert len(msg) > 29


# ==============================================================================
# Phase 10: OPEN Message Validation
# ==============================================================================


def test_open_with_various_hold_times() -> None:
    """Test OPEN with various Hold Time values.

    RFC 4271: Hold Time must be either 0 or >= 3 seconds.
    """
    hold_times = [0, 3, 90, 180, 240, 65535]

    for ht in hold_times:
        capabilities = Capabilities()
        open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(ht), RouterID('192.0.2.1'), capabilities)

        assert open_msg.hold_time == ht


def test_open_with_various_router_ids() -> None:
    """Test OPEN with various Router ID values."""
    router_ids = [
        '0.0.0.0',
        '10.0.0.1',
        '192.0.2.1',
        '172.16.0.1',
        '255.255.255.255',
    ]

    for rid in router_ids:
        capabilities = Capabilities()
        open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID(rid), capabilities)

        assert open_msg.router_id == RouterID(rid)


def test_open_version_field() -> None:
    """Test OPEN message version field.

    RFC 4271: BGP version is 4.
    """
    capabilities = Capabilities()
    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert open_msg.version == 4


# ==============================================================================
# Phase 11: Capability Code Constants
# ==============================================================================


def test_capability_code_constants() -> None:
    """Test that capability code constants are defined correctly."""
    assert hasattr(Capability.CODE, 'MULTIPROTOCOL')
    assert hasattr(Capability.CODE, 'ROUTE_REFRESH')
    assert hasattr(Capability.CODE, 'FOUR_BYTES_ASN')
    assert hasattr(Capability.CODE, 'GRACEFUL_RESTART')
    assert hasattr(Capability.CODE, 'ADD_PATH')
    assert hasattr(Capability.CODE, 'EXTENDED_MESSAGE')


def test_multiprotocol_capability_code() -> None:
    """Test Multiprotocol capability code.

    RFC 4760: Multiprotocol capability code is 1.
    """
    assert Capability.CODE.MULTIPROTOCOL == 1


def test_route_refresh_capability_code() -> None:
    """Test Route Refresh capability code.

    RFC 2918: Route Refresh capability code is 2.
    """
    assert Capability.CODE.ROUTE_REFRESH == 2


def test_four_byte_asn_capability_code() -> None:
    """Test 4-Byte ASN capability code.

    RFC 6793: 4-Byte ASN capability code is 65.
    """
    assert Capability.CODE.FOUR_BYTES_ASN == 65


def test_graceful_restart_capability_code() -> None:
    """Test Graceful Restart capability code.

    RFC 4724: Graceful Restart capability code is 64.
    """
    assert Capability.CODE.GRACEFUL_RESTART == 64


def test_add_path_capability_code() -> None:
    """Test ADD-PATH capability code.

    RFC 7911: ADD-PATH capability code is 69.
    """
    assert Capability.CODE.ADD_PATH == 69


# ==============================================================================
# Phase 12: Link-Local Next Hop Capability (draft-ietf-idr-linklocal-capability)
# ==============================================================================


def test_link_local_nexthop_capability_code() -> None:
    """Test Link-Local Next Hop capability code.

    draft-ietf-idr-linklocal-capability: Code 77 (0x4D).
    """
    assert Capability.CODE.LINK_LOCAL_NEXTHOP == 77


def test_link_local_nexthop_creation() -> None:
    """Test LinkLocalNextHop capability creation."""
    from exabgp.bgp.message.open.capability.linklocal import LinkLocalNextHop

    cap = LinkLocalNextHop()
    assert cap.ID == Capability.CODE.LINK_LOCAL_NEXTHOP
    assert str(cap) == 'Link-Local NextHop'


def test_link_local_nexthop_json() -> None:
    """Test LinkLocalNextHop JSON representation."""
    from exabgp.bgp.message.open.capability.linklocal import LinkLocalNextHop

    cap = LinkLocalNextHop()
    assert cap.json() == '{ "name": "link-local-nexthop" }'


def test_link_local_nexthop_extract_bytes() -> None:
    """Test LinkLocalNextHop extract_capability_bytes.

    Capability has no payload (length 0).
    """
    from exabgp.bgp.message.open.capability.linklocal import LinkLocalNextHop

    cap = LinkLocalNextHop()
    bytes_list = cap.extract_capability_bytes()
    assert bytes_list == [b'']


def test_link_local_nexthop_equality() -> None:
    """Test LinkLocalNextHop equality comparison."""
    from exabgp.bgp.message.open.capability.linklocal import LinkLocalNextHop

    cap1 = LinkLocalNextHop()
    cap2 = LinkLocalNextHop()

    assert cap1 == cap2
    assert not (cap1 != cap2)


def test_link_local_nexthop_inequality_with_other() -> None:
    """Test LinkLocalNextHop inequality with other types."""
    from exabgp.bgp.message.open.capability.linklocal import LinkLocalNextHop

    cap = LinkLocalNextHop()

    assert cap != 'not a capability'
    assert cap != 77
    assert cap != None  # noqa: E711


def test_link_local_nexthop_ordering_raises() -> None:
    """Test that ordering operations raise RuntimeError."""
    from exabgp.bgp.message.open.capability.linklocal import LinkLocalNextHop
    import pytest

    cap1 = LinkLocalNextHop()
    cap2 = LinkLocalNextHop()

    with pytest.raises(RuntimeError):
        cap1 < cap2

    with pytest.raises(RuntimeError):
        cap1 <= cap2

    with pytest.raises(RuntimeError):
        cap1 > cap2

    with pytest.raises(RuntimeError):
        cap1 >= cap2


def test_open_with_link_local_nexthop_capability() -> None:
    """Test OPEN message with Link-Local NextHop capability."""
    from exabgp.bgp.message.open.capability.linklocal import LinkLocalNextHop

    capabilities = Capabilities()
    capabilities[Capability.CODE.LINK_LOCAL_NEXTHOP] = LinkLocalNextHop()

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert Capability.CODE.LINK_LOCAL_NEXTHOP in open_msg.capabilities


def test_open_with_link_local_nexthop_and_ipv6() -> None:
    """Test OPEN with Link-Local NextHop and IPv6 Unicast.

    Common scenario: IPv6 peer using link-local addresses.
    """
    from exabgp.bgp.message.open.capability.linklocal import LinkLocalNextHop

    capabilities = Capabilities()
    capabilities[Capability.CODE.MULTIPROTOCOL] = [(AFI.ipv6, SAFI.unicast)]
    capabilities[Capability.CODE.LINK_LOCAL_NEXTHOP] = LinkLocalNextHop()

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert Capability.CODE.MULTIPROTOCOL in open_msg.capabilities
    assert Capability.CODE.LINK_LOCAL_NEXTHOP in open_msg.capabilities


def test_link_local_nexthop_unpack() -> None:
    """Test LinkLocalNextHop unpack_capability."""
    from exabgp.bgp.message.open.capability.linklocal import LinkLocalNextHop

    cap = LinkLocalNextHop()
    # Empty data - capability has no payload
    result = LinkLocalNextHop.unpack_capability(cap, b'', Capability.CODE.LINK_LOCAL_NEXTHOP)

    assert result is cap
    assert cap._seen is True


def test_link_local_nexthop_unpack_duplicate() -> None:
    """Test LinkLocalNextHop unpack handles duplicates."""
    from exabgp.bgp.message.open.capability.linklocal import LinkLocalNextHop

    cap = LinkLocalNextHop()

    # First unpack
    LinkLocalNextHop.unpack_capability(cap, b'', Capability.CODE.LINK_LOCAL_NEXTHOP)
    assert cap._seen is True

    # Second unpack (duplicate) - should still work, just logs
    LinkLocalNextHop.unpack_capability(cap, b'', Capability.CODE.LINK_LOCAL_NEXTHOP)
    assert cap._seen is True


# ==============================================================================
# Phase 13: PATHS-LIMIT Capability (draft-abraitis-idr-addpath-paths-limit-04)
# ==============================================================================


def test_paths_limit_capability_code() -> None:
    """Test PATHS-LIMIT capability code.

    draft-abraitis-idr-addpath-paths-limit-04: Code 76 (0x4C).
    """
    assert Capability.CODE.PATHS_LIMIT == 76


def test_paths_limit_creation() -> None:
    """Test PathsLimit capability creation."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    cap = PathsLimit()
    assert cap.ID == Capability.CODE.PATHS_LIMIT
    assert len(cap) == 0


def test_paths_limit_set_limit() -> None:
    """Test setting path limits per AFI/SAFI."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    cap = PathsLimit()
    cap.set_limit(AFI.ipv4, SAFI.unicast, 10)
    cap.set_limit(AFI.ipv6, SAFI.unicast, 20)

    assert cap[(AFI.ipv4, SAFI.unicast)] == 10
    assert cap[(AFI.ipv6, SAFI.unicast)] == 20
    assert len(cap) == 2


def test_paths_limit_init_with_families() -> None:
    """Test PathsLimit creation with families."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    families = {
        (AFI.ipv4, SAFI.unicast): 5,
        (AFI.ipv6, SAFI.unicast): 15,
    }
    cap = PathsLimit(families)

    assert cap[(AFI.ipv4, SAFI.unicast)] == 5
    assert cap[(AFI.ipv6, SAFI.unicast)] == 15


def test_paths_limit_extract_bytes() -> None:
    """Test PathsLimit wire encoding.

    Each tuple: AFI(2) + SAFI(1) + limit(2) = 5 bytes.
    """
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    cap = PathsLimit()
    cap.set_limit(AFI.ipv4, SAFI.unicast, 10)

    bytes_list = cap.extract_capability_bytes()
    assert len(bytes_list) == 1
    data = bytes_list[0]
    assert len(data) == 5
    # AFI IPv4 = 0x0001, SAFI unicast = 0x01, limit = 0x000A
    assert data == b'\x00\x01\x01\x00\x0a'


def test_paths_limit_extract_bytes_multiple() -> None:
    """Test PathsLimit wire encoding with multiple families."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    cap = PathsLimit()
    cap.set_limit(AFI.ipv4, SAFI.unicast, 10)
    cap.set_limit(AFI.ipv6, SAFI.unicast, 20)

    bytes_list = cap.extract_capability_bytes()
    data = bytes_list[0]
    assert len(data) == 10  # 2 * 5 bytes


def test_paths_limit_extract_bytes_skip_zero() -> None:
    """Test that zero limit entries are not encoded."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    cap = PathsLimit()
    cap.set_limit(AFI.ipv4, SAFI.unicast, 0)

    bytes_list = cap.extract_capability_bytes()
    data = bytes_list[0]
    assert len(data) == 0


def test_paths_limit_unpack() -> None:
    """Test PathsLimit wire decoding."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    cap = PathsLimit()
    # AFI IPv4 = 0x0001, SAFI unicast = 0x01, limit = 10 (0x000A)
    data = b'\x00\x01\x01\x00\x0a'
    result = PathsLimit.unpack_capability(cap, data, Capability.CODE.PATHS_LIMIT)

    assert isinstance(result, PathsLimit)
    assert result[(AFI.ipv4, SAFI.unicast)] == 10


def test_paths_limit_unpack_multiple() -> None:
    """Test PathsLimit decoding with multiple tuples."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    cap = PathsLimit()
    data = (
        b'\x00\x01\x01\x00\x0a'  # IPv4 unicast, limit=10
        b'\x00\x02\x01\x00\x14'  # IPv6 unicast, limit=20
    )
    result = PathsLimit.unpack_capability(cap, data, Capability.CODE.PATHS_LIMIT)

    assert result[(AFI.ipv4, SAFI.unicast)] == 10
    assert result[(AFI.ipv6, SAFI.unicast)] == 20


def test_paths_limit_unpack_zero_ignored() -> None:
    """Test that tuples with limit=0 are ignored."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    cap = PathsLimit()
    data = (
        b'\x00\x01\x01\x00\x00'  # IPv4 unicast, limit=0 (ignored)
        b'\x00\x02\x01\x00\x14'  # IPv6 unicast, limit=20
    )
    result = PathsLimit.unpack_capability(cap, data, Capability.CODE.PATHS_LIMIT)

    assert (AFI.ipv4, SAFI.unicast) not in result
    assert result[(AFI.ipv6, SAFI.unicast)] == 20


def test_paths_limit_unpack_duplicate_first_wins() -> None:
    """Test that duplicate AFI/SAFI uses first tuple only."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    cap = PathsLimit()
    data = (
        b'\x00\x01\x01\x00\x0a'  # IPv4 unicast, limit=10 (first)
        b'\x00\x01\x01\x00\x14'  # IPv4 unicast, limit=20 (duplicate, ignored)
    )
    result = PathsLimit.unpack_capability(cap, data, Capability.CODE.PATHS_LIMIT)

    assert result[(AFI.ipv4, SAFI.unicast)] == 10


def test_paths_limit_unpack_truncated() -> None:
    """Test that truncated data raises Notify."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit
    from exabgp.bgp.message.notification import Notify
    import pytest

    cap = PathsLimit()
    data = b'\x00\x01\x01'  # Only 3 bytes, need 5

    with pytest.raises(Notify):
        PathsLimit.unpack_capability(cap, data, Capability.CODE.PATHS_LIMIT)


def test_paths_limit_round_trip() -> None:
    """Test pack -> unpack returns same data."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    original = PathsLimit()
    original.set_limit(AFI.ipv4, SAFI.unicast, 10)
    original.set_limit(AFI.ipv6, SAFI.unicast, 20)

    packed = original.extract_capability_bytes()[0]
    unpacked = PathsLimit()
    PathsLimit.unpack_capability(unpacked, packed, Capability.CODE.PATHS_LIMIT)

    assert dict(unpacked) == dict(original)


def test_paths_limit_empty() -> None:
    """Test empty PathsLimit capability."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    cap = PathsLimit()
    bytes_list = cap.extract_capability_bytes()
    assert bytes_list == [b'']


def test_paths_limit_json() -> None:
    """Test PathsLimit JSON representation."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    cap = PathsLimit()
    cap.set_limit(AFI.ipv4, SAFI.unicast, 10)
    json_str = cap.json()
    assert '"name": "paths-limit"' in json_str
    assert '"ipv4/unicast": 10' in json_str


def test_paths_limit_str() -> None:
    """Test PathsLimit string representation."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    cap = PathsLimit()
    cap.set_limit(AFI.ipv4, SAFI.unicast, 10)
    s = str(cap)
    assert 'PathsLimit' in s
    assert '10' in s


def test_open_with_paths_limit_capability() -> None:
    """Test OPEN message with PATHS-LIMIT capability."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    capabilities = Capabilities()

    addpath = AddPath()
    addpath.add_path(AFI.ipv4, SAFI.unicast, 3)
    capabilities[Capability.CODE.ADD_PATH] = addpath

    pl = PathsLimit()
    pl.set_limit(AFI.ipv4, SAFI.unicast, 10)
    capabilities[Capability.CODE.PATHS_LIMIT] = pl

    open_msg = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert Capability.CODE.PATHS_LIMIT in open_msg.capabilities
    assert Capability.CODE.ADD_PATH in open_msg.capabilities


def test_paths_limit_max_value() -> None:
    """Test PathsLimit with maximum uint16 value (65535)."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    cap = PathsLimit()
    cap.set_limit(AFI.ipv4, SAFI.unicast, 65535)

    packed = cap.extract_capability_bytes()[0]
    assert packed == b'\x00\x01\x01\xff\xff'

    unpacked = PathsLimit()
    PathsLimit.unpack_capability(unpacked, packed, Capability.CODE.PATHS_LIMIT)
    assert unpacked[(AFI.ipv4, SAFI.unicast)] == 65535


def test_paths_limit_set_limit_rejects_negative() -> None:
    """Test that set_limit rejects negative values."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit
    import pytest

    cap = PathsLimit()
    with pytest.raises(ValueError, match='paths limit must be 0-65535'):
        cap.set_limit(AFI.ipv4, SAFI.unicast, -1)


def test_paths_limit_set_limit_rejects_overflow() -> None:
    """Test that set_limit rejects values exceeding uint16."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit
    import pytest

    cap = PathsLimit()
    with pytest.raises(ValueError, match='paths limit must be 0-65535'):
        cap.set_limit(AFI.ipv4, SAFI.unicast, 65536)


def test_paths_limit_negotiation_stores_peer_limit_only() -> None:
    """Test that negotiated paths_limit stores only the peer's limits."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit
    from exabgp.bgp.message.open.capability.mp import MultiProtocol

    # Our OPEN: ADD-PATH send/receive + PATHS-LIMIT=5
    sent_caps = Capabilities()
    sent_mp = MultiProtocol()
    sent_mp.append((AFI.ipv4, SAFI.unicast))
    sent_caps[Capability.CODE.MULTIPROTOCOL] = sent_mp
    sent_ap = AddPath()
    sent_ap.add_path(AFI.ipv4, SAFI.unicast, 3)
    sent_caps[Capability.CODE.ADD_PATH] = sent_ap
    sent_pl = PathsLimit()
    sent_pl.set_limit(AFI.ipv4, SAFI.unicast, 5)
    sent_caps[Capability.CODE.PATHS_LIMIT] = sent_pl

    # Peer's OPEN: ADD-PATH send/receive + PATHS-LIMIT=10
    recv_caps = Capabilities()
    recv_mp = MultiProtocol()
    recv_mp.append((AFI.ipv4, SAFI.unicast))
    recv_caps[Capability.CODE.MULTIPROTOCOL] = recv_mp
    recv_ap = AddPath()
    recv_ap.add_path(AFI.ipv4, SAFI.unicast, 3)
    recv_caps[Capability.CODE.ADD_PATH] = recv_ap
    recv_pl = PathsLimit()
    recv_pl.set_limit(AFI.ipv4, SAFI.unicast, 10)
    recv_caps[Capability.CODE.PATHS_LIMIT] = recv_pl

    sent_open = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), sent_caps)
    recv_open = Open.make_open(Version(4), ASN(65501), HoldTime(180), RouterID('192.0.2.2'), recv_caps)

    negotiated = create_negotiated()
    negotiated.sent(sent_open)
    negotiated.received(recv_open)

    assert negotiated.paths_limit[(AFI.ipv4, SAFI.unicast)] == 10


def test_paths_limit_negotiation_ignores_family_not_in_addpath() -> None:
    """Test that PATHS-LIMIT tuples not in received ADD-PATH are ignored."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit
    from exabgp.bgp.message.open.capability.mp import MultiProtocol

    # Both sides: ADD-PATH for IPv4 only
    sent_caps = Capabilities()
    sent_mp = MultiProtocol()
    sent_mp.append((AFI.ipv4, SAFI.unicast))
    sent_mp.append((AFI.ipv6, SAFI.unicast))
    sent_caps[Capability.CODE.MULTIPROTOCOL] = sent_mp
    sent_ap = AddPath()
    sent_ap.add_path(AFI.ipv4, SAFI.unicast, 3)
    sent_caps[Capability.CODE.ADD_PATH] = sent_ap

    recv_caps = Capabilities()
    recv_mp = MultiProtocol()
    recv_mp.append((AFI.ipv4, SAFI.unicast))
    recv_mp.append((AFI.ipv6, SAFI.unicast))
    recv_caps[Capability.CODE.MULTIPROTOCOL] = recv_mp
    recv_ap = AddPath()
    recv_ap.add_path(AFI.ipv4, SAFI.unicast, 3)
    recv_caps[Capability.CODE.ADD_PATH] = recv_ap

    # Peer's PATHS-LIMIT includes IPv6 which is NOT in their ADD-PATH
    recv_pl = PathsLimit()
    recv_pl.set_limit(AFI.ipv4, SAFI.unicast, 10)
    recv_pl.set_limit(AFI.ipv6, SAFI.unicast, 20)
    recv_caps[Capability.CODE.PATHS_LIMIT] = recv_pl

    sent_open = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), sent_caps)
    recv_open = Open.make_open(Version(4), ASN(65501), HoldTime(180), RouterID('192.0.2.2'), recv_caps)

    negotiated = create_negotiated()
    negotiated.sent(sent_open)
    negotiated.received(recv_open)

    assert negotiated.paths_limit[(AFI.ipv4, SAFI.unicast)] == 10
    assert (AFI.ipv6, SAFI.unicast) not in negotiated.paths_limit


def test_paths_limit_negotiation_ignored_without_addpath() -> None:
    """Test PATHS-LIMIT is ignored when ADD-PATH is not present."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit
    from exabgp.bgp.message.open.capability.mp import MultiProtocol

    sent_caps = Capabilities()
    sent_mp = MultiProtocol()
    sent_mp.append((AFI.ipv4, SAFI.unicast))
    sent_caps[Capability.CODE.MULTIPROTOCOL] = sent_mp
    # No ADD-PATH on our side

    recv_caps = Capabilities()
    recv_mp = MultiProtocol()
    recv_mp.append((AFI.ipv4, SAFI.unicast))
    recv_caps[Capability.CODE.MULTIPROTOCOL] = recv_mp

    # Peer sends PATHS-LIMIT but no ADD-PATH
    recv_pl = PathsLimit()
    recv_pl.set_limit(AFI.ipv4, SAFI.unicast, 10)
    recv_caps[Capability.CODE.PATHS_LIMIT] = recv_pl

    sent_open = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), sent_caps)
    recv_open = Open.make_open(Version(4), ASN(65501), HoldTime(180), RouterID('192.0.2.2'), recv_caps)

    negotiated = create_negotiated()
    negotiated.sent(sent_open)
    negotiated.received(recv_open)

    assert negotiated.paths_limit == {}


def test_paths_limit_negotiation_send_only_not_stored() -> None:
    """Test PATHS-LIMIT not stored for families where addpath is send-only."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit
    from exabgp.bgp.message.open.capability.mp import MultiProtocol

    # We send ADD-PATH receive-only, peer sends ADD-PATH receive-only
    sent_caps = Capabilities()
    sent_mp = MultiProtocol()
    sent_mp.append((AFI.ipv4, SAFI.unicast))
    sent_caps[Capability.CODE.MULTIPROTOCOL] = sent_mp
    sent_ap = AddPath()
    sent_ap.add_path(AFI.ipv4, SAFI.unicast, 1)
    sent_caps[Capability.CODE.ADD_PATH] = sent_ap

    recv_caps = Capabilities()
    recv_mp = MultiProtocol()
    recv_mp.append((AFI.ipv4, SAFI.unicast))
    recv_caps[Capability.CODE.MULTIPROTOCOL] = recv_mp
    recv_ap = AddPath()
    recv_ap.add_path(AFI.ipv4, SAFI.unicast, 1)
    recv_caps[Capability.CODE.ADD_PATH] = recv_ap
    recv_pl = PathsLimit()
    recv_pl.set_limit(AFI.ipv4, SAFI.unicast, 10)
    recv_caps[Capability.CODE.PATHS_LIMIT] = recv_pl

    sent_open = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), sent_caps)
    recv_open = Open.make_open(Version(4), ASN(65501), HoldTime(180), RouterID('192.0.2.2'), recv_caps)

    negotiated = create_negotiated()
    negotiated.sent(sent_open)
    negotiated.received(recv_open)

    assert negotiated.paths_limit == {}


def test_paths_limit_prefix_index_without_addpath() -> None:
    """Test INET prefix_index() without addpath returns same as index()."""
    nlri = make_inet('10.0.0.0/24')
    assert nlri.prefix_index() == nlri.index()


def test_paths_limit_prefix_index_with_addpath() -> None:
    """Test INET prefix_index() with addpath strips path_id."""
    nlri1 = make_inet('10.0.0.0/24', path_id=1)
    nlri2 = make_inet('10.0.0.0/24', path_id=2)

    assert nlri1.index() != nlri2.index()
    assert nlri1.prefix_index() == nlri2.prefix_index()


def test_paths_limit_prefix_index_different_prefixes() -> None:
    """Test prefix_index() differs for different prefixes."""
    nlri1 = make_inet('10.0.0.0/24', path_id=1)
    nlri2 = make_inet('10.0.1.0/24', path_id=1)

    assert nlri1.prefix_index() != nlri2.prefix_index()


def test_paths_limit_outgoing_rib_enforcement() -> None:
    """Test OutgoingRIB.updates() enforces paths-limit per prefix."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection
    from exabgp.rib.outgoing import OutgoingRIB
    from exabgp.rib.route import Route
    from exabgp.protocol.ip import IP

    family = (AFI.ipv4, SAFI.unicast)
    rib = OutgoingRIB(cache=False, families={family})

    attrs = AttributeCollection()

    for pid in (1, 2, 3):
        nlri = make_inet('10.0.0.0/24', path_id=pid)
        route = Route(nlri, attrs, nexthop=IP.from_string('1.2.3.4'))
        rib.add_to_rib(route, force=True)

    updates_no_limit = list(rib.updates(grouped=True, paths_limit=None))
    total_no_limit = sum(len(u.announces) for u in updates_no_limit if hasattr(u, 'announces'))
    assert total_no_limit == 3

    for pid in (1, 2, 3):
        nlri = make_inet('10.0.0.0/24', path_id=pid)
        route = Route(nlri, attrs, nexthop=IP.from_string('1.2.3.4'))
        rib.add_to_rib(route, force=True)

    updates_limited = list(rib.updates(grouped=True, paths_limit={family: 2}))
    total_limited = sum(len(u.announces) for u in updates_limited if hasattr(u, 'announces'))
    assert total_limited == 2


def test_paths_limit_outgoing_rib_different_prefixes() -> None:
    """Test paths-limit counts independently per prefix."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection
    from exabgp.rib.outgoing import OutgoingRIB
    from exabgp.rib.route import Route
    from exabgp.protocol.ip import IP

    family = (AFI.ipv4, SAFI.unicast)
    rib = OutgoingRIB(cache=False, families={family})

    attrs = AttributeCollection()

    for pid in (1, 2):
        nlri = make_inet('10.0.0.0/24', path_id=pid)
        rib.add_to_rib(Route(nlri, attrs, nexthop=IP.from_string('1.2.3.4')), force=True)
    for pid in (1, 2):
        nlri = make_inet('10.0.1.0/24', path_id=pid)
        rib.add_to_rib(Route(nlri, attrs, nexthop=IP.from_string('1.2.3.4')), force=True)

    updates = list(rib.updates(grouped=True, paths_limit={family: 1}))
    total = sum(len(u.announces) for u in updates if hasattr(u, 'announces'))
    assert total == 2


def test_paths_limit_outgoing_rib_no_limit_family() -> None:
    """Test paths-limit doesn't affect families without a limit."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection
    from exabgp.rib.outgoing import OutgoingRIB
    from exabgp.rib.route import Route
    from exabgp.protocol.ip import IP

    family = (AFI.ipv4, SAFI.unicast)
    rib = OutgoingRIB(cache=False, families={family})

    attrs = AttributeCollection()
    for pid in (1, 2, 3):
        nlri = make_inet('10.0.0.0/24', path_id=pid)
        rib.add_to_rib(Route(nlri, attrs, nexthop=IP.from_string('1.2.3.4')), force=True)

    updates = list(rib.updates(grouped=True, paths_limit={(AFI.ipv6, SAFI.unicast): 1}))
    total = sum(len(u.announces) for u in updates if hasattr(u, 'announces'))
    assert total == 3


def test_neighbor_capability_paths_limit_per_family_default() -> None:
    """Test NeighborCapability has empty per-family limits by default."""
    from exabgp.bgp.neighbor.capability import NeighborCapability

    cap = NeighborCapability()
    assert cap.paths_limit_per_family == {}


def test_neighbor_capability_paths_limit_per_family_copy() -> None:
    """Test per-family limits are copied correctly."""
    from exabgp.bgp.neighbor.capability import NeighborCapability

    cap = NeighborCapability()
    cap.paths_limit_per_family[(AFI.ipv4, SAFI.unicast)] = 5
    cap.paths_limit_per_family[(AFI.ipv6, SAFI.unicast)] = 10

    copy = cap.copy()
    assert copy.paths_limit_per_family == cap.paths_limit_per_family
    copy.paths_limit_per_family[(AFI.ipv4, SAFI.unicast)] = 99
    assert cap.paths_limit_per_family[(AFI.ipv4, SAFI.unicast)] == 5


def test_pathslimit_capability_per_family_override() -> None:
    """Test _pathslimit() uses per-family override over default."""
    from unittest.mock import Mock
    from exabgp.bgp.neighbor.capability import NeighborCapability

    neighbor = Mock()
    cap = NeighborCapability()
    cap.add_path = 3
    cap.paths_limit = 10
    cap.paths_limit_per_family = {(AFI.ipv4, SAFI.unicast): 5}
    neighbor.capability = cap

    addpath = AddPath()
    addpath.add_path(AFI.ipv4, SAFI.unicast, 3)
    addpath.add_path(AFI.ipv6, SAFI.unicast, 3)

    caps = Capabilities()
    caps[Capability.CODE.ADD_PATH] = addpath
    caps._pathslimit(neighbor)

    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

    pl = caps.get(Capability.CODE.PATHS_LIMIT)
    assert isinstance(pl, PathsLimit)
    assert pl[(AFI.ipv4, SAFI.unicast)] == 5
    assert pl[(AFI.ipv6, SAFI.unicast)] == 10


def test_advertised_paths_limit_default_empty() -> None:
    """advertised_paths_limit is empty before negotiation."""
    n = create_negotiated()
    assert n.advertised_paths_limit == {}


def test_advertised_paths_limit_unset_sentinel_empty() -> None:
    """Negotiated.UNSET sentinel exposes empty advertised_paths_limit."""
    assert Negotiated.UNSET.advertised_paths_limit == {}


def test_advertised_paths_limit_populated_from_sent_open() -> None:
    """advertised_paths_limit captures our own PATHS-LIMIT for receive-direction families."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit
    from exabgp.bgp.message.open.capability.mp import MultiProtocol

    sent_caps = Capabilities()
    sent_mp = MultiProtocol()
    sent_mp.append((AFI.ipv4, SAFI.unicast))
    sent_caps[Capability.CODE.MULTIPROTOCOL] = sent_mp
    sent_ap = AddPath()
    sent_ap.add_path(AFI.ipv4, SAFI.unicast, 3)
    sent_caps[Capability.CODE.ADD_PATH] = sent_ap
    sent_pl = PathsLimit()
    sent_pl.set_limit(AFI.ipv4, SAFI.unicast, 7)
    sent_caps[Capability.CODE.PATHS_LIMIT] = sent_pl

    recv_caps = Capabilities()
    recv_mp = MultiProtocol()
    recv_mp.append((AFI.ipv4, SAFI.unicast))
    recv_caps[Capability.CODE.MULTIPROTOCOL] = recv_mp
    recv_ap = AddPath()
    recv_ap.add_path(AFI.ipv4, SAFI.unicast, 3)
    recv_caps[Capability.CODE.ADD_PATH] = recv_ap

    sent_open = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), sent_caps)
    recv_open = Open.make_open(Version(4), ASN(65501), HoldTime(180), RouterID('192.0.2.2'), recv_caps)

    n = create_negotiated()
    n.sent(sent_open)
    n.received(recv_open)

    assert n.advertised_paths_limit[(AFI.ipv4, SAFI.unicast)] == 7


def test_advertised_paths_limit_skips_send_only_addpath() -> None:
    """advertised_paths_limit only includes families which we actually receive."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit
    from exabgp.bgp.message.open.capability.mp import MultiProtocol

    sent_caps = Capabilities()
    sent_mp = MultiProtocol()
    sent_mp.append((AFI.ipv4, SAFI.unicast))
    sent_caps[Capability.CODE.MULTIPROTOCOL] = sent_mp
    sent_ap = AddPath()
    sent_ap.add_path(AFI.ipv4, SAFI.unicast, 2)
    sent_caps[Capability.CODE.ADD_PATH] = sent_ap
    sent_pl = PathsLimit()
    sent_pl.set_limit(AFI.ipv4, SAFI.unicast, 9)
    sent_caps[Capability.CODE.PATHS_LIMIT] = sent_pl

    recv_caps = Capabilities()
    recv_mp = MultiProtocol()
    recv_mp.append((AFI.ipv4, SAFI.unicast))
    recv_caps[Capability.CODE.MULTIPROTOCOL] = recv_mp
    recv_ap = AddPath()
    recv_ap.add_path(AFI.ipv4, SAFI.unicast, 1)
    recv_caps[Capability.CODE.ADD_PATH] = recv_ap

    sent_open = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), sent_caps)
    recv_open = Open.make_open(Version(4), ASN(65501), HoldTime(180), RouterID('192.0.2.2'), recv_caps)

    n = create_negotiated()
    n.sent(sent_open)
    n.received(recv_open)

    assert n.advertised_paths_limit == {}


def test_advertised_paths_limit_skips_family_not_in_sent_addpath() -> None:
    """A PATHS-LIMIT entry for a family not in our ADD-PATH is discarded."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit
    from exabgp.bgp.message.open.capability.mp import MultiProtocol

    sent_caps = Capabilities()
    sent_mp = MultiProtocol()
    sent_mp.append((AFI.ipv4, SAFI.unicast))
    sent_mp.append((AFI.ipv6, SAFI.unicast))
    sent_caps[Capability.CODE.MULTIPROTOCOL] = sent_mp
    sent_ap = AddPath()
    sent_ap.add_path(AFI.ipv4, SAFI.unicast, 3)
    sent_caps[Capability.CODE.ADD_PATH] = sent_ap
    sent_pl = PathsLimit()
    sent_pl.set_limit(AFI.ipv4, SAFI.unicast, 5)
    sent_pl.set_limit(AFI.ipv6, SAFI.unicast, 6)
    sent_caps[Capability.CODE.PATHS_LIMIT] = sent_pl

    recv_caps = Capabilities()
    recv_mp = MultiProtocol()
    recv_mp.append((AFI.ipv4, SAFI.unicast))
    recv_mp.append((AFI.ipv6, SAFI.unicast))
    recv_caps[Capability.CODE.MULTIPROTOCOL] = recv_mp
    recv_ap = AddPath()
    recv_ap.add_path(AFI.ipv4, SAFI.unicast, 3)
    recv_caps[Capability.CODE.ADD_PATH] = recv_ap

    sent_open = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), sent_caps)
    recv_open = Open.make_open(Version(4), ASN(65501), HoldTime(180), RouterID('192.0.2.2'), recv_caps)

    n = create_negotiated()
    n.sent(sent_open)
    n.received(recv_open)

    assert n.advertised_paths_limit == {(AFI.ipv4, SAFI.unicast): 5}


def test_advertised_paths_limit_empty_without_addpath_negotiated() -> None:
    """When ADD-PATH is not bilaterally negotiated, advertised_paths_limit is empty."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit
    from exabgp.bgp.message.open.capability.mp import MultiProtocol

    sent_caps = Capabilities()
    sent_mp = MultiProtocol()
    sent_mp.append((AFI.ipv4, SAFI.unicast))
    sent_caps[Capability.CODE.MULTIPROTOCOL] = sent_mp
    sent_pl = PathsLimit()
    sent_pl.set_limit(AFI.ipv4, SAFI.unicast, 5)
    sent_caps[Capability.CODE.PATHS_LIMIT] = sent_pl
    # No ADD-PATH on our side

    recv_caps = Capabilities()
    recv_mp = MultiProtocol()
    recv_mp.append((AFI.ipv4, SAFI.unicast))
    recv_caps[Capability.CODE.MULTIPROTOCOL] = recv_mp
    recv_ap = AddPath()
    recv_ap.add_path(AFI.ipv4, SAFI.unicast, 3)
    recv_caps[Capability.CODE.ADD_PATH] = recv_ap

    sent_open = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), sent_caps)
    recv_open = Open.make_open(Version(4), ASN(65501), HoldTime(180), RouterID('192.0.2.2'), recv_caps)

    n = create_negotiated()
    n.sent(sent_open)
    n.received(recv_open)

    assert n.advertised_paths_limit == {}


def test_advertised_paths_limit_independent_from_paths_limit() -> None:
    """advertised_paths_limit (our caps) and paths_limit (peer caps) are tracked separately."""
    from exabgp.bgp.message.open.capability.pathslimit import PathsLimit
    from exabgp.bgp.message.open.capability.mp import MultiProtocol

    sent_caps = Capabilities()
    sent_mp = MultiProtocol()
    sent_mp.append((AFI.ipv4, SAFI.unicast))
    sent_caps[Capability.CODE.MULTIPROTOCOL] = sent_mp
    sent_ap = AddPath()
    sent_ap.add_path(AFI.ipv4, SAFI.unicast, 3)
    sent_caps[Capability.CODE.ADD_PATH] = sent_ap
    sent_pl = PathsLimit()
    sent_pl.set_limit(AFI.ipv4, SAFI.unicast, 5)
    sent_caps[Capability.CODE.PATHS_LIMIT] = sent_pl

    recv_caps = Capabilities()
    recv_mp = MultiProtocol()
    recv_mp.append((AFI.ipv4, SAFI.unicast))
    recv_caps[Capability.CODE.MULTIPROTOCOL] = recv_mp
    recv_ap = AddPath()
    recv_ap.add_path(AFI.ipv4, SAFI.unicast, 3)
    recv_caps[Capability.CODE.ADD_PATH] = recv_ap
    recv_pl = PathsLimit()
    recv_pl.set_limit(AFI.ipv4, SAFI.unicast, 11)
    recv_caps[Capability.CODE.PATHS_LIMIT] = recv_pl

    sent_open = Open.make_open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), sent_caps)
    recv_open = Open.make_open(Version(4), ASN(65501), HoldTime(180), RouterID('192.0.2.2'), recv_caps)

    n = create_negotiated()
    n.sent(sent_open)
    n.received(recv_open)

    assert n.advertised_paths_limit == {(AFI.ipv4, SAFI.unicast): 5}
    assert n.paths_limit == {(AFI.ipv4, SAFI.unicast): 11}


# ==============================================================================
# Summary
# ==============================================================================
# Total tests: 84
#
# Coverage:
# - Basic OPEN message creation (4 tests)
# - Multiprotocol capability (5 tests)
# - Route Refresh capability (2 tests)
# - 4-Byte ASN capability (2 tests)
# - Graceful Restart capability (3 tests)
# - ADD-PATH capability (3 tests)
# - Extended Message capability (1 test)
# - Multiple capabilities combined (2 tests)
# - Message encoding (2 tests)
# - Message validation (3 tests)
# - Capability code constants (6 tests)
# - Link-Local Next Hop capability (11 tests)
# - PATHS-LIMIT capability (40 tests)
#
# This test suite ensures:
# - Proper OPEN message creation with various capabilities
# - Correct capability encoding and representation
# - Support for modern BGP features
# - RFC compliance for all tested capabilities
# - Realistic multi-capability scenarios
# - Compliance for PATHS-LIMIT negotiation and enforcement
# ==============================================================================
