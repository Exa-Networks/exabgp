"""asn.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack

from exabgp.protocol.resource import Resource

# =================================================================== ASN


class ASN(Resource):
    MAX = pow(2, 16) - 1

    # ASN encoding size constants
    SIZE_4BYTE = 4  # 4-byte ASN encoding size
    SIZE_2BYTE = 2  # 2-byte ASN encoding size

    def asn4(self):
        return self > self.MAX

    def pack(self, negotiated=None):
        asn4 = negotiated if negotiated is not None else self.asn4()
        return pack('!L' if asn4 else '!H', self)

    @classmethod
    def unpack(cls, data, klass=None):
        kls = cls if klass is None else klass
        value = unpack('!L' if len(data) == cls.SIZE_4BYTE else '!H', data)[0]
        return kls(value)

    def __len__(self):
        return self.SIZE_4BYTE if self.asn4() else self.SIZE_2BYTE

    def extract(self):
        return [pack('!L', self)]

    def trans(self):
        if self.asn4():
            return AS_TRANS
        return self

    def __repr__(self):
        return '%ld' % int(self)

    def __str__(self):
        return '%ld' % int(self)

    @classmethod
    def from_string(cls, value):
        return cls(int(value))


AS_TRANS = ASN(23456)
