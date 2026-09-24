"""RFC 4360, and what is not in it.

This file carries no `@pytest.mark.rfc()`, and that is the finding rather than an
oversight.  RFC 4360 has exactly five sentences with an RFC 2119 keyword in them: one
MUST NOT about best path selection, two MUST NOTs addressed to IANA about allocating
codepoints, two MAYs about propagating a received route, and a SHOULD/SHOULD NOT pair
about stripping non-transitive communities at an AS boundary.  Not one of them binds a
decoder, and exabgp has neither a decision process nor a propagation path for four of the
five to apply to.  qa/rfc/rfc4360.toml records all five, all as not-applicable or gap,
with the reason for each.

The rule this document is usually cited for is not in it.  Section 2 says "Each Extended
Community is encoded as an 8-octet quantity" flatly, with no keyword, exactly as RFC 1997
states the four octet one.  The normative form is RFC 7606 section 7.14 for the IPv4
attribute and 7.15 for the IPv6 one, which live in qa/rfc/rfc7606.toml.

So the tests below are ordinary regression tests for the decoder, held here because this
is where a reader looking for RFC 4360 coverage will come.  They cover the two things
which would hurt: a length which is not a whole number of communities, and the eager walk
in `from_packet` which decodes each community at the boundary rather than lazily in the
API writer, where a Notify becomes a silently dropped session instead of a NOTIFICATION.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community import ExtendedCommunities, ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunitiesIPv6

from rfc.community_wire import parse, withdrawn

EXTENDED_COMMUNITY = int(Attribute.CODE.EXTENDED_COMMUNITY)
IPV6_EXTENDED_COMMUNITY = int(Attribute.CODE.IPV6_EXTENDED_COMMUNITY)

EXTENDED_COMMUNITY_SIZE_BYTES = 8
EXTENDED_COMMUNITY_IPV6_SIZE_BYTES = 20

# A two-octet AS specific Route Target, RFC 4360 sections 3.1 and 4: high-order octet
# 0x00, sub-type 0x02, then AS 64496 and a local administrator of 1.
ROUTE_TARGET = bytes([0x00, 0x02]) + (64496).to_bytes(2, 'big') + (1).to_bytes(4, 'big')
# The same community with the T bit set, which RFC 4360 section 2 defines as
# non-transitive across ASes.
ROUTE_TARGET_NON_TRANSITIVE = bytes([0x40, 0x02]) + ROUTE_TARGET[2:]


@pytest.mark.parametrize('count', [1, 2, 8])
def test_a_whole_number_of_extended_communities_is_accepted(count: int) -> None:
    collection = parse(EXTENDED_COMMUNITY, ROUTE_TARGET * count)

    assert not withdrawn(collection), f'{count} extended communities were refused'
    decoded = collection[Attribute.CODE.EXTENDED_COMMUNITY]
    assert isinstance(decoded, ExtendedCommunities)
    assert len(decoded.communities) == count


@pytest.mark.parametrize('length', [0, 1, 7, 9, 15, 17])
def test_a_length_which_is_not_a_whole_number_of_extended_communities_withdraws_the_route(length: int) -> None:
    """Treat-as-withdraw, from `TREAT_AS_WITHDRAW` on `ExtendedCommunitiesBase`.

    The flag is on the base class rather than on each of the two subclasses, so the IPv6
    attribute inherits it and a third family added later would too.  Zero length is
    refused elsewhere again, by `VALID_ZERO`, because 0 % 8 == 0 would otherwise pass.
    """
    assert withdrawn(parse(EXTENDED_COMMUNITY, bytes(length))), f'{length} bytes were accepted'


@pytest.mark.parametrize('length', [1, 7, 9, 15, 17])
def test_the_decoder_itself_refuses_a_bad_length(length: int) -> None:
    with pytest.raises(Notify):
        ExtendedCommunities.from_packet(bytes(length))


@pytest.mark.parametrize('length', [0, 1, 19, 21, 39])
def test_an_ipv6_extended_community_of_the_wrong_length_withdraws_the_route(length: int) -> None:
    """RFC 5701's 20 octet form, which shares this decoder and this failure mode."""
    assert withdrawn(parse(IPV6_EXTENDED_COMMUNITY, bytes(length))), f'{length} bytes were accepted'


def test_a_whole_number_of_ipv6_extended_communities_is_accepted() -> None:
    value = bytes(2 * EXTENDED_COMMUNITY_IPV6_SIZE_BYTES)
    collection = parse(IPV6_EXTENDED_COMMUNITY, value)

    assert not withdrawn(collection)
    decoded = collection[Attribute.CODE.IPV6_EXTENDED_COMMUNITY]
    assert isinstance(decoded, ExtendedCommunitiesIPv6)
    assert len(decoded.communities) == 2


def test_the_transitive_bit_is_read_from_the_high_order_octet() -> None:
    """RFC 4360 section 2: T set means non-transitive across ASes.

    Stated without a keyword, so it is not in the ledger, but getting the sense of this
    bit backwards would invert the meaning of every community which sets it.
    """
    assert ExtendedCommunity(ROUTE_TARGET).transitive()
    assert not ExtendedCommunity(ROUTE_TARGET_NON_TRANSITIVE).transitive()


def test_two_extended_communities_are_equal_only_when_all_eight_octets_are() -> None:
    """Also keywordless in section 2, and also worth pinning.

    The T bit is part of the eight octets, so the transitive and non-transitive forms of
    one Route Target are two communities, not one seen twice.
    """
    assert ExtendedCommunity(ROUTE_TARGET) == ExtendedCommunity(ROUTE_TARGET)
    assert ExtendedCommunity(ROUTE_TARGET) != ExtendedCommunity(ROUTE_TARGET_NON_TRANSITIVE)


def test_a_registered_type_and_subtype_reaches_its_own_class() -> None:
    """Section 3's "templates": the high-order octet picks the family, the low one the type.

    `ExtendedCommunityBase.unpack_attribute` masks the high-order octet with 0x0F before
    looking the pair up, so the IANA bit and the T bit do not change which class decodes
    the community.  A Route Target is therefore the same class transitive or not.
    """
    transitive = ExtendedCommunities.from_packet(ROUTE_TARGET).communities[0]
    non_transitive = ExtendedCommunities.from_packet(ROUTE_TARGET_NON_TRANSITIVE).communities[0]

    assert type(transitive) is type(non_transitive)
    assert type(transitive) is not ExtendedCommunity, 'the Route Target fell through to the generic class'
