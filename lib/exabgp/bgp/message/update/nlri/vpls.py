# encoding: utf-8
"""
vpls.py

Created by Nikita Shirokov on 2014-06-16.
Copyright (c) 2014-2017 Nikita Shirokov. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import unpack
from struct import pack
from exabgp.vendoring import six
from exabgp.util import concat_bytes
from exabgp.protocol.ip import IP
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.direction import OUT
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher


def _unique():
    value = 0
    while True:
        yield value
        value += 1


unique = _unique()


@NLRI.register(AFI.l2vpn, SAFI.vpls)
class VPLS(NLRI):

    __slots__ = ['action', 'nexthop', 'rd', 'base', 'offset', 'size', 'endpoint', 'unique']

    # XXX: Should take AFI, SAFI and OUT.direction as parameter to match other NLRI
    def __init__(self, rd, endpoint, base, offset, size):
        NLRI.__init__(self, AFI.l2vpn, SAFI.vpls)
        self.action = OUT.ANNOUNCE
        self.nexthop = None
        self.rd = rd
        self.base = base
        self.offset = offset
        self.size = size
        self.endpoint = endpoint
        self.unique = six.next(unique)

    def feedback(self, action):
        if self.nexthop is None and action == OUT.ANNOUNCE:
            return 'vpls nlri next-hop missing'
        if self.endpoint is None:
            return 'vpls nlri endpoint missing'
        if self.base is None:
            return 'vpls nlri base missing'
        if self.offset is None:
            return 'vpls nlri offset missing'
        if self.size is None:
            return 'vpls nlri size missing'
        if self.rd is None:
            return 'vpls nlri route-distinguisher missing'
        if self.base > (0xFFFFF - self.size):  # 20 bits, 3 bytes
            return 'vpls nlri size inconsistency'
        return ''

    def assign(self, name, value):
        setattr(self, name, value)

    def pack_nlri(self, negotiated=None):
        return concat_bytes(
            b'\x00\x11',  # pack('!H',17)
            self.rd.pack(),
            pack('!HHH', self.endpoint, self.offset, self.size),
            pack('!L', (self.base << 4) | 0x1)[1:],  # setting the bottom of stack, should we ?
        )

    # XXX: FIXME: we need an unique key here.
    # XXX: What can we use as unique key ?
    def json(self, compact=None):
        content = ', '.join(
            [
                self.rd.json(),
                '"endpoint": %s' % self.endpoint,
                '"base": %s' % self.base,
                '"offset": %s' % self.offset,
                '"size": %s' % self.size,
            ]
        )
        return '{ %s }' % (content)

    def extensive(self):
        return "vpls%s endpoint %s base %s offset %s size %s %s" % (
            self.rd,
            self.endpoint,
            self.base,
            self.offset,
            self.size,
            '' if self.nexthop is None else 'next-hop %s' % self.nexthop,
        )

    def __str__(self):
        return self.extensive()

    @classmethod
    def unpack_nlri(cls, afi, safi, bgp, action, addpath):
        # label is 20bits, stored using 3 bytes, 24 bits
        (length,) = unpack('!H', bgp[0:2])
        if len(bgp) != length + 2:
            raise Notify(3, 10, 'l2vpn vpls message length is not consistent with encoded bgp')
        rd = RouteDistinguisher(bgp[2:10])
        endpoint, offset, size = unpack('!HHH', bgp[10:16])
        base = unpack('!L', b'\x00' + bgp[16:19])[0] >> 4
        nlri = cls(rd, endpoint, base, offset, size)
        nlri.action = action
        # nlri.nexthop = IP.unpack(nexthop)
        return nlri, bgp[19:]
