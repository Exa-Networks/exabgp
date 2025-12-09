"""sr/labelindex.py

Created by Evelio Vila 2017-02-16
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from typing import ClassVar

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


@PrefixSid.register_sr()
class SrLabelIndex:
    TLV: ClassVar[int] = 1
    LENGTH: ClassVar[int] = 7

    def __init__(self, packed: bytes) -> None:
        if len(packed) != self.LENGTH:
            raise ValueError(f'SrLabelIndex requires exactly {self.LENGTH} bytes, got {len(packed)}')
        self._packed: bytes = packed

    @classmethod
    def make_labelindex(cls, labelindex: int) -> 'SrLabelIndex':
        """Factory method for semantic construction."""
        reserved, flags = 0, 0
        packed = pack('!B', reserved) + pack('!H', flags) + pack('!I', labelindex)
        return cls(packed)

    @property
    def labelindex(self) -> int:
        """Label index value (unpacked from bytes 3-7)."""
        value: int = unpack('!I', self._packed[3:7])[0]
        return value

    def __repr__(self) -> str:
        return '{}'.format(self.labelindex)

    def pack_tlv(self) -> bytes:
        return pack('!B', self.TLV) + pack('!H', self.LENGTH) + self._packed

    @classmethod
    def unpack_attribute(cls, data: bytes, length: int) -> SrLabelIndex:
        if length != cls.LENGTH:
            raise Notify(3, 5, f'Invalid TLV size. Should be {cls.LENGTH} but {length} received')
        # Data is: Reserved(1) + Flags(2) + LabelIndex(4) = 7 bytes
        # Validation happens in __init__
        return cls(data)

    def json(self, compact: bool = False) -> str:
        return '"sr-label-index": %d' % (self.labelindex)
