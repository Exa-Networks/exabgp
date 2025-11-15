"""sr/labelindex.py

Created by Evelio Vila 2017-02-16
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from typing import ClassVar, Optional

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
    TLV: ClassVar[int] = 1
    LENGTH: ClassVar[int] = 7

    def __init__(self, labelindex: int, packed: Optional[bytes] = None) -> None:
        self.labelindex: int = labelindex
        self.packed: bytes = self.pack_tlv()

    def __repr__(self) -> str:
        return '{}'.format(self.labelindex)

    def pack_tlv(self) -> bytes:
        reserved, flags = 0, 0
        return (
            pack('!B', self.TLV)
            + pack('!H', self.LENGTH)
            + pack('!B', reserved)
            + pack('!H', flags)
            + pack('!I', self.labelindex)
        )

    @classmethod
    def unpack_attribute(cls, data: bytes, length: int) -> SrLabelIndex:
        labelindex = -1
        if length != cls.LENGTH:
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

    def json(self, compact: bool = False) -> str:
        return '"sr-label-index": %d' % (self.labelindex)
