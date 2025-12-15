"""announce/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from typing import Iterator as TypingIterator, cast

from exabgp.protocol.ip import IP

from exabgp.rib.route import Route

from exabgp.protocol.family import AFI
from exabgp.configuration.core import Section
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import Container

from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.attribute import Attribute


# Take an integer an created it networked packed representation for the right family (ipv4/ipv6)
def pack_int(afi: AFI, integer: int) -> bytes:
    return b''.join(bytes([(integer >> (offset * 8)) & 0xFF]) for offset in range(IP.length(afi) - 1, -1, -1))


class ParseAnnounce(Section):
    syntax: str = ''
    afi: AFI | None = None

    def post(self) -> bool:
        self._split()
        routes = self.scope.pop(self.name)
        if routes:
            self.scope.extend_routes(routes)
        return True

    @staticmethod
    def split(last: Route) -> TypingIterator[Route]:
        if Attribute.CODE.INTERNAL_SPLIT not in last.attributes:
            yield last
            return

        # Cast to INET - split only works on INET-like NLRIs with cidr/path_info
        inet_nlri = cast(INET, last.nlri)

        # ignore if the request is for an aggregate, or the same size
        mask = inet_nlri.cidr.mask
        cut = last.attributes[Attribute.CODE.INTERNAL_SPLIT]
        if mask >= cut:
            yield last
            return

        # calculate the number of IP in the /<size> of the new route
        increment = pow(2, inet_nlri.afi.mask() - cut)
        # how many new routes are we going to create from the initial one
        number = pow(2, cut - inet_nlri.cidr.mask)

        # convert the IP into a integer/long
        ip = 0
        for c in inet_nlri.cidr.packed_cidr():
            ip <<= 8
            ip += c

        afi = inet_nlri.afi
        safi = inet_nlri.safi

        # Extract data from original NLRI and Route before clearing
        klass = inet_nlri.__class__
        path_info = inet_nlri.path_info
        nexthop = last.nexthop  # Get nexthop from Route, not NLRI

        last.nlri = NLRI.EMPTY  # Clear reference after extracting data

        # generate the new routes
        for _ in range(number):
            # update ip to the next route, this recalculate the "ip" field of the Inet class
            cidr = CIDR.make_cidr(pack_int(afi, ip), cut)
            nlri = klass.from_cidr(cidr, afi, safi, path_info)
            # next ip
            ip += increment
            yield Route(nlri, last.attributes, nexthop=nexthop)

    def _split(self) -> None:
        for route in self.scope.pop_routes():
            for splat in self.split(route):
                self.scope.append_route(splat)

    def _check(self) -> bool:
        if not self.check(self.scope.get(self.name), self.afi):
            return self.error.set(self.syntax)
        return True

    @staticmethod
    def check(route: Route, afi: AFI | None) -> bool:
        raise RuntimeError('need to be implemented by subclasses')


class SectionAnnounce(ParseAnnounce):
    # Schema definition for announce section
    schema = Container(
        description='Route announcements',
        children={
            'ipv4': Container(description='IPv4 route announcements'),
            'ipv6': Container(description='IPv6 route announcements'),
            'l2vpn': Container(description='L2VPN route announcements'),
        },
    )

    name = 'announce'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        ParseAnnounce.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        return True

    def post(self) -> bool:
        routes = self.scope.pop('routes', [])
        self.scope.pop()
        if routes:
            self.scope.extend('routes', routes)
        self.scope.pop(self.name)
        return True


class AnnounceIPv4(ParseAnnounce):
    name = 'ipv4'
    afi = AFI.ipv4

    def clear(self) -> None:
        pass


class AnnounceIPv6(ParseAnnounce):
    name = 'ipv6'
    afi = AFI.ipv6

    def clear(self) -> None:
        pass


class AnnounceL2VPN(ParseAnnounce):
    name = 'l2vpn'
    afi = AFI.l2vpn

    def clear(self) -> None:
        pass
