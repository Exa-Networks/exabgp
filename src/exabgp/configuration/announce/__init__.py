"""announce/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from typing import Iterator as TypingIterator

from exabgp.protocol.ip import IP

from exabgp.bgp.message import Action
from exabgp.rib.change import Change

from exabgp.protocol.family import AFI
from exabgp.configuration.core import Section
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error

from exabgp.bgp.message.update.nlri.cidr import CIDR
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
    def split(last: Change) -> TypingIterator[Change]:
        if Attribute.CODE.INTERNAL_SPLIT not in last.attributes:
            yield last
            return

        # ignore if the request is for an aggregate, or the same size
        mask = last.nlri.cidr.mask  # type: ignore[attr-defined]
        cut = last.attributes[Attribute.CODE.INTERNAL_SPLIT]
        if mask >= cut:
            yield last
            return

        # calculate the number of IP in the /<size> of the new route
        increment = pow(2, last.nlri.afi.mask() - cut)
        # how many new routes are we going to create from the initial one
        number = pow(2, cut - last.nlri.cidr.mask)  # type: ignore[attr-defined]

        # convert the IP into a integer/long
        ip = 0
        for c in last.nlri.cidr.ton():  # type: ignore[attr-defined]
            ip <<= 8
            ip += c

        afi = last.nlri.afi
        safi = last.nlri.safi

        # Really ugly
        klass = last.nlri.__class__
        path_info = last.nlri.path_info  # type: ignore[attr-defined]
        nexthop = last.nlri.nexthop

        # XXX: Looks weird to set and then set to None, check
        last.nlri.cidr.mask = cut  # type: ignore[attr-defined]
        last.nlri = None  # type: ignore[assignment]

        # generate the new routes
        for _ in range(number):
            # update ip to the next route, this recalculate the "ip" field of the Inet class
            nlri = klass(afi, safi, Action.ANNOUNCE)
            nlri.cidr = CIDR(pack_int(afi, ip), cut)  # type: ignore[attr-defined]
            nlri.nexthop = nexthop  # nexthop can be NextHopSelf
            nlri.path_info = path_info  # type: ignore[attr-defined]
            # next ip
            ip += increment
            yield Change(nlri, last.attributes)

    def _split(self) -> None:
        for route in self.scope.pop_routes():
            for splat in self.split(route):
                self.scope.append_route(splat)

    def _check(self) -> bool:
        if not self.check(self.scope.get(self.name), self.afi):
            return self.error.set(self.syntax)
        return True

    @staticmethod
    def check(change: Change, afi: AFI | None) -> bool:
        raise RuntimeError('need to be implemented by subclasses')


class SectionAnnounce(ParseAnnounce):
    name = 'announce'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        ParseAnnounce.__init__(self, parser, scope, error)

    def clear(self) -> bool:
        return True

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

    def clear(self) -> bool:
        return True


class AnnounceIPv6(ParseAnnounce):
    name = 'ipv6'
    afi = AFI.ipv6

    def clear(self) -> bool:
        return True


class AnnounceL2VPN(ParseAnnounce):
    name = 'l2vpn'
    afi = AFI.l2vpn

    def clear(self) -> bool:
        return True
