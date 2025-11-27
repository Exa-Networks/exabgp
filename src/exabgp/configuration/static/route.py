"""inet/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# This is a legacy file to handle 3.4.x like format

from __future__ import annotations

from typing import Any, Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.update.nlri.inet import INET

from exabgp.protocol.ip import IP
from exabgp.protocol.ip import NoNextHop

from exabgp.bgp.message import Action

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.attribute import Attribute

from exabgp.rib.change import Change

from exabgp.configuration.core import Section

# from exabgp.configuration.static.parser import inet
from exabgp.configuration.static.parser import mpls
from exabgp.configuration.static.parser import attribute
from exabgp.configuration.static.parser import next_hop
from exabgp.configuration.static.parser import origin
from exabgp.configuration.static.parser import med
from exabgp.configuration.static.parser import as_path
from exabgp.configuration.static.parser import local_preference
from exabgp.configuration.static.parser import atomic_aggregate
from exabgp.configuration.static.parser import aggregator
from exabgp.configuration.static.parser import originator_id
from exabgp.configuration.static.parser import cluster_list
from exabgp.configuration.static.parser import community
from exabgp.configuration.static.parser import large_community
from exabgp.configuration.static.parser import extended_community
from exabgp.configuration.static.parser import aigp
from exabgp.configuration.static.parser import path_information
from exabgp.configuration.static.parser import name as named
from exabgp.configuration.static.parser import split
from exabgp.configuration.static.parser import watchdog
from exabgp.configuration.static.parser import withdraw
from exabgp.configuration.static.mpls import route_distinguisher
from exabgp.configuration.static.mpls import label
from exabgp.configuration.static.mpls import prefix_sid
from exabgp.configuration.static.mpls import prefix_sid_srv6


# Take an integer an created it networked packed representation for the right family (ipv4/ipv6)
def pack_int(afi: AFI, integer: int) -> bytes:
    return b''.join(bytes([(integer >> (offset * 8)) & 0xFF]) for offset in range(IP.length(afi) - 1, -1, -1))


class ParseStaticRoute(Section):
    # put next-hop first as it is a requirement atm
    definition = [
        'next-hop <ip>',
        'path-information <ipv4 formated number>',
        'route-distinguisher|rd <ipv4>:<port>|<16bits number>:<32bits number>|<32bits number>:<16bits number>',
        'origin IGP|EGP|INCOMPLETE',
        'as-path [ <asn>.. ]',
        'med <16 bits number>',
        'local-preference <16 bits number>',
        'atomic-aggregate',
        'community <16 bits number>',
        'large-community <96 bits number>',
        'extended-community target:<16 bits number>:<ipv4 formated number>',
        'originator-id <ipv4>',
        'cluster-list <ipv4>',
        'label <15 bits number>',
        'bgp-prefix-sid [ 32 bits number> ] | [ <32 bits number>, [ ( <24 bits number>,<24 bits number> ) ]]',
        'bgp-prefix-sid-srv6 ( l3-service|l2-service <ipv6> <behavior> [<LBL>,<LNL>,<FL>,<AL>,<Tpose-Len>,<Tpose-Offset>])',
        'aigp <40 bits number>',
        'attribute [ generic attribute format ]name <mnemonic>',
        'split /<mask>',
        'watchdog <watchdog-name>',
        'withdraw',
    ]

    syntax: str = 'route <ip>/<netmask> { \n   ' + ' ;\n   '.join(definition) + '\n}'

    known: dict = {
        'path-information': path_information,
        'rd': route_distinguisher,
        'route-distinguisher': route_distinguisher,
        'label': label,
        'bgp-prefix-sid': prefix_sid,
        'bgp-prefix-sid-srv6': prefix_sid_srv6,
        'attribute': attribute,
        'next-hop': next_hop,
        'origin': origin,
        'med': med,
        'as-path': as_path,
        'local-preference': local_preference,
        'atomic-aggregate': atomic_aggregate,
        'aggregator': aggregator,
        'originator-id': originator_id,
        'cluster-list': cluster_list,
        'community': community,
        'large-community': large_community,
        'extended-community': extended_community,
        'aigp': aigp,
        'name': named,
        'split': split,
        'watchdog': watchdog,
        'withdraw': withdraw,
    }

    action: dict = {
        'path-information': 'nlri-set',
        'rd': 'nlri-set',
        'route-distinguisher': 'nlri-set',
        'label': 'nlri-set',
        'bgp-prefix-sid': 'attribute-add',
        'bgp-prefix-sid-srv6': 'attribute-add',
        'bgp-srv6-mup': 'nlri-set',
        'bgp-srv6-mup-ext': 'attribute-set',
        'attribute': 'attribute-add',
        'next-hop': 'nexthop-and-attribute',
        'origin': 'attribute-add',
        'med': 'attribute-add',
        'as-path': 'attribute-add',
        'local-preference': 'attribute-add',
        'atomic-aggregate': 'attribute-add',
        'aggregator': 'attribute-add',
        'originator-id': 'attribute-add',
        'cluster-list': 'attribute-add',
        'community': 'attribute-add',
        'large-community': 'attribute-add',
        'extended-community': 'attribute-add',
        'name': 'attribute-add',
        'split': 'attribute-add',
        'watchdog': 'attribute-add',
        'withdraw': 'attribute-add',
        'aigp': 'attribute-add',
    }

    assign: dict = {
        'path-information': 'path_info',
        'rd': 'rd',
        'route-distinguisher': 'rd',
        'label': 'labels',
    }

    name: str = 'static/route'

    def __init__(self, parser: Any, scope: Any, error: Any) -> None:
        Section.__init__(self, parser, scope, error)

    def clear(self) -> bool:
        return True

    def pre(self) -> bool:
        self.scope.append_route(mpls(self.parser.tokeniser))
        return True

    def post(self) -> bool:
        self._split()
        routes = self.scope.pop_routes()
        if routes:
            for route in routes:
                if route.nlri.has_rd() and route.nlri.rd is not RouteDistinguisher.NORD:
                    route.nlri.safi = SAFI.mpls_vpn
                elif route.nlri.has_label() and route.nlri.labels is not Labels.NOLABEL:
                    route.nlri.safi = SAFI.nlri_mpls
                self.scope.append_route(route)
        return True

    def _check(self) -> bool:
        change = self.scope.get(self.name)
        if not self.check(change):
            self.error.set(self.syntax)
            return False
        return True

    @staticmethod
    def check(change: Change) -> bool:
        # The NLRI is actually an INET subclass with nexthop attribute
        nlri: INET = change.nlri  # type: ignore[assignment]  # runtime: subclass of NLRI
        if (
            nlri.nexthop is NoNextHop
            and nlri.action == Action.ANNOUNCE
            and nlri.afi == AFI.ipv4
            and nlri.safi in (SAFI.unicast, SAFI.multicast)
        ):
            return False
        return True

    @staticmethod
    def split(last: Change) -> Iterator[Change]:
        if Attribute.CODE.INTERNAL_SPLIT not in last.attributes:
            yield last
            return

        # The NLRI is an Inet subclass with cidr, nexthop, etc. attributes
        # Use Any to access dynamically since the actual type depends on AFI/SAFI
        nlri: Any = last.nlri

        # ignore if the request is for an aggregate, or the same size
        mask = nlri.cidr.mask
        cut = last.attributes[Attribute.CODE.INTERNAL_SPLIT]
        if mask >= cut:
            yield last
            return

        # calculate the number of IP in the /<size> of the new route
        increment = pow(2, nlri.afi.mask() - cut)
        # how many new routes are we going to create from the initial one
        number = pow(2, cut - nlri.cidr.mask)

        # convert the IP into a integer/long
        ip = 0
        for c in nlri.cidr.ton():
            ip <<= 8
            ip += c

        afi = nlri.afi
        safi = nlri.safi

        # Really ugly
        klass = nlri.__class__
        nexthop = nlri.nexthop
        path_info = nlri.path_info if safi.has_path() else None
        labels = nlri.labels if safi.has_label() else None
        rd = nlri.rd if safi.has_rd() else None

        # XXX: Looks weird to set and then set to None, check
        nlri.cidr.mask = cut
        last.nlri = None  # type: ignore[assignment]  # intentionally clearing reference

        # generate the new routes
        for _ in range(number):
            # update ip to the next route, this recalculate the "ip" field of the Inet class
            new_nlri: Any = klass(afi, safi, Action.ANNOUNCE)
            new_nlri.cidr = CIDR(pack_int(afi, ip), cut)
            new_nlri.nexthop = nexthop  # nexthop can be NextHopSelf
            if path_info is not None:
                new_nlri.path_info = path_info
            if labels is not None:
                new_nlri.labels = labels
            if rd is not None:
                new_nlri.rd = rd
            # next ip
            ip += increment
            yield Change(new_nlri, last.attributes)

    def _split(self) -> None:
        for route in self.scope.pop_routes():
            for splat in self.split(route):
                self.scope.append_route(splat)
