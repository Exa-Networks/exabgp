"""RFC 8669 section 6 on a TLV which appears more than once in one Prefix-SID.

    "if a recognized TLV appears more than once in a BGP Prefix-SID attribute
    while the specification only allows for a single occurrence, then all the
    occurrences of the TLV other than the first one SHALL be discarded"

Sections 3.1 and 3.2 give the attribute one Label-Index and one Originator SRGB, and the
document defines no TLV which may repeat, so those two are the whole list.  An unknown
type is deliberately not on it: the same section promises unknown TLVs are "propagated
unmodified", so a repeat of one is kept.

Discarded means gone from both sides, the decoded TLVs and the bytes we re-advertise.
The decoder used to keep every occurrence, so `json()` emitted `"sr-label-index"` twice
inside one object, which is the shape that makes a consumer's parser silently pick one of
the two, and `pack()` handed the repeat onwards.

The attribute is rebuilt from the peer's own per-TLV slices rather than from the decoded
TLVs, so the only difference between what arrived and what leaves is the repeat: a TLV we
do not know cannot be re-encoded from its decoded form at all, and one we do know would
be re-encoded into our framing rather than the peer's.
"""

from __future__ import annotations

import json

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid

# a Label-Index TLV (type 1, RFC 8669 3.1): one reserved octet, two flag octets, four of index
LABEL_INDEX_100 = bytes.fromhex('01' '0007' '00' '0000' '00000064')
LABEL_INDEX_200 = bytes.fromhex('01' '0007' '00' '0000' '000000c8')

# an Originator SRGB TLV (type 3, RFC 8669 3.2): two flag octets, then six octet ranges
SRGB_FIRST = bytes.fromhex('03' '0008' '0000' '000064' '00000a')
SRGB_SECOND = bytes.fromhex('03' '0008' '0000' '0000c8' '00000a')

# a type this branch registers no decoder for, so section 6 propagates it unmodified
UNKNOWN_TLV = bytes.fromhex('7f' '0002' 'abcd')


def decode(value: bytes) -> PrefixSid:
    return PrefixSid.unpack(value, Direction.IN, None)


def test_a_repeated_label_index_keeps_only_the_first() -> None:
    parsed = decode(LABEL_INDEX_100 + LABEL_INDEX_200)

    label_indices = [tlv for tlv in parsed.sr_attrs if tlv.TLV == 1]
    assert len(label_indices) == 1, 'RFC 8669 section 6 discards every Label-Index but the first'
    assert label_indices[0].labelindex == 100, 'the first occurrence is the one which is kept'


def test_a_repeated_label_index_is_not_re_advertised() -> None:
    """Discarded means gone from the bytes we pass on, not merely from what we parsed."""
    parsed = decode(LABEL_INDEX_100 + LABEL_INDEX_200)

    assert LABEL_INDEX_200 not in parsed.pack(), 'the discarded repeat was advertised onwards'
    assert LABEL_INDEX_100 in parsed.pack(), 'the occurrence which is kept must arrive byte-identical'


def test_a_repeated_label_index_leaves_one_key_in_the_json() -> None:
    """Two `sr-label-index` keys in one object is what makes a consumer pick one in silence."""
    rendered = decode(LABEL_INDEX_100 + LABEL_INDEX_200).json()

    assert rendered.count('"sr-label-index"') == 1, 'the repeat reached the API as a duplicate key'
    assert json.loads(rendered)['sr-label-index'] == 100


def test_a_repeated_srgb_gets_the_same_answer() -> None:
    """Section 3.2 allows one Originator SRGB, so the rule is the same as for 3.1."""
    parsed = decode(SRGB_FIRST + SRGB_SECOND)

    assert len([tlv for tlv in parsed.sr_attrs if tlv.TLV == 3]) == 1
    assert SRGB_SECOND not in parsed.pack()


def test_a_repeated_unknown_tlv_is_left_alone() -> None:
    """Section 6 promises unknown TLVs are propagated unmodified, repeat included."""
    parsed = decode(UNKNOWN_TLV + UNKNOWN_TLV)

    assert len(parsed.sr_attrs) == 2, 'an unknown TLV is not one the specification limits to one'
    assert parsed.pack().count(UNKNOWN_TLV) == 2


def test_two_different_tlvs_are_not_a_repeat() -> None:
    """The control: the rule is per type, so a Label-Index beside an SRGB is untouched."""
    parsed = decode(LABEL_INDEX_100 + SRGB_FIRST)

    assert len(parsed.sr_attrs) == 2
    # pack() wraps the value in the attribute header, so the value is what is compared
    assert parsed.pack().endswith(LABEL_INDEX_100 + SRGB_FIRST), 'a sound attribute must be passed on unchanged'
