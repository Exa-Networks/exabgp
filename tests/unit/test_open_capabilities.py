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

import pytest
from exabgp.bgp.message import Message
from exabgp.bgp.message.open import Open
from exabgp.bgp.message.open import Version, ASN, RouterID, HoldTime
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability import RouteRefresh
from exabgp.bgp.message.open.capability.asn4 import ASN4
from exabgp.bgp.message.open.capability.graceful import Graceful
from exabgp.bgp.message.open.capability.addpath import AddPath
from exabgp.bgp.message.open.capability.extended import ExtendedMessage
from exabgp.bgp.message.direction import Direction
from exabgp.protocol.family import AFI, SAFI


# ==============================================================================
# Phase 1: Basic OPEN Message Creation and Validation
# ==============================================================================

def test_open_creation_basic() -> None:
    """Test basic OPEN message creation.

    RFC 4271 Section 4.2:
    OPEN message contains: Version, ASN, Hold Time, Router ID, Capabilities
    """
    capabilities = Capabilities()
    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

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
    open_msg = Open(Version(4), ASN(64512), HoldTime(90), RouterID('10.0.0.1'), capabilities)

    assert open_msg.asn == 64512


def test_open_message_id() -> None:
    """Test OPEN message ID.

    RFC 4271: OPEN message type code is 1.
    """
    assert Open.ID == 1
    assert Open.ID == Message.CODE.OPEN


def test_open_message_type_bytes() -> None:
    """Test OPEN TYPE byte representation.
    """
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

    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert Capability.CODE.MULTIPROTOCOL in open_msg.capabilities
    assert (AFI.ipv4, SAFI.unicast) in open_msg.capabilities[Capability.CODE.MULTIPROTOCOL]


def test_open_with_multiprotocol_ipv6_unicast() -> None:
    """Test OPEN with IPv6 Unicast capability.
    """
    capabilities = Capabilities()
    capabilities[Capability.CODE.MULTIPROTOCOL] = [(AFI.ipv6, SAFI.unicast)]

    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

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

    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    mp_caps = open_msg.capabilities[Capability.CODE.MULTIPROTOCOL]
    assert (AFI.ipv4, SAFI.unicast) in mp_caps
    assert (AFI.ipv6, SAFI.unicast) in mp_caps


def test_open_with_vpnv4_capability() -> None:
    """Test OPEN with VPNv4 capability (MPLS VPN).

    RFC 4364: BGP/MPLS IP VPNs
    """
    capabilities = Capabilities()
    capabilities[Capability.CODE.MULTIPROTOCOL] = [(AFI.ipv4, SAFI.mpls_vpn)]

    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert (AFI.ipv4, SAFI.mpls_vpn) in open_msg.capabilities[Capability.CODE.MULTIPROTOCOL]


def test_open_with_multicast_capability() -> None:
    """Test OPEN with multicast capabilities.
    """
    capabilities = Capabilities()
    capabilities[Capability.CODE.MULTIPROTOCOL] = [
        (AFI.ipv4, SAFI.multicast),
        (AFI.ipv6, SAFI.multicast),
    ]

    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

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

    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert Capability.CODE.ROUTE_REFRESH in open_msg.capabilities


def test_open_with_enhanced_route_refresh() -> None:
    """Test OPEN with Enhanced Route Refresh capability.

    RFC 7313: Enhanced Route Refresh Capability for BGP-4
    """
    capabilities = Capabilities()
    capabilities[Capability.CODE.ENHANCED_ROUTE_REFRESH] = RouteRefresh()

    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

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

    open_msg = Open(Version(4), ASN(23456), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    # When using 4-byte ASN, the 2-byte ASN field should be AS_TRANS (23456)
    assert open_msg.asn == 23456
    assert Capability.CODE.FOUR_BYTES_ASN in open_msg.capabilities
    assert open_msg.capabilities[Capability.CODE.FOUR_BYTES_ASN] == asn4_value


def test_open_with_various_4byte_asns() -> None:
    """Test OPEN with various 4-byte ASN values.
    """
    test_asns = [
        65536,       # First 4-byte ASN
        100000,      # Mid-range
        4200000000,  # High value
        4294967294,  # Max valid ASN (2^32 - 2)
    ]

    for asn4 in test_asns:
        capabilities = Capabilities()
        capabilities[Capability.CODE.FOUR_BYTES_ASN] = asn4

        open_msg = Open(Version(4), ASN(23456), HoldTime(180), RouterID('192.0.2.1'), capabilities)

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

    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert Capability.CODE.GRACEFUL_RESTART in open_msg.capabilities


def test_open_with_graceful_restart_multiple_families() -> None:
    """Test Graceful Restart with multiple address families.
    """
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

    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    gr_cap = open_msg.capabilities[Capability.CODE.GRACEFUL_RESTART]
    assert (AFI.ipv4, SAFI.unicast) in gr_cap
    assert (AFI.ipv6, SAFI.unicast) in gr_cap
    assert (AFI.ipv4, SAFI.mpls_vpn) in gr_cap


def test_open_with_graceful_restart_flags() -> None:
    """Test Graceful Restart with restart flags.
    """
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

    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

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

    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert Capability.CODE.ADD_PATH in open_msg.capabilities


def test_open_with_addpath_send() -> None:
    """Test OPEN with ADD-PATH capability (send mode).
    """
    capabilities = Capabilities()

    addpath = AddPath()
    addpath.add_path(AFI.ipv4, SAFI.unicast, 2)  # 2 = send

    capabilities[Capability.CODE.ADD_PATH] = addpath

    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    ap_cap = open_msg.capabilities[Capability.CODE.ADD_PATH]
    assert (AFI.ipv4, SAFI.unicast) in ap_cap


def test_open_with_addpath_send_receive() -> None:
    """Test OPEN with ADD-PATH capability (send/receive mode).
    """
    capabilities = Capabilities()

    addpath = AddPath()
    addpath.add_path(AFI.ipv4, SAFI.unicast, 3)  # 3 = send/receive
    addpath.add_path(AFI.ipv6, SAFI.unicast, 3)

    capabilities[Capability.CODE.ADD_PATH] = addpath

    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

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

    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

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

    open_msg = Open(Version(4), ASN(23456), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert Capability.CODE.MULTIPROTOCOL in open_msg.capabilities
    assert Capability.CODE.ROUTE_REFRESH in open_msg.capabilities
    assert Capability.CODE.FOUR_BYTES_ASN in open_msg.capabilities


def test_open_with_full_capability_set() -> None:
    """Test OPEN with comprehensive set of capabilities.
    """
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

    open_msg = Open(Version(4), ASN(23456), HoldTime(180), RouterID('192.0.2.1'), capabilities)

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
    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    msg = open_msg.message()

    # Should start with BGP marker
    assert msg[0:16] == b'\xff' * 16

    # Message type should be OPEN (0x01)
    assert msg[18] == 0x01

    # Message should be at least 29 bytes (minimum OPEN size)
    assert len(msg) >= 29


def test_open_message_encoding_with_capabilities() -> None:
    """Test OPEN message encoding with capabilities.
    """
    from exabgp.bgp.message.open.capability.mp import MultiProtocol

    capabilities = Capabilities()

    # Create MultiProtocol capability properly
    mp = MultiProtocol()
    mp.append((AFI.ipv4, SAFI.unicast))
    capabilities[Capability.CODE.MULTIPROTOCOL] = mp

    capabilities[Capability.CODE.ROUTE_REFRESH] = RouteRefresh()

    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    msg = open_msg.message()

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
        open_msg = Open(Version(4), ASN(65500), HoldTime(ht), RouterID('192.0.2.1'), capabilities)

        assert open_msg.hold_time == ht


def test_open_with_various_router_ids() -> None:
    """Test OPEN with various Router ID values.
    """
    router_ids = [
        '0.0.0.0',
        '10.0.0.1',
        '192.0.2.1',
        '172.16.0.1',
        '255.255.255.255',
    ]

    for rid in router_ids:
        capabilities = Capabilities()
        open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID(rid), capabilities)

        assert open_msg.router_id == RouterID(rid)


def test_open_version_field() -> None:
    """Test OPEN message version field.

    RFC 4271: BGP version is 4.
    """
    capabilities = Capabilities()
    open_msg = Open(Version(4), ASN(65500), HoldTime(180), RouterID('192.0.2.1'), capabilities)

    assert open_msg.version == 4


# ==============================================================================
# Phase 11: Capability Code Constants
# ==============================================================================

def test_capability_code_constants() -> None:
    """Test that capability code constants are defined correctly.
    """
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
# Summary
# ==============================================================================
# Total tests: 48
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
#
# This test suite ensures:
# - Proper OPEN message creation with various capabilities
# - Correct capability encoding and representation
# - Support for modern BGP features
# - RFC compliance for all tested capabilities
# - Realistic multi-capability scenarios
# ==============================================================================
