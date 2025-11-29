"""ospfroute.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack


#     https://tools.ietf.org/html/rfc7752#section-3.2.3

#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |  Route Type   |
#     +-+-+-+-+-+-+-+-+

#  Route Type can be:
#    Intra-Area (0x1)
#    Inter-Area (0x2)
#    External 1 (0x3)
#    External 2 (0x4)
#    NSSA 1 (0x5)
#    NSSA 2 (0x6)

# ================================================================== OSPF_ROUTE_TYPE


OSPF_ROUTE = {1: 'intra-area', 2: 'inter-area', 3: 'external-1', 4: 'external-2', 5: 'nssa-1', 6: 'nssa-2'}


class OspfRoute:
    def __init__(self, ospf_type: int, packed: bytes | None = None) -> None:
        self.ospf_type = ospf_type
        self._packed = packed if packed is not None else pack('!B', ospf_type)

    @classmethod
    def unpack_ospfroute(cls, data: bytes) -> 'OspfRoute':
        if len(data) == 1:
            ospf_type = unpack('!B', data[0:1])[0]
        return cls(ospf_type=ospf_type, packed=data)

    def json(self):
        content = '"ospf-route-type": {}'.format(self.ospf_type)
        return content

    def __eq__(self, other: 'OspfRoute') -> bool:  # type: ignore[override]
        return self.ospf_type == other.ospf_type

    def __lt__(self, other):
        raise RuntimeError('Not implemented')

    def __le__(self, other):
        raise RuntimeError('Not implemented')

    def __gt__(self, other):
        raise RuntimeError('Not implemented')

    def __ge__(self, other):
        raise RuntimeError('Not implemented')

    def __str__(self):
        return ':'.join('{:02X}'.format(_) for _ in self._packed)

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return hash(str(self))

    def pack_tlv(self):
        return self._packed
