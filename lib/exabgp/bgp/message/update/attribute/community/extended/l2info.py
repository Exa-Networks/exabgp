# encoding: utf-8
"""
l2info.py

Created by Thomas Mangin on 2014-06-20.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

# ============================================================ Layer2Information
# RFC 4761


@ExtendedCommunity.register
class L2Info(ExtendedCommunity):
    COMMUNITY_TYPE = 0x80
    COMMUNITY_SUBTYPE = 0x0A

    __slots__ = ['encaps', 'control', 'mtu', 'reserved']

    def __init__(self, encaps, control, mtu, reserved, community=None):
        self.encaps = encaps
        self.control = control
        self.mtu = mtu
        self.reserved = reserved
        # reserved is called preference in draft-ietf-l2vpn-vpls-multihoming-07
        ExtendedCommunity.__init__(
            self,
            community if community is not None else pack("!2sBBHH", self._subtype(), encaps, control, mtu, reserved),
        )

    def __repr__(self):
        return "l2info:%s:%s:%s:%s" % (self.encaps, self.control, self.mtu, self.reserved)

    @staticmethod
    def unpack(data):
        encaps, control, mtu, reserved = unpack('!BBHH', data[2:8])
        return L2Info(encaps, control, mtu, reserved, data[:8])
