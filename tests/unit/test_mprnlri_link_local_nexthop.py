"""The link-local half of an RFC 2545 next-hop pair survives as far as the JSON API.

RFC 2545 section 3 gives the MP_REACH Next Hop field for IPv6 "the global IPv6 address of
the next hop, potentially followed by the link-local IPv6 address of the next hop", and
sets the length of the field to 16 or 32 accordingly. The decoder used to split the 32
octet form in two and keep the first half, so the announce a peer sent with a link-local
address rendered as the announce it would have sent without one. These tests hold the two
apart: the first names what the pair decodes to, the last two are the pair and the single
address side by side, and they must not agree.

The document states all of this in lower case: it carries no RFC 2119 boilerplate and not
one upper case keyword, so there is no ledger under qa/rfc/ for it to join.
"""

from __future__ import annotations

import json
from struct import pack

from exabgp.bgp.message.update import UpdateCollection
from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI, NextHopWithLinkLocal
from exabgp.protocol.ip import IP, IPv6
from exabgp.reactor.api.response.json import JSON

# 2001:db8:1::1/128, so the tests below are about the next hop and not about prefixes.
NLRI_V6 = bytes([128]) + IPv6.pton('2001:db8:1::1')

GLOBAL_NEXTHOP = IPv6.pton('2001:db8::ffff')
LINK_LOCAL_NEXTHOP = IPv6.pton('fe80::1')

AFI_IPV6 = 2
SAFI_UNICAST = 1


def mp_reach(nexthop: bytes) -> MPRNLRI:
    """An IPv6 unicast MP_REACH_NLRI announcing one prefix behind this Next Hop field."""
    payload = pack('!HB', AFI_IPV6, SAFI_UNICAST) + bytes([len(nexthop)]) + nexthop + bytes([0]) + NLRI_V6
    return MPRNLRI(payload, addpath=False)


def announced(nexthop: bytes) -> dict[str, object]:
    """The "announce" object the JSON API renders for that MP_REACH_NLRI."""
    collection = UpdateCollection(list(mp_reach(nexthop).iter_routed()), [], AttributeCollection())
    rendered = json.loads(str(JSON('6.0.0')._update(collection)['message']))
    announce = rendered['update']['announce']['ipv6 unicast']
    assert isinstance(announce, dict), 'an announce is keyed by next hop'
    return announce


def test_a_thirty_two_octet_next_hop_keeps_both_of_its_addresses() -> None:
    routed = list(mp_reach(GLOBAL_NEXTHOP + LINK_LOCAL_NEXTHOP).iter_routed())
    assert len(routed) == 1
    nexthop = routed[0].nexthop
    assert isinstance(nexthop, NextHopWithLinkLocal)
    assert str(nexthop.link_local) == 'fe80::1'
    # The global address stays the next hop, unchanged in value, rendering and equality.
    assert str(nexthop) == '2001:db8::ffff'
    assert bytes(nexthop.pack_ip()) == GLOBAL_NEXTHOP
    assert nexthop == IP.create_ip(GLOBAL_NEXTHOP)


def test_a_sixteen_octet_next_hop_carries_no_second_address() -> None:
    routed = list(mp_reach(GLOBAL_NEXTHOP).iter_routed())
    assert len(routed) == 1
    assert not isinstance(routed[0].nexthop, NextHopWithLinkLocal)
    assert str(routed[0].nexthop) == '2001:db8::ffff'


def test_the_json_names_the_link_local_address_of_a_pair() -> None:
    routes = announced(GLOBAL_NEXTHOP + LINK_LOCAL_NEXTHOP)['2001:db8::ffff']
    assert isinstance(routes, list)
    assert routes[0]['nlri'] == '2001:db8:1::1/128'
    assert routes[0]['link-local-next-hop'] == 'fe80::1'


def test_the_json_of_a_pair_differs_from_the_json_of_a_global_address_alone() -> None:
    pair = announced(GLOBAL_NEXTHOP + LINK_LOCAL_NEXTHOP)
    alone = announced(GLOBAL_NEXTHOP)
    # Same key, same value under it before the fix, which is what made the loss invisible.
    assert list(pair) == list(alone) == ['2001:db8::ffff']
    assert pair != alone
    routes = alone['2001:db8::ffff']
    assert isinstance(routes, list)
    assert 'link-local-next-hop' not in routes[0]
