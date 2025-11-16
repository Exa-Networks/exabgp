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

    request = 0
    start = 1
    end = 2

    def __init__(self, afi: int, safi: int, reserved: int = 0) -> None:
        self.afi = AFI.create(afi)
        self.safi = SAFI.create(safi)
        self.reserved = Reserved(reserved)

    def pack_message(self, negotiated: Negotiated) -> bytes:
        return self._message(self.afi.pack_afi() + bytes([self.reserved]) + self.safi.pack_safi())

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
        return RouteRefresh(afi, safi, reserved)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RouteRefresh):
            return False
        if self.afi != other.afi:
            return False
        if self.safi != other.safi:
            return False
        if self.reserved != other.reserved:
            return False
        return True

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)
