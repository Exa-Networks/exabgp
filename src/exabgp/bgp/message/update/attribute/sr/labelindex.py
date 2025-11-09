
"""
sr/labelindex.py

Created by Evelio Vila 2017-02-16
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import pack, unpack

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid

# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |       Type    |             Length            |   RESERVED    |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |            Flags              |       Label Index             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |          Label Index          |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# 3.1.  Label-Index TLV


@PrefixSid.register()
class SrLabelIndex:
    TLV = 1
    LENGTH = 7

    def __init__(self, labelindex, packed=None):
        self.labelindex = labelindex
        self.packed = self.pack()

    def __repr__(self):
        return '%s' % (self.labelindex)

    def pack(self):
        reserved, flags = 0, 0
        return (
            pack('!B', self.TLV)
            + pack('!H', self.LENGTH)
            + pack('!B', reserved)
            + pack('!H', flags)
            + pack('!I', self.labelindex)
        )

    @classmethod
    def unpack(cls, data, length):
        labelindex = -1
        if cls.LENGTH != length:
            raise Notify(3, 5, f'Invalid TLV size. Should be 7 but {length} received')
        # Shift reserved bits
        data = data[1:]
        # Shift Flags
        # Flags: 16 bits of flags.  None is defined by this document.  The
        # flag field MUST be clear on transmission and MUST be ignored at
        # reception.
        data = data[2:6]
        labelindex = unpack('!I', data)[0]
        return cls(labelindex=labelindex, packed=data)

    def json(self, compact=None):
        return '"sr-label-index": %d' % (self.labelindex)
