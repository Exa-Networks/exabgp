"""cidr.py

Created by Thomas Mangin on 2013-08-07.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import math

from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP
from exabgp.bgp.message.notification import Notify

# CIDR netmask constants
CIDR_IPV4_MAX_MASK = 24  # Maximum IPv4 mask for heuristic detection
CIDR_IPV6_LENGTH_BYTES = 4  # IPv6 address length in bytes (for detection)


class CIDR:
    EOR = False

    _mask_to_bytes = {}

    NOCIDR: CIDR | None = None

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

    # comparing with anything which is not a CIDR returns NotImplemented rather
    # than reaching for a .mask it does not have. Python then falls back, so
    # `cidr == None` is False instead of an AttributeError, which is what the
    # data model promises and what any caller holding a mixed collection expects.

    def __eq__(self, other):
        if not isinstance(other, CIDR):
            return NotImplemented
        return self.mask == other.mask and self._packed == other._packed

    def __ne__(self, other):
        # the exact negation of __eq__, not a re-derivation: writing the
        # condition out twice is how the two drift apart
        equal = self.__eq__(other)
        if equal is NotImplemented:
            return equal
        return not equal

    def _order(self):
        """The key the ordering operators compare: address first, mask second.

        Update.messages() packs sorted(self.nlris), so this decides the order prefixes
        go onto the wire. The address stays the primary key, so nothing which already
        had a defined order moves; the mask is only a tiebreak.

        Without it 10.0.0.0/24 and 10.0.0.0/25 compared both <= and >= while __eq__ and
        __hash__ told them apart. An ordering which disagrees with equality breaks what
        bisect and every sorted-merge caller are entitled to assume, and sorted() on a
        list holding both returned them in the order they were given rather than a
        defined one.
        """
        return bytes(self._packed), self.mask

    def __lt__(self, other):
        if not isinstance(other, CIDR):
            return NotImplemented
        return self._order() < other._order()

    def __le__(self, other):
        if not isinstance(other, CIDR):
            return NotImplemented
        return self._order() <= other._order()

    def __gt__(self, other):
        if not isinstance(other, CIDR):
            return NotImplemented
        return self._order() > other._order()

    def __ge__(self, other):
        if not isinstance(other, CIDR):
            return NotImplemented
        return self._order() >= other._order()

    def top(self, negotiated=None, afi=AFI.undefined):
        if not self._ip:
            self._ip = IP.ntop(self._packed)
        return self._ip

    def ton(self, negotiated=None, afi=AFI.undefined):
        return self._packed

    def __repr__(self):
        return self.prefix()

    def prefix(self):
        return '{}/{}'.format(self.top(), self.mask)

    def index(self):
        return str(self.mask) + str(self._packed[: CIDR.size(self.mask)])

    def pack_ip(self):
        return self._packed[: CIDR.size(self.mask)]

    def pack_nlri(self):
        return bytes([self.mask]) + self._packed[: CIDR.size(self.mask)]

    @staticmethod
    def decode(afi, bgp):
        if not bgp:
            raise Notify(3, 10, 'could not decode CIDR, no data')

        mask = bgp[0]
        # a mask larger than the family holds would make the padding below negative
        if mask > IP.length(afi) * 8:
            raise Notify(3, 10, 'could not decode CIDR, invalid mask %d for %s' % (mask, afi))

        size = CIDR.size(mask)

        if len(bgp) < size + 1:
            raise Notify(3, 10, 'could not decode CIDR')

        return bgp[1 : size + 1] + bytes(IP.length(afi) - size), mask

        # data = bgp[1:size+1] + '\x0\x0\x0\x0'
        # return data[:4], mask

    @classmethod
    def unpack(cls, data):
        afi = AFI.ipv6 if len(data) > CIDR_IPV6_LENGTH_BYTES or data[0] > CIDR_IPV4_MAX_MASK else AFI.ipv4
        prefix, mask = cls.decode(afi, data)
        return cls(prefix, mask)

    def __len__(self):
        return CIDR.size(self.mask) + 1

    def __hash__(self):
        return hash(bytes([self.mask]) + self._packed)


for netmask in range(129):
    CIDR._mask_to_bytes[netmask] = int(math.ceil(float(netmask) / 8))

CIDR.NOCIDR = CIDR('', 0)
