"""A prefix announced A, then B, then A again in one batch leaves the peer with A.

With no role negotiated, every attribute set queued for a prefix still goes out (a
redefinition is sent as it always was), but the one sent last must be the latest: the peer
keeps what it receives last. The attribute buckets are walked in the order they were first
created, so A's bucket came before B's and the peer was left holding B.
"""

from __future__ import annotations

from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP, IPv4
from exabgp.rib.outgoing import OutgoingRIB
from exabgp.rib.route import Route


def _route(origin: int) -> Route:
    nlri = INET.from_cidr(CIDR.create_cidr(IP.pton('10.0.0.0'), 24), AFI.ipv4, SAFI.unicast)
    attributes = AttributeCollection()
    attributes[Origin.ID] = Origin.from_int(origin)
    return Route(nlri, attributes, nexthop=IPv4.from_string('192.0.2.1'))


def _origins(rib: OutgoingRIB) -> list[int]:
    return [update.attributes[Origin.ID].origin for update in rib.updates(False) if update.announces]


def test_a_b_a_leaves_the_peer_with_a() -> None:
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})
    rib.add_to_rib(_route(Origin.IGP))
    rib.add_to_rib(_route(Origin.EGP))
    rib.add_to_rib(_route(Origin.IGP))
    origins = _origins(rib)
    assert origins and origins[-1] == Origin.IGP


def test_a_b_still_sends_both_and_leaves_the_peer_with_b() -> None:
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})
    rib.add_to_rib(_route(Origin.IGP))
    rib.add_to_rib(_route(Origin.EGP))
    assert _origins(rib) == [Origin.IGP, Origin.EGP]
