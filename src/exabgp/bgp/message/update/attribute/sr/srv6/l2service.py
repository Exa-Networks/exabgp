"""srv6/l2service.py

Created by Ryoga Saito 2022-02-24
Copyright (c) 2022 Ryoga Saito. All rights reserved.
"""

from __future__ import annotations

from struct import pack, unpack
from typing import Any, Callable, ClassVar, Dict, List, Optional, Type

from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid
from exabgp.bgp.message.update.attribute.sr.srv6.generic import GenericSrv6ServiceSubTlv

# 2.  SRv6 Services TLVs
#
#  0                   1                   2                   3
#  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |   TLV Type    |         TLV Length            |   RESERVED    |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |   SRv6 Service Sub-TLVs                                      //
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#                   Figure 1: SRv6 Service TLVs


@PrefixSid.register()
class Srv6L2Service:
    TLV: ClassVar[int] = 6

    registered_subtlvs: ClassVar[Dict[int, Type[Any]]] = dict()

    def __init__(self, subtlvs: List[Any], packed: Optional[bytes] = None) -> None:
        self.subtlvs: List[Any] = subtlvs
        self.packed: bytes = self.pack()

    @classmethod
    def register(cls) -> Callable[[Type[Any]], Type[Any]]:
        def register_subtlv(klass: Type[Any]) -> Type[Any]:
            scode: int = klass.TLV
            if scode in cls.registered_subtlvs:
                raise RuntimeError('only one class can be registered per SRv6 Service Sub-TLV type')
            cls.registered_subtlvs[scode] = klass
            return klass

        return register_subtlv

    @classmethod
    def unpack(cls, data: bytes, length: int) -> Srv6L2Service:
        subtlvs: List[Any] = []

        # First byte is reserved
        data = data[1:]
        while data:
            code: int = data[0]
            length = unpack('!H', data[1:3])[0]
            if code in cls.registered_subtlvs:
                subtlv: Any = cls.registered_subtlvs[code].unpack(data[3 : length + 3], length)
            else:
                subtlv = GenericSrv6ServiceSubTlv(code, data[3 : length + 3])
            subtlvs.append(subtlv)
            data = data[length + 3 :]

        return cls(subtlvs=subtlvs)

    def pack(self) -> bytes:
        subtlvs_packed: bytes = b''.join([_.pack() for _ in self.subtlvs])
        length: int = len(subtlvs_packed) + 1
        reserved: int = 0

        return pack('!B', self.TLV) + pack('!H', length) + pack('!B', reserved) + subtlvs_packed

    def __str__(self) -> str:
        return 'l2-service [ ' + ', '.join([str(subtlv) for subtlv in self.subtlvs]) + ' ]'

    def json(self, compact: Optional[bool] = None) -> str:
        content: str = '[ ' + ', '.join(subtlv.json() for subtlv in self.subtlvs) + ' ]'
        return '"l2-service": {}'.format(content)
