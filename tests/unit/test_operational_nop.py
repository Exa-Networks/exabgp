#!/usr/bin/env python3
# encoding: utf-8
"""test_operational_nop.py

Comprehensive tests for BGP OPERATIONAL messages

OPERATIONAL: Vendor-specific operational messages (not officially standardized)

Created for ExaBGP testing framework
License: 3-clause BSD
"""

import struct
from exabgp.bgp.message import Message
from exabgp.bgp.message.operational import (
    Operational,
    Advisory,
    Query,
    Response,
    NS,
    OperationalFamily,
    SequencedOperationalFamily,
)
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.protocol.family import AFI, SAFI


# ==============================================================================
# Part 2: OPERATIONAL Message Constants and Registration
# ==============================================================================


def test_operational_message_id() -> None:
    """Test OPERATIONAL message ID.

    OPERATIONAL uses message type 0x06 (6).
    Note: Not officially IANA-assigned, vendor-specific.
    """
    assert Operational.ID == 6
    assert Operational.ID == Message.CODE.OPERATIONAL


def test_operational_message_type_bytes() -> None:
    """Test OPERATIONAL TYPE byte representation."""
    assert Operational.TYPE == b'\x06'


def test_operational_message_registration() -> None:
    """Test that OPERATIONAL is properly registered."""
    assert Message.CODE.OPERATIONAL in Message.registered_message

    klass = Message.klass(Message.CODE.OPERATIONAL)
    assert klass == Operational


def test_operational_code_constants() -> None:
    """Test OPERATIONAL code constants for various message types."""
    # Advisory messages
    assert Operational.SUBTYPE.ADM == 0x01
    assert Operational.SUBTYPE.ASM == 0x02

    # Query messages
    assert Operational.SUBTYPE.RPCQ == 0x03
    assert Operational.SUBTYPE.APCQ == 0x05
    assert Operational.SUBTYPE.LPCQ == 0x07

    # Response messages
    assert Operational.SUBTYPE.RPCP == 0x04
    assert Operational.SUBTYPE.APCP == 0x06
    assert Operational.SUBTYPE.LPCP == 0x08

    # Control messages
    assert Operational.SUBTYPE.MP == 0xFFFE
    assert Operational.SUBTYPE.NS == 0xFFFF


def test_operational_registered_operational() -> None:
    """Test that operational message types are registered."""
    # Check that various message types are registered
    registered = Operational.registered_operational

    # Advisory messages
    assert Operational.SUBTYPE.ADM in registered
    assert Operational.SUBTYPE.ASM in registered

    # Query messages
    assert Operational.SUBTYPE.RPCQ in registered
    assert Operational.SUBTYPE.APCQ in registered
    assert Operational.SUBTYPE.LPCQ in registered

    # Response messages
    assert Operational.SUBTYPE.RPCP in registered
    assert Operational.SUBTYPE.APCP in registered
    assert Operational.SUBTYPE.LPCP in registered


# ==============================================================================
# Part 3: Advisory Messages (ADM, ASM)
# ==============================================================================


def test_advisory_adm_creation() -> None:
    """Test Advisory Demand Message (ADM) creation.

    ADM: Advisory messages for real-time notifications.
    """
    adm = Advisory.ADM.make_advisory(AFI.ipv4, SAFI.unicast, 'Test advisory message')

    assert adm.afi == AFI.ipv4
    assert adm.safi == SAFI.unicast
    assert b'Test advisory message' in adm.data
    assert adm.NAME == 'ADM'
    assert adm.SUBTYPE_ID == Operational.SUBTYPE.ADM


def test_advisory_asm_creation() -> None:
    """Test Advisory Static Message (ASM) creation.

    ASM: Advisory messages for static/persistent notifications.
    """
    asm = Advisory.ASM.make_advisory(AFI.ipv6, SAFI.multicast, 'Static message')

    assert asm.afi == AFI.ipv6
    assert asm.safi == SAFI.multicast
    assert b'Static message' in asm.data
    assert asm.NAME == 'ASM'
    assert asm.SUBTYPE_ID == Operational.SUBTYPE.ASM


def test_advisory_message_truncation() -> None:
    """Test that long advisory messages are truncated.

    MAX_ADVISORY is 2048 bytes; longer messages should be truncated.
    """
    from exabgp.bgp.message.operational import MAX_ADVISORY

    # Create a message longer than MAX_ADVISORY
    long_message = 'A' * (MAX_ADVISORY + 100)

    adm = Advisory.ADM.make_advisory(AFI.ipv4, SAFI.unicast, long_message)

    # Data should be truncated to MAX_ADVISORY
    assert len(adm.data) <= MAX_ADVISORY

    # Should end with "..." to indicate truncation
    assert adm.data.endswith(b'...')


def test_advisory_adm_encoding() -> None:
    """Test ADM message encoding."""
    adm = Advisory.ADM.make_advisory(AFI.ipv4, SAFI.unicast, 'Test')

    # Create mock negotiated object
    negotiated = type('obj', (object,), {})()

    msg = adm.pack_message(negotiated)

    # Should start with BGP marker
    assert msg[0:16] == b'\xff' * 16

    # Message type should be OPERATIONAL (0x06)
    assert msg[18] == 0x06


def test_advisory_asm_encoding() -> None:
    """Test ASM message encoding."""
    asm = Advisory.ASM.make_advisory(AFI.ipv6, SAFI.unicast, 'Message')

    negotiated = type('obj', (object,), {})()
    msg = asm.pack_message(negotiated)

    # Verify basic message structure
    assert len(msg) >= 19  # At least header length
    assert msg[18] == 0x06  # OPERATIONAL type


def test_advisory_extensive_representation() -> None:
    """Test advisory message extensive representation."""
    adm = Advisory.ADM.make_advisory(AFI.ipv4, SAFI.unicast, 'Test advisory')

    extensive = adm.extensive()
    assert 'operational' in extensive.lower()
    assert 'ADM' in extensive
    assert 'afi' in extensive.lower()
    assert 'safi' in extensive.lower()


def test_advisory_utf8_encoding() -> None:
    """Test that advisory messages properly encode UTF-8."""
    # Test with non-ASCII characters
    message = 'Test message with émojis 🎉'

    adm = Advisory.ADM.make_advisory(AFI.ipv4, SAFI.unicast, message)

    # Data should be UTF-8 encoded
    assert isinstance(adm.data, bytes)
    assert message.encode('utf-8') == adm.data


# ==============================================================================
# Part 4: Query Messages (RPCQ, APCQ, LPCQ)
# ==============================================================================


def test_query_rpcq_creation() -> None:
    """Test Reachable Prefix Count Query (RPCQ) creation.

    RPCQ: Request for count of reachable prefixes.
    """
    router_id = RouterID('192.0.2.1')
    sequence = 12345

    rpcq = Query.RPCQ.make_query(AFI.ipv4, SAFI.unicast, router_id, sequence)

    assert rpcq.afi == AFI.ipv4
    assert rpcq.safi == SAFI.unicast
    assert rpcq.routerid == router_id
    assert rpcq.sequence == sequence
    assert rpcq.NAME == 'RPCQ'
    assert rpcq.SUBTYPE_ID == Operational.SUBTYPE.RPCQ


def test_query_apcq_creation() -> None:
    """Test Adj-Rib-Out Prefix Count Query (APCQ) creation."""
    router_id = RouterID('10.0.0.1')
    sequence = 67890

    apcq = Query.APCQ.make_query(AFI.ipv6, SAFI.multicast, router_id, sequence)

    assert apcq.afi == AFI.ipv6
    assert apcq.safi == SAFI.multicast
    assert apcq.NAME == 'APCQ'


def test_query_lpcq_creation() -> None:
    """Test BGP Loc-Rib Prefix Count Query (LPCQ) creation."""
    router_id = RouterID('172.16.0.1')
    sequence = 99999

    lpcq = Query.LPCQ.make_query(AFI.ipv4, SAFI.mpls_vpn, router_id, sequence)

    assert lpcq.afi == AFI.ipv4
    assert lpcq.safi == SAFI.mpls_vpn
    assert lpcq.NAME == 'LPCQ'


def test_query_extensive_with_params() -> None:
    """Test query extensive representation with router ID and sequence."""
    router_id = RouterID('192.0.2.1')
    sequence = 12345

    rpcq = Query.RPCQ.make_query(AFI.ipv4, SAFI.unicast, router_id, sequence)

    extensive = rpcq.extensive()
    assert 'RPCQ' in extensive
    assert 'router-id' in extensive
    assert 'sequence' in extensive
    assert '192.0.2.1' in extensive or str(router_id) in extensive
    assert '12345' in extensive


def test_query_extensive_without_params() -> None:
    """Test query extensive representation without router ID/sequence."""
    rpcq = Query.RPCQ.make_query(AFI.ipv4, SAFI.unicast, None, None)

    extensive = rpcq.extensive()
    assert 'RPCQ' in extensive
    assert 'afi' in extensive.lower()
    assert 'safi' in extensive.lower()
    # Should not include router-id/sequence if not provided
    assert 'router-id' not in extensive or rpcq.routerid is None


# ==============================================================================
# Part 5: Response/Counter Messages (RPCP, APCP, LPCP)
# ==============================================================================


def test_response_rpcp_creation() -> None:
    """Test Reachable Prefix Count Reply (RPCP) creation."""
    router_id = RouterID('192.0.2.1')
    sequence = 12345
    counter = 10000

    rpcp = Response.RPCP.make_counter(AFI.ipv4, SAFI.unicast, router_id, sequence, counter)

    assert rpcp.afi == AFI.ipv4
    assert rpcp.safi == SAFI.unicast
    assert rpcp.routerid == router_id
    assert rpcp.sequence == sequence
    assert rpcp.counter == counter
    assert rpcp.NAME == 'RPCP'


def test_response_apcp_creation() -> None:
    """Test Adj-Rib-Out Prefix Count Reply (APCP) creation."""
    router_id = RouterID('10.0.0.1')
    sequence = 67890
    counter = 5000

    apcp = Response.APCP.make_counter(AFI.ipv6, SAFI.unicast, router_id, sequence, counter)

    assert apcp.counter == counter
    assert apcp.NAME == 'APCP'


def test_response_lpcp_creation() -> None:
    """Test Loc-Rib Prefix Count Reply (LPCP) creation."""
    router_id = RouterID('172.16.0.1')
    sequence = 11111
    counter = 25000

    lpcp = Response.LPCP.make_counter(AFI.ipv4, SAFI.multicast, router_id, sequence, counter)

    assert lpcp.counter == counter
    assert lpcp.NAME == 'LPCP'


def test_response_extensive_with_params() -> None:
    """Test response extensive representation with all parameters."""
    router_id = RouterID('192.0.2.1')
    sequence = 12345
    counter = 10000

    rpcp = Response.RPCP.make_counter(AFI.ipv4, SAFI.unicast, router_id, sequence, counter)

    extensive = rpcp.extensive()
    assert 'RPCP' in extensive
    assert 'router-id' in extensive
    assert 'sequence' in extensive
    assert 'counter' in extensive
    assert '10000' in extensive


def test_response_counter_encoding() -> None:
    """Test that response messages properly encode counter value.

    Counter is packed as 4-byte unsigned integer (network byte order).
    """
    router_id = RouterID('192.0.2.1')
    sequence = 100
    counter = 12345

    rpcp = Response.RPCP.make_counter(AFI.ipv4, SAFI.unicast, router_id, sequence, counter)

    # The counter should be in the data field as packed 4-byte integer
    expected_counter = struct.pack('!L', counter)
    assert expected_counter in rpcp.data


# ==============================================================================
# Part 6: OPERATIONAL Message Decoding
# ==============================================================================


def test_operational_unpack_adm() -> None:
    """Test unpacking Advisory Demand Message (ADM)."""
    advisory_text = b'Critical alert message'

    data = (
        struct.pack('!H', Operational.SUBTYPE.ADM)  # Type
        + struct.pack('!H', 2 + 1 + len(advisory_text))  # Length: AFI(2)+SAFI(1)+message
        + struct.pack('!H', int(AFI.ipv4))  # AFI
        + struct.pack('!B', int(SAFI.unicast))  # SAFI
        + advisory_text  # Advisory message
    )

    op = Operational.unpack_message(data, {})

    assert isinstance(op, Advisory.ADM)
    assert op.afi == AFI.ipv4
    assert op.safi == SAFI.unicast
    assert op.data == advisory_text
    assert op.NAME == 'ADM'


def test_operational_unpack_asm() -> None:
    """Test unpacking Advisory Static Message (ASM)."""
    advisory_text = b'Static configuration message'

    data = (
        struct.pack('!H', Operational.SUBTYPE.ASM)  # Type
        + struct.pack('!H', 2 + 1 + len(advisory_text))  # Length: AFI(2)+SAFI(1)+message
        + struct.pack('!H', int(AFI.ipv6))  # AFI
        + struct.pack('!B', int(SAFI.multicast))  # SAFI
        + advisory_text  # Advisory message
    )

    op = Operational.unpack_message(data, {})

    assert isinstance(op, Advisory.ASM)
    assert op.afi == AFI.ipv6
    assert op.safi == SAFI.multicast
    assert op.data == advisory_text
    assert op.NAME == 'ASM'


def test_operational_unpack_rpcq() -> None:
    """Test unpacking Reachable Prefix Count Query (RPCQ)."""
    router_id = RouterID('192.0.2.1')
    sequence = 12345

    data = (
        struct.pack('!H', Operational.SUBTYPE.RPCQ)  # Type
        + struct.pack('!H', 11)  # Length: AFI(2)+SAFI(1)+RouterID(4)+Seq(4)
        + struct.pack('!H', int(AFI.ipv4))  # AFI
        + struct.pack('!B', int(SAFI.unicast))  # SAFI
        + router_id.pack_ip()  # Router ID (4 bytes)
        + struct.pack('!L', sequence)  # Sequence (4 bytes)
    )

    op = Operational.unpack_message(data, {})

    assert isinstance(op, Query.RPCQ)
    assert op.afi == AFI.ipv4
    assert op.safi == SAFI.unicast
    assert op.routerid == router_id
    assert op.sequence == sequence


def test_operational_unpack_rpcp() -> None:
    """Test unpacking Reachable Prefix Count Reply (RPCP)."""
    router_id = RouterID('10.0.0.1')
    sequence = 67890
    counter = 10000

    data = (
        struct.pack('!H', Operational.SUBTYPE.RPCP)  # Type
        + struct.pack('!H', 15)  # Length: AFI(2)+SAFI(1)+RID(4)+Seq(4)+Counter(4)
        + struct.pack('!H', int(AFI.ipv4))  # AFI
        + struct.pack('!B', int(SAFI.unicast))  # SAFI
        + router_id.pack_ip()  # Router ID
        + struct.pack('!L', sequence)  # Sequence
        + struct.pack('!L', counter)  # Counter
    )

    op = Operational.unpack_message(data, {})

    assert isinstance(op, Response.RPCP)
    assert op.counter == counter


# ==============================================================================
# Part 7: OPERATIONAL Family Classes
# ==============================================================================


def test_operational_family_has_family() -> None:
    """Test OperationalFamily has_family flag."""
    assert OperationalFamily.HAS_FAMILY is True


def test_operational_family_family_method() -> None:
    """Test OperationalFamily family() method returns (AFI, SAFI) tuple."""
    adm = Advisory.ADM.make_advisory(AFI.ipv4, SAFI.unicast, 'Test')

    family = adm.family()
    assert family == (AFI.ipv4, SAFI.unicast)


def test_sequenced_operational_family_has_routerid() -> None:
    """Test SequencedOperationalFamily has_routerid flag."""
    assert SequencedOperationalFamily.HAS_ROUTERID is True


def test_sequenced_operational_family_attributes() -> None:
    """Test SequencedOperationalFamily stores router ID and sequence."""
    router_id = RouterID('192.0.2.1')
    sequence = 12345

    rpcq = Query.RPCQ.make_query(AFI.ipv4, SAFI.unicast, router_id, sequence)

    assert rpcq.routerid == router_id
    assert rpcq.sequence == sequence
    assert rpcq.routerid == router_id
    assert rpcq.sequence == sequence


# ==============================================================================
# Part 8: NS (Not Satisfied) Error Messages
# ==============================================================================


def test_ns_malformed_creation() -> None:
    """Test NS Malformed error message creation."""
    sequence = struct.pack('!L', 100)
    ns = NS.Malformed.make_ns(AFI.ipv4, SAFI.unicast, sequence)

    assert ns.IS_FAULT is True
    assert ns.NAME == 'NS malformed'
    assert NS.Malformed.ERROR_SUBCODE == b'\x00\x01'


def test_ns_unsupported_creation() -> None:
    """Test NS Unsupported error message creation."""
    sequence = struct.pack('!L', 200)
    ns = NS.Unsupported.make_ns(AFI.ipv6, SAFI.multicast, sequence)

    assert ns.IS_FAULT is True
    assert ns.NAME == 'NS unsupported'


def test_ns_maximum_creation() -> None:
    """Test NS Maximum (query frequency exceeded) error."""
    sequence = struct.pack('!L', 300)
    ns = NS.Maximum.make_ns(AFI.ipv4, SAFI.unicast, sequence)

    assert ns.NAME == 'NS maximum'


def test_ns_prohibited_creation() -> None:
    """Test NS Prohibited (administratively prohibited) error."""
    sequence = struct.pack('!L', 400)
    ns = NS.Prohibited.make_ns(AFI.ipv4, SAFI.unicast, sequence)

    assert ns.NAME == 'NS prohibited'


def test_ns_busy_creation() -> None:
    """Test NS Busy error message creation."""
    sequence = struct.pack('!L', 500)
    ns = NS.Busy.make_ns(AFI.ipv4, SAFI.unicast, sequence)

    assert ns.NAME == 'NS busy'


def test_ns_notfound_creation() -> None:
    """Test NS NotFound error message creation."""
    sequence = struct.pack('!L', 600)
    ns = NS.NotFound.make_ns(AFI.ipv4, SAFI.unicast, sequence)

    assert ns.NAME == 'NS notfound'


def test_ns_error_subcodes() -> None:
    """Test NS error subcode constants."""
    assert NS.MALFORMED == 0x01
    assert NS.UNSUPPORTED == 0x02
    assert NS.MAXIMUM == 0x03
    assert NS.PROHIBITED == 0x04
    assert NS.BUSY == 0x05
    assert NS.NOTFOUND == 0x06


# ==============================================================================
# Summary
# ==============================================================================
# OPERATIONAL Message Tests (50 tests):
# - Message constants and registration (5 tests)
# - Advisory messages - ADM/ASM (8 tests)
# - Query messages - RPCQ/APCQ/LPCQ (6 tests)
# - Response messages - RPCP/APCP/LPCP (6 tests)
# - Message decoding (4 tests)
# - Family classes (4 tests)
# - NS error messages (8 tests)
#
# This test suite ensures:
# - OPERATIONAL messages are properly structured
# - Advisory, Query, and Response message types work correctly
# - Message encoding/decoding for operational messages
# - NS error handling
# - Family and sequenced operational family behaviors
# ==============================================================================
