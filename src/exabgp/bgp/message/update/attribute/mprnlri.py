"""mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack

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

from exabgp.logger import log


# ==================================================== MP Unreacheable NLRI (15)
#


@Attribute.register()
class MPRNLRI(Attribute, Family):
    FLAG = Attribute.Flag.OPTIONAL
    ID = Attribute.CODE.MP_REACH_NLRI

    def __init__(self, afi, safi, nlris):
        Family.__init__(self, afi, safi)
        # all the routes must have the same next-hop
        self.nlris = nlris

    def __eq__(self, other):
        if not isinstance(other, MPRNLRI):
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

        # addpath = negotiated.addpath.send(self.afi,self.safi)
        # nexthopself = negotiated.nexthopself(self.afi)
        mpnlri = {}
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

        # An NLRI which does not fit a message of its own used to raise Notify(6, 0), a Cease
        # sent to the peer over the size of what WE were about to encode.  The peer had done
        # nothing: it lost every route of every family, and on the next session it would lose
        # them again, because the announcement we could not pack is still in our RIB.  A local
        # encoding limit is not a protocol error, so it is logged and the route is left out,
        # which is what the native IPv4 pass in Update._packed_nlris already does.
        for nexthop, nlris in mpnlri.items():
            header = self.afi.pack() + self.safi.pack() + bytes([len(nexthop)]) + nexthop + bytes([0])
            payload = header
            for nlri in nlris:
                if self._len(header + nlri) > maximum:
                    log.critical(lambda: 'can not pack one NLRI in an MP_REACH_NLRI, not announcing it', 'parser')
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
        raise RuntimeError('we can not give you the size of an MPRNLRI - was it with our witout addpath ?')
        # return len(self.pack(False))

    def __repr__(self):
        return 'MP_REACH_NLRI for %s %s with %d NLRI(s)' % (self.afi, self.safi, len(self.nlris))

    @classmethod
    def unpack(cls, data, direction, negotiated):
        nlris = []

        # Every Notify below is 3/9, "UPDATE Message Error"/"Optional Attribute Error".
        # RFC 4760 section 7 names that code and subcode for a session terminated over an
        # incorrect MP attribute, and every raise in here is us deciding the attribute is
        # incorrect.  3/0 Unspecific, which most of them used to send, told the peer only
        # that we had ended the session and left it to guess at which attribute.

        # -- Reading AFI/SAFI
        # AFI(2) + SAFI(1) + next-hop length(1) + reserved(1) is the smallest MP_REACH
        # there can be.  Checking only the first three left `data[3]` reading off the end
        # of a three octet attribute, and IndexError is re-raised out of
        # Attributes.parse for an attribute which is not treat-as-withdraw.
        if len(data) < 5:
            raise Notify(3, 9, 'invalid %s, not enough data for the family and next-hop' % cls.__name__)
        _afi, _safi = unpack('!HB', data[:3])
        afi, safi = AFI.create(_afi), SAFI.create(_safi)
        offset = 3
        nh_afi = afi

        # we do not want to accept unknown families
        if negotiated and (afi, safi) not in negotiated.families:
            raise Notify(3, 9, 'presented a non-negotiated family {}/{}'.format(afi, safi))

        # -- Reading length of next-hop
        len_nh = data[offset]
        offset += 1

        # the next-hop and the reserved octet behind it are both sized by the peer
        if len(data) < offset + len_nh + 1:
            raise Notify(3, 9, f'MP_REACH_NLRI truncated: need {offset + len_nh + 1} bytes, got {len(data)}')

        if (afi, safi) not in Family.size:
            raise Notify(3, 9, 'unsupported {} {}'.format(afi, safi))

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
                    3, 9, 'unsupported family {} {} with extended next-hop capability enabled'.format(afi, safi)
                )
            length, _ = Family.size[(nh_afi, safi)]

        if len_nh not in length:
            raise Notify(
                3,
                9,
                'invalid %s %s next-hop length %d expected %s'
                % (afi, safi, len_nh, ' or '.join(str(_) for _ in length)),
            )

        size = len_nh - rd

        # XXX: FIXME: GET IT FROM CACHE HERE ?
        nhs = data[offset + rd : offset + rd + size]
        nexthops = [nhs[pos : pos + 16] for pos in range(0, len(nhs), 16)]

        # check the route distinguisher is indeed zero. This read the fixed slice
        # data[offset:8], which with an offset of 4 and an eight byte RD inspected
        # only its first four bytes, and inspected nothing at all had the offset
        # ever passed 8. Every VPN family was half checked.
        if rd and sum(data[offset : offset + rd]) != 0:
            raise Notify(3, 9, "MP_REACH_NLRI next-hop's route-distinguisher must be zero")

        offset += len_nh

        # RFC 4760 section 3 reads "A 1 octet field that MUST be set to 0, and SHOULD be
        # ignored upon receipt".  We ignore it.  Ending the session over this byte cost the
        # peer every route it had announced, in every family, over a field the document
        # tells the receiver not to read, and a reserved field carrying something one day
        # is what reserved fields are for.  The length check above already proved the octet
        # is inside the attribute, so only the offset matters here.
        offset += 1

        # Reading the NLRIs
        data = data[offset:]

        if not data:
            raise Notify(3, 9, 'No data to decode in an MPREACHNLRI but it is not an EOR %d/%d' % (afi, safi))

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
