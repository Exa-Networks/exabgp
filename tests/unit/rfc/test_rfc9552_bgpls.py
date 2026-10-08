"""RFC 9552: what a BGP-LS receiver may and may not call malformed.

RFC 9552 replaced RFC 7752 without changing a byte of the wire format, so the encoding
tests here would have passed against the old document too.  What it did change is the
receiver's licence to complain.  Section 5.1 and section 8.2.2 between them say, four
times over, that an unknown TLV, an unexpected TLV, a missing TLV or an unfamiliar value
inside a TLV is NOT a malformed message, and that the only grounds for calling a
Link-State NLRI or a BGP-LS Attribute malformed are syntactic: lengths which do not add
up, and TLVs which do not end where they said they would.

That is the line every test in this file is drawn along.  A decoder which validates too
much fails this RFC exactly as surely as one which validates too little, and the two
failures look nothing alike from outside: the over-strict one takes the session down when
a perfectly legal producer ships a code point published after the decoder was written.

Everything is driven through the real entry points.  `BGPLS.unpack_nlri` is what an
MP_REACH calls, `LinkState.unpack_attribute` is what the attribute parser calls, and
`AttributeCollection.parse` is the only thing which knows that DISCARD means the route
survives the attribute.  No test here asserts on a mock.
"""

from __future__ import annotations

import json
from struct import pack

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import NLRIDiscard, Notify
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS, GenericBGPLS
from exabgp.bgp.message.update.nlri.bgpls.node import NODE
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol.family import AFI, SAFI

from rfc.community_wire import session

# Section 5.2, Table 1
NLRI_TYPE_NODE = 1
# 65000-65535 is Private Use in the BGP-LS NLRI Types registry, so nothing will ever
# register it and it stands in for "a type published after this decoder was written".
NLRI_TYPE_UNKNOWN = 65000

# Section 5.2.2, the Link NLRI, which is the one carrying a Remote Node Descriptor too
NLRI_TYPE_LINK = 2

# Section 5.2.3, the IPv4 Topology Prefix NLRI, and its IP Reachability Information TLV
NLRI_TYPE_PREFIX_V4 = 3
IP_REACHABILITY_INFORMATION = 265

# Section 5.2.1: the Local Node Descriptors TLV and its sub-TLVs
LOCAL_NODE_DESCRIPTORS = 256
REMOTE_NODE_DESCRIPTORS = 257
LINK_LOCAL_REMOTE_IDENTIFIERS = 258
SUB_TLV_AUTONOMOUS_SYSTEM = 512
SUB_TLV_IGP_ROUTER_ID = 515
# 516 is assigned (BGP Router Identifier, RFC 9086) and is not one of the four codes this
# decoder knows, which is the whole point of using it.
SUB_TLV_BGP_ROUTER_ID = 516

# Section 7.1.2: Protocol-IDs.  3 is OSPFv2 and is understood; 7 is BGP, assigned by
# RFC 9086 after RFC 7752 was written, and is not.
PROTOCOL_ID_OSPFV2 = 3
PROTOCOL_ID_BGP = 7
# Section 5.2, Table 2: the two Protocol-IDs for information BGP-LS sources itself
PROTOCOL_ID_DIRECT = 4
PROTOCOL_ID_STATIC = 5

# BGP-LS Attribute TLVs this build registers, used because they are registered: the point
# of the ordering tests is that a recognised TLV is still found out of order.
ATTRIBUTE_TLV_NODE_NAME = 1026
ATTRIBUTE_TLV_LOCAL_ROUTER_ID = 1028
# Private Use in the BGP-LS TLVs registry, so it decodes to a GenericLSID.
ATTRIBUTE_TLV_UNKNOWN = 65001

BGP_LS_ATTRIBUTE = int(Attribute.CODE.BGP_LS)
INTERNAL_DISCARD = int(Attribute.CODE.INTERNAL_DISCARD)

OPTIONAL = 0x80
WELL_KNOWN_TRANSITIVE = 0x40

ROUTER_ID = bytes([10, 0, 0, 1])
ORIGIN_IGP = bytes([WELL_KNOWN_TRANSITIVE, int(Attribute.CODE.ORIGIN), 1, 0x00])


def tlv(code: int, value: bytes) -> bytes:
    """One TLV in the section 5.1 encoding: two octets of type, two of length, the value."""
    return pack('!HH', int(code), len(value)) + value


def descriptors() -> bytes:
    """A Local Node Descriptor a conforming producer could send, sub-TLVs ascending."""
    return tlv(SUB_TLV_AUTONOMOUS_SYSTEM, pack('!L', 65000)) + tlv(SUB_TLV_IGP_ROUTER_ID, ROUTER_ID)


def node_nlri(
    inner: bytes | None = None,
    protocol: int = PROTOCOL_ID_OSPFV2,
    identifier: int = 0,
    code: int = NLRI_TYPE_NODE,
) -> bytes:
    """A Node NLRI: type, Total NLRI Length, Protocol-ID, Identifier, descriptors."""
    payload = pack('!BQ', protocol, identifier) + tlv(LOCAL_NODE_DESCRIPTORS, descriptors() if inner is None else inner)
    return pack('!HH', int(code), len(payload)) + payload


def link_nlri(remote: bytes, ascending: bool = True) -> bytes:
    """A Link NLRI: the same header, then the Local, Remote and Link Descriptors.

    5.2.1 says "any Node Descriptor", not "the local one", so the Link NLRI is where the
    rule has a second place to hold.  With `ascending` False the Link Descriptor (258) is
    moved ahead of the Remote Node Descriptors (257), every TLV otherwise unchanged.
    """
    remote_tlv = tlv(REMOTE_NODE_DESCRIPTORS, remote)
    identifiers = tlv(LINK_LOCAL_REMOTE_IDENTIFIERS, pack('!LL', 1, 2))
    descriptor_tlvs = remote_tlv + identifiers if ascending else identifiers + remote_tlv
    payload = pack('!BQ', PROTOCOL_ID_OSPFV2, 0) + tlv(LOCAL_NODE_DESCRIPTORS, descriptors()) + descriptor_tlvs
    return pack('!HH', NLRI_TYPE_LINK, len(payload)) + payload


def vpn_node_nlri() -> bytes:
    """The same Node NLRI under SAFI 72: a Route Distinguisher sits before the payload."""
    inner = pack('!BQ', PROTOCOL_ID_OSPFV2, 0) + tlv(LOCAL_NODE_DESCRIPTORS, descriptors())
    route_distinguisher = pack('!HHL', 0, 65000, 1)
    return pack('!HH', NLRI_TYPE_NODE, len(route_distinguisher) + len(inner)) + route_distinguisher + inner


def unpack_nlri(data: bytes, safi: SAFI = SAFI.bgp_ls) -> tuple[NLRI, bytes]:
    """Feed wire bytes to the decoder an MP_REACH would reach."""
    nlri, left = BGPLS.unpack_nlri(AFI.bgpls, safi, data, Action.ANNOUNCE, False, session())
    return nlri, bytes(left)


def mp_reach(nlris: bytes) -> MPRNLRI:
    """An MP_REACH_NLRI value for AFI 16388 / SAFI 71, through the real attribute decoder.

    The session is the shared one with BGP-LS negotiated and no ADD-PATH, which is all
    `MPRNLRI.unpack_attribute` asks of it.
    """
    negotiated = session()
    negotiated.families = [(AFI.bgpls, SAFI.bgp_ls)]
    value = pack('!HB', int(AFI.bgpls), int(SAFI.bgp_ls)) + bytes([len(ROUTER_ID)]) + ROUTER_ID + b'\x00' + nlris
    reach = MPRNLRI.unpack_attribute(value, negotiated)
    assert isinstance(reach, MPRNLRI)
    return reach


def mp_unreach(nlris: bytes) -> MPURNLRI:
    """An MP_UNREACH_NLRI value for AFI 16388 / SAFI 71, through the real attribute decoder."""
    negotiated = session()
    negotiated.families = [(AFI.bgpls, SAFI.bgp_ls)]
    unreach = MPURNLRI.unpack_attribute(pack('!HB', int(AFI.bgpls), int(SAFI.bgp_ls)) + nlris, negotiated)
    assert isinstance(unreach, MPURNLRI)
    return unreach


def unpack_attribute(value: bytes) -> LinkState:
    """Feed a BGP-LS Attribute value to the decoder the attribute parser reaches."""
    attribute = LinkState.unpack_attribute(value, session())
    assert isinstance(attribute, LinkState)
    return attribute


def parse_attributes(value: bytes) -> AttributeCollection:
    """The BGP-LS Attribute alongside a well known one, through the real collection parser.

    The second attribute is what makes the difference between 'Attribute Discard' and a
    session reset visible: after a discard the UPDATE still has its ORIGIN.
    """
    header = bytes([OPTIONAL, BGP_LS_ATTRIBUTE, len(value)])
    return AttributeCollection().parse(ORIGIN_IGP + header + value, session())


def codes(attribute: LinkState) -> list[int]:
    """The TLV code of every TLV the attribute decoded, in the order they were read."""
    # tlv(): the code the TLV arrived with, TLV being only the default of its class
    return [entry.tlv() for entry in attribute.ls_attrs]


# ==================================================== section 5.1, unknown and unexpected


@pytest.mark.rfc('rfc9552#5.1-unknown-tlv-preserved')
def test_an_unknown_attribute_tlv_is_kept_with_its_bytes() -> None:
    unknown = bytes([0xDE, 0xAD, 0xBE, 0xEF])

    attribute = unpack_attribute(tlv(ATTRIBUTE_TLV_UNKNOWN, unknown))

    assert codes(attribute) == [ATTRIBUTE_TLV_UNKNOWN]
    assert getattr(type(attribute.ls_attrs[0]), 'GENERIC', False)
    assert 'deadbeef' in attribute.json().lower()


@pytest.mark.rfc('rfc9552#5.1-unknown-tlv-preserved', polarity='negative')
def test_an_unknown_node_descriptor_sub_tlv_is_kept() -> None:
    """Preserved means the bytes come back out, not merely that the NLRI was accepted."""
    inner = descriptors() + tlv(SUB_TLV_BGP_ROUTER_ID, pack('!L', 0x01020304))
    wire = node_nlri(inner)

    nlri, left = unpack_nlri(wire)

    assert left == b''
    assert isinstance(nlri, NODE)
    assert bytes(nlri.pack_nlri(session())) == wire
    assert [descriptor.node_type for descriptor in nlri.node_ids] == [
        SUB_TLV_AUTONOMOUS_SYSTEM,
        SUB_TLV_IGP_ROUTER_ID,
        SUB_TLV_BGP_ROUTER_ID,
    ]
    assert '01020304' in nlri.json()


@pytest.mark.rfc('rfc9552#5.1-unknown-tlv-not-malformed')
def test_an_unknown_attribute_tlv_does_not_make_the_attribute_malformed() -> None:
    value = tlv(ATTRIBUTE_TLV_UNKNOWN, b'\x00') + tlv(ATTRIBUTE_TLV_LOCAL_ROUTER_ID, ROUTER_ID)

    attribute = unpack_attribute(value)

    assert codes(attribute) == [ATTRIBUTE_TLV_UNKNOWN, ATTRIBUTE_TLV_LOCAL_ROUTER_ID]


@pytest.mark.rfc('rfc9552#5.1-unknown-tlv-not-malformed', polarity='negative')
def test_an_unknown_node_descriptor_sub_tlv_does_not_make_the_nlri_malformed() -> None:
    """Two unknown codes in one descriptor, which is where a shared fallback collides."""
    inner = (
        descriptors()
        + tlv(SUB_TLV_BGP_ROUTER_ID, pack('!L', 0x01020304))
        + tlv(SUB_TLV_BGP_ROUTER_ID + 1, pack('!L', 65000))
    )

    nlri, left = unpack_nlri(node_nlri(inner))

    assert left == b''
    assert len(nlri.node_ids) == 4
    rendered = nlri.json()
    assert f'generic-node-descriptor-{SUB_TLV_BGP_ROUTER_ID}' in rendered
    assert f'generic-node-descriptor-{SUB_TLV_BGP_ROUTER_ID + 1}' in rendered


@pytest.mark.rfc('rfc9552#5.1-unordered-attribute-not-malformed')
def test_attribute_tlvs_in_descending_order_all_decode() -> None:
    value = tlv(ATTRIBUTE_TLV_LOCAL_ROUTER_ID, ROUTER_ID) + tlv(ATTRIBUTE_TLV_NODE_NAME, b'router-one')

    attribute = unpack_attribute(value)

    assert codes(attribute) == [ATTRIBUTE_TLV_LOCAL_ROUTER_ID, ATTRIBUTE_TLV_NODE_NAME]


@pytest.mark.rfc('rfc9552#5.1-unordered-attribute-not-malformed', polarity='negative')
def test_descending_order_does_not_excuse_a_tlv_which_runs_past_the_value() -> None:
    value = tlv(ATTRIBUTE_TLV_LOCAL_ROUTER_ID, ROUTER_ID) + pack('!HH', ATTRIBUTE_TLV_NODE_NAME, 40) + b'short'

    with pytest.raises(Notify):
        unpack_attribute(value)


@pytest.mark.rfc('rfc9552#5.1-nlri-tlvs-ascending-order')
def test_a_link_nlri_whose_tlvs_are_not_ascending_is_not_taken_as_well_formed() -> None:
    """Sub-TLV order is checked inside a Node Descriptor; the TLVs around it are not.

    An NLRI which compares unequal to its own ascending twin is two routes for one link,
    which is what the rule exists to prevent.  `link_nlri(...)` in order is the control,
    and decodes: the test above the Remote Node Descriptor sub-TLVs uses it.
    """
    with pytest.raises(Notify):
        unpack_nlri(link_nlri(descriptors(), ascending=False))


# ================================================================ section 5.2, the NLRI


@pytest.mark.rfc('rfc9552#5.2-afi-safi-assignment')
def test_bgp_ls_is_afi_16388_with_safi_71_and_72() -> None:
    assert int(AFI.bgpls) == 16388
    assert int(SAFI.bgp_ls) == 71
    assert int(SAFI.bgp_ls_vpn) == 72

    nlri, left = unpack_nlri(node_nlri())

    assert left == b''
    assert isinstance(nlri, NODE)
    assert not nlri.route_d


@pytest.mark.rfc('rfc9552#5.2-afi-safi-assignment', polarity='negative')
def test_safi_72_reads_a_route_distinguisher_where_safi_71_reads_descriptors() -> None:
    # under SAFI 72 the eight octets after the header are a Route Distinguisher, so the
    # same bytes cannot mean the same thing under the two SAFIs
    wire = vpn_node_nlri()

    vpn, left = unpack_nlri(wire, SAFI.bgp_ls_vpn)

    assert left == b''
    assert isinstance(vpn, NODE)
    assert vpn.route_d

    # read as SAFI 71 the first octet of the Route Distinguisher is taken for a
    # Protocol-ID, which is how far apart the two encodings are
    with pytest.raises(Notify):
        unpack_nlri(wire, SAFI.bgp_ls)

    # and a VPN NLRI too short to hold its own Route Distinguisher is refused
    with pytest.raises(Notify):
        unpack_nlri(pack('!HH', NLRI_TYPE_NODE, 4) + bytes(4), SAFI.bgp_ls_vpn)


NLRI_TYPE_SRV6_SID = 6  # RFC 9514 6
SRV6_SID_INFORMATION = 518


def vpn_srv6_sid_nlri(route_distinguisher: bytes) -> bytes:
    """An SRv6 SID NLRI of RFC 9514 under SAFI 72, the Route Distinguisher in front."""
    sid = tlv(SRV6_SID_INFORMATION, bytes([0x20, 0x01, 0x0D, 0xB8]) + bytes(12))
    inner = pack('!BQ', PROTOCOL_ID_OSPFV2, 0) + tlv(LOCAL_NODE_DESCRIPTORS, descriptors()) + sid
    return pack('!HH', NLRI_TYPE_SRV6_SID, len(route_distinguisher) + len(inner)) + route_distinguisher + inner


@pytest.mark.rfc('rfc9552#5.2-afi-safi-assignment')
def test_a_vpn_srv6_sid_nlri_keeps_its_route_distinguisher() -> None:
    """It was decoded without one: packed back eight octets short, and under no VPN.

    Two SRv6 SID NLRI differing by their Route Distinguisher alone compared equal and
    shared an index, so the second VPN's route replaced the first's in the RIB.
    """
    first_rd, second_rd = pack('!HHL', 0, 65000, 1), pack('!HHL', 0, 65000, 2)
    first, left = unpack_nlri(vpn_srv6_sid_nlri(first_rd), SAFI.bgp_ls_vpn)
    second, _ = unpack_nlri(vpn_srv6_sid_nlri(second_rd), SAFI.bgp_ls_vpn)

    assert left == b''
    assert bytes(first.pack_nlri(session())) == vpn_srv6_sid_nlri(first_rd)
    assert first != second
    assert first.index() != second.index()
    assert hash(first) != hash(second)
    assert json.loads(first.json())['rd'] == '65000:1'


@pytest.mark.rfc('rfc9552#5.2-unknown-nlri-type-opaque')
def test_an_unknown_nlri_type_is_opaque_and_survives_byte_for_byte() -> None:
    opaque = bytes([0x01, 0x02, 0x03, 0x04, 0x05])
    wire = pack('!HH', NLRI_TYPE_UNKNOWN, len(opaque)) + opaque

    nlri, left = unpack_nlri(wire + b'\xff\xff')

    assert isinstance(nlri, GenericBGPLS)
    assert nlri.route_code == NLRI_TYPE_UNKNOWN
    assert bytes(nlri.pack_nlri(session())) == wire
    assert left == b'\xff\xff'


@pytest.mark.rfc('rfc9552#5.2-unknown-nlri-type-opaque', polarity='negative')
def test_an_opaque_nlri_whose_length_runs_past_the_buffer_is_still_refused() -> None:
    with pytest.raises(Notify):
        unpack_nlri(pack('!HH', NLRI_TYPE_UNKNOWN, 40) + b'short')


# ================================================== section 5.2.1, the Node Descriptors


@pytest.mark.rfc('rfc9552#5.2.1-one-instance-per-sub-tlv', polarity='negative')
def test_two_instances_of_one_node_descriptor_sub_tlv_are_refused() -> None:
    twice = tlv(SUB_TLV_AUTONOMOUS_SYSTEM, pack('!L', 65000)) + tlv(SUB_TLV_AUTONOMOUS_SYSTEM, pack('!L', 65001))

    with pytest.raises(Notify):
        unpack_nlri(node_nlri(twice))


def test_a_link_nlri_with_both_descriptors_in_order_decodes() -> None:
    """The control for the two tests below: what they feed differs only in the order."""
    _nlri, left = unpack_nlri(link_nlri(descriptors()))

    assert left == b''


@pytest.mark.rfc('rfc9552#5.2.1-one-instance-per-sub-tlv', polarity='negative')
def test_two_instances_of_one_sub_tlv_in_a_remote_node_descriptor_are_refused() -> None:
    twice = tlv(SUB_TLV_AUTONOMOUS_SYSTEM, pack('!L', 65000)) + tlv(SUB_TLV_AUTONOMOUS_SYSTEM, pack('!L', 65001))

    with pytest.raises(Notify):
        unpack_nlri(link_nlri(twice))


@pytest.mark.rfc('rfc9552#8.2.2-nlri-syntactic-validation', polarity='negative')
def test_remote_node_descriptor_sub_tlvs_out_of_ascending_order_are_refused() -> None:
    descending = tlv(SUB_TLV_IGP_ROUTER_ID, ROUTER_ID) + tlv(SUB_TLV_AUTONOMOUS_SYSTEM, pack('!L', 65000))

    with pytest.raises(Notify):
        unpack_nlri(link_nlri(descending))


# ==================================================== section 8.2.2, the NLRI validation


@pytest.mark.rfc('rfc9552#8.2.2-nlri-not-malformed-on-semantics')
def test_a_node_descriptor_missing_a_router_id_is_not_malformed() -> None:
    only_an_as = tlv(SUB_TLV_AUTONOMOUS_SYSTEM, pack('!L', 65000))

    nlri, left = unpack_nlri(node_nlri(only_an_as))

    assert left == b''
    assert isinstance(nlri, NODE)
    assert len(nlri.node_ids) == 1


@pytest.mark.rfc('rfc9552#8.2.2-nlri-not-malformed-on-semantics', polarity='negative')
@pytest.mark.parametrize('protocol', [PROTOCOL_ID_BGP, 8, 9, 200])
def test_an_unrecognised_protocol_id_is_not_malformed(protocol: int) -> None:
    """7, 8 and 9 were assigned after RFC 7752; 200 stands for the next one.

    Widening the list would only move the cliff, so the field is no longer gated at all.
    """
    nlri, left = unpack_nlri(node_nlri(protocol=protocol))

    assert left == b''
    assert isinstance(nlri, NODE)
    assert nlri.proto_id == protocol


@pytest.mark.rfc('rfc9552#8.2.2-nlri-syntactic-validation')
def test_a_descriptor_tlv_running_past_the_total_nlri_length_is_refused() -> None:
    payload = pack('!BQ', PROTOCOL_ID_OSPFV2, 0) + pack('!HH', LOCAL_NODE_DESCRIPTORS, 40) + descriptors()
    wire = pack('!HH', NLRI_TYPE_NODE, len(payload)) + payload

    with pytest.raises(Notify):
        unpack_nlri(wire)


@pytest.mark.rfc('rfc9552#8.2.2-nlri-syntactic-validation')
def test_a_sub_tlv_of_the_wrong_size_for_its_type_is_refused() -> None:
    # an Autonomous System sub-TLV is four octets by definition; three is a length error
    # rather than a semantic one, and this is the bullet which asks for it to be caught.
    short = tlv(SUB_TLV_AUTONOMOUS_SYSTEM, bytes(3))

    with pytest.raises(Notify):
        unpack_nlri(node_nlri(short))


@pytest.mark.rfc('rfc9552#8.2.2-nlri-syntactic-validation', polarity='negative')
def test_node_descriptor_sub_tlvs_out_of_ascending_order_are_refused() -> None:
    descending = tlv(SUB_TLV_IGP_ROUTER_ID, ROUTER_ID) + tlv(SUB_TLV_AUTONOMOUS_SYSTEM, pack('!L', 65000))

    with pytest.raises(Notify):
        unpack_nlri(node_nlri(descending))


@pytest.mark.rfc('rfc9552#8.2.2-nlri-discard', polarity='negative')
def test_an_nlri_violating_the_ordering_rule_is_discarded_and_the_next_one_kept() -> None:
    """The example 8.2.2 gives itself: the ordering rule broken, the length still honest.

    The Total NLRI Length says where the bad NLRI ends, so the decoder can step over it,
    and the NLRI after it in the same MP_REACH is owed to the RIB rather than lost with
    the session.
    """
    descending = tlv(SUB_TLV_IGP_ROUTER_ID, ROUTER_ID) + tlv(SUB_TLV_AUTONOMOUS_SYSTEM, pack('!L', 65000))
    good = node_nlri()

    announced = list(mp_reach(node_nlri(descending) + good).iter_routed())

    assert [bytes(routed.nlri.pack_nlri(session())) for routed in announced] == [good]


def framed(code: int, payload: bytes) -> bytes:
    """An NLRI whose Total NLRI Length is honest, whatever the payload holds."""
    return pack('!HH', code, len(payload)) + payload


def prefix_nlri(reachability: bytes) -> bytes:
    """An IPv4 Topology Prefix NLRI around the given IP Reachability Information value."""
    payload = pack('!BQ', PROTOCOL_ID_OSPFV2, 0) + tlv(LOCAL_NODE_DESCRIPTORS, descriptors())
    return framed(NLRI_TYPE_PREFIX_V4, payload + tlv(IP_REACHABILITY_INFORMATION, reachability))


# Each of these breaks a rule inside an NLRI whose Total NLRI Length is honest, so the
# decoder knows where the NLRI ends and can step over it: section 8.2.2's "NLRI discard".
FRAMED_BUT_MALFORMED = {
    # "the length of its sub-TLVs in the NLRI are valid": an AS sub-TLV is four octets
    'short-autonomous-system': node_nlri(tlv(SUB_TLV_AUTONOMOUS_SYSTEM, bytes(3))),
    # "The sum of all TLV lengths found in a Link-State NLRI corresponds to the Total NLRI
    # Length field": the descriptor TLV claims more than the NLRI holds
    'descriptor-past-the-nlri': framed(
        NLRI_TYPE_NODE, pack('!BQ', PROTOCOL_ID_OSPFV2, 0) + pack('!HH', LOCAL_NODE_DESCRIPTORS, 40) + descriptors()
    ),
    # a Node NLRI with no Local Node Descriptors TLV at all
    'no-local-node-descriptor': framed(NLRI_TYPE_NODE, pack('!BQ', PROTOCOL_ID_OSPFV2, 0)),
    # a Link Local/Remote Identifiers TLV is eight octets
    'short-link-identifiers': framed(
        NLRI_TYPE_LINK,
        pack('!BQ', PROTOCOL_ID_OSPFV2, 0)
        + tlv(LOCAL_NODE_DESCRIPTORS, descriptors())
        + tlv(LINK_LOCAL_REMOTE_IDENTIFIERS, bytes(3)),
    ),
    # a /8 carried in four octets of prefix
    'long-ip-reachability': prefix_nlri(bytes([8, 10, 0, 0, 0])),
}


@pytest.mark.rfc('rfc9552#8.2.2-nlri-discard', polarity='negative')
@pytest.mark.parametrize('malformed', list(FRAMED_BUT_MALFORMED.values()), ids=list(FRAMED_BUT_MALFORMED))
def test_a_framed_nlri_with_a_bad_sub_tlv_is_discarded_and_the_next_one_kept(malformed: bytes) -> None:
    """Any error inside a length the decoder could check, not only the ordering rule.

    A sub-TLV length error, a missing mandatory TLV and a descriptor which overruns the
    NLRI all reset the session, when the Total NLRI Length told the decoder exactly where
    the next NLRI started.
    """
    good = node_nlri()

    announced = list(mp_reach(malformed + good).iter_routed())

    assert [bytes(routed.nlri.pack_nlri(session())) for routed in announced] == [good]


@pytest.mark.rfc('rfc9552#8.2.2-nlri-discard', polarity='negative')
@pytest.mark.parametrize('malformed', list(FRAMED_BUT_MALFORMED.values()), ids=list(FRAMED_BUT_MALFORMED))
def test_the_decoder_says_how_far_to_skip_a_framed_malformed_nlri(malformed: bytes) -> None:
    """The NLRIDiscard carries the octets the NLRI took, or the caller cannot step over it."""
    with pytest.raises(NLRIDiscard) as raised:
        unpack_nlri(malformed)

    assert raised.value.skip == len(malformed)


@pytest.mark.rfc('rfc9552#8.2.2-nlri-discard', polarity='negative')
def test_a_malformed_nlri_in_mp_unreach_is_discarded_and_the_next_one_withdrawn() -> None:
    """The same rule for MP_UNREACH_NLRI, whose loop let NLRIDiscard out as a reset."""
    descending = tlv(SUB_TLV_IGP_ROUTER_ID, ROUTER_ID) + tlv(SUB_TLV_AUTONOMOUS_SYSTEM, pack('!L', 65000))
    good = node_nlri()

    withdrawn = list(mp_unreach(node_nlri(descending) + good))

    assert [bytes(nlri.pack_nlri(session())) for nlri in withdrawn] == [good]


@pytest.mark.rfc('rfc9552#8.2.2-session-reset-when-unable-to-process')
def test_an_nlri_overrunning_the_mp_unreach_still_resets_the_session() -> None:
    """Discard needs a length to trust: one running past the attribute leaves none."""
    with pytest.raises(Notify) as raised:
        list(mp_unreach(node_nlri() + pack('!HH', NLRI_TYPE_NODE, 200) + bytes(13)))

    assert not isinstance(raised.value, NLRIDiscard), 'an NLRI with no trustworthy length cannot be skipped'


# ======================================== section 5.2.1.4, the IGP Router-ID of Direct and Static


def router_id_json(protocol: int, router_id: bytes) -> dict[str, object]:
    """The Local Node Descriptor of a Node NLRI carrying only this IGP Router-ID, as JSON."""
    nlri, left = unpack_nlri(node_nlri(tlv(SUB_TLV_IGP_ROUTER_ID, router_id), protocol=protocol))
    assert left == b''
    assert isinstance(nlri, NODE)
    descriptor: dict[str, object] = json.loads(nlri.json())['node-descriptors'][0]
    return descriptor


IPV6_LOOPBACK = bytes.fromhex('20010db8000000000000000000000001')


@pytest.mark.rfc('rfc9552#5.2.1.4-direct-static-router-id-address')
@pytest.mark.parametrize('protocol', [PROTOCOL_ID_DIRECT, PROTOCOL_ID_STATIC])
@pytest.mark.parametrize(
    'router_id,expected', [(ROUTER_ID, '10.0.0.1'), (IPV6_LOOPBACK, '2001:db8::1')], ids=['ipv4', 'ipv6']
)
def test_a_direct_or_static_router_id_is_read_as_an_address(protocol: int, router_id: bytes, expected: str) -> None:
    """Table 2 numbers Direct 4 and Static configuration 5, and either takes an IPv6 address.

    The decoder had Direct as 5 and Static as 227, so a 16 octet IGP Router-ID under 5
    reset the session and any Router-ID under 4 was not read as an address at all.
    """
    assert router_id_json(protocol, router_id) == {'router-id': expected}


@pytest.mark.rfc('rfc9552#5.2.1.4-direct-static-router-id-address', polarity='negative')
def test_an_ospf_router_id_is_not_read_as_an_ipv6_address() -> None:
    """The size is read with the Protocol-ID: sixteen octets are no OSPFv2 Router-ID."""
    with pytest.raises(NLRIDiscard):
        unpack_nlri(node_nlri(tlv(SUB_TLV_IGP_ROUTER_ID, IPV6_LOOPBACK), protocol=PROTOCOL_ID_OSPFV2))


@pytest.mark.rfc('rfc9552#8.2.2-session-reset-when-unable-to-process')
def test_a_length_error_the_decoder_cannot_step_over_resets_the_session() -> None:
    # a Total NLRI Length longer than the bytes which follow leaves the decoder with no
    # way to find where the next NLRI in the MP_REACH begins
    with pytest.raises(Notify) as raised:
        unpack_nlri(pack('!HH', NLRI_TYPE_NODE, 200) + bytes(13))

    assert raised.value.code == 3


# =============================================== section 8.2.2, the attribute validation


@pytest.mark.rfc('rfc9552#8.2.2-attribute-not-malformed-on-semantics')
def test_an_attribute_of_only_unregistered_tlvs_is_not_malformed() -> None:
    value = tlv(ATTRIBUTE_TLV_UNKNOWN, b'\x01') + tlv(ATTRIBUTE_TLV_UNKNOWN + 1, b'\x02')

    attribute = unpack_attribute(value)

    assert codes(attribute) == [ATTRIBUTE_TLV_UNKNOWN, ATTRIBUTE_TLV_UNKNOWN + 1]


@pytest.mark.rfc('rfc9552#8.2.2-attribute-not-malformed-on-semantics', polarity='negative')
def test_a_repeated_attribute_tlv_is_not_malformed() -> None:
    """Both values survive, and the render does not write the same key twice.

    Section 5.3.2 does not say a Link Attribute TLV may appear once; 5.3.2.1 says the
    opposite for the Router-ID TLVs.  What 8.2.2 does say is that 'Attribute Discard'
    loses every TLV in the attribute, which is what refusing the repeat used to cost.
    """
    twice = tlv(ATTRIBUTE_TLV_NODE_NAME, b'one') + tlv(ATTRIBUTE_TLV_NODE_NAME, b'two')

    attribute = unpack_attribute(twice)

    assert codes(attribute) == [ATTRIBUTE_TLV_NODE_NAME, ATTRIBUTE_TLV_NODE_NAME]

    rendered = json.loads(attribute.json())
    assert rendered == {'node-name': ['one', 'two']}

    # and the route keeps the attribute rather than losing it to an Attribute Discard
    collection = parse_attributes(twice)
    assert INTERNAL_DISCARD not in collection
    assert BGP_LS_ATTRIBUTE in collection


@pytest.mark.rfc('rfc9552#8.2.2-attribute-not-malformed-on-semantics', polarity='negative')
def test_a_tlv_which_appears_once_is_rendered_by_its_own_class() -> None:
    """The grouping is for the repeat only: a single TLV keeps the shape it always had."""
    value = tlv(ATTRIBUTE_TLV_NODE_NAME, b'router-one') + tlv(ATTRIBUTE_TLV_LOCAL_ROUTER_ID, ROUTER_ID)

    rendered = json.loads(unpack_attribute(value).json())

    assert rendered['node-name'] == 'router-one'
    # 1028 is a MERGE class, so it is an array whether or not it repeated
    assert rendered['local-router-ids'] == ['10.0.0.1']


@pytest.mark.rfc('rfc9552#8.2.2-attribute-syntactic-validation')
@pytest.mark.timeout(10)
def test_a_well_formed_attribute_decodes_and_the_walk_terminates() -> None:
    # the zero-length TLV is the one which can spin: a walk which advanced by the value
    # length rather than by four plus it would never leave this attribute
    value = (
        tlv(ATTRIBUTE_TLV_UNKNOWN, b'')
        + tlv(ATTRIBUTE_TLV_NODE_NAME, b'router-one')
        + tlv(ATTRIBUTE_TLV_LOCAL_ROUTER_ID, ROUTER_ID)
    )

    attribute = unpack_attribute(value)

    assert codes(attribute) == [ATTRIBUTE_TLV_UNKNOWN, ATTRIBUTE_TLV_NODE_NAME, ATTRIBUTE_TLV_LOCAL_ROUTER_ID]


@pytest.mark.rfc('rfc9552#8.2.2-attribute-syntactic-validation', polarity='negative')
def test_a_truncated_tlv_header_is_refused() -> None:
    with pytest.raises(Notify):
        unpack_attribute(tlv(ATTRIBUTE_TLV_NODE_NAME, b'router-one') + b'\x04')


@pytest.mark.rfc('rfc9552#8.2.2-attribute-syntactic-validation', polarity='negative')
def test_a_tlv_length_disagreeing_with_what_follows_is_refused() -> None:
    with pytest.raises(Notify):
        unpack_attribute(pack('!HH', ATTRIBUTE_TLV_NODE_NAME, 30) + b'router-one')


@pytest.mark.rfc('rfc9552#8.2.2-attribute-syntactic-validation', polarity='negative')
def test_a_recognised_tlv_with_a_value_of_the_wrong_size_is_refused() -> None:
    # a Local Router-ID is four octets or sixteen, never five
    with pytest.raises(Notify):
        unpack_attribute(tlv(ATTRIBUTE_TLV_LOCAL_ROUTER_ID, ROUTER_ID + b'\x05'))


@pytest.mark.rfc('rfc9552#8.2.2-attribute-discard')
def test_a_bad_tlv_length_inside_an_honest_attribute_is_an_attribute_discard() -> None:
    collection = parse_attributes(pack('!HH', ATTRIBUTE_TLV_NODE_NAME, 30) + b'router-one')

    assert INTERNAL_DISCARD in collection
    assert BGP_LS_ATTRIBUTE not in collection


@pytest.mark.rfc('rfc9552#8.2.2-attribute-discard', polarity='negative')
def test_an_attribute_discard_is_not_a_notification_and_spares_the_other_attributes() -> None:
    collection = parse_attributes(pack('!HH', ATTRIBUTE_TLV_NODE_NAME, 30) + b'router-one')

    # the UPDATE was not abandoned: the well known attribute alongside it came through
    assert int(Attribute.CODE.ORIGIN) in collection

    # and a well formed attribute in the same position is not discarded
    good = parse_attributes(tlv(ATTRIBUTE_TLV_LOCAL_ROUTER_ID, ROUTER_ID))
    assert INTERNAL_DISCARD not in good
    assert BGP_LS_ATTRIBUTE in good


# ================================================ section 5.1, the order of the NLRI TLVs

NLRI_TYPE_PREFIX_V6 = 4
IPV4_INTERFACE_ADDRESS = 259
REACHABILITY_10_0_0_0_24 = bytes([24, 10, 0, 0])
UNKNOWN_NLRI_TLV = 255  # below the Local Node Descriptors, so it may never follow them
UNKNOWN_LINK_TLV = 1000


def topology_nlri(code: int, after_header: list[bytes]) -> bytes:
    """An NLRI of type `code` whose TLVs, after Protocol-ID and Identifier, are `after_header`."""
    return framed(code, pack('!BQ', PROTOCOL_ID_OSPFV2, 0) + b''.join(after_header))


def link_tlvs(code: int, *values: bytes) -> bytes:
    """A Link NLRI with one TLV of type `code` per value, in the order given."""
    return topology_nlri(
        NLRI_TYPE_LINK,
        [tlv(LOCAL_NODE_DESCRIPTORS, descriptors()), tlv(REMOTE_NODE_DESCRIPTORS, descriptors())]
        + [tlv(code, value) for value in values],
    )


LOCAL = tlv(LOCAL_NODE_DESCRIPTORS, descriptors())
SRV6_SID = tlv(SRV6_SID_INFORMATION, bytes([0x20, 0x01, 0x0D, 0xB8]) + bytes(12))

# Every NLRI type exabgp decodes, each with its TLVs once ascending and once not.  Only the
# Link NLRI checked the order, and only by type.
ORDERED_AND_NOT = {
    'node': (
        topology_nlri(NLRI_TYPE_NODE, [LOCAL]),
        topology_nlri(NLRI_TYPE_NODE, [LOCAL, tlv(UNKNOWN_NLRI_TLV, b'')]),
    ),
    'prefix v4': (
        topology_nlri(NLRI_TYPE_PREFIX_V4, [LOCAL, tlv(IP_REACHABILITY_INFORMATION, REACHABILITY_10_0_0_0_24)]),
        topology_nlri(NLRI_TYPE_PREFIX_V4, [tlv(IP_REACHABILITY_INFORMATION, REACHABILITY_10_0_0_0_24), LOCAL]),
    ),
    'prefix v6': (
        topology_nlri(NLRI_TYPE_PREFIX_V6, [LOCAL, tlv(IP_REACHABILITY_INFORMATION, bytes([32, 0x20, 1, 0xD, 0xB8]))]),
        topology_nlri(NLRI_TYPE_PREFIX_V6, [tlv(IP_REACHABILITY_INFORMATION, bytes([32, 0x20, 1, 0xD, 0xB8])), LOCAL]),
    ),
    'srv6 sid': (
        topology_nlri(NLRI_TYPE_SRV6_SID, [LOCAL, SRV6_SID]),
        topology_nlri(NLRI_TYPE_SRV6_SID, [LOCAL, SRV6_SID, tlv(UNKNOWN_NLRI_TLV + 1, b'')]),
    ),
    # 5.1: TLVs of one type are ordered by Length, then by Value
    'link, one type, by value': (
        link_tlvs(IPV4_INTERFACE_ADDRESS, bytes([10, 0, 0, 1]), bytes([10, 0, 0, 2])),
        link_tlvs(IPV4_INTERFACE_ADDRESS, bytes([10, 0, 0, 2]), bytes([10, 0, 0, 1])),
    ),
    # a TLV this decoder does not know, whose values may have any length
    'link, one type, by length': (
        link_tlvs(UNKNOWN_LINK_TLV, bytes([9]), bytes([1, 0])),
        link_tlvs(UNKNOWN_LINK_TLV, bytes([1, 0]), bytes([9])),
    ),
}


@pytest.mark.rfc('rfc9552#5.1-nlri-tlvs-ascending-order')
@pytest.mark.rfc('rfc9552#5.1-same-type-tlvs-by-length-then-value')
@pytest.mark.rfc('rfc9552#5.1-unordered-nlri-malformed')
@pytest.mark.parametrize('name', sorted(ORDERED_AND_NOT))
def test_an_nlri_whose_tlvs_ascend_decodes(name: str) -> None:
    nlri, left = unpack_nlri(ORDERED_AND_NOT[name][0])

    assert left == b''
    assert bytes(nlri.pack_nlri(session())) == ORDERED_AND_NOT[name][0]


@pytest.mark.rfc('rfc9552#5.1-nlri-tlvs-ascending-order', polarity='negative')
@pytest.mark.rfc('rfc9552#5.1-same-type-tlvs-by-length-then-value', polarity='negative')
@pytest.mark.rfc('rfc9552#5.1-unordered-nlri-malformed', polarity='negative')
@pytest.mark.rfc('rfc9552#8.2.2-nlri-syntactic-validation', polarity='negative')
@pytest.mark.parametrize('name', sorted(ORDERED_AND_NOT))
def test_an_nlri_whose_tlvs_do_not_ascend_is_malformed(name: str) -> None:
    """8.2.2 lists the 5.1 ordering among the checks "A BGP-LS Speaker MUST perform"."""
    with pytest.raises(NLRIDiscard):
        unpack_nlri(ORDERED_AND_NOT[name][1])


@pytest.mark.rfc('rfc9552#5.1-nlri-tlvs-ascending-order')
def test_a_node_nlri_we_build_has_its_descriptor_sub_tlvs_ascending() -> None:
    """The only BGP-LS NLRI exabgp builds rather than relays: given out of order, sent in order."""
    by_hand = list(NODE.unpack_bgpls_nlri(node_nlri(), RouteDistinguisher.NORD).node_ids)
    built = NODE.make_node(0, PROTOCOL_ID_OSPFV2, list(reversed(by_hand)))

    assert bytes(built.pack_nlri(session())) == node_nlri()
