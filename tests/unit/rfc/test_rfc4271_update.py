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

The finding left is `test_an_unrecognised_well_known_attribute_is_refused`.
"""

from __future__ import annotations

from struct import pack
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Action, Notify, Update, UpdateCollection
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection
from exabgp.bgp.message.update.attribute.aspath import SEQUENCE, ASPath
from exabgp.bgp.message.update.attribute.atomicaggregate import AtomicAggregate
from exabgp.bgp.message.update.attribute.med import MED
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.protocol.family import AFI, SAFI

UPDATE_MESSAGE_ERROR = 3
MALFORMED_ATTRIBUTE_LIST = 1
UNRECOGNIZED_WELL_KNOWN_ATTRIBUTE = 2
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
    session = Mock()
    session.asn4 = False
    session.addpath = Mock()
    session.addpath.receive = Mock(return_value=False)
    session.addpath.send = Mock(return_value=False)
    session.required = Mock(return_value=False)
    session.families = list(families)
    session.nexthop = []
    session.msg_size = 4096
    session.direction = Action.ANNOUNCE

    neighbour = Mock()
    neighbour.__getitem__ = Mock(return_value={'aigp': False})
    neighbour.session = Mock()
    neighbour.session.local_address = Mock()
    neighbour.session.local_address.afi = AFI.ipv4
    session.neighbor = neighbour
    return session


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
def test_a_well_known_attribute_with_the_partial_bit_set_is_not_taken() -> None:
    parsed = parse(
        body(attributes=bytes([TRANSITIVE | PARTIAL, Attribute.CODE.ORIGIN, 1, 0]) + EMPTY_AS_PATH + NEXT_HOP)
    )

    assert Attribute.CODE.ORIGIN not in parsed.attributes, 'an ORIGIN with the Partial bit set was accepted'


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
    """The RFC says a speaker SHOULD NOT send this, and MUST cope when one does."""
    parsed = parse(body(withdrawn=IPV4_PREFIX, nlri=IPV4_PREFIX))

    assert len(parsed.announces) == 1, 'the announcement was lost'
    assert len(parsed.withdraws) == 1, 'the withdrawal was lost'


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


@pytest.mark.rfc('rfc4271#6.3-optional-attribute-error', polarity='negative')
def test_a_well_formed_mp_reach_is_accepted() -> None:
    parsed = parse(body(attributes=ORIGIN_IGP + EMPTY_AS_PATH + mp_reach(WELL_FORMED_MP_REACH), nlri=b''), IPV4_UNICAST)

    assert len(parsed.announces) == 1, 'a well formed MP_REACH_NLRI announced nothing'


# ------------------------------------------------- 6.3 an unrecognised well-known attribute


@pytest.mark.parametrize('code', [200, 201, 254], ids=lambda value: f'type {value}')
@pytest.mark.rfc('rfc4271#6.3-unrecognized-well-known-attribute')
@pytest.mark.xfail(
    strict=True,
    reason='an attribute with the Optional bit clear and an unregistered type code is kept as '
    'a GenericAttribute when the Transitive bit is set, and dropped silently when it is not, '
    'which is the handling RFC 4271 section 5 gives an optional attribute',
)
def test_an_unrecognised_well_known_attribute_is_refused(code: int) -> None:
    notify = refused(body(attributes=MANDATORY + bytes([WELL_KNOWN_TRANSITIVE, code, 1, 9])))

    assert notify.code == UPDATE_MESSAGE_ERROR
    assert notify.subcode == UNRECOGNIZED_WELL_KNOWN_ATTRIBUTE


def test_an_unrecognised_well_known_attribute_is_kept_as_a_generic_one() -> None:
    """Unmarked: what happens instead, written down so the xfail above says what it means."""
    parsed = parse(body(attributes=MANDATORY + bytes([WELL_KNOWN_TRANSITIVE, 200, 1, 9])))

    assert 200 in parsed.attributes
    assert len(parsed.announces) == 1


# ------------------------------------------------------------ 6.3 an UPDATE with no NLRI


@pytest.mark.rfc('rfc4271#6.3-no-nlri-is-still-valid')
def test_correct_attributes_with_no_nlri_are_a_valid_update() -> None:
    parsed = parse(body(nlri=b''))

    assert len(parsed.announces) == 0
    assert len(parsed.withdraws) == 0
    assert Attribute.CODE.ORIGIN in parsed.attributes, 'the attributes were thrown away with the empty NLRI'
