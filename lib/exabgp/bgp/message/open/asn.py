# encoding: utf-8
"""
asn.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from struct import unpack
import sys

from exabgp.protocol.resource import Resource

if sys.version_info > (3,):
    long = int

# =================================================================== ASN


class ASN(Resource):
    MAX = pow(2, 16) - 1

    def asn4(self):
        return self > self.MAX

    def pack(self, negotiated=None):
        asn4 = negotiated if negotiated is not None else self.asn4()
        return pack('!L' if asn4 else '!H', self)

    @classmethod
    def unpack(cls, data, klass=None):
        kls = cls if klass is None else klass
        value = unpack('!L' if len(data) == 4 else '!H', data)[0]
        return kls(value)

    def __len__(self):
        return 4 if self.asn4() else 2

    def extract(self):
        return [pack('!L', self)]

    def trans(self):
        if self.asn4():
            return AS_TRANS
        return self

    def __repr__(self):
        return '%ld' % long(self)

    def __str__(self):
        return '%ld' % long(self)

    @classmethod
    def from_string(cls, value):
        return cls(long(value))


AS_TRANS = ASN(23456)
