"""
nlri.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from struct import unpack

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.util import ordinal
from exabgp.bgp.message import OUT

from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher

# https://tools.ietf.org/html/rfc7752#section-3.2
#
#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |            NLRI Type          |     Total NLRI Length         |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |                                                               |
#     //                  Link-State NLRI (variable)                 //
#     |                                                               |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |            NLRI Type          |     Total NLRI Length         |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |                                                               |
#     +                       Route Distinguisher                     +
#     |                                                               |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |                                                               |
#     //                  Link-State NLRI (variable)                 //
#     |                                                               |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#                   +------+---------------------------+
#                   | Type | NLRI Type                 |
#                   +------+---------------------------+
#                   |  1   | Node NLRI                 |
#                   |  2   | Link NLRI                 |
#                   |  3   | IPv4 Topology Prefix NLRI |
#                   |  4   | IPv6 Topology Prefix NLRI |
#                   +------+---------------------------+
# ==================================================================== BGP LINK_STATE
#            +-------------+----------------------------------+
#            | Protocol-ID | NLRI information source protocol |
#            +-------------+----------------------------------+
#            |      1      | IS-IS Level 1                    |
#            |      2      | IS-IS Level 2                    |
#            |      3      | OSPFv2                           |
#            |      4      | Direct                           |
#            |      5      | Static configuration             |
#            |      6      | OSPFv3                           |
#            +-------------+----------------------------------+
# ===================================================================== PROTO_ID

PROTO_CODES = {
    1: 'isis_l1',
    2: 'isis_l2',
    3: 'ospf_v2',
    4: 'direct',
    5: 'static',
    6: 'ospfv3',
}


@NLRI.register(AFI.bgpls, SAFI.bgp_ls)
@NLRI.register(AFI.bgpls, SAFI.bgp_ls_vpn)
class BGPLS(NLRI):
    registered_bgpls = dict()

    CODE = -1
    NAME = 'Unknown'
    SHORT_NAME = 'unknown'

    def __init__(self, action=OUT.UNSET, addpath=None):
        NLRI.__init__(self, AFI.bgpls, SAFI.bgp_ls, action)
        self._packed = b''

    def pack_nlri(self, negotiated=None):
        return pack('!BB', self.CODE, len(self._packed)) + self._packed

    def __len__(self):
        return len(self._packed) + 2

    def __hash__(self):
        return hash("%s:%s:%s:%s" % (self.afi, self.safi, self.CODE, self._packed))

    def __str__(self):
        return "bgp-ls:%s:%s" % (
            self.registered_bgpls.get(self.CODE, self).SHORT_NAME.lower(),
            '0x' + ''.join('%02x' % ordinal(_) for _ in self._packed),
        )

    @classmethod
    def register(cls, klass):
        if klass.CODE in cls.registered_bgpls:
            raise RuntimeError('only one BGP LINK_STATE registration allowed')
        cls.registered_bgpls[klass.CODE] = klass
        return klass

    @classmethod
    def unpack_nlri(cls, afi, safi, bgp, action, addpath):
        code, length = unpack('!HH', bgp[:4])
        if code in cls.registered_bgpls:
            if safi == SAFI.bgp_ls_vpn:
                # Extract Route Distinguisher
                rd = RouteDistinguisher.unpack(bgp[4:12])
                klass = cls.registered_bgpls[code].unpack_nlri(bgp[12 : length + 4], rd)
            else:
                rd = None
                klass = cls.registered_bgpls[code].unpack_nlri(bgp[4 : length + 4], rd)
        else:
            klass = GenericBGPLS(code, bgp[4 : length + 4])
        klass.CODE = code
        klass.action = action
        klass.addpath = addpath

        return klass, bgp[length + 4 :]

    def _raw(self):
        return ''.join('%02X' % ordinal(_) for _ in self.pack())


class GenericBGPLS(BGPLS):
    def __init__(self, code, packed):
        BGPLS.__init__(self)
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
