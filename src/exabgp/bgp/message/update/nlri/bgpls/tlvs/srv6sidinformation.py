"""srv6sidinformation.py

Created by Quentin De Muynck
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

from __future__ import annotations


from exabgp.protocol.ip import IPv6

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
    def __init__(self, sid, packed=None):
        self.sid = sid

    @classmethod
    def unpack_srv6sid(cls, data):
        sid = IPv6.ntop(data)
        return cls(sid)

    def json(self, compact: bool = False):
        return '"srv6-sid": "{}"'.format(str(self.sid))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Srv6SIDInformation):
            return False
        return self.sid == other.sid

    def __lt__(self, other):
        raise RuntimeError('Not implemented')

    def __le__(self, other):
        raise RuntimeError('Not implemented')

    def __gt__(self, other):
        raise RuntimeError('Not implemented')

    def __ge__(self, other):
        raise RuntimeError('Not implemented')

    def __str__(self):
        return str(self.sid)

    def __repr__(self):
        return self.__str__()

    def __len__(self):
        return len(self.sid)

    def __hash__(self):
        return hash(str(self))

    def pack_tlv(self):
        raise RuntimeError('Not implemented')
