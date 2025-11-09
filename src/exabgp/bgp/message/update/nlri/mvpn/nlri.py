from __future__ import annotations

from struct import pack

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message import Action

from exabgp.bgp.message.update.nlri import NLRI

# https://datatracker.ietf.org/doc/html/rfc6514

# +-----------------------------------+
# |    Route Type (1 octet)           |
# +-----------------------------------+
# |     Length (1 octet)              |
# +-----------------------------------+
# | Route Type specific (variable)    |
# +-----------------------------------+

# ========================================================================= MVPN


@NLRI.register(AFI.ipv4, SAFI.mcast_vpn)
@NLRI.register(AFI.ipv6, SAFI.mcast_vpn)
class MVPN(NLRI):
    registered_mvpn = dict()

    # NEED to be defined in the subclasses
    CODE = -1
    NAME = 'Unknown'
    SHORT_NAME = 'unknown'

    def __init__(self, afi, action=Action.UNSET, addpath=None):
        NLRI.__init__(self, afi=afi, safi=SAFI.mcast_vpn, action=action)
        self._packed = b''

    def __hash__(self):
        return hash('{}:{}:{}:{}'.format(self.afi, self.safi, self.CODE, self._packed))

    def __len__(self):
        return len(self._packed) + 2

    def __eq__(self, other):
        return NLRI.__eq__(self, other) and self.CODE == other.CODE

    def __str__(self):
        return 'mvpn:{}:{}'.format(
            self.registered_mvpn.get(self.CODE, self).SHORT_NAME.lower(),
            '0x' + ''.join('{:02x}'.format(_) for _ in self._packed),
        )

    def __repr__(self):
        return str(self)

    def feedback(self, action):
        # if self.nexthop is None and action == Action.ANNOUNCE:
        # 	return 'mvpn nlri next-hop is missing'
        return ''

    def _prefix(self):
        return 'mvpn:{}:'.format(self.registered_mvpn.get(self.CODE, self).SHORT_NAME.lower())

    def pack_nlri(self, negotiated=None):
        # XXX: addpath not supported yet
        return pack('!BB', self.CODE, len(self._packed)) + self._packed

    @classmethod
    def register(cls, klass):
        if klass.CODE in cls.registered_mvpn:
            raise RuntimeError('only one MVPN registration allowed')
        cls.registered_mvpn[klass.CODE] = klass
        return klass

    @classmethod
    def unpack_nlri(cls, afi, safi, bgp, action, addpath):
        code = bgp[0]
        length = bgp[1]

        if code in cls.registered_mvpn:
            klass = cls.registered_mvpn[code].unpack(bgp[2 : length + 2], afi)
        else:
            klass = GenericMVPN(afi, code, bgp[2 : length + 2])
        klass.CODE = code
        klass.action = action
        klass.addpath = addpath

        return klass, bgp[length + 2 :]

    def _raw(self):
        return ''.join('{:02X}'.format(_) for _ in self.pack_nlri())


class GenericMVPN(MVPN):
    def __init__(self, afi, code, packed):
        MVPN.__init__(self, afi)
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
