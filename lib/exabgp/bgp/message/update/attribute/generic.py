# encoding: utf-8
"""
generic.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from exabgp.util import character
from exabgp.util import ordinal
from exabgp.util import concat_bytes
from exabgp.util import hexstring
from exabgp.bgp.message.update.attribute.attribute import Attribute


# ============================================================= GenericAttribute
#


class GenericAttribute(Attribute):
    __slots__ = ['ID', 'FLAG', 'data', 'index']

    GENERIC = True

    def __init__(self, code, flag, data):
        self.ID = code
        self.FLAG = flag
        self.data = data
        self.index = ''

    def __eq__(self, other):
        return self.ID == other.ID and self.FLAG == other.FLAG and self.data == other.data

    def __ne__(self, other):
        return not self.__eq__(other)

    def pack(self, negotiated=None):
        flag = self.FLAG
        length = len(self.data)
        if length > 0xFF:
            flag |= Attribute.Flag.EXTENDED_LENGTH
        if flag & Attribute.Flag.EXTENDED_LENGTH:
            len_value = pack('!H', length)
        else:
            len_value = character(length)
        return concat_bytes(character(flag), character(self.ID), len_value, self.data)

    def __len__(self):
        return len(self.data)

    def __repr__(self):
        return '0x' + ''.join('%02x' % ordinal(_) for _ in self.data)

    @classmethod
    def unpack(cls, code, flag, data):
        return cls(code, flag, data)

    def json(self):
        return '{ "id": %d, "flag": %d, "payload": "%s"}' % (self.ID, self.FLAG, hexstring(self.data))
