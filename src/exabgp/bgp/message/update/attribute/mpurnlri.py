"""mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.nlri import NLRI

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability import Negotiated

from exabgp.logger import log


# ================================================================= MP NLRI (14)


@Attribute.register()
class MPURNLRI(Attribute, Family):
    FLAG = Attribute.Flag.OPTIONAL
    ID = Attribute.CODE.MP_UNREACH_NLRI

    def __init__(self, afi, safi, nlris):
        Family.__init__(self, afi, safi)
        self.nlris = nlris

    def __eq__(self, other):
        if not isinstance(other, MPURNLRI):
            return NotImplemented
        return self.ID == other.ID and self.FLAG == other.FLAG and self.nlris == other.nlris

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def packed_attributes(self, negotiated, maximum=Negotiated.FREE_SIZE):
        if not self.nlris:
            return

        # we changed the API to nrli.pack from addpath to negotiated but not pack itself

        mpurnlri = []
        for nlri in self.nlris:
            if nlri.family().afi_safi() != self.family().afi_safi():  # nlri is not part of specified family
                continue
            mpurnlri.append(nlri.pack(negotiated))

        # The same Cease over our own encoding as MPRNLRI used to raise, see the note there.
        # A withdrawal we cannot pack is worse than an announcement we cannot pack, since the
        # peer keeps forwarding to a prefix we have stopped carrying, but a Cease does not send
        # it either: it takes the other families with it and returns on the next session.
        header = self.afi.pack() + self.safi.pack()
        payload = header
        for nlri in mpurnlri:
            if self._len(header + nlri) > maximum:
                log.critical(lambda: 'can not pack one NLRI in an MP_UNREACH_NLRI, not withdrawing it', 'parser')
                continue
            if self._len(payload + nlri) > maximum:
                yield self._attribute(payload)
                payload = header
            payload = payload + nlri
        if payload != header:
            yield self._attribute(payload)

    def pack(self, negotiated):
        return b''.join(self.packed_attributes(negotiated))

    def __len__(self):
        raise RuntimeError('we can not give you the size of an MPURNLRI - was it with our witout addpath ?')

    def __repr__(self):
        return 'MP_UNREACH_NLRI for %s %s with %d NLRI(s)' % (self.afi, self.safi, len(self.nlris))

    @classmethod
    def unpack(cls, data, direction, negotiated):
        nlris = []

        # Both raises below are 3/9, "UPDATE Message Error"/"Optional Attribute Error",
        # which RFC 4760 section 7 names for a session ended over an incorrect MP
        # attribute.  They used to be 3/0 Unspecific, which named nothing.

        # -- Reading AFI/SAFI
        if len(data) < 3:
            raise Notify(3, 9, 'invalid %s, not enough data for the family' % cls.__name__)
        afi, safi = unpack('!HB', data[:3])
        offset = 3
        data = data[offset:]

        if negotiated and (afi, safi) not in negotiated.families:
            raise Notify(3, 9, 'presented a non-negotiated family {} {}'.format(AFI.create(afi), SAFI.create(safi)))

        # Do we need to handle Path Information with the route (AddPath)
        if direction == Direction.IN:
            addpath = negotiated.addpath.receive(afi, safi)
        else:
            addpath = negotiated.addpath.send(afi, safi)

        while data:
            nlri, data = NLRI.unpack_nlri(afi, safi, data, Action.WITHDRAW, addpath)
            # allow unpack_nlri to return none for "treat as withdraw" controlled by NLRI.unpack_nlri
            if nlri:
                nlris.append(nlri)

        return cls(afi, safi, nlris)


EMPTY_MPURNLRI = MPURNLRI(AFI.undefined, SAFI.undefined, [])
