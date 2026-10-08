"""draft-ietf-idr-linklocal-capability-06: which IPv6 next hop a session can carry.

Section 2 makes every procedure of the draft depend on the capability being negotiated,
not on our configuration enabling it.  A link-local next hop which the session can not
carry, the capability not negotiated or the peer further than one hop, raised RuntimeError
out of the encoder: the session reset, came back with the route still in the RIB, and
reset again.  Such a route is now withheld, and the configuration refuses a link-local
next hop for a multihop neighbour.

RFC 2545 3 gives the link-local address "of the next hop": ours was appended to every
global next hop, a third party's too.  It is now only appended to our own address.

Section 5 has an IPv4 route with a link-local only next hop sent as 32 octets unless both
this capability and RFC 8950's were negotiated: it went out as 16 in every case.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.collection import RoutedNLRI, UpdateCollection
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.collection import MPNLRICollection
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier.labels import Labels
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.protocol.ip import IP, IPv6
from exabgp.util.enumeration import TriState
from tests import negotiation


IPV4_UNICAST: FamilyTuple = (AFI.ipv4, SAFI.unicast)
IPV4_VPN: FamilyTuple = (AFI.ipv4, SAFI.mpls_vpn)
IPV6_UNICAST: FamilyTuple = (AFI.ipv6, SAFI.unicast)
EXTENDED = [(AFI.ipv4, SAFI.unicast, AFI.ipv6), (AFI.ipv4, SAFI.mpls_vpn, AFI.ipv6)]

OURS = '2001:db8::1'
THIRD_PARTY = '2001:db8::99'
OUR_LINK_LOCAL = 'fe80::1'
LINK_LOCAL_NEXT_HOP = 'fe80::2'
RD_ZERO = bytes(8)


def session(*, linklocal: bool, multihop: bool = False, extended: bool = True) -> Negotiated:
    """A session whose local address is OURS and whose local-link-local is OUR_LINK_LOCAL."""
    configured = negotiation.neighbor()
    configured.session.local_address = IP.from_string(OURS)
    configured.session.local_link_local = IP.from_string(OUR_LINK_LOCAL)
    configured.session.outgoing_ttl = 5 if multihop else None
    configured.capability.link_local_nexthop = TriState.TRUE
    families = [IPV4_UNICAST, IPV4_VPN, IPV6_UNICAST]
    return negotiation.negotiated(
        families,
        linklocal_nexthop=linklocal,
        nexthop=EXTENDED if extended else [],
        session=configured,
    )


def v6_route() -> INET:
    return INET.from_cidr(CIDR.create_cidr(IP.pton('2001:db8:100::'), 48), AFI.ipv6, SAFI.unicast)


def v4_route() -> INET:
    return INET.from_cidr(CIDR.create_cidr(IP.pton('10.0.0.0'), 24), AFI.ipv4, SAFI.unicast)


def v4_vpn_route() -> IPVPN:
    rd = RouteDistinguisher.make_from_elements('65000', 1)
    cidr = CIDR.create_cidr(IP.pton('10.0.0.0'), 24)
    return IPVPN.from_cidr(cidr, AFI.ipv4, labels=Labels.make_labels([100]), rd=rd)


def sent_next_hops(nlri: NLRI, next_hop: str, negotiated: Negotiated) -> list[bytes]:
    """The Next Hop field of every MP_REACH_NLRI the encoder produces for this one route."""
    afi, safi = nlri.family().afi_safi()
    collection = MPNLRICollection.from_routed([RoutedNLRI(nlri, IP.from_string(next_hop))], {}, afi, safi)
    fields = []
    for attribute in collection.packed_reach_attributes(negotiated):
        header = 4 if attribute[0] & 0x10 else 3
        length = attribute[header + 3]
        fields.append(bytes(attribute[header + 4 : header + 4 + length]))
    return fields


def packed(address: str) -> bytes:
    return bytes(IPv6.pton(address))


# ------------------------------------------------------------- withheld, not reset


@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#4-no-next-hop-not-advertised', polarity='negative')
@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#4-internal-no-next-hop-not-announced', polarity='negative')
@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#4-external-no-next-hop-not-announced', polarity='negative')
def test_a_link_local_next_hop_is_withheld_when_the_peer_did_not_negotiate_the_capability() -> None:
    # our configuration enables it, the peer's OPEN did not carry code 77
    negotiated = session(linklocal=False)
    assert sent_next_hops(v6_route(), LINK_LOCAL_NEXT_HOP, negotiated) == []


@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#4-internal-multihop-no-link-local', polarity='negative')
@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#4-multihop-external-no-link-local', polarity='negative')
@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#4-multihop-external-needs-global', polarity='negative')
def test_a_link_local_next_hop_is_withheld_from_a_multihop_peer() -> None:
    negotiated = session(linklocal=True, multihop=True)
    assert sent_next_hops(v6_route(), LINK_LOCAL_NEXT_HOP, negotiated) == []


@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#4-no-next-hop-not-advertised')
@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#4-internal-no-next-hop-not-announced')
@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#4-external-no-next-hop-not-announced')
@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#3-link-local-only-is-sixteen-octets')
def test_a_link_local_next_hop_is_sent_alone_once_negotiated_to_a_peer_one_hop_away() -> None:
    negotiated = session(linklocal=True)
    assert sent_next_hops(v6_route(), LINK_LOCAL_NEXT_HOP, negotiated) == [packed(LINK_LOCAL_NEXT_HOP)]


def test_the_rest_of_the_update_still_goes_out_when_a_route_is_withheld() -> None:
    negotiated = session(linklocal=False)
    routed = [
        RoutedNLRI(v6_route(), IP.from_string(LINK_LOCAL_NEXT_HOP)),
        RoutedNLRI(
            INET.from_cidr(CIDR.create_cidr(IP.pton('2001:db8:200::'), 48), AFI.ipv6, SAFI.unicast),
            IP.from_string(OURS),
        ),
    ]
    messages = list(UpdateCollection(routed, [], AttributeCollection()).messages(negotiated))
    assert len(messages) == 1
    assert packed(OURS) in messages[0]
    assert packed(LINK_LOCAL_NEXT_HOP) not in messages[0]


# ------------------------------------------------------------ our link-local address


@pytest.mark.rfc('rfc2545#3-link-local-if-and-only-if-common-subnet')
@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#4-own-link-local-included')
@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#3-global-and-link-local-is-thirty-two-octets')
def test_our_link_local_address_follows_our_own_global_next_hop() -> None:
    negotiated = session(linklocal=True)
    assert sent_next_hops(v6_route(), OURS, negotiated) == [packed(OURS) + packed(OUR_LINK_LOCAL)]


@pytest.mark.rfc('rfc2545#3-link-local-if-and-only-if-common-subnet', polarity='negative')
@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#4-own-link-local-included', polarity='negative')
def test_our_link_local_address_is_not_given_to_a_third_party_next_hop() -> None:
    negotiated = session(linklocal=True)
    assert sent_next_hops(v6_route(), THIRD_PARTY, negotiated) == [packed(THIRD_PARTY)]


@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#4-internal-multihop-no-link-local')
@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#4-multihop-external-no-link-local')
@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#4-multihop-external-needs-global')
def test_our_link_local_address_is_not_sent_to_a_multihop_peer() -> None:
    negotiated = session(linklocal=True, multihop=True)
    assert sent_next_hops(v6_route(), OURS, negotiated) == [packed(OURS)]


def test_our_link_local_address_is_not_sent_without_the_capability() -> None:
    negotiated = session(linklocal=False)
    assert sent_next_hops(v6_route(), OURS, negotiated) == [packed(OURS)]


# ------------------------------------------------------------- RFC 8950, section 5


@pytest.mark.rfc(
    'draft-ietf-idr-linklocal-capability-06#5-thirty-two-octets-without-the-combination', polarity='negative'
)
def test_an_ipv4_route_with_a_link_local_next_hop_is_sixteen_octets_with_both_capabilities() -> None:
    negotiated = session(linklocal=True)
    assert sent_next_hops(v4_route(), LINK_LOCAL_NEXT_HOP, negotiated) == [packed(LINK_LOCAL_NEXT_HOP)]


@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#5-thirty-two-octets-without-the-combination')
def test_an_ipv4_route_with_a_link_local_next_hop_is_thirty_two_octets_without_the_combination() -> None:
    negotiated = session(linklocal=False)
    pair = bytes(16) + packed(LINK_LOCAL_NEXT_HOP)
    assert sent_next_hops(v4_route(), LINK_LOCAL_NEXT_HOP, negotiated) == [pair]
    vpn_pair = RD_ZERO + bytes(16) + RD_ZERO + packed(LINK_LOCAL_NEXT_HOP)
    assert sent_next_hops(v4_vpn_route(), LINK_LOCAL_NEXT_HOP, negotiated) == [vpn_pair]


@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#4-multihop-external-no-link-local', polarity='negative')
def test_an_ipv4_route_with_a_link_local_next_hop_is_withheld_from_a_multihop_peer() -> None:
    assert sent_next_hops(v4_route(), LINK_LOCAL_NEXT_HOP, session(linklocal=True, multihop=True)) == []
    assert sent_next_hops(v4_route(), LINK_LOCAL_NEXT_HOP, session(linklocal=False, multihop=True)) == []


# ------------------------------------------------------------------ configuration


def _parse(next_hop: str, extra: str = '') -> tuple[bool, Configuration]:
    text = f"""neighbor 2001:db8::2 {{
    router-id 1.2.3.4;
    local-address {OURS};
    local-as 1;
    peer-as 1;
    {extra}
    family {{ ipv6 unicast; }}
    capability {{ link-local-nexthop enable; }}
    static {{ route 2001:db8:100::/48 next-hop {next_hop}; }}
}}"""
    configuration = Configuration([text], text=True)
    return configuration.reload(), configuration


@pytest.mark.rfc('draft-ietf-idr-linklocal-capability-06#4-multihop-external-no-link-local', polarity='negative')
def test_the_configuration_refuses_a_link_local_next_hop_for_a_multihop_neighbor() -> None:
    accepted, configuration = _parse(LINK_LOCAL_NEXT_HOP, 'outgoing-ttl 5;')
    assert not accepted
    assert 'multihop' in str(configuration.error)


def test_the_configuration_accepts_a_link_local_next_hop_for_a_neighbor_one_hop_away() -> None:
    accepted, configuration = _parse(LINK_LOCAL_NEXT_HOP)
    assert accepted, configuration.error


def test_the_api_refuses_a_link_local_next_hop_for_a_multihop_neighbor() -> None:
    accepted, configuration = _parse(OURS, 'outgoing-ttl 5;')
    assert accepted, configuration.error
    neighbor = next(iter(configuration.neighbors.values()))
    assert 'multihop' in neighbor.next_hop_refused(IP.from_string(LINK_LOCAL_NEXT_HOP))
    assert neighbor.next_hop_refused(IP.from_string(THIRD_PARTY)) == ''
