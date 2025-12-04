"""refresh.py

Created by Thomas Mangin on 2012-07-19.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import error, unpack
from typing import Generator, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.message import Message
from exabgp.bgp.message.notification import Notify
from exabgp.protocol.family import AFI, SAFI

# =================================================================== Notification
# A Notification received from our peer.
# RFC 4271 Section 4.5


class Reserved(int):
    # Route Refresh reserved field values (RFC 2918, RFC 7313)
    ROUTE_REFRESH_QUERY = 0  # Normal route refresh request
    ROUTE_REFRESH_BEGIN = 1  # Beginning of Route Refresh (BoRR)
    ROUTE_REFRESH_END = 2  # End of Route Refresh (EoRR)

    def __str__(self) -> str:
        if self == self.ROUTE_REFRESH_QUERY:
            return 'query'
        if self == self.ROUTE_REFRESH_BEGIN:
            return 'begin'
        if self == self.ROUTE_REFRESH_END:
            return 'end'
        return 'invalid'


@Message.register
class RouteRefresh(Message):
    ID = Message.CODE.ROUTE_REFRESH
    TYPE = bytes([Message.CODE.ROUTE_REFRESH])

    # Reserved field values for route refresh subtypes
    request = 0
    start = 1
    end = 2

    def __init__(self, packed: bytes) -> None:
        if len(packed) != 4:
            raise ValueError(f'RouteRefresh requires exactly 4 bytes, got {len(packed)}')
        self._packed = packed

    @classmethod
    def make_route_refresh(cls, afi: int, safi: int, reserved: int = 0) -> 'RouteRefresh':
        afi_obj = AFI.create(afi)
        safi_obj = SAFI.create(safi)
        packed = afi_obj.pack_afi() + bytes([reserved]) + safi_obj.pack_safi()
        return cls(packed)

    @property
    def afi(self) -> AFI:
        return AFI.create(unpack('!H', self._packed[0:2])[0])

    @property
    def safi(self) -> SAFI:
        return SAFI.create(self._packed[3])

    @property
    def reserved(self) -> Reserved:
        return Reserved(self._packed[2])

    def pack_message(self, negotiated: Negotiated) -> bytes:
        return self._message(self._packed)

    def messages(self, negotiated: Negotiated, include_withdraw: bool) -> Generator[bytes, None, None]:
        yield self.pack_message(negotiated)

    def __str__(self) -> str:
        return 'REFRESH'

    def extensive(self) -> str:
        return 'route refresh %s/%d/%s' % (self.afi, self.reserved, self.safi)

    # XXX: Check how we get this data into the RR
    # def families (self):
    # 	return self._families[:]

    @classmethod
    def unpack_message(cls, data: bytes, negotiated: Negotiated) -> RouteRefresh:
        try:
            afi, reserved, safi = unpack('!HBB', data)
        except error:
            raise Notify(7, 1, 'invalid route-refresh message') from None
        if reserved not in (0, 1, 2):
            raise Notify(7, 2, 'invalid route-refresh message subtype')
        return cls(data)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RouteRefresh):
            return False
        return self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)
