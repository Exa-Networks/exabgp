"""eor.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.message import Message
from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP

# =================================================================== End-Of-RIB
# not technically a different message type but easier to treat as one


class EOR(Message):
    ID = Message.CODE.UPDATE
    TYPE = bytes([Message.CODE.UPDATE])
    EOR: bool = True  # End-of-RIB marker (Update has EOR = False)

    class EOR_NLRI(NLRI):
        PREFIX: bytes = b'\x00\x00\x00\x07\x90\x0f\x00\x03'
        MP_LENGTH: int = len(PREFIX) + 1 + 2  # len(AFI) and len(SAFI)
        EOR: bool = True  # Override class variable

        nexthop = IP.NoNextHop

        def __init__(self, afi: AFI, safi: SAFI, action: Action) -> None:
            NLRI.__init__(self, afi, safi, action)
            self.action = action
            self.afi = afi
            self.safi = safi

        def pack_nlri(self, negotiated: 'Negotiated') -> Buffer:
            # EOR (End-of-RIB) marker - addpath not applicable
            if self.afi == AFI.ipv4 and self.safi == SAFI.unicast:
                return b'\x00\x00\x00\x00'
            return self.PREFIX + self.afi.pack_afi() + self.safi.pack_safi()

        def __repr__(self) -> str:
            return self.extensive()

        def extensive(self) -> str:
            return 'eor %ld/%ld (%s %s)' % (int(self.afi), int(self.safi), self.afi, self.safi)

        def json(self, compact: bool = False) -> str:
            return '"eor": {{ "afi" : "{}", "safi" : "{}" }}'.format(self.afi, self.safi)

        def __len__(self) -> int:
            if self.afi == AFI.ipv4 and self.safi == SAFI.unicast:
                # May not have been the size read on the wire if MP was used for IPv4 unicast
                return 4
            return self.MP_LENGTH

    def __init__(self, afi: AFI, safi: SAFI, action: Action = Action.UNSET) -> None:
        Message.__init__(self)
        self.nlris = [
            EOR.EOR_NLRI(afi, safi, action),
        ]
        self.attributes = AttributeCollection()

    def pack_message(self, negotiated: 'Negotiated') -> bytes:
        return self._message(self.nlris[0].pack_nlri(negotiated))

    def __repr__(self) -> str:
        return 'EOR'

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: 'Negotiated') -> 'EOR':
        header_length = len(EOR.EOR_NLRI.PREFIX)
        return cls(
            AFI.unpack_afi(data[header_length : header_length + 2]),
            SAFI.unpack_safi(data[header_length + 2 : header_length + 3]),
        )
