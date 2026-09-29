"""refresh.py

Created by Thomas Mangin on 2012-07-19.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack
from typing import TYPE_CHECKING, Generator

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.message import Message
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.capability import Capability
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

    # the Reserved field, the RFC 7313 Message Subtype
    REQUEST = Reserved.ROUTE_REFRESH_QUERY
    BEGIN = Reserved.ROUTE_REFRESH_BEGIN
    END = Reserved.ROUTE_REFRESH_END

    FIXED_SIZE = 4  # RFC 2918 3: AFI, Reserved (the RFC 7313 Message Subtype) and SAFI
    LENGTH_MAX = Message.HEADER_LEN + FIXED_SIZE
    # RFC 7313 5 gives a wrong length an error of its own, which only the decoder can pick
    HEADER_CHECKS_LENGTH = False

    def __init__(self, packed: Buffer) -> None:
        if len(packed) != self.FIXED_SIZE:
            raise ValueError(f'RouteRefresh requires exactly {self.FIXED_SIZE} bytes, got {len(packed)}')
        self._packed = packed

    @classmethod
    def make_route_refresh(cls, afi: int, safi: int, reserved: int = 0) -> 'RouteRefresh':
        afi_obj = AFI.from_int(afi)
        safi_obj = SAFI.from_int(safi)
        packed = afi_obj.pack_afi() + bytes([reserved]) + safi_obj.pack_safi()
        return cls(packed)

    @property
    def afi(self) -> AFI:
        return AFI.from_int(unpack('!H', self._packed[0:2])[0])

    @property
    def safi(self) -> SAFI:
        return SAFI.from_int(self._packed[3])

    @property
    def reserved(self) -> Reserved:
        return Reserved(self._packed[2])

    def pack_body(self, negotiated: Negotiated) -> Buffer:
        return self._packed

    def messages(self, negotiated: Negotiated, include_withdraw: bool) -> Generator[bytes, None, None]:
        yield self.pack_message(negotiated)

    def __str__(self) -> str:
        return 'REFRESH'

    def extensive(self) -> str:
        return 'route refresh %s/%d/%s' % (self.afi, self.reserved, self.safi)

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: Negotiated) -> RouteRefresh:
        # An unknown subtype is not an error here, the RFC says it is ignored, which is
        # RouteRefreshHandler's decision since only it knows what was negotiated
        if len(data) != cls.FIXED_SIZE:
            raise cls._wrong_length(data, negotiated)
        return cls(data)

    @classmethod
    def _wrong_length(cls, data: Buffer, negotiated: Negotiated) -> Notify:
        """What a body which is not four octets is answered with, which depends on the peer.

        RFC 7313 5 "is applicable only when a BGP speaker has received the Enhanced Route
        Refresh Capability", so it is the peer's OPEN which is asked, not what was
        negotiated.  Then Invalid Message Length, whatever the subtype: a body of the wrong
        size has no subtype to trust.  The Data field "MUST contain the complete
        ROUTE-REFRESH message", and the header held nothing the body does not give back.

        Without it RFC 2918 gives no error, and the answer is the one RFC 4271 6.1 gives
        the other types: Bad Message Length, the Data field the Length field.
        """
        received = negotiated.received_open
        if received is not None and received.capabilities.announced(Capability.CODE.ENHANCED_ROUTE_REFRESH):
            return Notify(7, 1, f'ROUTE-REFRESH body of {len(data)} octets', data=cls.frame(cls.ID, data))
        length = cls.HEADER_LEN + len(data)
        return Notify(1, 2, f'ROUTE-REFRESH body of {len(data)} octets', data=pack('!H', length))
