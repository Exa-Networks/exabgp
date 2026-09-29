"""RFC 4360, and what is not in it.

This file carries one `@pytest.mark.rfc()`, and the scarcity is the finding rather than an
oversight.  RFC 4360 has exactly five sentences with an RFC 2119
keyword in them: one MUST NOT about best path selection, two MUST NOTs addressed to IANA about allocating
codepoints, two MAYs about propagating a received route, and a SHOULD/SHOULD NOT pair
about stripping non-transitive communities at an AS boundary.  Not one of them binds a
decoder, and exabgp has neither a decision process nor a propagation path for four of the
five to apply to.  qa/rfc/rfc4360.toml records all five, with the reason for each.

The rule this document is usually cited for is not in it.  Section 2 says "Each Extended
Community is encoded as an 8-octet quantity" flatly, with no keyword, exactly as RFC 1997
states the four octet one.  The normative form is RFC 7606 section 7.14 for the IPv4
attribute and 7.15 for the IPv6 one, which live in qa/rfc/rfc7606.toml.

The one marker is on the SHOULD at the AS boundary.  A route received from a peer and
handed to another neighbour loses its non-transitive communities when that neighbour is in
another AS, and keeps them inside the AS and the confederation.  A route we originate is
left alone: a non-transitive community an operator configures, link bandwidth being the
usual one, is meant for the EBGP neighbour it is sent to.

Otherwise the tests below are ordinary regression tests for the decoder, held here
because this is where a reader looking for RFC 4360 coverage will come.  They cover the two things
which would hurt: a length which is not a whole number of communities, and the eager walk
in `from_packet` which decodes each community at the boundary rather than lazily in the
API writer, where a Notify becomes a silently dropped session instead of a NOTIFICATION.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community import ExtendedCommunities, ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunitiesIPv6

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.protocol.ip import IP

from rfc import rfc7606_wire
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


# ------------------------------------------------ 6 the T bit at the AS boundary

CONFEDERATION_IDENTIFIER = 65000
OTHER_MEMBER = 65002
LEARNED_FROM = '192.0.2.1'


def extended_communities_sent(negotiated: Negotiated, received: bool = True) -> list[bytes]:
    """The extended communities a peer decodes from a route carrying both Route Targets.

    `received` decodes the route off an EBGP session first, as a route re-advertised would
    be; otherwise it is built the way the configuration builds one, originated by us.
    """
    attributes = AttributeCollection()
    attributes.add(ExtendedCommunities.from_packet(ROUTE_TARGET + ROUTE_TARGET_NON_TRANSITIVE))
    if received:
        source = rfc7606_wire.session()
        source.neighbor.session.peer_address = IP.from_string(LEARNED_FROM)
        attributes = AttributeCollection.unpack(attributes.pack_attribute(source), source)
        assert attributes.learned_from == LEARNED_FROM, 'the decoded route did not record its peer'
    sent = AttributeCollection.unpack(attributes.pack_attribute(negotiated), rfc7606_wire.session())
    decoded = sent.get(Attribute.CODE.EXTENDED_COMMUNITY)
    if decoded is None:
        return []
    assert isinstance(decoded, ExtendedCommunities)
    return [bytes(community.pack_attribute(Negotiated.UNSET)) for community in decoded.communities]


def confederation_member_session() -> Negotiated:
    """An EBGP session to another Member-AS of our confederation, as RFC 5065 configures it."""
    negotiated = rfc7606_wire.session(peer_as=OTHER_MEMBER)
    configured = negotiated.neighbor.session
    configured.local_as = ASN(rfc7606_wire.LOCAL_AS)
    configured.peer_as = ASN(OTHER_MEMBER)
    configured.confederation = ASN(CONFEDERATION_IDENTIFIER)
    configured.confederation_members = (ASN(OTHER_MEMBER),)
    return negotiated


@pytest.mark.rfc('rfc4360#6-non-transitive-removed-across-as-boundary')
def test_a_non_transitive_extended_community_is_not_sent_to_another_as() -> None:
    """The T bit set means the community stops at the edge of our AS.

    The route goes out, and so does its transitive Route Target: it is only the
    non-transitive one which is removed before the route crosses into the peer's AS.
    """
    sent = extended_communities_sent(rfc7606_wire.session())

    assert sent == [ROUTE_TARGET], [community.hex() for community in sent]


@pytest.mark.parametrize(
    'negotiated',
    [rfc7606_wire.internal_session, confederation_member_session],
    ids=['ibgp', 'confederation-member'],
)
@pytest.mark.rfc('rfc4360#6-non-transitive-removed-across-as-boundary')
def test_a_non_transitive_extended_community_is_kept_inside_the_as_and_the_confederation(
    negotiated: Callable[[], Negotiated],
) -> None:
    """The other half of the test above.

    Stripping every non-transitive community on every session would pass the test
    above, so this pins what must survive it: the SHOULD NOT for the confederation
    boundary, and IBGP, which is no boundary at all.
    """
    sent = extended_communities_sent(negotiated())

    assert sorted(sent) == sorted([ROUTE_TARGET, ROUTE_TARGET_NON_TRANSITIVE]), [community.hex() for community in sent]


def test_a_non_transitive_extended_community_we_originate_goes_to_another_as() -> None:
    """Unmarked: the SHOULD is about re-advertising, and this route was configured.

    Link bandwidth is non-transitive and made for the EBGP link it is sent over; an
    operator configuring it on a route towards an EBGP neighbour means it to arrive.
    """
    sent = extended_communities_sent(rfc7606_wire.session(), received=False)

    assert sorted(sent) == sorted([ROUTE_TARGET, ROUTE_TARGET_NON_TRANSITIVE]), [community.hex() for community in sent]
