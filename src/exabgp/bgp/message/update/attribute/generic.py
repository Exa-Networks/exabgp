"""generic.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, ClassVar, Optional, Type

from struct import pack
from exabgp.util import hexstring
from exabgp.bgp.message.update.attribute.attribute import Attribute

# ============================================================= GenericAttribute
#

# Attribute length threshold for extended length encoding
MAX_SINGLE_OCTET_LENGTH: int = 0xFF  # Maximum value that fits in a single byte (255)


class GenericAttribute(Attribute):
    GENERIC: ClassVar[bool] = True

    ID: int
    FLAG: int
    data: bytes
    index: str

    def __init__(self, code: int, flag: int, data: bytes) -> None:
        self.ID = code
        self.FLAG = flag
        self.data = data
        self.index = ''

    def __eq__(self, other: Any) -> bool:
        return self.ID == other.ID and self.FLAG == other.FLAG and self.data == other.data

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def pack(self, negotiated: Optional[Any] = None) -> bytes:
        flag: int = self.FLAG
        length: int = len(self.data)
        if length > MAX_SINGLE_OCTET_LENGTH:
            flag |= Attribute.Flag.EXTENDED_LENGTH
        len_value: bytes
        if flag & Attribute.Flag.EXTENDED_LENGTH:
            len_value = pack('!H', length)
        else:
            len_value = bytes([length])
        return bytes([flag, self.ID]) + len_value + self.data

    def __len__(self) -> int:
        return len(self.data)

    def __repr__(self) -> str:
        return '0x' + ''.join('{:02x}'.format(_) for _ in self.data)

    @classmethod
    def unpack(cls: Type[GenericAttribute], code: int, flag: int, data: bytes) -> GenericAttribute:
        return cls(code, flag, data)

    def json(self) -> str:
        return '{ "id": %d, "flag": %d, "payload": "%s"}' % (self.ID, self.FLAG, hexstring(self.data))
