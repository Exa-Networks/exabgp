"""mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack
from typing import Generator, List, Union

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.nlri import NLRI

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability import Negotiated


# ================================================================= MP NLRI (14)


@Attribute.register()
class MPURNLRI(Attribute, Family):
    FLAG = Attribute.Flag.OPTIONAL
    ID = Attribute.CODE.MP_UNREACH_NLRI

    def __init__(self, afi: Union[int, AFI], safi: Union[int, SAFI], nlris: List[NLRI]) -> None:
        Family.__init__(self, afi, safi)
        self.nlris: List[NLRI] = nlris

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MPURNLRI):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self.nlris == other.nlris

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def packed_attributes(
        self, negotiated: Negotiated, maximum: int = Negotiated.FREE_SIZE
    ) -> Generator[bytes, None, None]:
        if not self.nlris:
            return

        # we changed the API to nrli.pack from addpath to negotiated but not pack itself

        mpurnlri = []
        for nlri in self.nlris:
            if nlri.family().afi_safi() != self.family().afi_safi():  # nlri is not part of specified family
                continue
            mpurnlri.append(nlri.pack(negotiated))

        payload = self.afi.pack() + self.safi.pack()
        header_length = len(payload)
        for nlri in mpurnlri:
            if self._len(payload + nlri) > maximum:  # type: ignore[operator]
                if len(payload) == header_length or len(payload) > maximum:
                    raise Notify(6, 0, 'attributes size is so large we can not even pack on MPURNLRI')
                yield self._attribute(payload)
                payload = self.afi.pack() + self.safi.pack() + nlri  # type: ignore[operator]
                continue
            payload = payload + nlri  # type: ignore[operator]
        if len(payload) == header_length or len(payload) > maximum:
            raise Notify(6, 0, 'attributes size is so large we can not even pack on MPURNLRI')
        yield self._attribute(payload)

    def pack(self, negotiated: Negotiated) -> bytes:
        return b''.join(self.packed_attributes(negotiated))

    def __len__(self) -> int:
        raise RuntimeError('we can not give you the size of an MPURNLRI - was it with our witout addpath ?')

    def __repr__(self) -> str:
        return 'MP_UNREACH_NLRI for %s %s with %d NLRI(s)' % (self.afi, self.safi, len(self.nlris))

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> MPURNLRI:
        nlris = []

        # -- Reading AFI/SAFI
        afi, safi = unpack('!HB', data[:3])
        offset = 3
        data = data[offset:]

        if negotiated and (afi, safi) not in negotiated.families:
            raise Notify(3, 0, 'presented a non-negotiated family {} {}'.format(AFI.create(afi), SAFI.create(safi)))

        # Do we need to handle Path Information with the route (AddPath)
        addpath = negotiated.required(afi, safi)

        while data:
            nlri, data = NLRI.unpack_nlri(afi, safi, data, Action.WITHDRAW, addpath)
            # allow unpack_nlri to return none for "treat as withdraw" controlled by NLRI.unpack_nlri
            if nlri:  # type: ignore[has-type]
                nlris.append(nlri)  # type: ignore[has-type]

        return cls(afi, safi, nlris)


EMPTY_MPURNLRI = MPURNLRI(AFI.undefined, SAFI.undefined, [])
