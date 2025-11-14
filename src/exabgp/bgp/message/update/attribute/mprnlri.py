"""mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack
from typing import TYPE_CHECKING, Generator, List, Union

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.protocol.ip import NoNextHop
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.direction import Direction

# from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute import NextHop
from exabgp.bgp.message.update.nlri import NLRI

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability import Negotiated


# ==================================================== MP Unreacheable NLRI (15)
#


@Attribute.register()
class MPRNLRI(Attribute, Family):
    FLAG = Attribute.Flag.OPTIONAL
    ID = Attribute.CODE.MP_REACH_NLRI

    def __init__(self, afi: Union[int, AFI], safi: Union[int, SAFI], nlris: List[NLRI]) -> None:
        Family.__init__(self, afi, safi)
        # all the routes must have the same next-hop
        self.nlris: List[NLRI] = nlris

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MPRNLRI):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self.nlris == other.nlris

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def packed_attributes(
        self, negotiated: Negotiated, maximum: int = Negotiated.FREE_SIZE
    ) -> Generator[bytes, None, None]:
        if not self.nlris:
            return

        # addpath = negotiated.addpath.send(self.afi,self.safi)
        # nexthopself = negotiated.nexthopself(self.afi)
        mpnlri: dict[bytes, list] = {}
        for nlri in self.nlris:
            if nlri.family().afi_safi() != self.family().afi_safi():  # nlri is not part of specified family
                continue
            if nlri.nexthop is NoNextHop:
                # EOR and Flow may not have any next_hop
                nexthop = b''
            else:
                _, rd_size = Family.size.get(self.family().afi_safi(), (0, 0))
                nh_rd = bytes([0]) * rd_size if rd_size else b''
                try:
                    # TODO: remove nlri.afi as it should be in the nexthop already
                    nexthop = nh_rd + nlri.nexthop.ton(negotiated, nlri.afi)
                except TypeError:
                    # we could not match "next-hop self" with the BGP AFI of the BGP sesion
                    # attempting invalid IPv4 next-hop (0.0.0.0) to try to not kill the session
                    # and preserve some form of backward compatibility (for some vendors)
                    # the next-hop may have been IPv6 but not valided as the RFC says
                    #
                    # An UPDATE message that carries no NLRI, other than the one encoded in
                    # the MP_REACH_NLRI attribute, SHOULD NOT carry the NEXT_HOP attribute.
                    # If such a message contains the NEXT_HOP attribute, the BGP speaker
                    # that receives the message SHOULD ignore this attribute.
                    #
                    # Some vendors may have therefore not valided the next-hop
                    # and accepted invalid IPv6 next-hop in the past
                    nexthop = bytes([0]) * 4

            # mpunli[nexthop] = nlri
            mpnlri.setdefault(nexthop, []).append(nlri.pack(negotiated))

        for nexthop, nlris in mpnlri.items():
            payload = self.afi.pack() + self.safi.pack() + bytes([len(nexthop)]) + nexthop + bytes([0])
            header_length = len(payload)
            for nlri in nlris:
                if self._len(payload + nlri) > maximum:
                    if len(payload) == header_length or len(payload) > maximum:
                        raise Notify(6, 0, 'attributes size is so large we can not even pack on MPRNLRI')
                    yield self._attribute(payload)
                    payload = self.afi.pack() + self.safi.pack() + bytes([len(nexthop)]) + nexthop + bytes([0]) + nlri
                    continue
                payload = payload + nlri
            if len(payload) == header_length or len(payload) > maximum:
                raise Notify(6, 0, 'attributes size is so large we can not even pack on MPRNLRI')
            yield self._attribute(payload)

    def pack(self, negotiated: Negotiated) -> bytes:
        return b''.join(self.packed_attributes(negotiated))

    def __len__(self) -> int:
        raise RuntimeError('we can not give you the size of an MPRNLRI - was it with our witout addpath ?')
        # return len(self.pack(False))

    def __repr__(self) -> str:
        return 'MP_REACH_NLRI for %s %s with %d NLRI(s)' % (self.afi, self.safi, len(self.nlris))

    @classmethod
    def unpack(cls, data: bytes, direction: int, negotiated: Negotiated) -> MPRNLRI:
        nlris = []

        # -- Reading AFI/SAFI
        _afi, _safi = unpack('!HB', data[:3])
        afi, safi = AFI.create(_afi), SAFI.create(_safi)
        offset = 3
        nh_afi = afi

        # we do not want to accept unknown families
        if negotiated and (afi, safi) not in negotiated.families:
            raise Notify(3, 0, 'presented a non-negotiated family {}/{}'.format(afi, safi))

        # -- Reading length of next-hop
        len_nh = data[offset]
        offset += 1

        if (afi, safi) not in Family.size:
            raise Notify(3, 0, 'unsupported {} {}'.format(afi, safi))

        length, rd = Family.size[(afi, safi)]

        # Is the peer going to send us some Path Information with the route (AddPath)
        # It need to be done before adapting the family for another possible next-hop
        if direction == Direction.IN:
            addpath = negotiated.addpath.receive(afi, safi)
        else:
            addpath = negotiated.addpath.send(afi, safi)

        if negotiated.nexthop:
            if len_nh in (16, 32, 24):
                nh_afi = AFI.ipv6
            elif len_nh in (4, 12):
                nh_afi = AFI.ipv4
            else:
                raise Notify(
                    3, 0, 'unsupported family {} {} with extended next-hop capability enabled'.format(afi, safi)
                )
            length, _ = Family.size[(nh_afi, safi)]

        if len_nh not in length:
            raise Notify(
                3,
                0,
                'invalid %s %s next-hop length %d expected %s'
                % (afi, safi, len_nh, ' or '.join(str(_) for _ in length)),
            )

        size = len_nh - rd

        # XXX: FIXME: GET IT FROM CACHE HERE ?
        nhs = data[offset + rd : offset + rd + size]
        nexthops = [nhs[pos : pos + 16] for pos in range(0, len(nhs), 16)]

        # chech the RD is well zero
        if rd and sum([int(_) for _ in data[offset:8]]) != 0:
            raise Notify(3, 0, "MP_REACH_NLRI next-hop's route-distinguisher must be zero")

        offset += len_nh

        # Skip a reserved bit as somone had to bug us !
        reserved = data[offset]
        offset += 1

        if reserved != 0:
            raise Notify(3, 0, 'the reserved bit of MP_REACH_NLRI is not zero')

        # Reading the NLRIs
        data = data[offset:]

        if not data:
            raise Notify(3, 0, 'No data to decode in an MPREACHNLRI but it is not an EOR %d/%d' % (afi, safi))

        while data:
            if nexthops:
                for nexthop in nexthops:
                    nlri, left = NLRI.unpack_nlri(afi, safi, data, Action.ANNOUNCE, addpath)
                    # allow unpack_nlri to return none for "treat as withdraw" controlled by NLRI.unpack_nlri
                    if nlri:
                        nlri.nexthop = NextHop.unpack(nexthop)
                        nlris.append(nlri)
            else:
                nlri, left = NLRI.unpack_nlri(afi, safi, data, Action.ANNOUNCE, addpath)
                # allow unpack_nlri to return none for "treat as withdraw" controlled by NLRI.unpack_nlri
                if nlri:
                    nlris.append(nlri)

            if left == data:
                raise RuntimeError('sub-calls should consume data')

            data = left
        return cls(afi, safi, nlris)


EMPTY_MPRNLRI = MPRNLRI(AFI.undefined, SAFI.undefined, [])
