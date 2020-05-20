"""
nlri.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2017 Orange. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack

from exabgp.protocol.ip import NoNextHop

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.util import ordinal
from exabgp.bgp.message import OUT

from exabgp.bgp.message.update.nlri import NLRI

# https://tools.ietf.org/html/rfc7432

# +-----------------------------------+
# |    Route Type (1 octet)           |
# +-----------------------------------+
# |     Length (1 octet)              |
# +-----------------------------------+
# | Route Type specific (variable)    |
# +-----------------------------------+

# ========================================================================= EVPN


@NLRI.register(AFI.l2vpn, SAFI.evpn)
class EVPN(NLRI):
    registered_evpn = dict()

    # NEED to be defined in the subclasses
    CODE = -1
    NAME = 'Unknown'
    SHORT_NAME = 'unknown'

    def __init__(self, action=OUT.UNSET, addpath=None):
        NLRI.__init__(self, AFI.l2vpn, SAFI.evpn, action)
        self._packed = b''

    def __hash__(self):
        return hash("%s:%s:%s:%s" % (self.afi, self.safi, self.CODE, self._packed))

    def __len__(self):
        return len(self._packed) + 2

    def __eq__(self, other):
        return NLRI.__eq__(self, other) and self.CODE == other.CODE

    def __str__(self):
        return "evpn:%s:%s" % (
            self.registered_evpn.get(self.CODE, self).SHORT_NAME.lower(),
            '0x' + ''.join('%02x' % ordinal(_) for _ in self._packed),
        )

    def __repr__(self):
        return str(self)

    def feedback(self, action):
        # if self.nexthop is None and action == OUT.ANNOUNCE:
        # 	return 'evpn nlri next-hop is missing'
        return ''

    def _prefix(self):
        return "evpn:%s:" % (self.registered_evpn.get(self.CODE, self).SHORT_NAME.lower())

    def pack_nlri(self, negotiated=None):
        # XXX: addpath not supported yet
        return pack('!BB', self.CODE, len(self._packed)) + self._packed

    @classmethod
    def register(cls, klass):
        if klass.CODE in cls.registered_evpn:
            raise RuntimeError('only one EVPN registration allowed')
        cls.registered_evpn[klass.CODE] = klass
        return klass

    @classmethod
    def unpack_nlri(cls, afi, safi, bgp, action, addpath):
        code = ordinal(bgp[0])
        length = ordinal(bgp[1])

        if code in cls.registered_evpn:
            klass = cls.registered_evpn[code].unpack(bgp[2 : length + 2])
        else:
            klass = GenericEVPN(code, bgp[2 : length + 2])
        klass.CODE = code
        klass.action = action
        klass.addpath = addpath

        return klass, bgp[length + 2 :]

    def _raw(self):
        return ''.join('%02X' % ordinal(_) for _ in self.pack_nlri())


class GenericEVPN(EVPN):
    def __init__(self, code, packed):
        EVPN.__init__(self)
        self.CODE = code
        self._pack(packed)

    def _pack(self, packed=None):
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

    def json(self, compact=None):
        return '{ "code": %d, "parsed": false, "raw": "%s" }' % (self.CODE, self._raw())
