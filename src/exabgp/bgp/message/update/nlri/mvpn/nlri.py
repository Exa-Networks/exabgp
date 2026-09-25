from __future__ import annotations

from struct import pack

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message import Action

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.ip import IPv4
from exabgp.protocol.ip import IPv6

# https://datatracker.ietf.org/doc/html/rfc6514

# +-----------------------------------+
# |    Route Type (1 octet)           |
# +-----------------------------------+
# |     Length (1 octet)              |
# +-----------------------------------+
# | Route Type specific (variable)    |
# +-----------------------------------+

# RFC 6514 sections 4.3, 4.5, 4.6 and 4.7 all end the same way: a Multicast Source
# Length or Multicast Group Length octet is 32 when the address which follows is IPv4
# and 128 when it is IPv6, and "usage of other values [...] is outside the scope of this
# document".
MVPN_ADDRESS_LENGTH_BITS = (IPv4.BITS, IPv6.BITS)


def check_source_and_group(packed, cursor, name):
    """Check the Multicast Source and Multicast Group of a route which carries both.

    The octet is compared against 32 and 128 rather than its quotient by eight, because a
    quotient accepts far more than the RFC defines: 33 to 39 divide to four octets and are
    read back as an IPv4 address the peer never sent, and 129 to 135 divide to sixteen and
    move the cursor past the end of an eighteen octet payload, where the address is built
    from a short slice and IP.unpack raises ValueError instead of the session being closed
    with a NOTIFICATION.

    `cursor` is the offset of the Multicast Source Length octet within `packed`.
    """
    for field in ('Multicast Source', 'Multicast Group'):
        if cursor >= len(packed):
            raise Notify(3, 5, f'{name} is too short to hold its {field} Length octet.')
        bits = packed[cursor]
        if bits not in MVPN_ADDRESS_LENGTH_BITS:
            raise Notify(
                3,
                5,
                f'Unsupported {name} {field} IP length ({bits} bits). Expected 32 bits (IPv4) or 128 bits (IPv6).',
            )
        cursor += 1 + bits // 8
    if cursor != len(packed):
        raise Notify(3, 5, f'{name} length does not match its Multicast Source and Multicast Group addresses.')


# ========================================================================= MVPN


@NLRI.register(AFI.ipv4, SAFI.mcast_vpn)
@NLRI.register(AFI.ipv6, SAFI.mcast_vpn)
class MVPN(NLRI):
    registered_mvpn = dict()

    HEADER_SIZE = 2  # Route Type(1) + Length(1)

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

    def as_dict(self):
        family = self.family().afi_safi()
        return {
            'code': self.CODE,
            'parsed': False,
            'raw': self._raw(),
            'name': self.NAME,
            'family': {'afi': str(family[0]), 'safi': str(family[1])},
        }

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
        # RFC 7911 section 3: with ADD-PATH negotiated the peer puts a four byte Path
        # Identifier in front of every NLRI of this family, and it has to come off
        # before the NLRI is read.
        path_info, bgp = NLRI.consume_path_information(bgp, addpath)
        if len(bgp) < cls.HEADER_SIZE:
            raise Notify(3, 10, 'not enough data to extract the header of the mvpn NLRI')

        code = bgp[0]
        length = bgp[1]

        if len(bgp) < length + cls.HEADER_SIZE:
            raise Notify(3, 10, 'the mvpn NLRI announces more data than it carries')

        if code in cls.registered_mvpn:
            klass = cls.registered_mvpn[code].unpack(bgp[2 : length + 2], afi)
        else:
            klass = GenericMVPN(afi, code, bgp[2 : length + 2])
        klass.CODE = code
        klass.action = action
        klass.addpath = path_info

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
