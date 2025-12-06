"""inet/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# This is a legacy file to handle 3.4.x like format

from __future__ import annotations

from typing import Any, Iterator, cast

from exabgp.protocol.ip import IP

from exabgp.bgp.message import Action

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.attribute import Attribute

from exabgp.rib.route import Route

from exabgp.configuration.core import Section
from exabgp.configuration.schema import Container, Leaf, LeafList, ValueType

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
    # Schema definition for static route attributes
    schema = Container(
        description='Static route configuration',
        children={
            'next-hop': Leaf(
                type=ValueType.NEXT_HOP,
                description='Next-hop IP address or "self"',
                action='nexthop-and-attribute',
            ),
            'path-information': Leaf(
                type=ValueType.IP_ADDRESS,
                description='Path information (path ID for ADD-PATH)',
                action='nlri-set',
            ),
            'rd': Leaf(
                type=ValueType.RD,
                description='Route distinguisher',
                action='nlri-set',
            ),
            'route-distinguisher': Leaf(
                type=ValueType.RD,
                description='Route distinguisher (alias for rd)',
                action='nlri-set',
            ),
            'label': Leaf(
                type=ValueType.LABEL,
                description='MPLS label stack',
                action='nlri-set',
            ),
            'bgp-prefix-sid': Leaf(
                type=ValueType.STRING,
                description='BGP Prefix-SID attribute',
                action='attribute-add',
            ),
            'bgp-prefix-sid-srv6': Leaf(
                type=ValueType.STRING,
                description='BGP Prefix-SID SRv6 attribute',
                action='attribute-add',
            ),
            'attribute': Leaf(
                type=ValueType.HEX_STRING,
                description='Generic BGP attribute in hex format',
                action='attribute-add',
            ),
            'origin': Leaf(
                type=ValueType.ORIGIN,
                description='BGP origin attribute',
                choices=['igp', 'egp', 'incomplete'],
                action='attribute-add',
            ),
            'med': Leaf(
                type=ValueType.MED,
                description='Multi-exit discriminator',
                action='attribute-add',
            ),
            'as-path': LeafList(
                type=ValueType.AS_PATH,
                description='AS path',
                action='attribute-add',
            ),
            'local-preference': Leaf(
                type=ValueType.LOCAL_PREF,
                description='Local preference',
                action='attribute-add',
            ),
            'atomic-aggregate': Leaf(
                type=ValueType.ATOMIC_AGGREGATE,
                description='Atomic aggregate flag',
                action='attribute-add',
            ),
            'aggregator': Leaf(
                type=ValueType.AGGREGATOR,
                description='Aggregator (AS number and IP)',
                action='attribute-add',
            ),
            'originator-id': Leaf(
                type=ValueType.IP_ADDRESS,
                description='Originator ID (route reflector)',
                action='attribute-add',
            ),
            'cluster-list': LeafList(
                type=ValueType.IP_ADDRESS,
                description='Cluster list (route reflector)',
                action='attribute-add',
            ),
            'community': LeafList(
                type=ValueType.COMMUNITY,
                description='Standard BGP communities',
                action='attribute-add',
            ),
            'large-community': LeafList(
                type=ValueType.LARGE_COMMUNITY,
                description='Large BGP communities',
                action='attribute-add',
            ),
            'extended-community': LeafList(
                type=ValueType.EXTENDED_COMMUNITY,
                description='Extended BGP communities',
                action='attribute-add',
            ),
            'aigp': Leaf(
                type=ValueType.INTEGER,
                description='Accumulated IGP metric',
                action='attribute-add',
            ),
            'name': Leaf(
                type=ValueType.STRING,
                description='Route name/mnemonic',
                action='attribute-add',
            ),
            'split': Leaf(
                type=ValueType.INTEGER,
                description='Split prefix into smaller prefixes',
                action='attribute-add',
            ),
            'watchdog': Leaf(
                type=ValueType.STRING,
                description='Watchdog name for route withdrawal',
                action='attribute-add',
            ),
            'withdraw': Leaf(
                type=ValueType.BOOLEAN,
                description='Mark route for withdrawal',
                action='attribute-add',
            ),
        },
    )

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

    known: dict[str | tuple[Any, ...], Any] = {
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

    action: dict[str | tuple[Any, ...], str] = {
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

    assign: dict[str, str] = {
        'path-information': 'path_info',
        'rd': 'rd',
        'route-distinguisher': 'rd',
        'label': 'labels',
    }

    name: str = 'static/route'

    def __init__(self, parser: Any, scope: Any, error: Any) -> None:
        Section.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        self.scope.append_route(mpls(self.parser.tokeniser))
        return True

    def post(self) -> bool:
        self._split()
        routes = self.scope.pop_routes()
        if routes:
            for route in routes:
                # Cast to INET to access rd/labels attributes (verified by has_rd/has_label)
                inet_nlri = cast(INET, route.nlri)
                if route.nlri.has_rd() and inet_nlri.rd is not RouteDistinguisher.NORD:
                    route.nlri.safi = SAFI.mpls_vpn
                elif route.nlri.has_label() and inet_nlri.labels is not Labels.NOLABEL:
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
    def check(route: Route) -> bool:
        nlri: NLRI = route.nlri
        if (
            nlri.nexthop is IP.NoNextHop
            and nlri.action == Action.ANNOUNCE
            and nlri.afi == AFI.ipv4
            and nlri.safi in (SAFI.unicast, SAFI.multicast)
        ):
            return False
        return True

    @staticmethod
    def split(last: Route) -> Iterator[Route]:
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

        # Extract data from original NLRI before clearing
        # Check NLRI class type rather than SAFI (SAFI may be unicast even for VPN routes)
        from exabgp.bgp.message.update.nlri.label import Label
        from exabgp.bgp.message.update.nlri.ipvpn import IPVPN

        klass = nlri.__class__
        nexthop = nlri.nexthop
        path_info = nlri.path_info if safi.has_path() else None
        # Check class type since SAFI may not reflect actual capabilities
        labels = nlri.labels if isinstance(nlri, Label) else None
        rd = nlri.rd if isinstance(nlri, IPVPN) else None

        last.nlri = NLRI.EMPTY  # Clear reference after extracting data

        # generate the new routes
        for _ in range(number):
            # update ip to the next route, this recalculate the "ip" field of the Inet class
            new_cidr = CIDR.make_cidr(pack_int(afi, ip), cut)
            new_nlri: Any = klass.from_cidr(new_cidr, afi, safi, Action.ANNOUNCE)
            new_nlri.nexthop = nexthop  # nexthop can be NextHopSelf
            if path_info is not None:
                new_nlri.path_info = path_info
            if labels is not None:
                new_nlri.labels = labels
            if rd is not None:
                new_nlri.rd = rd
            # next ip
            ip += increment
            yield Route(new_nlri, last.attributes)

    def _split(self) -> None:
        for route in self.scope.pop_routes():
            for splat in self.split(route):
                self.scope.append_route(splat)
