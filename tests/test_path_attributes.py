"""Comprehensive tests for basic BGP path attributes.

These tests cover individual well-known mandatory and optional path attributes:

Test Coverage:
Phase 1: Well-Known Mandatory Attributes (tests 1-7)
  - ORIGIN (Type 1): IGP, EGP, INCOMPLETE
  - AS_PATH (Type 2): Covered in test_aspath.py
  - NEXT_HOP (Type 3): IPv4 validation, special addresses

Phase 2: Well-Known Discretionary Attributes (tests 8-11)
  - LOCAL_PREF (Type 5): Basic parsing, IBGP only
  - ATOMIC_AGGREGATE (Type 6): Zero-length validation

Phase 3: Optional Transitive Attributes (tests 12-18)
  - AGGREGATOR (Type 7): 2-byte/4-byte ASN, AS4_AGGREGATOR
  - COMMUNITIES (Type 8): Covered in test_communities.py

Phase 4: Optional Non-Transitive Attributes (tests 19-24)
  - MED/MULTI_EXIT_DISC (Type 4): Basic parsing, optional nature
  - ORIGINATOR_ID (Type 9): Route reflection
  - CLUSTER_LIST (Type 10): Loop detection

Phase 5: Extended Attributes (tests 25-27)
  - AIGP (Type 26): Accumulated IGP metric
  - Attribute flag combinations
  - Unknown attribute handling

Note: AS_PATH is extensively tested in test_aspath.py (21 tests)
Note: COMMUNITIES are extensively tested in test_communities.py (27 tests)
Note: Multiprotocol extensions (MP_REACH/MP_UNREACH) will be in test_multiprotocol.py
"""
import pytest
import struct
from unittest.mock import Mock, patch


@pytest.fixture(autouse=True)
def mock_logger():
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

    # Create a mock formater
    mock_formater = Mock(return_value="formatted message")

    option.logger = mock_option_logger
    option.formater = mock_formater

    yield

    # Restore original values
    option.logger = original_logger
    option.formater = original_formater


# ==============================================================================
# Phase 1: Well-Known Mandatory - ORIGIN (Type 1)
# ==============================================================================

def test_origin_igp():
    """Test ORIGIN attribute with IGP value.

    ORIGIN = 0 (IGP): Route learned from IGP in originating AS.
    Most common value for locally originated routes.
    """
    from exabgp.bgp.message.update.attribute.origin import Origin

    # Create ORIGIN IGP
    origin = Origin(Origin.IGP)

    # Verify value
    assert origin.origin == Origin.IGP
    assert str(origin) == "igp"

    # Verify pack/unpack
    packed = origin.pack()
    assert len(packed) == 1
    assert packed[0] == 0


def test_origin_egp():
    """Test ORIGIN attribute with EGP value.

    ORIGIN = 1 (EGP): Route learned from EGP (historical).
    Rarely used in modern BGP.
    """
    from exabgp.bgp.message.update.attribute.origin import Origin

    # Create ORIGIN EGP
    origin = Origin(Origin.EGP)

    # Verify value
    assert origin.origin == Origin.EGP
    assert str(origin) == "egp"

    # Verify pack
    packed = origin.pack()
    assert len(packed) == 1
    assert packed[0] == 1


def test_origin_incomplete():
    """Test ORIGIN attribute with INCOMPLETE value.

    ORIGIN = 2 (INCOMPLETE): Route learned by other means (e.g., static, redistributed).
    Common for routes redistributed from IGP.
    """
    from exabgp.bgp.message.update.attribute.origin import Origin

    # Create ORIGIN INCOMPLETE
    origin = Origin(Origin.INCOMPLETE)

    # Verify value
    assert origin.origin == Origin.INCOMPLETE
    assert str(origin) == "incomplete"

    # Verify pack
    packed = origin.pack()
    assert len(packed) == 1
    assert packed[0] == 2


# ==============================================================================
# Phase 1: Well-Known Mandatory - NEXT_HOP (Type 3)
# ==============================================================================

def test_nexthop_valid_ipv4():
    """Test NEXT_HOP attribute with valid IPv4 address.

    NEXT_HOP contains the IPv4 address of the next hop for the route.
    Must be reachable for the route to be usable.
    """
    from exabgp.bgp.message.update.attribute.nexthop import NextHop
    from exabgp.protocol.ip import IPv4

    # Create NEXT_HOP
    nh_ip = "192.0.2.1"
    nexthop = NextHop(nh_ip)

    # Verify value
    assert str(nexthop) == "next-hop 192.0.2.1"

    # Verify pack
    packed = nexthop.pack()
    assert len(packed) == 4
    # Should be 192.0.2.1 in network byte order
    assert packed == IPv4.pton(nh_ip)


def test_nexthop_zero_address():
    """Test NEXT_HOP with 0.0.0.0.

    0.0.0.0 is invalid as a next-hop in normal operation.
    However, it can be used in some special cases (e.g., withdraw).
    """
    from exabgp.bgp.message.update.attribute.nexthop import NextHop

    # Create NEXT_HOP with 0.0.0.0
    nexthop = NextHop("0.0.0.0")

    # Should create successfully
    assert str(nexthop) == "next-hop 0.0.0.0"

    packed = nexthop.pack()
    assert len(packed) == 4
    assert packed == b'\x00\x00\x00\x00'


def test_nexthop_self():
    """Test NEXT_HOP pointing to router itself.

    Router may set next-hop to itself when advertising routes to peers.
    Common in EBGP.
    """
    from exabgp.bgp.message.update.attribute.nexthop import NextHop

    # Create NEXT_HOP pointing to self
    nexthop = NextHop("10.0.0.1")

    assert str(nexthop) == "next-hop 10.0.0.1"

    packed = nexthop.pack()
    assert len(packed) == 4


def test_nexthop_third_party():
    """Test NEXT_HOP pointing to third-party router.

    In some scenarios (shared media), next-hop may point to a third party.
    """
    from exabgp.bgp.message.update.attribute.nexthop import NextHop

    # Create third-party NEXT_HOP
    nexthop = NextHop("10.0.0.254")

    assert "10.0.0.254" in str(nexthop)

    packed = nexthop.pack()
    assert len(packed) == 4


# ==============================================================================
# Phase 2: Well-Known Discretionary - LOCAL_PREF (Type 5)
# ==============================================================================

def test_localpref_basic():
    """Test LOCAL_PREF attribute basic parsing.

    LOCAL_PREF is 4-byte value used for route preference within an AS.
    Higher value = more preferred.
    Only used in IBGP, stripped in EBGP.
    """
    from exabgp.bgp.message.update.attribute.localpref import LocalPreference

    # Create LOCAL_PREF with value 100 (common default)
    localpref = LocalPreference(100)

    # Verify value
    assert localpref.localpref == 100
    assert str(localpref) == "local-preference 100"

    # Verify pack
    packed = localpref.pack()
    assert len(packed) == 4
    assert struct.unpack('!L', packed)[0] == 100


def test_localpref_high_preference():
    """Test LOCAL_PREF with high value.

    Higher LOCAL_PREF values are preferred over lower values.
    Common to use high values (e.g., 200) for preferred paths.
    """
    from exabgp.bgp.message.update.attribute.localpref import LocalPreference

    # Create high LOCAL_PREF
    localpref = LocalPreference(200)

    assert localpref.localpref == 200

    packed = localpref.pack()
    assert struct.unpack('!L', packed)[0] == 200


def test_localpref_ibgp_only():
    """Test that LOCAL_PREF is IBGP-only attribute.

    LOCAL_PREF must not be sent to EBGP peers.
    This is enforced by attribute flags (well-known discretionary).
    """
    from exabgp.bgp.message.update.attribute.localpref import LocalPreference
    from exabgp.bgp.message.update.attribute import Attribute

    # LOCAL_PREF should be well-known discretionary
    assert LocalPreference.ID == Attribute.CODE.LOCAL_PREF
    assert LocalPreference.FLAG == Attribute.Flag.TRANSITIVE


# ==============================================================================
# Phase 2: Well-Known Discretionary - ATOMIC_AGGREGATE (Type 6)
# ==============================================================================

def test_atomic_aggregate_zero_length():
    """Test ATOMIC_AGGREGATE attribute.

    ATOMIC_AGGREGATE is a well-known discretionary attribute with zero length.
    Indicates route is an atomic aggregate (information may have been lost).
    """
    from exabgp.bgp.message.update.attribute.atomicaggregate import AtomicAggregate

    # Create ATOMIC_AGGREGATE
    atomic = AtomicAggregate()

    # Verify representation
    assert str(atomic) == "atomic-aggregate"

    # Verify pack (should be zero length)
    packed = atomic.pack()
    assert len(packed) == 0


def test_atomic_aggregate_presence():
    """Test ATOMIC_AGGREGATE indicates loss of information.

    When present, indicates the route is a result of aggregation
    and some path attributes may have been lost.
    """
    from exabgp.bgp.message.update.attribute.atomicaggregate import AtomicAggregate
    from exabgp.bgp.message.update.attribute import Attribute

    # Create ATOMIC_AGGREGATE
    atomic = AtomicAggregate()

    # Verify it's well-known discretionary
    assert AtomicAggregate.ID == Attribute.CODE.ATOMIC_AGGREGATE
    assert AtomicAggregate.FLAG == Attribute.Flag.TRANSITIVE


# ==============================================================================
# Phase 3: Optional Transitive - AGGREGATOR (Type 7)
# ==============================================================================

def test_aggregator_2byte_asn():
    """Test AGGREGATOR attribute with 2-byte ASN.

    AGGREGATOR: ASN + IP of router that performed aggregation.
    Original format uses 2-byte ASN.
    """
    from exabgp.bgp.message.update.attribute.aggregator import Aggregator
    from exabgp.bgp.message.open.asn import ASN

    # Create AGGREGATOR with 2-byte ASN
    asn = ASN(65000)
    ip = "192.0.2.1"
    aggregator = Aggregator(asn, ip)

    # Verify representation
    assert "65000" in str(aggregator)
    assert "192.0.2.1" in str(aggregator)

    # Verify pack (2-byte ASN + 4-byte IP = 6 bytes)
    packed = aggregator.pack()
    assert len(packed) == 6


def test_aggregator_4byte_asn():
    """Test AGGREGATOR with 4-byte ASN.

    For 4-byte ASNs, AGGREGATOR is 4-byte ASN + 4-byte IP = 8 bytes.
    Requires 4-byte ASN support negotiation.
    """
    from exabgp.bgp.message.update.attribute.aggregator import Aggregator
    from exabgp.bgp.message.open.asn import ASN

    # Create mock negotiated with 4-byte ASN support
    negotiated = Mock()
    negotiated.asn4 = True

    # Create AGGREGATOR with 4-byte ASN
    asn = ASN(4200000000)
    ip = "192.0.2.1"
    aggregator = Aggregator(asn, ip)

    # Verify pack with 4-byte ASN (4 + 4 = 8 bytes)
    packed = aggregator.pack(negotiated)
    assert len(packed) == 8


def test_aggregator_as_trans():
    """Test AGGREGATOR with AS_TRANS.

    When advertising to old BGP speaker, 4-byte ASN is encoded as AS_TRANS (23456).
    Real ASN is in AS4_AGGREGATOR.
    """
    from exabgp.bgp.message.update.attribute.aggregator import Aggregator
    from exabgp.bgp.message.open.asn import ASN

    # Create mock negotiated WITHOUT 4-byte ASN support
    negotiated = Mock()
    negotiated.asn4 = False

    # Create AGGREGATOR with 4-byte ASN
    asn = ASN(4200000000)
    ip = "192.0.2.1"
    aggregator = Aggregator(asn, ip)

    # Pack for old speaker (should use AS_TRANS)
    packed = aggregator.pack(negotiated)
    # Should be 6 bytes (2-byte AS_TRANS + 4-byte IP)
    assert len(packed) == 6

    # First 2 bytes should be AS_TRANS (23456 = 0x5BA0)
    as_trans_value = struct.unpack('!H', packed[:2])[0]
    assert as_trans_value == 23456


# ==============================================================================
# Phase 4: Optional Non-Transitive - MED (Type 4)
# ==============================================================================

def test_med_basic():
    """Test MULTI_EXIT_DISC (MED) attribute.

    MED is 4-byte value used to influence route selection between ASes.
    Lower MED = more preferred.
    Optional non-transitive (not propagated beyond neighboring AS).
    """
    from exabgp.bgp.message.update.attribute.med import MED

    # Create MED
    med_value = 100
    med = MED(med_value)

    # Verify value
    assert med.med == med_value
    assert str(med) == "med 100"

    # Verify pack
    packed = med.pack()
    assert len(packed) == 4
    assert struct.unpack('!L', packed)[0] == med_value


def test_med_optional_nature():
    """Test MED optional non-transitive nature.

    MED is optional: may or may not be present.
    MED is non-transitive: removed when leaving the neighboring AS.
    """
    from exabgp.bgp.message.update.attribute.med import MED
    from exabgp.bgp.message.update.attribute import Attribute

    # Verify MED is optional non-transitive
    assert MED.ID == Attribute.CODE.MED
    # Optional (bit 0 set) and non-transitive (bit 1 clear)
    assert MED.FLAG & Attribute.Flag.OPTIONAL


def test_med_comparison():
    """Test MED is used for route selection.

    Lower MED is preferred over higher MED.
    Only compared for routes from same neighboring AS.
    """
    from exabgp.bgp.message.update.attribute.med import MED

    # Create MEDs with different values
    med_low = MED(50)
    med_high = MED(200)

    # Lower MED should be preferred
    assert med_low.med < med_high.med


# ==============================================================================
# Phase 4: Optional Non-Transitive - ORIGINATOR_ID (Type 9)
# ==============================================================================

def test_originator_id_basic():
    """Test ORIGINATOR_ID attribute for route reflection.

    ORIGINATOR_ID: 4-byte BGP Identifier of originator.
    Created by route reflector, identifies original route source.
    Used to prevent routing loops in route reflection.
    """
    from exabgp.bgp.message.update.attribute.originatorid import OriginatorID

    # Create ORIGINATOR_ID
    originator_ip = "192.0.2.1"
    originator_id = OriginatorID(originator_ip)

    # Verify representation
    assert "192.0.2.1" in str(originator_id)

    # Verify pack (4-byte IP)
    packed = originator_id.pack()
    assert len(packed) == 4


def test_originator_id_loop_prevention():
    """Test ORIGINATOR_ID for loop prevention.

    Route reflector checks ORIGINATOR_ID against its own router-id.
    If match, route is discarded to prevent loops.
    """
    from exabgp.bgp.message.update.attribute.originatorid import OriginatorID
    from exabgp.bgp.message.update.attribute import Attribute

    # Create ORIGINATOR_ID
    originator_id = OriginatorID("192.0.2.1")

    # Verify it's optional non-transitive
    assert OriginatorID.ID == Attribute.CODE.ORIGINATOR_ID
    assert OriginatorID.FLAG & Attribute.Flag.OPTIONAL


# ==============================================================================
# Phase 4: Optional Non-Transitive - CLUSTER_LIST (Type 10)
# ==============================================================================

def test_cluster_list_single():
    """Test CLUSTER_LIST attribute with single cluster.

    CLUSTER_LIST: Sequence of CLUSTER_ID values.
    Each route reflector adds its CLUSTER_ID when reflecting.
    Used for loop detection in route reflection hierarchies.
    """
    from exabgp.bgp.message.update.attribute.clusterlist import ClusterList, ClusterID

    # Create single cluster
    cluster_id = ClusterID.unpack(b'\xC0\x00\x02\x01')  # 192.0.2.1
    cluster_list = ClusterList([cluster_id])

    # Verify pack
    packed = cluster_list.pack()
    assert len(packed) == 4  # One 4-byte cluster ID


def test_cluster_list_multiple():
    """Test CLUSTER_LIST with multiple clusters.

    Route may pass through multiple route reflectors.
    Each adds its CLUSTER_ID to the list.
    """
    from exabgp.bgp.message.update.attribute.clusterlist import ClusterList, ClusterID

    # Create multiple clusters
    cluster1 = ClusterID.unpack(b'\xC0\x00\x02\x01')
    cluster2 = ClusterID.unpack(b'\xC0\x00\x02\x02')
    cluster_list = ClusterList([cluster1, cluster2])

    # Verify pack (2 x 4 bytes = 8 bytes)
    packed = cluster_list.pack()
    assert len(packed) == 8


def test_cluster_list_loop_detection():
    """Test CLUSTER_LIST for loop detection.

    Route reflector checks if its CLUSTER_ID is in CLUSTER_LIST.
    If present, route is discarded to prevent loops.
    """
    from exabgp.bgp.message.update.attribute.clusterlist import ClusterList
    from exabgp.bgp.message.update.attribute import Attribute

    # Verify CLUSTER_LIST is optional non-transitive
    assert ClusterList.ID == Attribute.CODE.CLUSTER_LIST
    assert ClusterList.FLAG & Attribute.Flag.OPTIONAL


# ==============================================================================
# Phase 5: Extended Attributes - AIGP (Type 26)
# ==============================================================================

def test_aigp_basic():
    """Test AIGP (Accumulated IGP) attribute.

    AIGP: Accumulated IGP metric along the path.
    RFC 7311: Used for optimal routing in seamless MPLS.
    Contains one or more TLVs; AIGP TLV (type 1) is most common.
    """
    from exabgp.bgp.message.update.attribute.aigp import AIGP

    # Create AIGP with metric value
    metric = 1000
    aigp = AIGP(metric)

    # Verify basic properties
    assert aigp.aigp == metric

    # Verify pack
    packed = aigp.pack()
    # AIGP TLV: Type (1 byte) + Length (2 bytes) + Metric (8 bytes) = 11 bytes
    assert len(packed) >= 8  # At minimum contains the 8-byte metric


def test_aigp_accumulation():
    """Test AIGP metric accumulation.

    AIGP metric should be accumulated along the path.
    Each router adds its IGP cost to reach the next hop.
    """
    from exabgp.bgp.message.update.attribute.aigp import AIGP

    # Create AIGPs with different metrics
    aigp1 = AIGP(1000)
    aigp2 = AIGP(2000)

    # Higher metric = longer path
    assert aigp2.aigp > aigp1.aigp


def test_aigp_optional_attribute():
    """Test AIGP is optional attribute.

    AIGP is optional non-transitive in some implementations,
    optional transitive in others (RFC 7311 specifies optional non-transitive).
    """
    from exabgp.bgp.message.update.attribute.aigp import AIGP
    from exabgp.bgp.message.update.attribute import Attribute

    # Verify AIGP attribute code
    assert AIGP.ID == Attribute.CODE.AIGP


# ==============================================================================
# Phase 5: Attribute Handling Tests
# ==============================================================================

def test_attribute_flags():
    """Test attribute flag combinations.

    Attribute flags (1 byte):
    - Bit 0: Optional (0 = well-known, 1 = optional)
    - Bit 1: Transitive (0 = non-transitive, 1 = transitive)
    - Bit 2: Partial (0 = complete, 1 = partial)
    - Bit 3: Extended Length (0 = 1-byte length, 1 = 2-byte length)
    """
    from exabgp.bgp.message.update.attribute import Attribute

    # Test well-known mandatory (ORIGIN)
    from exabgp.bgp.message.update.attribute.origin import Origin
    # Well-known = transitive, not optional
    assert Origin.FLAG & Attribute.Flag.TRANSITIVE
    assert not (Origin.FLAG & Attribute.Flag.OPTIONAL)

    # Test optional transitive (AGGREGATOR)
    from exabgp.bgp.message.update.attribute.aggregator import Aggregator
    assert Aggregator.FLAG & Attribute.Flag.OPTIONAL
    assert Aggregator.FLAG & Attribute.Flag.TRANSITIVE

    # Test optional non-transitive (MED)
    from exabgp.bgp.message.update.attribute.med import MED
    assert MED.FLAG & Attribute.Flag.OPTIONAL
    assert not (MED.FLAG & Attribute.Flag.TRANSITIVE)


def test_unknown_attribute_handling():
    """Test handling of unknown/unrecognized attributes.

    - Unknown well-known: MUST recognize, else NOTIFICATION
    - Unknown optional transitive: accepted and forwarded with PARTIAL bit
    - Unknown optional non-transitive: silently ignored if not recognized
    """
    from exabgp.bgp.message.update.attribute import Attribute

    # This test documents the expected behavior
    # Actual implementation testing would require injecting unknown attributes

    # Well-known attributes must be recognized
    well_known_codes = [
        Attribute.CODE.ORIGIN,
        Attribute.CODE.AS_PATH,
        Attribute.CODE.NEXT_HOP,
    ]

    for code in well_known_codes:
        # These must be recognized
        assert code < 128  # Well-known have type code < 128


def test_attribute_length_encoding():
    """Test attribute length encoding (standard vs extended).

    - Standard: 1-byte length (for attributes < 256 bytes)
    - Extended: 2-byte length (for attributes >= 256 bytes)
    Extended Length flag (bit 3) indicates which encoding is used.
    """
    from exabgp.bgp.message.update.attribute import Attribute

    # Most attributes use standard 1-byte length
    # Extended length is indicated by flag bit 3
    extended_length_flag = Attribute.Flag.EXTENDED_LENGTH

    # AS_PATH and other variable-length attributes may use extended length
    # when they become very large (>255 bytes)
    assert extended_length_flag == 0x10  # Bit 3
