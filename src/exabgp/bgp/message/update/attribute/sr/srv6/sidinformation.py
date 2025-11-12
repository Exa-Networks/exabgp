"""srv6/sidinformation.py

Created by Ryoga Saito 2022-02-24
Copyright (c) 2022 Ryoga Saito. All rights reserved.
"""

from __future__ import annotations

from struct import pack, unpack
from typing import Any, Callable, ClassVar, Dict, List, Optional, Type

from exabgp.protocol.ip import IPv6

from exabgp.bgp.message.update.attribute.sr.srv6.l2service import Srv6L2Service
from exabgp.bgp.message.update.attribute.sr.srv6.l3service import Srv6L3Service
from exabgp.bgp.message.update.attribute.sr.srv6.generic import GenericSrv6ServiceDataSubSubTlv

# 3.1.  SRv6 SID Information Sub-TLV
#
#  0                   1                   2                   3
#  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | SRv6 Service  |    SRv6 Service               |               |
# | Sub-TLV       |    Sub-TLV                    |               |
# | Type=1        |    Length                     |  RESERVED1    |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |  SRv6 SID Value (16 octets)                                  //
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | Svc SID Flags |   SRv6 Endpoint Behavior      |   RESERVED2   |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |  SRv6 Service Data Sub-Sub-TLVs                              //
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

#            Figure 3: SRv6 SID Information Sub-TLV


@Srv6L2Service.register()
@Srv6L3Service.register()
class Srv6SidInformation:
    TLV: ClassVar[int] = 1

    registered_subsubtlvs: ClassVar[Dict[int, Type[Any]]] = dict()

    def __init__(self, sid: IPv6, behavior: int, subsubtlvs: List[Any], packed: Optional[bytes] = None) -> None:
        self.sid: IPv6 = sid
        self.behavior: int = behavior
        self.subsubtlvs: List[Any] = subsubtlvs
        self.packed: bytes = self.pack()

    @classmethod
    def register(cls) -> Callable[[Type[Any]], Type[Any]]:
        def register_subsubtlv(klass: Type[Any]) -> Type[Any]:
            code: int = klass.TLV
            if code in cls.registered_subsubtlvs:
                raise RuntimeError('only one class can be registered per SRv6 Service Sub-Sub-TLV type')
            cls.registered_subsubtlvs[code] = klass
            return klass

        return register_subsubtlv

    @classmethod
    def unpack(cls, data: bytes, length: int) -> Srv6SidInformation:
        sid: IPv6 = IPv6.unpack(data[1:17])
        behavior: int = unpack('!H', data[18:20])[0]
        subsubtlvs: List[Any] = []

        data = data[21:]
        while data:
            code: int = data[0]
            length = unpack('!H', data[1:3])[0]
            if code in cls.registered_subsubtlvs:
                subsubtlv: Any = cls.registered_subsubtlvs[code].unpack(data[3 : length + 3], length)
            else:
                subsubtlv = GenericSrv6ServiceDataSubSubTlv(code, data[3 : length + 3])
            subsubtlvs.append(subsubtlv)
            data = data[length + 3 :]

        return cls(sid=sid, behavior=behavior, subsubtlvs=subsubtlvs)

    def pack(self) -> bytes:
        subsubtlvs_packed: bytes = b''.join([_.pack() for _ in self.subsubtlvs])
        length: int = len(subsubtlvs_packed) + 21
        reserved: int = 0
        flags: int = 0

        return (
            pack('!B', self.TLV)
            + pack('!H', length)
            + pack('!B', reserved)
            + self.sid.pack()
            + pack('!B', flags)
            + pack('!H', self.behavior)
            + pack('!B', reserved)
            + subsubtlvs_packed
        )

    def __str__(self) -> str:
        s: str = 'sid-information [ sid:{} flags:0 endpoint_behavior:0x{:x} '.format(str(self.sid), self.behavior)
        if len(self.subsubtlvs) != 0:
            s += ' [ ' + ', '.join([str(subsubtlv) for subsubtlv in self.subsubtlvs]) + ' ]'
        s + ' ]'
        return s

    def json(self, compact: Optional[bool] = None) -> str:
        s: str = '{ "sid": "%s", "flags": 0, "endpoint_behavior": %d'
        content: str = ', '.join(subsubtlv.json() for subsubtlv in self.subsubtlvs)
        if content:
            s += ', {}'.format(content)
        s += ' }'
        return s
