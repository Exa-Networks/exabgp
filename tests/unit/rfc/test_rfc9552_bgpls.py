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
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS, GenericBGPLS
from exabgp.bgp.message.update.nlri.bgpls.node import NODE
from exabgp.protocol.family import AFI, SAFI

from rfc.community_wire import session

# Section 5.2, Table 1
NLRI_TYPE_NODE = 1
# 65000-65535 is Private Use in the BGP-LS NLRI Types registry, so nothing will ever
# register it and it stands in for "a type published after this decoder was written".
NLRI_TYPE_UNKNOWN = 65000

# Section 5.2.1: the Local Node Descriptors TLV and its sub-TLVs
LOCAL_NODE_DESCRIPTORS = 256
SUB_TLV_AUTONOMOUS_SYSTEM = 512
SUB_TLV_IGP_ROUTER_ID = 515
# 516 is assigned (BGP Router Identifier, RFC 9086) and is not one of the four codes this
# decoder knows, which is the whole point of using it.
SUB_TLV_BGP_ROUTER_ID = 516

# Section 7.1.2: Protocol-IDs.  3 is OSPFv2 and is understood; 7 is BGP, assigned by
# RFC 9086 after RFC 7752 was written, and is not.
PROTOCOL_ID_OSPFV2 = 3
PROTOCOL_ID_BGP = 7

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
    return pack('!HH', code, len(value)) + value


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
    return pack('!HH', code, len(payload)) + payload


def vpn_node_nlri() -> bytes:
    """The same Node NLRI under SAFI 72: a Route Distinguisher sits before the payload."""
    inner = pack('!BQ', PROTOCOL_ID_OSPFV2, 0) + tlv(LOCAL_NODE_DESCRIPTORS, descriptors())
    route_distinguisher = pack('!HHL', 0, 65000, 1)
    return pack('!HH', NLRI_TYPE_NODE, len(route_distinguisher) + len(inner)) + route_distinguisher + inner


def unpack_nlri(data: bytes, safi: SAFI = SAFI.bgp_ls) -> tuple[NLRI, bytes]:
    """Feed wire bytes to the decoder an MP_REACH would reach."""
    nlri, left = BGPLS.unpack_nlri(AFI.bgpls, safi, data, Action.ANNOUNCE, False, session())
    return nlri, bytes(left)


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
    return [entry.TLV for entry in attribute.ls_attrs]


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
@pytest.mark.xfail(
    strict=True,
    reason='NODE.unpack_bgpls_nlri loops over the descriptor value with no set of seen '
    'types, so two Autonomous System sub-TLVs are accepted and both reach the JSON',
)
def test_two_instances_of_one_node_descriptor_sub_tlv_are_refused() -> None:
    twice = tlv(SUB_TLV_AUTONOMOUS_SYSTEM, pack('!L', 65000)) + tlv(SUB_TLV_AUTONOMOUS_SYSTEM, pack('!L', 65001))

    with pytest.raises(Notify):
        unpack_nlri(node_nlri(twice))


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
@pytest.mark.xfail(
    strict=True,
    reason='no decoder compares one TLV type to the next, so the section 5.1 ordering rule '
    'is never checked and a descending descriptor is accepted',
)
def test_node_descriptor_sub_tlvs_out_of_ascending_order_are_refused() -> None:
    descending = tlv(SUB_TLV_IGP_ROUTER_ID, ROUTER_ID) + tlv(SUB_TLV_AUTONOMOUS_SYSTEM, pack('!L', 65000))

    with pytest.raises(Notify):
        unpack_nlri(node_nlri(descending))


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
