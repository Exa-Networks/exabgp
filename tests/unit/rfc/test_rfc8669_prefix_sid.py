"""RFC 8669: the BGP Prefix-SID attribute, and what section 6 says to do when it is wrong.

Section 6 is the whole point of this file.  It names three malformed shapes - an attribute
below the minimum length, a TLV length outside the TLV's own constraints, and a TLV length
running past the end of the attribute - and gives all three the same answer: ignore the
attribute, keep the route, do not advertise the attribute onwards.  RFC 7606 calls that
"Attribute discard", and in this codebase it is `DISCARD = True` on the attribute class.

The interesting part is that a class flag is a single switch and section 6 names three
doors.  Two of them go through `Attribute.unpack` and hit the flag.  The third, the
zero-length attribute, used to be caught by the generic `length == 0 and not VALID_ZERO`
rule in `AttributeCollection.parse` before the flag was ever consulted, and came out as
treat-as-withdraw instead.  `PrefixSid` now sets `VALID_ZERO` to keep that generic rule
from answering for it and refuses the empty value in its own decoder, so all three doors
reach `DISCARD`.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid
from exabgp.bgp.message.update.attribute.sr.srgb import SrGb

pytestmark = pytest.mark.timeout(10)

PREFIX_SID = int(Attribute.CODE.BGP_PREFIX_SID)
DISCARD = Attribute.CODE.INTERNAL_DISCARD
TREAT_AS_WITHDRAW = Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW

OPTIONAL_TRANSITIVE = 0xC0

LABEL_INDEX_TLV = 1
ORIGINATOR_SRGB_TLV = 3
# Section 7 reserves 0 and 255 and leaves 1-254 to expert review, so 99 is a type a future
# document could be given and this implementation would not know.
UNKNOWN_TLV = 99


def tlv(code: int, value: bytes) -> bytes:
    """A Prefix-SID TLV: one octet of type, two of length, then the value."""
    return bytes([code]) + pack('!H', len(value)) + value


def label_index(index: int, reserved: int = 0, flags: int = 0) -> bytes:
    """Section 3.1: RESERVED(1) + Flags(2) + Label Index(4), seven octets."""
    return tlv(LABEL_INDEX_TLV, pack('!B', reserved) + pack('!H', flags) + pack('!I', index))


def srgb(ranges: list[tuple[int, int]], flags: int = 0) -> bytes:
    """Section 3.2: Flags(2) then one or more (base, range) pairs of three octets each."""
    value = pack('!H', flags)
    for base, size in ranges:
        value += pack('!I', base)[1:] + pack('!I', size)[1:]
    return tlv(ORIGINATOR_SRGB_TLV, value)


def attribute(value: bytes, flag: int = OPTIONAL_TRANSITIVE) -> bytes:
    """One path attribute, non-extended length, wrapping a Prefix-SID value."""
    return bytes([flag, PREFIX_SID, len(value)]) + value


def parse(wire: bytes) -> AttributeCollection:
    return AttributeCollection().parse(wire, Negotiated.UNSET)


def decoded(wire: bytes) -> PrefixSid:
    collection = parse(wire)
    attr = collection[PREFIX_SID]
    assert isinstance(attr, PrefixSid)
    return attr


# --------------------------------------------------------------------------------------
# 3. unknown TLVs MUST be ignored and propagated unmodified


@pytest.mark.rfc('rfc8669#3-unknown-tlv-ignored-and-propagated')
def test_a_prefix_sid_holding_only_an_unknown_tlv_still_decodes() -> None:
    attr = decoded(attribute(tlv(UNKNOWN_TLV, b'\xde\xad\xbe\xef')))
    assert len(attr.sr_attrs) == 1
    assert attr.sr_attrs[0].TLV == UNKNOWN_TLV


@pytest.mark.rfc('rfc8669#3-unknown-tlv-ignored-and-propagated', polarity='negative')
def test_an_unknown_tlv_is_re_emitted_byte_for_byte_beside_a_known_one() -> None:
    value = label_index(100) + tlv(UNKNOWN_TLV, b'\xde\xad\xbe\xef') + srgb([(4096, 100)])
    attr = decoded(attribute(value))
    # "propagated unmodified" is about the bytes, not about our idea of them
    assert bytes(attr.pack_attribute(Negotiated.UNSET)) == attribute(value)


# --------------------------------------------------------------------------------------
# 3.1 RESERVED and Flags MUST be ignored on reception


@pytest.mark.rfc('rfc8669#3.1-reserved-ignored-on-reception')
def test_a_label_index_with_a_zero_reserved_octet_decodes_to_its_index() -> None:
    attr = decoded(attribute(label_index(0x0001E240)))
    assert attr.sr_attrs[0].labelindex == 0x0001E240


@pytest.mark.rfc('rfc8669#3.1-reserved-ignored-on-reception', polarity='negative')
def test_a_non_zero_reserved_octet_neither_refuses_the_tlv_nor_changes_the_index() -> None:
    attr = decoded(attribute(label_index(0x0001E240, reserved=0xFF)))
    assert attr.sr_attrs[0].labelindex == 0x0001E240


@pytest.mark.rfc('rfc8669#3.1-flags-ignored-on-reception')
def test_a_label_index_with_zero_flags_decodes() -> None:
    assert decoded(attribute(label_index(7))).sr_attrs[0].labelindex == 7


@pytest.mark.rfc('rfc8669#3.1-flags-ignored-on-reception', polarity='negative')
def test_every_flag_bit_set_neither_refuses_the_tlv_nor_changes_the_index() -> None:
    attr = decoded(attribute(label_index(7, reserved=0xFF, flags=0xFFFF)))
    assert attr.sr_attrs[0].labelindex == 7


# --------------------------------------------------------------------------------------
# 3.1 the Label-Index TLV MUST be present on labelled unicast


@pytest.mark.rfc('rfc8669#3.1-label-index-must-be-present')
@pytest.mark.xfail(strict=True, reason='the attribute decoder never sees the AFI/SAFI, so it cannot apply this')
def test_a_prefix_sid_without_a_label_index_tlv_is_refused() -> None:
    collection = parse(attribute(srgb([(4096, 100)])))
    assert DISCARD in collection


@pytest.mark.rfc('rfc8669#3.1-label-index-must-be-present', polarity='negative')
def test_a_prefix_sid_with_a_label_index_tlv_is_accepted() -> None:
    attr = decoded(attribute(label_index(100) + srgb([(4096, 100)])))
    assert [each.TLV for each in attr.sr_attrs] == [LABEL_INDEX_TLV, ORIGINATOR_SRGB_TLV]


# --------------------------------------------------------------------------------------
# 3.2 Originator SRGB flags, and the TLV MUST NOT change while propagating


@pytest.mark.rfc('rfc8669#3.2-srgb-flags-ignored-on-reception')
def test_an_originator_srgb_decodes_its_ranges() -> None:
    attr = decoded(attribute(srgb([(4096, 100), (20000, 50)])))
    tlv_decoded = attr.sr_attrs[0]
    assert isinstance(tlv_decoded, SrGb)
    assert tlv_decoded.srgbs == [(4096, 100), (20000, 50)]


@pytest.mark.rfc('rfc8669#3.2-srgb-flags-ignored-on-reception', polarity='negative')
def test_non_zero_srgb_flags_do_not_shift_the_first_range() -> None:
    attr = decoded(attribute(srgb([(4096, 100)], flags=0xFFFF)))
    tlv_decoded = attr.sr_attrs[0]
    assert isinstance(tlv_decoded, SrGb)
    assert tlv_decoded.srgbs == [(4096, 100)]


@pytest.mark.rfc('rfc8669#3.2-srgb-not-changed-in-propagation')
def test_a_single_range_srgb_is_packed_back_as_it_arrived() -> None:
    wire = attribute(label_index(100) + srgb([(4096, 100)]))
    assert bytes(decoded(wire).pack_attribute(Negotiated.UNSET)) == wire


@pytest.mark.rfc('rfc8669#3.2-srgb-not-changed-in-propagation', polarity='negative')
def test_three_concatenated_srgb_ranges_keep_their_order_and_their_bytes() -> None:
    ranges = [(4096, 100), (16000, 8), (900000, 1)]
    wire = attribute(label_index(100) + srgb(ranges))
    attr = decoded(wire)
    tlv_decoded = attr.sr_attrs[1]
    assert isinstance(tlv_decoded, SrGb)
    # a decoder which sorted, merged or de-duplicated the ranges would still round-trip
    # the bytes, so check the ranges as well as the wire
    assert tlv_decoded.srgbs == ranges
    assert bytes(attr.pack_attribute(Negotiated.UNSET)) == wire


# --------------------------------------------------------------------------------------
# 4 EBGP outside the SR domain, and 4.1 "invalid" without a Label-Index


@pytest.mark.rfc('rfc8669#4-ebgp-outside-sr-domain-discard')
@pytest.mark.rfc('rfc8669#4-ebgp-outside-sr-domain-discard', polarity='negative')
def test_the_attribute_reaches_the_api_unfiltered_for_the_operator_to_judge() -> None:
    # exabgp has no SR domain boundary, so what it owes is that the operator can see
    # exactly what arrived and decide.  That is the json, and it must carry the value.
    attr = decoded(attribute(label_index(100)))
    assert attr.json() == '{ "sr-label-index": 100 }'


@pytest.mark.rfc('rfc8669#4.1-no-label-index-is-invalid')
@pytest.mark.xfail(strict=True, reason='an SRGB-only attribute decodes and is handed on as valid')
def test_a_prefix_sid_carrying_only_an_srgb_is_treated_as_invalid() -> None:
    assert DISCARD in parse(attribute(srgb([(4096, 100)])))


@pytest.mark.rfc('rfc8669#4.1-no-label-index-is-invalid', polarity='negative')
def test_a_prefix_sid_carrying_a_label_index_is_not_treated_as_invalid() -> None:
    collection = parse(attribute(label_index(100)))
    assert DISCARD not in collection
    assert PREFIX_SID in collection


# --------------------------------------------------------------------------------------
# 6 error handling: the three malformed shapes the section names


@pytest.mark.rfc('rfc8669#6-malformed-attribute-discard')
def test_a_tlv_length_outside_the_tlv_constraint_is_discarded_not_withdrawn() -> None:
    # section 3.1 fixes the Label-Index value at seven octets; six is well formed framing
    # carrying a TLV length the TLV does not allow
    collection = parse(attribute(tlv(LABEL_INDEX_TLV, b'\x00' * 6)))
    assert DISCARD in collection
    assert TREAT_AS_WITHDRAW not in collection


@pytest.mark.rfc('rfc8669#6-malformed-attribute-discard')
def test_a_tlv_running_past_the_end_of_the_attribute_is_discarded() -> None:
    overrun = bytes([LABEL_INDEX_TLV]) + pack('!H', 50) + b'\x00' * 7
    collection = parse(attribute(overrun))
    assert DISCARD in collection
    assert TREAT_AS_WITHDRAW not in collection


@pytest.mark.rfc('rfc8669#6-malformed-attribute-discard')
def test_an_srgb_which_is_not_two_plus_a_multiple_of_six_is_discarded() -> None:
    collection = parse(attribute(tlv(ORIGINATOR_SRGB_TLV, b'\x00' * 5)))
    assert DISCARD in collection
    assert TREAT_AS_WITHDRAW not in collection


@pytest.mark.rfc('rfc8669#6-malformed-attribute-discard')
def test_an_attribute_below_the_minimum_length_is_discarded_and_the_route_kept() -> None:
    collection = parse(attribute(b''))
    assert DISCARD in collection
    assert TREAT_AS_WITHDRAW not in collection


@pytest.mark.rfc('rfc8669#6-malformed-attribute-discard', polarity='negative')
def test_a_well_formed_prefix_sid_is_not_discarded() -> None:
    collection = parse(attribute(label_index(100) + srgb([(4096, 100)])))
    assert DISCARD not in collection
    assert TREAT_AS_WITHDRAW not in collection


# --------------------------------------------------------------------------------------
# 6 duplicates: of the attribute, and of a TLV within it


@pytest.mark.rfc('rfc8669#6-duplicate-attribute-first-wins')
def test_the_second_prefix_sid_attribute_is_dropped_and_the_first_kept() -> None:
    wire = attribute(label_index(100)) + attribute(label_index(999))
    assert decoded(wire).sr_attrs[0].labelindex == 100


@pytest.mark.rfc('rfc8669#6-duplicate-attribute-first-wins', polarity='negative')
def test_an_attribute_after_the_duplicate_is_still_decoded() -> None:
    # ORIGIN, well-known transitive, code 1, value IGP: the UPDATE must keep being read
    origin = bytes([0x40, 0x01, 0x01, 0x00])
    wire = attribute(label_index(100)) + attribute(label_index(999)) + origin
    collection = parse(wire)
    assert PREFIX_SID in collection
    assert int(Attribute.CODE.ORIGIN) in collection


@pytest.mark.rfc('rfc8669#6-duplicate-tlv-first-wins')
def test_a_repeated_label_index_tlv_keeps_only_the_first() -> None:
    attr = decoded(attribute(label_index(100) + label_index(999)))
    assert [each.TLV for each in attr.sr_attrs] == [LABEL_INDEX_TLV]
    # one key per object: two would leave the consumer's parser to pick a winner
    assert attr.json() == '{ "sr-label-index": 100 }'


@pytest.mark.rfc('rfc8669#6-duplicate-tlv-first-wins')
def test_a_discarded_repeat_is_not_advertised_onwards_but_its_neighbours_are() -> None:
    # section 6 grants propagation to unknown TLVs, not to a discarded repeat, so the
    # second Label-Index goes and the unknown TLV between them keeps its bytes
    unknown = tlv(UNKNOWN_TLV, b'\xde\xad\xbe\xef')
    wire = attribute(label_index(100) + unknown + label_index(999))
    attr = decoded(wire)
    assert bytes(attr.pack_attribute(Negotiated.UNSET)) == attribute(label_index(100) + unknown)


@pytest.mark.rfc('rfc8669#6-duplicate-tlv-first-wins')
def test_a_repeated_originator_srgb_keeps_only_the_first() -> None:
    attr = decoded(attribute(label_index(100) + srgb([(4096, 100)]) + srgb([(20000, 50)])))
    assert [each.TLV for each in attr.sr_attrs] == [LABEL_INDEX_TLV, ORIGINATOR_SRGB_TLV]
    first = attr.sr_attrs[1]
    assert isinstance(first, SrGb)
    assert first.srgbs == [(4096, 100)]


@pytest.mark.rfc('rfc8669#6-duplicate-tlv-first-wins')
def test_a_repeated_unknown_tlv_is_left_alone() -> None:
    # "unknown TLVs MUST be ignored and propagated unmodified" has no first-wins clause:
    # this implementation cannot know whether that type is allowed to repeat
    value = label_index(100) + tlv(UNKNOWN_TLV, b'\x01') + tlv(UNKNOWN_TLV, b'\x02')
    attr = decoded(attribute(value))
    assert [each.TLV for each in attr.sr_attrs] == [LABEL_INDEX_TLV, UNKNOWN_TLV, UNKNOWN_TLV]
    assert bytes(attr.pack_attribute(Negotiated.UNSET)) == attribute(value)
