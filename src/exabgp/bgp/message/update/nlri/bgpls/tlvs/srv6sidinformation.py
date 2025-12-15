"""srv6sidinformation.py

Created by Quentin De Muynck
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

from __future__ import annotations


from exabgp.protocol.ip import IPv6
from exabgp.util.types import Buffer

#     RFC 9514 6.1.  SRv6 SID Information TLV
#     0                   1                   2                   3
#     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |               Type            |          Length               |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |    SID (16 octets) ...                                        |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |    SID (cont ...)                                             |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |    SID (cont ...)                                             |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |    SID (cont ...)                                             |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#                  Figure 6: SRv6 SID Information TLV Format


class Srv6SIDInformation:
    def __init__(self, sid: str, packed: Buffer) -> None:
        self.sid = sid
        self._packed = packed

    @classmethod
    def unpack_srv6sid(cls, data: Buffer) -> 'Srv6SIDInformation':
        sid = IPv6.ntop(data)
        return cls(sid, data)

    def json(self, compact: bool = False) -> str:
        return '"srv6-sid": "{}"'.format(str(self.sid))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Srv6SIDInformation):
            return NotImplemented
        return self.sid == other.sid

    def __lt__(self, other: Srv6SIDInformation) -> bool:
        raise RuntimeError('Not implemented')

    def __le__(self, other: Srv6SIDInformation) -> bool:
        raise RuntimeError('Not implemented')

    def __gt__(self, other: Srv6SIDInformation) -> bool:
        raise RuntimeError('Not implemented')

    def __ge__(self, other: Srv6SIDInformation) -> bool:
        raise RuntimeError('Not implemented')

    def __str__(self) -> str:
        return str(self.sid)

    def __repr__(self) -> str:
        return self.__str__()

    def __len__(self) -> int:
        return len(self._packed)

    def __hash__(self) -> int:
        return hash(str(self))

    def pack_tlv(self) -> bytes:
        return self._packed
