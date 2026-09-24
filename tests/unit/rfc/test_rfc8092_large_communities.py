"""RFC 8092: the only one of the three community RFCs which states its own length rule.

RFC 1997 and RFC 4360 describe their fixed width encoding in plain declarative prose and
leave the malformed case to RFC 7606.  RFC 8092 section 6 writes it out itself, with a
keyword, and adds three more sentences around it which are easy to get backwards:

  - not a non-zero multiple of 12 is malformed.  The "non-zero" is load bearing and is
    enforced somewhere else entirely, by `VALID_ZERO` on the class rather than by the
    decoder, so it is the half a refactor loses.
  - duplicate values are NOT malformed, and are removed silently.  A decoder which
    rejected them would be wrong in the other direction.
  - an unallocated or reserved ASN in the Global Administrator field is NOT malformed,
    which is why section 3's SHOULD that the field be an ASN is not enforced anywhere.
  - and a malformed attribute is treat-as-withdraw, not a session reset.

Every negative test here checks a boundary rather than a happy path, because these four
sentences are a set of tolerances and a decoder can fail them by being too strict just as
easily as by being too lax.
"""

from __future__ import annotations

import re
from struct import pack

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community import LargeCommunities, LargeCommunity
from exabgp.configuration.static.parser import _large_community

from rfc.community_wire import parse, withdrawn

LARGE_COMMUNITY = int(Attribute.CODE.LARGE_COMMUNITY)
LARGE_COMMUNITY_SIZE_BYTES = 12

FIRST = pack('!LLL', 64496, 1, 2)
SECOND = pack('!LLL', 64497, 3, 4)
THIRD = pack('!LLL', 64498, 5, 6)

# RFC 8092 section 3 names these three as Reserved, and section 6 says in as many words
# that finding one here does not make the attribute malformed.
RESERVED_ASNS = [0, 65535, 4294967295]
# 65550 is inside the 64512-65534 private range's neighbourhood but is not assigned to
# anyone; it stands in for "unallocated" as distinct from "reserved".
UNALLOCATED_ASN = 65550

# The canonical representation of section 5: three decimal integers, single colons, and
# no leading zero on any of them.
CANONICAL = re.compile(r'^(0|[1-9][0-9]*):(0|[1-9][0-9]*):(0|[1-9][0-9]*)$')

# Values chosen to break a formatter which pads, groups or aligns.
ADVERSARIAL = [
    (0, 0, 0),
    (64496, 0, 0),
    (64496, 4294967295, 2),
    (4294967295, 4294967295, 4294967295),
    (1, 10, 100),
]


def value_of(attribute: LargeCommunities) -> bytes:
    """The attribute value as it would go on the wire, without its header."""
    packed = bytes(attribute.pack_attribute(Negotiated.UNSET))
    # optional transitive, type code, one length byte, then the value
    return packed[3:]


# ============================================================ section 3, duplicates


@pytest.mark.rfc('rfc8092#3-no-duplicate-transmitted')
def test_building_an_attribute_from_duplicates_transmits_one_of_each() -> None:
    built = LargeCommunities.make_large_communities(
        [LargeCommunity(FIRST), LargeCommunity(SECOND), LargeCommunity(FIRST)]
    )

    assert len(value_of(built)) == 2 * LARGE_COMMUNITY_SIZE_BYTES


@pytest.mark.rfc('rfc8092#3-no-duplicate-transmitted')
def test_adding_a_community_twice_transmits_it_once() -> None:
    built = LargeCommunities().add(LargeCommunity(FIRST)).add(LargeCommunity(FIRST))

    assert len(value_of(built)) == LARGE_COMMUNITY_SIZE_BYTES


@pytest.mark.rfc('rfc8092#3-no-duplicate-transmitted', polarity='negative')
def test_a_duplicate_which_arrived_from_a_peer_does_not_go_back_out() -> None:
    """The half which reaches the wire.

    A receiver which deduplicated only its own `communities` view and re-packed the bytes
    it was handed would satisfy every test above and still transmit the duplicate.
    """
    received = LargeCommunities.from_packet(FIRST + SECOND + FIRST)

    assert value_of(received) == FIRST + SECOND


# ============================================================ section 3, removal


@pytest.mark.rfc('rfc8092#3-receiver-removes-redundant')
def test_a_received_duplicate_is_removed() -> None:
    received = LargeCommunities.from_packet(FIRST + FIRST + FIRST)

    assert [bytes(c.large_community) for c in received.communities] == [FIRST]


@pytest.mark.rfc('rfc8092#3-receiver-removes-redundant', polarity='negative')
def test_distinct_communities_all_survive_in_the_order_they_arrived() -> None:
    """Removing too much is the other way to fail this sentence.

    "Redundant" means byte for byte identical.  Three communities which share a Global
    Administrator, or which differ only in the last octet, are three communities.
    """
    near_miss = pack('!LLL', 64496, 1, 3)
    received = LargeCommunities.from_packet(FIRST + near_miss + SECOND + THIRD)

    assert [bytes(c.large_community) for c in received.communities] == [FIRST, near_miss, SECOND, THIRD]


# ============================================================ section 5, canonical form


@pytest.mark.rfc('rfc8092#5-canonical-no-leading-zeros')
@pytest.mark.parametrize('parts', ADVERSARIAL, ids=[':'.join(str(p) for p in v) for v in ADVERSARIAL])
def test_no_number_is_rendered_with_a_leading_zero(parts: tuple[int, int, int]) -> None:
    rendered = repr(LargeCommunity(pack('!LLL', *parts)))

    assert CANONICAL.match(rendered), f'{rendered!r} is not three bare decimal integers'


@pytest.mark.rfc('rfc8092#5-canonical-no-leading-zeros', polarity='negative')
def test_a_zero_field_is_one_zero_and_not_a_run_of_them() -> None:
    """The sentence's second half, and the one a width-aligned format string breaks.

    '%012d' would render 64496:0:0 as a column of zeros which is still parseable by
    anything reading integers, so nothing downstream would notice.
    """
    assert repr(LargeCommunity(pack('!LLL', 64496, 0, 0))) == '64496:0:0'
    assert repr(LargeCommunity(pack('!LLL', 0, 0, 0))) == '0:0:0'


@pytest.mark.rfc('rfc8092#5-canonical-representation')
def test_the_rfcs_own_examples_render_exactly_as_the_rfc_writes_them() -> None:
    assert repr(LargeCommunity(pack('!LLL', 64496, 4294967295, 2))) == '64496:4294967295:2'
    assert repr(LargeCommunity(pack('!LLL', 64496, 0, 0))) == '64496:0:0'


@pytest.mark.rfc('rfc8092#5-canonical-representation', polarity='negative')
@pytest.mark.parametrize('parts', ADVERSARIAL, ids=[':'.join(str(p) for p in v) for v in ADVERSARIAL])
def test_what_we_print_parses_back_to_the_bytes_we_printed_it_from(parts: tuple[int, int, int]) -> None:
    """A representation which is not the canonical one is a representation we cannot read.

    exabgp is on both ends of this: `repr` writes the string an operator copies out of a
    log, and `_large_community` is what parses it back when they paste it into a
    configuration.  A non-canonical rendering breaks that loop silently.
    """
    packed = pack('!LLL', *parts)

    assert bytes(_large_community(repr(LargeCommunity(packed))).large_community) == packed


# ============================================================ section 6, error handling


@pytest.mark.rfc('rfc8092#6-malformed-if-not-nonzero-multiple-of-12')
@pytest.mark.parametrize('count', [1, 2, 10])
def test_a_non_zero_multiple_of_twelve_is_well_formed(count: int) -> None:
    collection = parse(LARGE_COMMUNITY, bytes(count * LARGE_COMMUNITY_SIZE_BYTES))

    assert not withdrawn(collection), f'{count} large communities were refused'
    assert isinstance(collection[Attribute.CODE.LARGE_COMMUNITY], LargeCommunities)


@pytest.mark.rfc('rfc8092#6-malformed-if-not-nonzero-multiple-of-12', polarity='negative')
@pytest.mark.parametrize('length', [0, 1, 11, 13, 23, 25])
def test_a_length_which_is_not_a_non_zero_multiple_of_twelve_is_malformed(length: int) -> None:
    """Zero is in the list because it is checked in a different file from the others.

    `LargeCommunities.from_packet` never sees an empty value: 0 % 12 == 0, so it would
    accept one.  What refuses it is `VALID_ZERO` being false on the class, which
    `AttributeCollection.parse` checks before calling the decoder at all.  Two places,
    one sentence.
    """
    assert withdrawn(parse(LARGE_COMMUNITY, bytes(length))), f'{length} bytes were accepted'


@pytest.mark.rfc('rfc8092#6-malformed-if-not-nonzero-multiple-of-12', polarity='negative')
@pytest.mark.parametrize('length', [1, 11, 13, 23, 25])
def test_the_decoder_itself_refuses_a_bad_length(length: int) -> None:
    """Under the treat-as-withdraw there has to be a decoder which actually said no."""
    with pytest.raises(Notify):
        LargeCommunities.from_packet(bytes(length))


@pytest.mark.rfc('rfc8092#6-duplicates-not-malformed')
def test_an_attribute_full_of_duplicates_is_not_malformed() -> None:
    collection = parse(LARGE_COMMUNITY, FIRST + FIRST + FIRST)

    assert not withdrawn(collection), 'duplicate large communities were treated as malformed'
    decoded = collection[Attribute.CODE.LARGE_COMMUNITY]
    assert isinstance(decoded, LargeCommunities)
    assert len(decoded.communities) == 1


@pytest.mark.rfc('rfc8092#6-duplicates-not-malformed', polarity='negative')
def test_duplicates_do_not_excuse_a_bad_length() -> None:
    """The tolerance is about duplication only, and does not extend to the framing."""
    assert withdrawn(parse(LARGE_COMMUNITY, FIRST + FIRST + b'\x00')), 'a 25 byte value was accepted'


@pytest.mark.rfc('rfc8092#6-treat-as-withdraw')
@pytest.mark.parametrize('length', [1, 13, 25])
def test_a_malformed_attribute_withdraws_the_route_instead_of_dropping_the_session(length: int) -> None:
    """The Notify must not escape the attribute parser.

    `pytest.raises` is not what proves this; the absence of an exception is.  If
    `TREAT_AS_WITHDRAW` were taken off `LargeCommunities` the Notify from `from_packet`
    would leave `AttributeCollection.parse`, reach the reactor, and close the adjacency
    over one badly encoded optional transitive attribute.
    """
    collection = parse(LARGE_COMMUNITY, bytes(length))

    assert withdrawn(collection)
    assert Attribute.CODE.LARGE_COMMUNITY not in collection, 'a malformed attribute was also kept'


@pytest.mark.rfc('rfc8092#6-treat-as-withdraw', polarity='negative')
def test_a_well_formed_attribute_does_not_withdraw_the_route() -> None:
    """Treat-as-withdraw has to be a decision, not the default.

    A parser which marked every UPDATE carrying large communities as withdrawn would
    pass every positive test above and lose every route which carries one.
    """
    collection = parse(LARGE_COMMUNITY, FIRST + SECOND)

    assert not withdrawn(collection)
    assert repr(collection[Attribute.CODE.LARGE_COMMUNITY]) == '[ 64496:1:2 64497:3:4 ]'


@pytest.mark.rfc('rfc8092#6-unallocated-global-administrator-not-malformed')
@pytest.mark.parametrize('asn', RESERVED_ASNS + [UNALLOCATED_ASN])
def test_a_reserved_or_unallocated_global_administrator_is_accepted(asn: int) -> None:
    """Section 3 says the field SHOULD be an ASN and reserved ones are NOT RECOMMENDED.

    Section 6 then forbids turning either of those into an error, which is why neither is
    enforced anywhere in the tree.  Any code added to check this field would have to fail
    this test to do its job.
    """
    collection = parse(LARGE_COMMUNITY, pack('!LLL', asn, 1, 2))

    assert not withdrawn(collection), f'AS {asn} in the Global Administrator field was refused'
    assert repr(collection[Attribute.CODE.LARGE_COMMUNITY]) == f'{asn}:1:2'


@pytest.mark.rfc('rfc8092#6-unallocated-global-administrator-not-malformed', polarity='negative')
def test_a_reserved_global_administrator_does_not_excuse_a_bad_length() -> None:
    """The tolerance is a rule about one field, not a blanket over the attribute."""
    assert withdrawn(parse(LARGE_COMMUNITY, pack('!LLL', 0, 1, 2) + b'\x00')), 'a 13 byte value was accepted'
