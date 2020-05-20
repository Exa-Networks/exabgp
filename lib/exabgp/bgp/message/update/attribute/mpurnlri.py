# encoding: utf-8
"""
mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import unpack

from exabgp.util import concat_bytes
from exabgp.util import concat_bytes_i

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family

from exabgp.bgp.message.direction import IN
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.nlri import NLRI

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability import Negotiated


# ================================================================= MP NLRI (14)


@Attribute.register()
class MPURNLRI(Attribute, Family):
    FLAG = Attribute.Flag.OPTIONAL
    ID = Attribute.CODE.MP_UNREACH_NLRI

    # __slots__ = ['nlris']

    def __init__(self, afi, safi, nlris):
        Family.__init__(self, afi, safi)
        self.nlris = nlris

    def __eq__(self, other):
        return self.ID == other.ID and self.FLAG == other.FLAG and self.nlris == other.nlris

    def __ne__(self, other):
        return not self.__eq__(other)

    def packed_attributes(self, negotiated, maximum=Negotiated.FREE_SIZE):
        if not self.nlris:
            return

        # we changed the API to nrli.pack from addpath to negotiated but not pack itself

        mpurnlri = []
        for nlri in self.nlris:
            if nlri.family() != self.family():  # nlri is not part of specified family
                continue
            mpurnlri.append(nlri.pack(negotiated))

        payload = concat_bytes(self.afi.pack(), self.safi.pack())
        header_length = len(payload)
        for nlri in mpurnlri:
            if self._len(payload + nlri) > maximum:
                if len(payload) == header_length or len(payload) > maximum:
                    raise Notify(6, 0, 'attributes size is so large we can not even pack on MPURNLRI')
                yield self._attribute(payload)
                payload = concat_bytes(self.afi.pack(), self.safi.pack(), nlri)
                continue
            payload = concat_bytes(payload, nlri)
        if len(payload) == header_length or len(payload) > maximum:
            raise Notify(6, 0, 'attributes size is so large we can not even pack on MPURNLRI')
        yield self._attribute(payload)

    def pack(self, negotiated):
        return concat_bytes_i(self.packed_attributes(negotiated))

    def __len__(self):
        raise RuntimeError('we can not give you the size of an MPURNLRI - was it with our witout addpath ?')

    def __repr__(self):
        return "MP_UNREACH_NLRI for %s %s with %d NLRI(s)" % (self.afi, self.safi, len(self.nlris))

    @classmethod
    def unpack(cls, data, negotiated):
        nlris = []

        # -- Reading AFI/SAFI
        afi, safi = unpack('!HB', data[:3])
        offset = 3
        data = data[offset:]

        if negotiated and (afi, safi) not in negotiated.families:
            raise Notify(3, 0, 'presented a non-negotiated family %s %s' % (AFI.create(afi), SAFI.create(safi)))

        # Is the peer going to send us some Path Information with the route (AddPath)
        addpath = negotiated.addpath.receive(afi, safi)

        while data:
            nlri, data = NLRI.unpack_nlri(afi, safi, data, IN.WITHDRAWN, addpath)
            # allow unpack_nlri to return none for "treat as withdraw" controlled by NLRI.unpack_nlri
            if nlri:
                nlris.append(nlri)

        return cls(afi, safi, nlris)


EMPTY_MPURNLRI = MPURNLRI(AFI.undefined, SAFI.undefined, [])
