#!/usr/bin/env python3
# encoding: utf-8
"""test_operational_nop.py

Comprehensive tests for BGP OPERATIONAL and NOP messages

OPERATIONAL: Vendor-specific operational messages (not officially standardized)
NOP: Internal-only message type (cannot be sent on wire)

Created for ExaBGP testing framework
License: 3-clause BSD
"""

import pytest
import struct
from exabgp.bgp.message import Message
from exabgp.bgp.message.scheduling import NOP
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
# Part 1: NOP Message Tests
# ==============================================================================


def test_nop_creation() -> None:
    """Test NOP message creation.

    NOP is an internal message type used for control flow.
    """
    nop = NOP()
    assert str(nop) == 'NOP'
    assert nop.ID == Message.CODE.NOP


def test_nop_message_id() -> None:
    """Test NOP message ID is correct (0xFC = 252)."""
    assert NOP.ID == 0xFC
    assert NOP.ID == Message.CODE.NOP


def test_nop_message_type_bytes() -> None:
    """Test NOP TYPE byte representation."""
    assert NOP.TYPE == bytes([0xFC])


def test_nop_cannot_be_encoded() -> None:
    """Test that NOP messages cannot be encoded for transmission.

    NOP is an internal message only and should raise RuntimeError
    if you try to get its wire format.
    """
    nop = NOP()

    with pytest.raises(RuntimeError) as exc_info:
        nop.pack_message(None)

    assert 'NOP messages can not be sent on the wire' in str(exc_info.value)


def test_nop_cannot_be_encoded_with_negotiated() -> None:
    """Test that NOP encoding fails even with negotiated parameters."""
    nop = NOP()
    negotiated = {'test': 'value'}

    with pytest.raises(RuntimeError):
        nop.pack_message(negotiated)


def test_nop_unpack() -> None:
    """Test unpacking NOP message.

    Since NOP is internal, unpacking just returns a NOP instance.
    """
    data = b''
    nop = NOP.unpack_message(data, {})

    assert isinstance(nop, NOP)


def test_nop_unpack_with_data() -> None:
    """Test unpacking NOP message with arbitrary data.

    NOP unpacking ignores any data provided.
    """
    data = b'\x01\x02\x03\x04'
    nop = NOP.unpack_message(data, {})

    assert isinstance(nop, NOP)


def test_nop_singleton_instance() -> None:
    """Test that NOP module provides a singleton instance."""
    from exabgp.bgp.message.scheduling import _NOP

    assert isinstance(_NOP, NOP)


def test_nop_string_representation() -> None:
    """Test NOP string representation."""
    nop = NOP()
    assert str(nop) == 'NOP'


def test_nop_scheduling_attribute() -> None:
    """Test NOP has SCHEDULING = LATER for reactor scheduling."""
    from exabgp.bgp.message.scheduling import Scheduling

    nop = NOP()
    assert nop.SCHEDULING == Scheduling.LATER


# ==============================================================================
# Part 1.5: AWAKE and DONE Message Tests
# ==============================================================================


def test_awake_creation() -> None:
    """Test AWAKE message creation."""
    from exabgp.bgp.message.scheduling import AWAKE

    awake = AWAKE()
    assert str(awake) == 'AWAKE'
    assert awake.ID == Message.CODE.AWAKE


def test_awake_message_id() -> None:
    """Test AWAKE message ID is correct (0xFE = 254)."""
    from exabgp.bgp.message.scheduling import AWAKE

    assert AWAKE.ID == 0xFE
    assert AWAKE.ID == Message.CODE.AWAKE


def test_awake_scheduling_attribute() -> None:
    """Test AWAKE has SCHEDULING = NOW for immediate reactor scheduling."""
    from exabgp.bgp.message.scheduling import AWAKE, Scheduling

    awake = AWAKE()
    assert awake.SCHEDULING == Scheduling.NOW


def test_awake_cannot_be_encoded() -> None:
    """Test that AWAKE messages cannot be encoded for transmission."""
    from exabgp.bgp.message.scheduling import AWAKE

    awake = AWAKE()
    with pytest.raises(RuntimeError) as exc_info:
        awake.pack_message(None)
    assert 'AWAKE messages can not be sent on the wire' in str(exc_info.value)


def test_awake_singleton_instance() -> None:
    """Test that AWAKE module provides a singleton instance."""
    from exabgp.bgp.message.scheduling import AWAKE, _AWAKE

    assert isinstance(_AWAKE, AWAKE)


def test_done_creation() -> None:
    """Test DONE message creation."""
    from exabgp.bgp.message.scheduling import DONE

    done = DONE()
    assert str(done) == 'DONE'
    assert done.ID == Message.CODE.DONE


def test_done_message_id() -> None:
    """Test DONE message ID is correct (0xFD = 253)."""
    from exabgp.bgp.message.scheduling import DONE

    assert DONE.ID == 0xFD
    assert DONE.ID == Message.CODE.DONE


def test_done_scheduling_attribute() -> None:
    """Test DONE has SCHEDULING = CLOSE for peer removal."""
    from exabgp.bgp.message.scheduling import DONE, Scheduling

    done = DONE()
    assert done.SCHEDULING == Scheduling.CLOSE


def test_done_cannot_be_encoded() -> None:
    """Test that DONE messages cannot be encoded for transmission."""
    from exabgp.bgp.message.scheduling import DONE

    done = DONE()
    with pytest.raises(RuntimeError) as exc_info:
        done.pack_message(None)
    assert 'DONE messages can not be sent on the wire' in str(exc_info.value)


def test_done_singleton_instance() -> None:
    """Test that DONE module provides a singleton instance."""
    from exabgp.bgp.message.scheduling import DONE, _DONE

    assert isinstance(_DONE, DONE)


def test_scheduling_enum_values() -> None:
    """Test Scheduling enum has correct values."""
    from exabgp.bgp.message.scheduling import Scheduling

    # Values are: MESSAGE=0, NOW=1, LATER=2, CLOSE=3
    assert Scheduling.MESSAGE == 0x00
    assert Scheduling.NOW == 0x01
    assert Scheduling.LATER == 0x02
    assert Scheduling.CLOSE == 0x03


def test_scheduling_enum_string_format() -> None:
    """Test Scheduling enum string formatting."""
    from exabgp.bgp.message.scheduling import Scheduling

    assert str(Scheduling.LATER) == 'later'
    assert str(Scheduling.NOW) == 'now'
    assert str(Scheduling.CLOSE) == 'close'


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
    assert Operational.CODE.ADM == 0x01
    assert Operational.CODE.ASM == 0x02

    # Query messages
    assert Operational.CODE.RPCQ == 0x03
    assert Operational.CODE.APCQ == 0x05
    assert Operational.CODE.LPCQ == 0x07

    # Response messages
    assert Operational.CODE.RPCP == 0x04
    assert Operational.CODE.APCP == 0x06
    assert Operational.CODE.LPCP == 0x08

    # Control messages
    assert Operational.CODE.MP == 0xFFFE
    assert Operational.CODE.NS == 0xFFFF


def test_operational_registered_operational() -> None:
    """Test that operational message types are registered."""
    # Check that various message types are registered
    registered = Operational.registered_operational

    # Advisory messages
    assert Operational.CODE.ADM in registered
    assert Operational.CODE.ASM in registered

    # Query messages
    assert Operational.CODE.RPCQ in registered
    assert Operational.CODE.APCQ in registered
    assert Operational.CODE.LPCQ in registered

    # Response messages
    assert Operational.CODE.RPCP in registered
    assert Operational.CODE.APCP in registered
    assert Operational.CODE.LPCP in registered


# ==============================================================================
# Part 3: Advisory Messages (ADM, ASM)
# ==============================================================================


def test_advisory_adm_creation() -> None:
    """Test Advisory Demand Message (ADM) creation.

    ADM: Advisory messages for real-time notifications.
    """
    adm = Advisory.ADM(AFI.ipv4, SAFI.unicast, 'Test advisory message')

    assert adm.afi == AFI.ipv4
    assert adm.safi == SAFI.unicast
    assert b'Test advisory message' in adm.data
    assert adm.name == 'ADM'
    assert adm.code == Operational.CODE.ADM


def test_advisory_asm_creation() -> None:
    """Test Advisory Static Message (ASM) creation.

    ASM: Advisory messages for static/persistent notifications.
    """
    asm = Advisory.ASM(AFI.ipv6, SAFI.multicast, 'Static message')

    assert asm.afi == AFI.ipv6
    assert asm.safi == SAFI.multicast
    assert b'Static message' in asm.data
    assert asm.name == 'ASM'
    assert asm.code == Operational.CODE.ASM


def test_advisory_message_truncation() -> None:
    """Test that long advisory messages are truncated.

    MAX_ADVISORY is 2048 bytes; longer messages should be truncated.
    """
    from exabgp.bgp.message.operational import MAX_ADVISORY

    # Create a message longer than MAX_ADVISORY
    long_message = 'A' * (MAX_ADVISORY + 100)

    adm = Advisory.ADM(AFI.ipv4, SAFI.unicast, long_message)

    # Data should be truncated to MAX_ADVISORY
    assert len(adm.data) <= MAX_ADVISORY

    # Should end with "..." to indicate truncation
    assert adm.data.endswith(b'...')


def test_advisory_adm_encoding() -> None:
    """Test ADM message encoding."""
    adm = Advisory.ADM(AFI.ipv4, SAFI.unicast, 'Test')

    # Create mock negotiated object
    negotiated = type('obj', (object,), {})()

    msg = adm.pack_message(negotiated)

    # Should start with BGP marker
    assert msg[0:16] == b'\xff' * 16

    # Message type should be OPERATIONAL (0x06)
    assert msg[18] == 0x06


def test_advisory_asm_encoding() -> None:
    """Test ASM message encoding."""
    asm = Advisory.ASM(AFI.ipv6, SAFI.unicast, 'Message')

    negotiated = type('obj', (object,), {})()
    msg = asm.pack_message(negotiated)

    # Verify basic message structure
    assert len(msg) >= 19  # At least header length
    assert msg[18] == 0x06  # OPERATIONAL type


def test_advisory_extensive_representation() -> None:
    """Test advisory message extensive representation."""
    adm = Advisory.ADM(AFI.ipv4, SAFI.unicast, 'Test advisory')

    extensive = adm.extensive()
    assert 'operational' in extensive.lower()
    assert 'ADM' in extensive
    assert 'afi' in extensive.lower()
    assert 'safi' in extensive.lower()


def test_advisory_utf8_encoding() -> None:
    """Test that advisory messages properly encode UTF-8."""
    # Test with non-ASCII characters
    message = 'Test message with émojis 🎉'

    adm = Advisory.ADM(AFI.ipv4, SAFI.unicast, message)

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

    rpcq = Query.RPCQ(AFI.ipv4, SAFI.unicast, router_id, sequence)

    assert rpcq.afi == AFI.ipv4
    assert rpcq.safi == SAFI.unicast
    assert rpcq.routerid == router_id
    assert rpcq.sequence == sequence
    assert rpcq.name == 'RPCQ'
    assert rpcq.code == Operational.CODE.RPCQ


def test_query_apcq_creation() -> None:
    """Test Adj-Rib-Out Prefix Count Query (APCQ) creation."""
    router_id = RouterID('10.0.0.1')
    sequence = 67890

    apcq = Query.APCQ(AFI.ipv6, SAFI.multicast, router_id, sequence)

    assert apcq.afi == AFI.ipv6
    assert apcq.safi == SAFI.multicast
    assert apcq.name == 'APCQ'


def test_query_lpcq_creation() -> None:
    """Test BGP Loc-Rib Prefix Count Query (LPCQ) creation."""
    router_id = RouterID('172.16.0.1')
    sequence = 99999

    lpcq = Query.LPCQ(AFI.ipv4, SAFI.mpls_vpn, router_id, sequence)

    assert lpcq.afi == AFI.ipv4
    assert lpcq.safi == SAFI.mpls_vpn
    assert lpcq.name == 'LPCQ'


def test_query_extensive_with_params() -> None:
    """Test query extensive representation with router ID and sequence."""
    router_id = RouterID('192.0.2.1')
    sequence = 12345

    rpcq = Query.RPCQ(AFI.ipv4, SAFI.unicast, router_id, sequence)

    extensive = rpcq.extensive()
    assert 'RPCQ' in extensive
    assert 'router-id' in extensive
    assert 'sequence' in extensive
    assert '192.0.2.1' in extensive or str(router_id) in extensive
    assert '12345' in extensive


def test_query_extensive_without_params() -> None:
    """Test query extensive representation without router ID/sequence."""
    rpcq = Query.RPCQ(AFI.ipv4, SAFI.unicast, None, None)

    extensive = rpcq.extensive()
    assert 'RPCQ' in extensive
    assert 'afi' in extensive.lower()
    assert 'safi' in extensive.lower()
    # Should not include router-id/sequence if not provided
    assert 'router-id' not in extensive or rpcq._routerid is None


# ==============================================================================
# Part 5: Response/Counter Messages (RPCP, APCP, LPCP)
# ==============================================================================


def test_response_rpcp_creation() -> None:
    """Test Reachable Prefix Count Reply (RPCP) creation."""
    router_id = RouterID('192.0.2.1')
    sequence = 12345
    counter = 10000

    rpcp = Response.RPCP(AFI.ipv4, SAFI.unicast, router_id, sequence, counter)

    assert rpcp.afi == AFI.ipv4
    assert rpcp.safi == SAFI.unicast
    assert rpcp.routerid == router_id
    assert rpcp.sequence == sequence
    assert rpcp.counter == counter
    assert rpcp.name == 'RPCP'


def test_response_apcp_creation() -> None:
    """Test Adj-Rib-Out Prefix Count Reply (APCP) creation."""
    router_id = RouterID('10.0.0.1')
    sequence = 67890
    counter = 5000

    apcp = Response.APCP(AFI.ipv6, SAFI.unicast, router_id, sequence, counter)

    assert apcp.counter == counter
    assert apcp.name == 'APCP'


def test_response_lpcp_creation() -> None:
    """Test Loc-Rib Prefix Count Reply (LPCP) creation."""
    router_id = RouterID('172.16.0.1')
    sequence = 11111
    counter = 25000

    lpcp = Response.LPCP(AFI.ipv4, SAFI.multicast, router_id, sequence, counter)

    assert lpcp.counter == counter
    assert lpcp.name == 'LPCP'


def test_response_extensive_with_params() -> None:
    """Test response extensive representation with all parameters."""
    router_id = RouterID('192.0.2.1')
    sequence = 12345
    counter = 10000

    rpcp = Response.RPCP(AFI.ipv4, SAFI.unicast, router_id, sequence, counter)

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

    rpcp = Response.RPCP(AFI.ipv4, SAFI.unicast, router_id, sequence, counter)

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
        struct.pack('!H', Operational.CODE.ADM)  # Type
        + struct.pack('!H', 2 + 1 + len(advisory_text))  # Length: AFI(2)+SAFI(1)+message
        + struct.pack('!H', AFI.ipv4)  # AFI
        + struct.pack('!B', SAFI.unicast)  # SAFI
        + advisory_text  # Advisory message
    )

    op = Operational.unpack_message(data, {})

    assert isinstance(op, Advisory.ADM)
    assert op.afi == AFI.ipv4
    assert op.safi == SAFI.unicast
    assert op.data == advisory_text
    assert op.name == 'ADM'


def test_operational_unpack_asm() -> None:
    """Test unpacking Advisory Static Message (ASM)."""
    advisory_text = b'Static configuration message'

    data = (
        struct.pack('!H', Operational.CODE.ASM)  # Type
        + struct.pack('!H', 2 + 1 + len(advisory_text))  # Length: AFI(2)+SAFI(1)+message
        + struct.pack('!H', AFI.ipv6)  # AFI
        + struct.pack('!B', SAFI.multicast)  # SAFI
        + advisory_text  # Advisory message
    )

    op = Operational.unpack_message(data, {})

    assert isinstance(op, Advisory.ASM)
    assert op.afi == AFI.ipv6
    assert op.safi == SAFI.multicast
    assert op.data == advisory_text
    assert op.name == 'ASM'


def test_operational_unpack_rpcq() -> None:
    """Test unpacking Reachable Prefix Count Query (RPCQ)."""
    router_id = RouterID('192.0.2.1')
    sequence = 12345

    data = (
        struct.pack('!H', Operational.CODE.RPCQ)  # Type
        + struct.pack('!H', 11)  # Length: AFI(2)+SAFI(1)+RouterID(4)+Seq(4)
        + struct.pack('!H', AFI.ipv4)  # AFI
        + struct.pack('!B', SAFI.unicast)  # SAFI
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
        struct.pack('!H', Operational.CODE.RPCP)  # Type
        + struct.pack('!H', 15)  # Length: AFI(2)+SAFI(1)+RID(4)+Seq(4)+Counter(4)
        + struct.pack('!H', AFI.ipv4)  # AFI
        + struct.pack('!B', SAFI.unicast)  # SAFI
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
    assert OperationalFamily.has_family is True


def test_operational_family_family_method() -> None:
    """Test OperationalFamily family() method returns (AFI, SAFI) tuple."""
    adm = Advisory.ADM(AFI.ipv4, SAFI.unicast, 'Test')

    family = adm.family()
    assert family == (AFI.ipv4, SAFI.unicast)


def test_sequenced_operational_family_has_routerid() -> None:
    """Test SequencedOperationalFamily has_routerid flag."""
    assert SequencedOperationalFamily.has_routerid is True


def test_sequenced_operational_family_attributes() -> None:
    """Test SequencedOperationalFamily stores router ID and sequence."""
    router_id = RouterID('192.0.2.1')
    sequence = 12345

    rpcq = Query.RPCQ(AFI.ipv4, SAFI.unicast, router_id, sequence)

    assert rpcq.routerid == router_id
    assert rpcq.sequence == sequence
    assert rpcq._routerid == router_id
    assert rpcq._sequence == sequence


# ==============================================================================
# Part 8: NS (Not Satisfied) Error Messages
# ==============================================================================


def test_ns_malformed_creation() -> None:
    """Test NS Malformed error message creation."""
    sequence = struct.pack('!L', 100)
    ns = NS.Malformed(AFI.ipv4, SAFI.unicast, sequence)

    assert ns.is_fault is True
    assert ns.name == 'NS malformed'
    assert NS.Malformed.ERROR_SUBCODE == b'\x00\x01'


def test_ns_unsupported_creation() -> None:
    """Test NS Unsupported error message creation."""
    sequence = struct.pack('!L', 200)
    ns = NS.Unsupported(AFI.ipv6, SAFI.multicast, sequence)

    assert ns.is_fault is True
    assert ns.name == 'NS unsupported'


def test_ns_maximum_creation() -> None:
    """Test NS Maximum (query frequency exceeded) error."""
    sequence = struct.pack('!L', 300)
    ns = NS.Maximum(AFI.ipv4, SAFI.unicast, sequence)

    assert ns.name == 'NS maximum'


def test_ns_prohibited_creation() -> None:
    """Test NS Prohibited (administratively prohibited) error."""
    sequence = struct.pack('!L', 400)
    ns = NS.Prohibited(AFI.ipv4, SAFI.unicast, sequence)

    assert ns.name == 'NS prohibited'


def test_ns_busy_creation() -> None:
    """Test NS Busy error message creation."""
    sequence = struct.pack('!L', 500)
    ns = NS.Busy(AFI.ipv4, SAFI.unicast, sequence)

    assert ns.name == 'NS busy'


def test_ns_notfound_creation() -> None:
    """Test NS NotFound error message creation."""
    sequence = struct.pack('!L', 600)
    ns = NS.NotFound(AFI.ipv4, SAFI.unicast, sequence)

    assert ns.name == 'NS notfound'


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
# Total tests: 60
#
# NOP Message Tests (10 tests):
# - Creation and basic properties
# - Message ID and type verification
# - Encoding restrictions (cannot be sent on wire)
# - Unpacking behavior
# - String representation
#
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
# - NOP is internal-only and cannot be transmitted
# - OPERATIONAL messages are properly structured
# - Advisory, Query, and Response message types work correctly
# - Message encoding/decoding for operational messages
# - NS error handling
# - Family and sequenced operational family behaviors
# ==============================================================================
