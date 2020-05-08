# encoding: utf-8
"""
announce/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from exabgp.util import ordinal
from exabgp.util import character
from exabgp.util import concat_bytes_i

from exabgp.protocol.ip import IP

from exabgp.bgp.message import OUT
from exabgp.rib.change import Change

from exabgp.protocol.family import AFI
from exabgp.configuration.core import Section

from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.attribute import Attribute


# Take an integer an created it networked packed representation for the right family (ipv4/ipv6)
def pack_int(afi, integer):
    return concat_bytes_i(character((integer >> (offset * 8)) & 0xFF) for offset in range(IP.length(afi) - 1, -1, -1))


class ParseAnnounce(Section):
    syntax = ''
    afi = None

    def post(self):
        self._split()
        routes = self.scope.pop(self.name)
        if routes:
            self.scope.extend_routes(routes)
        return True

    @staticmethod
    def split(last):
        if Attribute.CODE.INTERNAL_SPLIT not in last.attributes:
            yield last
            return

        # ignore if the request is for an aggregate, or the same size
        mask = last.nlri.cidr.mask
        cut = last.attributes[Attribute.CODE.INTERNAL_SPLIT]
        if mask >= cut:
            yield last
            return

        # calculate the number of IP in the /<size> of the new route
        increment = pow(2, last.nlri.afi.mask() - cut)
        # how many new routes are we going to create from the initial one
        number = pow(2, cut - last.nlri.cidr.mask)

        # convert the IP into a integer/long
        ip = 0
        for c in last.nlri.cidr.ton():
            ip <<= 8
            ip += ordinal(c)

        afi = last.nlri.afi
        safi = last.nlri.safi

        # Really ugly
        klass = last.nlri.__class__
        path_info = last.nlri.path_info
        nexthop = last.nlri.nexthop

        # XXX: Looks weird to set and then set to None, check
        last.nlri.cidr.mask = cut
        last.nlri = None

        # generate the new routes
        for _ in range(number):
            # update ip to the next route, this recalculate the "ip" field of the Inet class
            nlri = klass(afi, safi, OUT.ANNOUNCE)
            nlri.cidr = CIDR(pack_int(afi, ip), cut)
            nlri.nexthop = nexthop  # nexthop can be NextHopSelf
            nlri.path_info = path_info
            # next ip
            ip += increment
            yield Change(nlri, last.attributes)

    def _split(self):
        for route in self.scope.pop_routes():
            for splat in self.split(route):
                self.scope.append_route(splat)

    def _check(self):
        if not self.check(self.scope.get(self.name), self.afi):
            return self.error.set(self.syntax)
        return True

    @staticmethod
    def check(change, afi):
        raise RuntimeError('need to be implemented by subclasses')


class SectionAnnounce(ParseAnnounce):
    name = 'announce'

    def __init__(self, tokeniser, scope, error, logger):
        Section.__init__(self, tokeniser, scope, error, logger)

    def clear(self):
        return True

    def pre(self):
        return True

    def post(self):
        routes = self.scope.pop('routes', [])
        self.scope.pop()
        if routes:
            self.scope.extend('routes', routes)
        self.scope.pop(self.name)
        return True


class AnnounceIPv4(ParseAnnounce):
    name = 'ipv4'
    afi = AFI.ipv4

    def clear(self):
        return True


class AnnounceIPv6(ParseAnnounce):
    name = 'ipv6'
    afi = AFI.ipv6

    def clear(self):
        return True


class AnnounceL2VPN(ParseAnnounce):
    name = 'l2vpn'
    afi = AFI.l2vpn

    def clear(self):
        return True
