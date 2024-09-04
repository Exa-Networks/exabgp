# encoding: utf-8
"""
cidr.py

Created by Thomas Mangin on 2013-08-07.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import math

from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP
from exabgp.util import character
from exabgp.util import ordinal
from exabgp.util import padding
from exabgp.bgp.message.notification import Notify


class CIDR(object):
    EOR = False
    # __slots__ = ['packed','mask','_ip']

    _mask_to_bytes = {}

    def __init__(self, packed, mask):
        self._packed = packed
        self.mask = mask
        self._ip = None

    @classmethod
    def size(cls, mask):
        return cls._mask_to_bytes.get(mask, 0)

    # have a .raw for the ip
    # have a .mask for the mask
    # have a .bgp with the bgp wire format of the prefix

    def __eq__(self, other):
        return self.mask == other.mask and self._packed == other._packed

    def __ne__(self, other):
        return self.mask != other.mask or self._packed != other._packed

    def __lt__(self, other):
        return self._packed < other._packed

    def __le__(self, other):
        return self._packed <= other._packed

    def __gt__(self, other):
        return self._packed > other._packed

    def __ge__(self, other):
        return self._packed >= other._packed

    def top(self, negotiated=None, afi=AFI.undefined):
        if not self._ip:
            self._ip = IP.ntop(self._packed)
        return self._ip

    def ton(self, negotiated=None, afi=AFI.undefined):
        return self._packed

    def __repr__(self):
        return self.prefix()

    def prefix(self):
        return "%s/%s" % (self.top(), self.mask)

    def index(self):
        return str(self.mask) + str(self._packed[: CIDR.size(self.mask)])

    def pack_ip(self):
        return self._packed[: CIDR.size(self.mask)]

    def pack_nlri(self):
        return character(self.mask) + self._packed[: CIDR.size(self.mask)]

    @staticmethod
    def decode(afi, bgp):
        mask = ordinal(bgp[0])
        size = CIDR.size(mask)

        if len(bgp) < size + 1:
            raise Notify(3, 10, 'could not decode CIDR')

        return bgp[1 : size + 1] + padding(IP.length(afi) - size), mask

        # data = bgp[1:size+1] + '\x0\x0\x0\x0'
        # return data[:4], mask

    @classmethod
    def unpack(cls, data):
        afi = AFI.ipv6 if len(data) > 4 or ordinal(data[0]) > 24 else AFI.ipv4
        prefix, mask = cls.decode(afi, data)
        return cls(prefix, mask)

    def __len__(self):
        return CIDR.size(self.mask) + 1

    def __hash__(self):
        return hash(character(self.mask) + self._packed)


for netmask in range(0, 129):
    CIDR._mask_to_bytes[netmask] = int(math.ceil(float(netmask) / 8))

CIDR.NOCIDR = CIDR('', 0)
