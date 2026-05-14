"""announce/sr_policy.py

Announce parser for SR Policy NLRI (SAFI 73, RFC 9830).

Inline syntax (announce section):
  announce ipv4 sr-policy distinguisher 0 color 100 endpoint 1.2.3.4 \\
      next-hop 5.6.7.8 preference 100 binding-sid mpls 24000 \\
      segment-list weight 1 segment type-a mpls 16001

Created by Manoharan Sundaramoorthy 2026-05-14.
"""

from __future__ import annotations

from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget
from exabgp.configuration.static.sr_policy import sr_policy_route
from exabgp.protocol.family import AFI, SAFI
from exabgp.rib.route import Route


def _build_sr_policy_route(tokeniser: Tokeniser, afi: AFI) -> list[Route]:
    nlri, nexthop, tunnel_encap = sr_policy_route(tokeniser, afi)
    attributes = AttributeCollection()
    if tunnel_encap is not None:
        attributes.add(tunnel_encap)
    return [Route(nlri, attributes, nexthop=nexthop)]


@ParseAnnounce.register_family(AFI.ipv4, SAFI.sr_policy, ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.NAME)
def sr_policy_ipv4(tokeniser: Tokeniser) -> list[Route]:
    return _build_sr_policy_route(tokeniser, AFI.ipv4)


@ParseAnnounce.register_family(AFI.ipv6, SAFI.sr_policy, ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.NAME)
def sr_policy_ipv6(tokeniser: Tokeniser) -> list[Route]:
    return _build_sr_policy_route(tokeniser, AFI.ipv6)
