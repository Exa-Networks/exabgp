
"""
nlri.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from __future__ import annotations

from struct import pack
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.nlri import NLRI

# https://datatracker.ietf.org/doc/draft-mpmz-bess-mup-safi/02/

# +-----------------------------------+
# |    Architecture Type (1 octet)    |
# +-----------------------------------+
# |       Route Type (2 octets)       |
# +-----------------------------------+
# |         Length (1 octet)          |
# +-----------------------------------+
# |  Route Type specific (variable)   |
# +-----------------------------------+


@NLRI.register(AFI.ipv4, SAFI.mup)
@NLRI.register(AFI.ipv6, SAFI.mup)
class MUP(NLRI):
    registered = dict()

    # NEED to be defined in the subclasses
    ARCHTYPE = 0
    CODE = 0
    NAME = 'Unknown'
    SHORT_NAME = 'unknown'

    def __init__(self, afi, action=Action.ANNOUNCE):
        NLRI.__init__(self, afi, SAFI.mup, action)
        self._packed = b''

    def __hash__(self):
        return hash('%s:%s:%s:%s:%s' % (self.afi, self.safi, self.ARCHTYPE, self.CODE, self._packed))

    def __len__(self):
        return len(self._packed) + 2

    def __eq__(self, other):
        return NLRI.__eq__(self, other) and self.CODE == other.CODE

    def __str__(self):
        return 'mup:%s:%s' % (
            self.registered.get(self.CODE, self).SHORT_NAME.lower(),
            '0x' + ''.join('%02x' % _ for _ in self._packed),
        )

    def __repr__(self):
        return str(self)

    def feedback(self, action):
        return ''

    def _prefix(self):
        return 'mup:%s:' % (self.registered.get(self.CODE, self).SHORT_NAME.lower())

    def pack_nlri(self, negotiated=None):
        return pack('!BHB', self.ARCHTYPE, self.CODE, len(self._packed)) + self._packed

    @classmethod
    def register(cls, klass):
        key = '%s:%s' % (klass.ARCHTYPE, klass.CODE)
        if key in cls.registered:
            raise RuntimeError('only one Mup registration allowed')
        cls.registered[key] = klass
        return klass

    @classmethod
    def unpack_nlri(cls, afi, safi, bgp, action, addpath):
        arch = bgp[0]
        code = int.from_bytes(bgp[1:3], 'big')
        length = bgp[3]

        # arch and code byte size is 4 byte
        end = length + 4
        key = '%s:%s' % (arch, code)
        if key in cls.registered:
            klass = cls.registered[key].unpack(bgp[4:end], afi)
        else:
            klass = GenericMUP(arch, afi, code, bgp[4:end])
        klass.CODE = code
        klass.action = action
        klass.addpath = addpath

        return klass, bgp[end:]

    def _raw(self):
        return ''.join('%02X' % _ for _ in self.pack_nlri())


class GenericMUP(MUP):
    def __init__(self, afi, arch, code, packed):
        MUP.__init__(self, afi)
        self.ARCHTYPE = arch
        self.CODE = code
        self._pack(packed)

    def _pack(self, packed=None):
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

    def json(self, compact=None):
        return '{ "arch": %d, "code": %d, "raw": "%s" }' % (self.ARCHTYPE, self.CODE, self._raw())
