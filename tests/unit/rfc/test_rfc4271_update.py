"""RFC 4271 sections 4.3 and 6.3: the UPDATE message, its length fields and its flags.

RFC 7606 rewrote most of section 6.3, replacing a session reset with treat-as-withdraw or
attribute discard, and qa/rfc/rfc4271.toml records each of those sentences as
not-applicable with the clause which replaced it.  What is left here is the handful of
UPDATE errors RFC 7606 deliberately left alone: the two length fields, the NLRI field,
and an MP_REACH_NLRI which cannot be parsed far enough to find the NLRI at all.

`test_the_four_unused_flag_bits_are_ignored` was a finding and is now a regression test.
RFC 4271 4.3 says the low four bits of the Attribute Flags octet MUST be ignored on
receipt, and the attribute registry used to be keyed on the whole flags octet with only
the Extended Length bit normalised away, so a peer which set any of them lost the
attribute.  `Attribute._registry_key` now normalises the four bits away as well.

The last finding here was `test_an_unrecognised_well_known_attribute_is_refused`, and it is
gone: qa/rfc/rfc4271.toml now records 6.3-unrecognized-well-known-attribute as
not-applicable, because we recognise every well-known attribute there is and an unknown
type code with the Optional bit clear is a weaker thing than the sentence describes. The
note on that entry carries the argument. What is left below is the unmarked pair which
pins the behaviour the decision keeps.
"""

from __future__ import annotations

import logging

from struct import pack
from typing import Any

import pytest

from exabgp.bgp.message import Action, Notify, Update, UpdateCollection
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection
from exabgp.bgp.message.update.attribute.aggregator import Aggregator
from exabgp.bgp.message.update.attribute.aspath import SEQUENCE, ASPath
from exabgp.bgp.message.update.attribute.community.initial.communities import Communities
from exabgp.bgp.message.update.attribute.atomicaggregate import AtomicAggregate
from exabgp.bgp.message.update.attribute.collection import in_type_order
from exabgp.bgp.message.update.attribute.med import MED
from exabgp.bgp.message.update.attribute.nexthop import NextHop
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.logger import log
from exabgp.logger.option import echo, option
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IPv4
from tests import negotiation

UPDATE_MESSAGE_ERROR = 3
MALFORMED_ATTRIBUTE_LIST = 1
OPTIONAL_ATTRIBUTE_ERROR = 9
INVALID_NETWORK_FIELD = 10

OPTIONAL = 0x80
TRANSITIVE = 0x40
PARTIAL = 0x20
EXTENDED_LENGTH = 0x10
UNUSED_BITS = 0x0F

WELL_KNOWN_TRANSITIVE = TRANSITIVE

# One announcement, its three mandatory attributes, and nothing else to go wrong.
ORIGIN_IGP = bytes([WELL_KNOWN_TRANSITIVE, Attribute.CODE.ORIGIN, 1, 0])
EMPTY_AS_PATH = bytes([WELL_KNOWN_TRANSITIVE, Attribute.CODE.AS_PATH, 0])
NEXT_HOP = bytes([WELL_KNOWN_TRANSITIVE, Attribute.CODE.NEXT_HOP, 4]) + bytes([10, 0, 0, 1])
MANDATORY = ORIGIN_IGP + EMPTY_AS_PATH + NEXT_HOP
IPV4_PREFIX = bytes([24, 10, 0, 0])


def negotiated(families: tuple[tuple[AFI, SAFI], ...] = ()) -> Any:
    """The session state the decoder and the semantic transformation both read.

    Same shape as tests/unit/test_rfc7606_prescribed_action.py: everything which looks at
    the bytes below is production code, this only says what was negotiated.
    """
    return negotiation.negotiated(list(families), asn4=False, msg_size=4096)


def body(withdrawn: bytes = b'', attributes: bytes = MANDATORY, nlri: bytes = IPV4_PREFIX) -> bytes:
    """An UPDATE payload, the nineteen octets of header already taken off."""
    return pack('!H', len(withdrawn)) + withdrawn + pack('!H', len(attributes)) + attributes + nlri


def parse(payload: bytes, families: tuple[tuple[AFI, SAFI], ...] = ()) -> UpdateCollection:
    session = negotiated(families)
    message = Update.unpack_message(payload, session)
    assert isinstance(message, Update), f'an UPDATE payload decoded to {type(message).__name__}'
    return message.parse(session)


def refused(payload: bytes, families: tuple[tuple[AFI, SAFI], ...] = ()) -> Notify:
    try:
        parsed = parse(payload, families)
    except Notify as notify:
        return notify
    pytest.fail(f'{payload.hex()} was accepted: {len(parsed.announces)} announced, {len(parsed.withdraws)} withdrawn')


def attribute_flags(packed: bytes) -> list[tuple[int, int]]:
    """Every (flags octet, type code) in a packed attribute section, in order.

    The loop is bounded by the buffer: each iteration consumes at least three octets of
    it, and stops as soon as a whole header no longer fits.
    """
    found: list[tuple[int, int]] = []
    offset = 0
    while offset + 3 <= len(packed):
        flag = packed[offset]
        code = packed[offset + 1]
        if flag & EXTENDED_LENGTH:
            if offset + 4 > len(packed):
                break
            length = int.from_bytes(packed[offset + 2 : offset + 4], 'big')
            offset += 4
        else:
            length = packed[offset + 2]
            offset += 3
        found.append((flag, code))
        offset += length
    return found


def what_we_send() -> list[tuple[int, int]]:
    """The flags octets of a packed attribute section we generated ourselves."""
    attributes = AttributeCollection()
    attributes.add(Origin.from_int(2))
    attributes.add(ASPath.make_aspath((SEQUENCE([ASN(65001)]),)))
    attributes.add(MED(pack('!L', 100)))
    attributes.add(AtomicAggregate(b''))
    return attribute_flags(bytes(attributes.pack_attribute(Negotiated.UNSET)))


# ------------------------------------------------------------------ 5 attribute order

LARGE_ASN = 4200000000


def attributes_to_a_two_octet_session() -> AttributeCollection:
    """A path and an aggregator neither of which fits two octets, with a community after them.

    To a session without the four-octet AS capability AS_PATH (2) brings AS4_PATH (17) and
    AGGREGATOR (7) brings AS4_AGGREGATOR (18), each packed right behind its partner.
    """
    attributes = AttributeCollection()
    attributes.add(Origin.from_int(0))
    attributes.add(ASPath.make_aspath((SEQUENCE([ASN(LARGE_ASN)]),), asn4=True))
    attributes.add(NextHop.from_string('10.0.0.1'))
    attributes.add(Aggregator.make_aggregator(ASN(LARGE_ASN), IPv4.from_string('10.0.0.2')))
    attributes.add(Communities(pack('!HH', 65000, 1)))
    return attributes


@pytest.mark.rfc('rfc4271#5-send-attributes-in-ascending-order')
def test_the_attributes_we_send_are_in_ascending_type_order() -> None:
    packed = bytes(attributes_to_a_two_octet_session().pack_attribute(negotiated()))
    codes = [code for _, code in attribute_flags(packed)]

    assert Attribute.CODE.AS4_PATH in codes and Attribute.CODE.AS4_AGGREGATOR in codes, f'nothing to order: {codes}'
    assert codes == sorted(codes), f'the attributes went out as {codes}'


@pytest.mark.rfc('rfc4271#5-send-attributes-in-ascending-order')
def test_the_otc_added_after_the_rest_is_packed_takes_its_place() -> None:
    """RFC 9234's OTC (35) is appended once the attributes are packed, which may hold a 40."""
    prefix_sid = bytes([OPTIONAL | TRANSITIVE, 40, 0])
    otc = bytes([OPTIONAL | TRANSITIVE, Attribute.CODE.OTC, 4]) + pack('!L', 65000)
    long_one = bytes([OPTIONAL | TRANSITIVE | EXTENDED_LENGTH, 128, 0, 1, 0])

    ordered = in_type_order(ORIGIN_IGP + prefix_sid + long_one + otc)

    assert [code for _, code in attribute_flags(ordered)] == [Attribute.CODE.ORIGIN, Attribute.CODE.OTC, 40, 128]


@pytest.mark.rfc('rfc4271#5-handle-attributes-out-of-order')
def test_attributes_out_of_order_are_taken() -> None:
    parsed = parse(body(attributes=NEXT_HOP + EMPTY_AS_PATH + ORIGIN_IGP))

    assert Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW not in parsed.attributes
    for code in (Attribute.CODE.ORIGIN, Attribute.CODE.AS_PATH, Attribute.CODE.NEXT_HOP):
        assert code in parsed.attributes, f'attribute {code} was lost to the order it came in'


# ------------------------------------------------------------------ 4.3 the attribute flags


@pytest.mark.rfc('rfc4271#4.3-well-known-attributes-are-transitive')
def test_the_well_known_attributes_we_send_are_transitive() -> None:
    sent = what_we_send()

    assert sent, 'no attribute was packed, so this test is watching nothing'
    for flag, code in sent:
        if flag & OPTIONAL:
            continue
        assert flag & TRANSITIVE, f'well-known attribute {code} went out with the Transitive bit clear'


@pytest.mark.parametrize(
    'code,payload',
    [
        (Attribute.CODE.ORIGIN, bytes([1, 0])),
        (Attribute.CODE.AS_PATH, bytes([0])),
        (Attribute.CODE.NEXT_HOP, bytes([4, 10, 0, 0, 1])),
    ],
    ids=['origin', 'as-path', 'next-hop'],
)
@pytest.mark.rfc('rfc4271#4.3-well-known-attributes-are-transitive', polarity='negative')
def test_a_well_known_attribute_without_the_transitive_bit_is_not_taken(code: int, payload: bytes) -> None:
    """The flags are part of what identifies the attribute, so a conflict loses it.

    RFC 7606 3.c is what says the route is withdrawn rather than the session reset; what
    this asserts is only that the malformed flags were noticed at all.
    """
    others = b''.join(part for part in (ORIGIN_IGP, EMPTY_AS_PATH, NEXT_HOP) if part[1] != code)
    parsed = parse(body(attributes=bytes([0x00, code]) + payload + others))

    assert code not in parsed.attributes, f'attribute {code} was accepted with the Transitive bit clear'


@pytest.mark.rfc('rfc4271#4.3-partial-bit-is-zero')
def test_the_partial_bit_is_clear_on_everything_we_send() -> None:
    sent = what_we_send()

    assert sent, 'no attribute was packed, so this test is watching nothing'
    for flag, code in sent:
        if flag & OPTIONAL and flag & TRANSITIVE:
            continue
        assert not flag & PARTIAL, f'attribute {code} went out with the Partial bit set'


@pytest.mark.rfc('rfc4271#4.3-partial-bit-is-zero', polarity='negative')
def test_a_well_known_attribute_received_with_the_partial_bit_goes_out_without_it() -> None:
    """The peer broke the sentence; we neither punish the route nor repeat the mistake.

    RFC 7606 3 (c) makes only the Optional and Transitive bits a malformation, so the
    Partial bit of what we receive is ignored. This UPDATE was treated as withdraw.
    """
    parsed = parse(
        body(attributes=bytes([TRANSITIVE | PARTIAL, Attribute.CODE.ORIGIN, 1, 0]) + EMPTY_AS_PATH + NEXT_HOP)
    )

    assert Attribute.CODE.ORIGIN in parsed.attributes, 'an ORIGIN with the Partial bit set was refused'
    assert Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW not in parsed.attributes
    sent = attribute_flags(bytes(parsed.attributes.pack_attribute(Negotiated.UNSET)))
    assert (TRANSITIVE, int(Attribute.CODE.ORIGIN)) in sent, f'ORIGIN went out as {sent}'


@pytest.mark.rfc('rfc4271#4.3-unused-flag-bits')
def test_the_four_unused_flag_bits_are_zero_on_everything_we_send() -> None:
    sent = what_we_send()

    assert sent, 'no attribute was packed, so this test is watching nothing'
    for flag, code in sent:
        assert not flag & UNUSED_BITS, f'attribute {code} went out with flags {flag:#04x}'


@pytest.mark.parametrize('bits', [0x01, 0x02, 0x04, 0x08, 0x0F], ids=lambda value: f'bits {value:#04x}')
@pytest.mark.rfc('rfc4271#4.3-unused-flag-bits', polarity='negative')
def test_the_four_unused_flag_bits_are_ignored(bits: int) -> None:
    parsed = parse(body(attributes=bytes([TRANSITIVE | bits, Attribute.CODE.ORIGIN, 1, 0]) + EMPTY_AS_PATH + NEXT_HOP))

    assert Attribute.CODE.ORIGIN in parsed.attributes, f'an ORIGIN with flags {TRANSITIVE | bits:#04x} was lost'


# ------------------------------------------------------- 4.3 a prefix in both of the fields


@pytest.mark.rfc('rfc4271#4.3-process-a-prefix-in-both-fields')
def test_the_same_prefix_withdrawn_and_announced_is_processed() -> None:
    """The RFC says a speaker SHOULD NOT send this, and MUST cope when one does.

    Coping is parsing it into the announcement.  The withdrawal is dropped, as the SHOULD
    below asks, so the count of withdrawals is zero rather than one.
    """
    parsed = parse(body(withdrawn=IPV4_PREFIX, nlri=IPV4_PREFIX))

    assert len(parsed.announces) == 1, 'the announcement was lost'
    assert len(parsed.withdraws) == 0, 'the withdrawal of an announced prefix was kept'


@pytest.mark.rfc('rfc4271#4.3-ignore-a-prefix-in-both-fields')
def test_the_same_prefix_withdrawn_and_announced_is_only_announced() -> None:
    """The SHOULD which follows the MUST above: act as if the withdrawal was not there.

    A consumer which batches, or sorts withdrawals ahead of announcements, would otherwise
    remove the route the same UPDATE installs.
    """
    parsed = parse(body(withdrawn=IPV4_PREFIX, nlri=IPV4_PREFIX))

    assert [str(routed.nlri) for routed in parsed.announces] == ['10.0.0.0/24'], 'the announcement was lost'
    assert not parsed.withdraws, f'the prefix was withdrawn as well: {parsed.withdraws}'


@pytest.mark.rfc('rfc4271#4.3-ignore-a-prefix-in-both-fields', polarity='negative')
def test_a_withdrawn_prefix_which_is_not_announced_is_still_withdrawn() -> None:
    """Only the prefix in both fields loses its withdrawal: dropping them all passes the test above."""
    other = bytes([24, 10, 0, 1])
    parsed = parse(body(withdrawn=IPV4_PREFIX + other, nlri=IPV4_PREFIX))

    assert [str(routed.nlri) for routed in parsed.announces] == ['10.0.0.0/24']
    assert [str(nlri) for nlri in parsed.withdraws] == ['10.0.1.0/24'], 'a withdrawal of another prefix was lost'


# ------------------------------------------------------------ 6.3 the two length fields


TOO_LARGE = [
    (pack('!H', 40) + IPV4_PREFIX + pack('!H', 0), 'withdrawn routes length'),
    (pack('!H', 0) + pack('!H', 40) + MANDATORY, 'total attribute length'),
    (pack('!H', 0xFFFF) + pack('!H', 0), 'withdrawn routes length is the whole message'),
    (pack('!H', 4) + IPV4_PREFIX + pack('!H', 0xFFFF) + MANDATORY, 'both'),
]


@pytest.mark.parametrize('payload', [payload for payload, _ in TOO_LARGE], ids=[name for _, name in TOO_LARGE])
@pytest.mark.rfc('rfc4271#6.3-malformed-attribute-list')
def test_a_length_field_larger_than_the_message_is_a_malformed_attribute_list(payload: bytes) -> None:
    notify = refused(payload)

    assert notify.code == UPDATE_MESSAGE_ERROR
    assert notify.subcode == MALFORMED_ATTRIBUTE_LIST


@pytest.mark.parametrize(
    'payload',
    [body(), body(withdrawn=IPV4_PREFIX, attributes=b'', nlri=b''), body(nlri=b'')],
    ids=['announce', 'withdraw only', 'attributes only'],
)
@pytest.mark.rfc('rfc4271#6.3-malformed-attribute-list', polarity='negative')
def test_length_fields_which_add_up_are_not_refused(payload: bytes) -> None:
    """The boundary matters: a check written with the wrong inequality fails this half."""
    parse(payload)


@pytest.mark.rfc('rfc4271#6.3-malformed-attribute-list', polarity='negative')
def test_the_smallest_update_the_rfc_defines_is_not_refused() -> None:
    """Two zero length fields and nothing else: RFC 4271 4.3's 23 octet minimum UPDATE.

    It does not reach parse(): two zero lengths is the End-of-RIB marker, which
    Update.unpack_message answers before the split, so the assertion is that it decodes.
    """
    session = negotiated()

    assert Update.unpack_message(pack('!H', 0) + pack('!H', 0), session) is not None


# ------------------------------------------------------------------------ 6.3 the NLRI field


BAD_PREFIXES = [
    (bytes([33, 10, 0, 0, 0]), 'mask above 32'),
    (bytes([255, 10, 0, 0]), 'mask of 255'),
    (bytes([24, 10, 0]), 'prefix shorter than its mask'),
    (bytes([32]), 'mask with no prefix at all'),
]


@pytest.mark.parametrize('prefix', [prefix for prefix, _ in BAD_PREFIXES], ids=[name for _, name in BAD_PREFIXES])
@pytest.mark.rfc('rfc4271#6.3-invalid-network-field')
def test_a_syntactically_invalid_prefix_is_an_invalid_network_field(prefix: bytes) -> None:
    notify = refused(body(nlri=prefix))

    assert notify.code == UPDATE_MESSAGE_ERROR
    assert notify.subcode == INVALID_NETWORK_FIELD


@pytest.mark.parametrize(
    'prefix',
    [bytes([0]), bytes([8, 10]), bytes([24, 10, 0, 0]), bytes([32, 10, 0, 0, 1])],
    ids=['default route', 'a /8', 'a /24', 'a /32'],
)
@pytest.mark.rfc('rfc4271#6.3-invalid-network-field', polarity='negative')
def test_a_syntactically_valid_prefix_is_accepted(prefix: bytes) -> None:
    """Zero and 32 are the two ends of the range, and both are legal."""
    parsed = parse(body(nlri=prefix))

    assert len(parsed.announces) == 1


@pytest.mark.parametrize('prefix', [prefix for prefix, _ in BAD_PREFIXES], ids=[name for _, name in BAD_PREFIXES])
@pytest.mark.rfc('rfc4271#6.3-invalid-network-field')
def test_an_invalid_prefix_in_the_withdrawn_routes_is_refused_too(prefix: bytes) -> None:
    """RFC 7606 3.i: the WITHDRAWN ROUTES field is checked the same way as the NLRI."""
    notify = refused(body(withdrawn=prefix, attributes=b'', nlri=b''))

    assert notify.code == UPDATE_MESSAGE_ERROR
    assert notify.subcode == INVALID_NETWORK_FIELD


# The NLRI of the other families are decoded from MP_REACH_NLRI by their own decoders, and
# a Notify out of one ends the session as raised.  These answered 3/5, Attribute Length
# Error, which names an attribute rather than the NLRI field the RFC says is wrong.
ROUTE_FIELDS = bytes(8 + 10 + 4)  # Route Distinguisher, ESI, Ethernet Tag
NO_IP_MAC_ROUTE = bytes(6) + bytes([0]) + bytes([0x00, 0x06, 0x41])
MALFORMED_FAMILY_NLRI: list[tuple[str, AFI, SAFI, bytes]] = [
    ('evpn mac length 24', AFI.l2vpn, SAFI.evpn, bytes([2, 33]) + ROUTE_FIELDS + bytes([24]) + NO_IP_MAC_ROUTE),
    (
        'evpn mac with an ip length of 8',
        AFI.l2vpn,
        SAFI.evpn,
        bytes([2, 33]) + ROUTE_FIELDS + bytes([48]) + bytes(6) + bytes([8, 0x00, 0x06, 0x41]),
    ),
    (
        'evpn mac shorter than its ip length',
        AFI.l2vpn,
        SAFI.evpn,
        bytes([2, 33]) + ROUTE_FIELDS + bytes([48]) + bytes(6) + bytes([32, 0x00, 0x06, 0x41]),
    ),
    ('evpn segment with an ip length of 8', AFI.l2vpn, SAFI.evpn, bytes([4, 20]) + bytes(18) + bytes([8, 0])),
    ('evpn prefix of 35 octets', AFI.l2vpn, SAFI.evpn, bytes([5, 35]) + bytes(35)),
    ('mvpn source active of 3 octets', AFI.ipv4, SAFI.mcast_vpn, bytes([5, 3]) + bytes(3)),
    ('mvpn shared join of 3 octets', AFI.ipv4, SAFI.mcast_vpn, bytes([6, 3]) + bytes(3)),
    ('mvpn source join of 3 octets', AFI.ipv4, SAFI.mcast_vpn, bytes([7, 3]) + bytes(3)),
    (
        'mvpn source active with a source length of 8',
        AFI.ipv4,
        SAFI.mcast_vpn,
        bytes([5, 18]) + bytes(8) + bytes([8]) + bytes(4) + bytes([32]) + bytes(4),
    ),
]


@pytest.mark.parametrize(
    ('afi', 'safi', 'wire'),
    [entry[1:] for entry in MALFORMED_FAMILY_NLRI],
    ids=[entry[0] for entry in MALFORMED_FAMILY_NLRI],
)
@pytest.mark.rfc('rfc4271#6.3-invalid-network-field')
def test_a_syntactically_invalid_nlri_of_another_family_is_an_invalid_network_field(
    afi: AFI, safi: SAFI, wire: bytes
) -> None:
    with pytest.raises(Notify) as raised:
        NLRI.unpack_nlri(afi, safi, wire, Action.ANNOUNCE, False, Negotiated.UNSET)

    assert (raised.value.code, raised.value.subcode) == (UPDATE_MESSAGE_ERROR, INVALID_NETWORK_FIELD), str(raised.value)


# ------------------------------------------------------- 6.3 semantically incorrect values

# The real dispatcher, kept before any test can swap it for the no-op one.
ENABLED_LOG_DISPATCH = log.logger
LOG_LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')


def enable_every_log(monkeypatch: pytest.MonkeyPatch, caplog: Any) -> None:
    """Every level and every source switched on, so silence is the parser's own."""
    monkeypatch.setattr(log, 'logger', staticmethod(ENABLED_LOG_DISPATCH))
    monkeypatch.setattr(option, 'logger', logging.getLogger('test.rfc4271.update'))
    monkeypatch.setattr(option, 'formater', echo)
    monkeypatch.setattr(option, 'option', {})
    monkeypatch.setattr(option, 'logit', {level: True for level in LOG_LEVELS})
    caplog.set_level(logging.DEBUG, logger='test.rfc4271.update')


@pytest.mark.parametrize(
    'address',
    [bytes([0, 0, 0, 0]), bytes([224, 0, 0, 1])],
    ids=['unspecified', 'multicast'],
)
@pytest.mark.rfc('rfc4271#6.3-next-hop-semantically-incorrect', polarity='negative')
def test_a_route_with_a_semantically_incorrect_next_hop_is_ignored(address: bytes) -> None:
    """Syntactically a NEXT_HOP is four octets, and these are four octets.

    Neither is an address a router can forward to, which is what RFC 4271 5.1.3 asks a
    NEXT_HOP to be, so the route SHOULD be ignored: not a session reset, not a withdrawal,
    simply not announced onwards to the API.
    """
    next_hop = bytes([WELL_KNOWN_TRANSITIVE, Attribute.CODE.NEXT_HOP, 4]) + address
    parsed = parse(body(attributes=ORIGIN_IGP + EMPTY_AS_PATH + next_hop))

    assert not parsed.announces, f'a route with next hop {".".join(map(str, address))} was kept: {parsed.announces}'
    assert not parsed.withdraws, 'an ignored route is not a withdrawn one'
    assert Attribute.CODE.ORIGIN in parsed.attributes, 'the rest of the UPDATE was not processed'


@pytest.mark.parametrize(
    'address',
    [bytes([10, 0, 0, 1]), bytes([223, 255, 255, 255]), bytes([240, 0, 0, 1])],
    ids=['private', 'last of class C', 'class E'],
)
@pytest.mark.rfc('rfc4271#6.3-next-hop-semantically-incorrect')
def test_a_route_with_a_unicast_next_hop_is_kept(address: bytes) -> None:
    """The boundary of 224.0.0.0/4 on both sides: an ignore of every next hop fails here."""
    next_hop = bytes([WELL_KNOWN_TRANSITIVE, Attribute.CODE.NEXT_HOP, 4]) + address
    parsed = parse(body(attributes=ORIGIN_IGP + EMPTY_AS_PATH + next_hop))

    assert [str(routed.nlri) for routed in parsed.announces] == ['10.0.0.0/24']
    assert [str(routed.nexthop) for routed in parsed.announces] == ['.'.join(map(str, address))]


@pytest.mark.rfc('rfc4271#6.3-next-hop-semantically-incorrect', polarity='negative')
def test_a_semantically_incorrect_next_hop_is_logged(monkeypatch: pytest.MonkeyPatch, caplog: Any) -> None:
    """The first half of the SHOULD: the error is logged, not only acted on."""
    next_hop = bytes([WELL_KNOWN_TRANSITIVE, Attribute.CODE.NEXT_HOP, 4]) + bytes([224, 0, 0, 1])
    enable_every_log(monkeypatch, caplog)
    parse(body(attributes=ORIGIN_IGP + EMPTY_AS_PATH + next_hop))

    assert any('224.0.0.1' in record.getMessage() and record.levelno >= logging.ERROR for record in caplog.records), [
        record.getMessage() for record in caplog.records
    ]


@pytest.mark.parametrize(
    'prefix',
    [bytes([4, 224]), bytes([24, 239, 1, 1])],
    ids=['224.0.0.0/4', '239.1.1.0/24'],
)
@pytest.mark.rfc('rfc4271#6.3-nlri-semantically-incorrect', polarity='negative')
def test_a_multicast_prefix_in_the_nlri_is_ignored(prefix: bytes) -> None:
    """The RFC's own example of a semantically incorrect prefix, in the unicast NLRI field.

    The prefix alone is ignored: the UPDATE is otherwise well formed, so it is no reason
    to reset the session, and a unicast prefix beside it would still be announced.
    """
    parsed = parse(body(nlri=prefix + IPV4_PREFIX))

    assert [str(routed.nlri) for routed in parsed.announces] == ['10.0.0.0/24']
    assert not parsed.withdraws, 'an ignored prefix is not a withdrawn one'


@pytest.mark.parametrize(
    'prefix',
    [bytes([0]), bytes([3, 224]), bytes([24, 223, 255, 255]), bytes([4, 240])],
    ids=['0.0.0.0/0', '224.0.0.0/3', '223.255.255.0/24', '240.0.0.0/4'],
)
@pytest.mark.rfc('rfc4271#6.3-nlri-semantically-incorrect')
def test_a_unicast_prefix_in_the_nlri_is_kept(prefix: bytes) -> None:
    """Around 224.0.0.0/4: a covering /3 and the default route are not multicast addresses."""
    parsed = parse(body(nlri=prefix))

    assert len(parsed.announces) == 1, f'{prefix.hex()} was ignored'


@pytest.mark.rfc('rfc4271#6.3-nlri-semantically-incorrect', polarity='negative')
def test_a_multicast_prefix_in_the_nlri_is_logged(monkeypatch: pytest.MonkeyPatch, caplog: Any) -> None:
    enable_every_log(monkeypatch, caplog)
    parse(body(nlri=bytes([24, 239, 1, 1])))

    assert any(
        '239.1.1.0/24' in record.getMessage() and record.levelno >= logging.ERROR for record in caplog.records
    ), [record.getMessage() for record in caplog.records]


# ----------------------------------------------------------- 6.3 an optional attribute error

IPV4_UNICAST = ((AFI.ipv4, SAFI.unicast),)


def mp_reach(value: bytes) -> bytes:
    return bytes([OPTIONAL, Attribute.CODE.MP_REACH_NLRI, len(value)]) + value


WELL_FORMED_MP_REACH = pack('!HB', 1, 1) + bytes([4]) + bytes([10, 0, 0, 2]) + bytes([0]) + IPV4_PREFIX

TRUNCATED_MP_REACH = [
    (bytes(3), 'shorter than afi, safi and the next-hop length'),
    (bytes(4), 'no reserved octet'),
    (pack('!HB', 1, 1) + bytes([16, 0]), 'next hop runs past the attribute'),
]


@pytest.mark.parametrize(
    'value', [value for value, _ in TRUNCATED_MP_REACH], ids=[name for _, name in TRUNCATED_MP_REACH]
)
@pytest.mark.rfc('rfc4271#6.3-optional-attribute-error')
def test_an_mp_reach_which_cannot_be_read_is_an_optional_attribute_error(value: bytes) -> None:
    """RFC 7606 5.3 keeps the session reset here, because treat-as-withdraw needs the NLRI."""
    notify = refused(body(attributes=ORIGIN_IGP + EMPTY_AS_PATH + mp_reach(value), nlri=b''), IPV4_UNICAST)

    assert notify.code == UPDATE_MESSAGE_ERROR
    assert notify.subcode == OPTIONAL_ATTRIBUTE_ERROR


@pytest.mark.parametrize(
    'value', [value for value, _ in TRUNCATED_MP_REACH], ids=[name for _, name in TRUNCATED_MP_REACH]
)
@pytest.mark.rfc('rfc4271#6.3-optional-attribute-error-data-field')
def test_an_optional_attribute_error_carries_the_attribute(value: bytes) -> None:
    """The Data field held an English sentence; the RFC asks for the attribute as it came."""
    notify = refused(body(attributes=ORIGIN_IGP + EMPTY_AS_PATH + mp_reach(value), nlri=b''), IPV4_UNICAST)

    assert notify.data == mp_reach(value)


def test_an_mp_reach_with_the_wrong_flags_carries_the_attribute_as_sent() -> None:
    """Unmarked: the flag check raises 3/9 outside the decoder, and must carry the same."""
    sent = (
        bytes([OPTIONAL | TRANSITIVE, Attribute.CODE.MP_REACH_NLRI, len(WELL_FORMED_MP_REACH)]) + WELL_FORMED_MP_REACH
    )
    notify = refused(body(attributes=ORIGIN_IGP + EMPTY_AS_PATH + sent, nlri=b''), IPV4_UNICAST)

    assert (notify.code, notify.subcode) == (UPDATE_MESSAGE_ERROR, OPTIONAL_ATTRIBUTE_ERROR)
    assert notify.data == sent


@pytest.mark.rfc('rfc4271#6.3-optional-attribute-error', polarity='negative')
def test_a_well_formed_mp_reach_is_accepted() -> None:
    parsed = parse(body(attributes=ORIGIN_IGP + EMPTY_AS_PATH + mp_reach(WELL_FORMED_MP_REACH), nlri=b''), IPV4_UNICAST)

    assert len(parsed.announces) == 1, 'a well formed MP_REACH_NLRI announced nothing'


# ------------------------------------------- 6.3 an unrecognised attribute claiming to be well-known


@pytest.mark.parametrize('code', [200, 201, 254], ids=lambda value: f'type {value}')
def test_an_unrecognised_attribute_with_the_optional_bit_clear_is_kept_as_a_generic_one(code: int) -> None:
    """Unmarked, because qa/rfc/rfc4271.toml records 6.3-unrecognized-well-known-attribute
    as not-applicable and the checker refuses a marker against a requirement we do not
    claim.  What is on the wire here is a type code we do not know whose Optional bit is
    clear, which is not the same thing as a well-known mandatory attribute we failed to
    recognise: the flags octet says nothing about mandatory against discretionary.  We
    carry it to the API and announce the route.  The ledger note argues the case."""
    parsed = parse(body(attributes=MANDATORY + bytes([WELL_KNOWN_TRANSITIVE, code, 1, 9])))

    assert code in parsed.attributes
    assert len(parsed.announces) == 1


def test_every_attribute_the_registry_calls_well_known_is_one_we_decode() -> None:
    """The fact the not-applicable rests on, so it cannot rot quietly.

    RFC 4271 section 5 makes ORIGIN, AS_PATH and NEXT_HOP well-known mandatory, and adds
    LOCAL_PREF and ATOMIC_AGGREGATE to the well-known side.  Every path attribute assigned
    since is optional.  The day that stops being true, or the day one of these stops being
    decoded, "we recognise every well-known attribute there is" needs re-arguing and this
    fails.
    """
    well_known = {
        Attribute.CODE.ORIGIN,
        Attribute.CODE.AS_PATH,
        Attribute.CODE.NEXT_HOP,
        Attribute.CODE.LOCAL_PREF,
        Attribute.CODE.ATOMIC_AGGREGATE,
    }

    assert set(Attribute.attributes_well_know) == well_known
    for code in well_known:
        klass = Attribute.klass_by_id(code)
        assert klass is not None, f'{Attribute.CODE.name(code)} is well-known and has no decoder'
        assert not klass.FLAG & OPTIONAL, f'{Attribute.CODE.name(code)} is registered as optional'


# ------------------------------------------------------------ 6.3 an UPDATE with no NLRI


@pytest.mark.rfc('rfc4271#6.3-no-nlri-is-still-valid')
def test_correct_attributes_with_no_nlri_are_a_valid_update() -> None:
    parsed = parse(body(nlri=b''))

    assert len(parsed.announces) == 0
    assert len(parsed.withdraws) == 0
    assert Attribute.CODE.ORIGIN in parsed.attributes, 'the attributes were thrown away with the empty NLRI'
