"""mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from struct import unpack
from typing import ClassVar, Iterator, TYPE_CHECKING

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update.collection import RoutedNLRI

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.notification import NLRIDiscard, Notify
from exabgp.bgp.message.open.capability import Negotiated
from exabgp.bgp.message.update.attribute import Attribute, NextHop
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import AFI, SAFI, Family, next_hop_lengths
from exabgp.protocol.ip import IP, IPv6

# The RFC 2545 Next Hop field holds either one address or a global one followed by a
# link-local one, so a field of exactly two addresses is the pair and nothing else is.
NEXTHOP_ADDRESS_SIZE = 16


def _split_next_hop(field: Buffer, rd: int) -> tuple[Buffer | None, Buffer | None]:
    """The address of a Next Hop field, and the link-local one when the field is a pair.

    RFC 2545 3 and RFC 8950 3 give the pair as two addresses, 32 octets; RFC 4659 3.2.1.1
    gives it as two VPN-IPv6 addresses, an RD in front of each, 48. Anything else is one
    address behind its RD, and next_hop_lengths() refused every length which is neither.
    """
    single = rd + NEXTHOP_ADDRESS_SIZE
    if len(field) == 2 * single:
        return field[rd:single], field[single + rd :]
    return (field[rd:] or None), None


def _route_distinguishers_are_zero(field: Buffer, rd: int) -> bool:
    """RFC 4659 3.2.1.1 and RFC 8950 3: the RD in front of each next hop address is zero."""
    single = rd + NEXTHOP_ADDRESS_SIZE
    if any(field[:rd]):
        return False
    return len(field) != 2 * single or not any(field[single : single + rd])


class NextHopWithLinkLocal(IPv6):
    """The global half of an RFC 2545 next-hop pair, carrying the link-local half with it.

    RFC 2545 section 3: a BGP speaker advertises "the global IPv6 address of the next hop,
    potentially followed by the link-local IPv6 address of the next hop", and sets the
    length of the field to 16 or 32 accordingly. Everything downstream of the decoder,
    the RIB, the JSON API and every consumer of it, reads a route's next hop as one
    address, and that address is the global one. So this stays an IPv6 holding the global
    address, with identical str(), pack_ip() and equality, and remembers the other half
    rather than losing it. Reporting the pair as two next hops would change what a key
    already in use means.
    """

    def __init__(self, packed: Buffer, link_local: IPv6) -> None:
        IPv6.__init__(self, packed)
        self.link_local = link_local


def _log_discarded(nlri: NLRI, reason: str) -> None:
    """Say which announced route was dropped on receipt and why.

    The route vanishes with no NOTIFICATION and no withdrawal, so the log is the only
    record an operator has that the peer sent it.
    """
    log.warning(
        lazymsg('update.route.discarded nlri={nlri} reason="{reason}"', nlri=nlri, reason=reason),
        'parser',
    )


def log_discarded_bytes(discard: NLRIDiscard) -> None:
    """An NLRI which could not be built at all, so only its reason can be named."""
    log.warning(
        lazymsg('update.nlri.discarded octets={n} reason="{reason}"', n=discard.skip, reason=discard.detail),
        'parser',
    )


# ==================================================== MP Reachable NLRI (14)
#


class MPRNLRI(Attribute):
    """Wire-format MP_REACH_NLRI attribute container.

    Stores raw wire bytes and yields NLRIs lazily via __iter__.
    For semantic operations (building/packing), use MPNLRICollection.
    """

    FLAG: ClassVar = Attribute.Flag.OPTIONAL
    ID: ClassVar = Attribute.CODE.MP_REACH_NLRI
    NO_DUPLICATE: ClassVar[bool] = True

    def __init__(self, packed: Buffer, addpath: bool, negotiated: Negotiated = Negotiated.UNSET) -> None:
        """Create MPRNLRI from wire-format bytes.

        Args:
            packed: Wire-format payload (after attribute header)
            addpath: Whether AddPath is enabled for this AFI/SAFI
            negotiated: The session the attribute arrived on, which the NLRI decoders read
                the Multiple Labels Capability from (RFC 8277 2.3)
        """
        self._packed = packed
        self._addpath = addpath
        self._negotiated = negotiated
        # read once: every NLRI decoded from the attribute asks. It inherited Family for
        # this, next to Attribute, which mypyc cannot compile (two concrete bases).
        self._afi = AFI.from_int(unpack('!H', packed[:2])[0])
        self._safi = SAFI.from_int(packed[2])

    @property
    def afi(self) -> AFI:
        """Address Family Identifier."""
        return self._afi

    @property
    def safi(self) -> SAFI:
        """Subsequent Address Family Identifier."""
        return self._safi

    @property
    def packed(self) -> bytes:
        """Raw wire-format bytes."""
        return bytes(self._packed)

    def _parse_nexthop_and_nlris(self) -> tuple[Buffer | None, Buffer | None, Iterator[NLRI]]:
        """Parse wire format, returning (nexthop_bytes, link_local_bytes, nlri_iterator).

        Internal method that separates nexthop parsing from NLRI parsing. The second
        address of an RFC 2545 pair is returned alongside the first because nothing can
        recover it afterwards: the attribute's own bytes are the only record of it.
        """
        data = self._packed

        # -- Reading AFI/SAFI (already done in __init__ for Family)
        offset = 3

        # -- Reading length of next-hop
        len_nh = data[offset]
        offset += 1

        if (self.afi, self.safi) not in Family.size:
            raise Notify(3, 9, 'unsupported {} {}'.format(self.afi, self.safi))

        _, rd = Family.size[(self.afi, self.safi)]
        # Only a field of exactly two addresses is the pair. A shorter field is one address,
        # whatever its length, and unpack_attribute refused any other length before we arrive.
        nexthop_bytes, link_local_bytes = _split_next_hop(data[offset : offset + len_nh], rd)

        offset += len_nh

        # Skip reserved byte
        offset += 1

        # Reading the NLRIs
        nlri_data = data[offset:]

        def nlri_generator() -> Iterator[NLRI]:
            nonlocal nlri_data
            while nlri_data:
                try:
                    nlri_result, left_result = NLRI.unpack_nlri(
                        self.afi, self.safi, nlri_data, Action.ANNOUNCE, self._addpath, self._negotiated
                    )
                except NLRIDiscard as discard:
                    # RFC 9552 8.2.2: framed but broken inside, so only this NLRI goes
                    if not discard.skip:
                        raise
                    log_discarded_bytes(discard)
                    nlri_data = nlri_data[discard.skip :]
                    continue

                if nlri_result is not NLRI.INVALID:
                    reason = nlri_result.discard_on_receipt()
                    if reason is None:
                        yield nlri_result
                    else:
                        _log_discarded(nlri_result, reason)

                if left_result == nlri_data:
                    raise RuntimeError('sub-calls should consume data')

                nlri_data = left_result

        return nexthop_bytes, link_local_bytes, nlri_generator()

    def __iter__(self) -> Iterator[NLRI]:
        """Yield NLRIs from wire format.

        Generator that yields NLRIs one by one, parsing lazily.
        Note: Does NOT set nlri.nexthop - use iter_routed() for RoutedNLRI.
        """
        _, _, nlri_iter = self._parse_nexthop_and_nlris()
        yield from nlri_iter

    def iter_routed(self) -> Iterator['RoutedNLRI']:
        """Yield RoutedNLRI from wire format.

        Generator that yields RoutedNLRI (nlri + nexthop) one by one.
        This is the preferred method for getting announces with nexthop.
        """
        from exabgp.bgp.message.update.collection import RoutedNLRI

        nexthop_bytes, link_local_bytes, nlri_iter = self._parse_nexthop_and_nlris()
        # Convert NextHop (Attribute) to IP for RoutedNLRI
        nexthop: IP
        if nexthop_bytes is None:
            nexthop = IP.NoNextHop
        else:
            nexthop_attr = NextHop.unpack_attribute(nexthop_bytes, Negotiated.UNSET)
            if nexthop_attr is NextHop.UNSET:
                nexthop = IP.NoNextHop
            elif isinstance(nexthop_attr, NextHop):
                nexthop = IP.create_ip(nexthop_attr.pack_ip())
            else:
                nexthop = IP.NoNextHop
        # The pair's global half is the next hop every consumer already reads. Keep it as
        # the next hop and hang the link-local one off it, so nothing existing moves.
        if link_local_bytes is not None and isinstance(nexthop, IPv6):
            nexthop = NextHopWithLinkLocal(nexthop.pack_ip(), IPv6(link_local_bytes))
        for nlri in nlri_iter:
            yield RoutedNLRI(nlri, nexthop)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MPRNLRI):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __len__(self) -> int:
        # Return 0 to indicate unknown length - use list(mprnlri) to iterate
        return 0

    def __repr__(self) -> str:
        return 'MP_REACH_NLRI for %s %s' % (self.afi, self.safi)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Attribute:
        """Unpack MPRNLRI from wire format.

        Validates the data and creates an MPRNLRI instance storing the wire bytes.
        NLRIs are parsed lazily when iterating over the instance.
        """
        # Every Notify below is 3/9, "UPDATE Message Error"/"Optional Attribute Error".
        # RFC 4760 section 7 names that code and subcode for a session terminated over an
        # incorrect MP attribute, and every raise in here is us deciding the attribute is
        # incorrect. 3/0 Unspecific, which most of them used to send, told the peer only
        # that we had ended the session and left it to guess at which attribute. It is
        # also the subcode AttributeCollection.parse answers for an MP attribute whose
        # flags are wrong, on the same reading of the same section.

        # MP_REACH_NLRI minimum: AFI(2) + SAFI(1) + NH_len(1) + reserved(1) = 5 bytes
        if len(data) < 5:
            raise Notify.short(3, 9, 'MP_REACH_NLRI', 5, len(data))

        # -- Reading AFI/SAFI for validation
        _afi, _safi = unpack('!HB', data[:3])
        afi, safi = AFI.from_int(_afi), SAFI.from_int(_safi)
        offset = 3

        # we do not want to accept unknown families
        if negotiated and (afi, safi) not in negotiated.families:
            raise Notify(3, 9, 'presented a non-negotiated family {}/{}'.format(afi, safi))

        # -- Reading length of next-hop
        len_nh = data[offset]
        offset += 1

        # Validate we have enough data for next-hop + reserved byte
        if len(data) < offset + len_nh + 1:
            raise Notify.short(3, 9, 'MP_REACH_NLRI', offset + len_nh + 1, len(data))

        if (afi, safi) not in Family.size:
            raise Notify(3, 9, 'unsupported {} {}'.format(afi, safi))

        # RFC 8950 3: the length says which protocol the next hop belongs to, out of those
        # the family allows, and the Extended Next Hop Encoding capability adds IPv6 to an
        # IPv4 family only for the <AFI, SAFI> our OPEN offered it for: RFC 8950 4 has a
        # triple say what its sender accepts. RFC 7606 7.11: a length "inconsistent with
        # that which was expected" is a session reset.
        length, rd = next_hop_lengths(afi, safi, negotiated.nexthop_receive)

        if len_nh not in length:
            raise Notify(
                3,
                9,
                'invalid %s %s next-hop length %d expected %s'
                % (afi, safi, len_nh, ' or '.join(str(_) for _ in length)),
            )

        # check the RD is well zero, the RD of the link-local address too when there is one
        if rd and not _route_distinguishers_are_zero(data[offset : offset + len_nh], rd):
            raise Notify(3, 9, "MP_REACH_NLRI next-hop's route-distinguisher must be zero")

        offset += len_nh

        # RFC 4760 section 3 reads "A 1 octet field that MUST be set to 0, and SHOULD be
        # ignored upon receipt".  We ignore it.  Ending the session over this byte cost the
        # peer every route it had announced, in every family, over a field the document
        # tells the receiver not to read, and a reserved field carrying something one day
        # is what reserved fields are for.  The length check above already proved the octet
        # is inside the attribute, so only the offset matters here.
        offset += 1

        # Verify there's NLRI data
        if offset >= len(data):
            raise Notify(3, 9, 'No data to decode in an MPREACHNLRI but it is not an EOR %d/%d' % (afi, safi))

        # Get addpath flag for lazy NLRI parsing
        addpath = negotiated.required(afi, safi)

        # Store wire bytes, addpath flag and session - NLRIs parsed lazily
        return cls(data, addpath, negotiated)


Attribute.register()(MPRNLRI)


# Create empty MPRNLRI with minimal packed structure
# AFI(2) + SAFI(1) + NH_LEN(1)=0 + RESERVED(1)=0 = 5 bytes minimum
_EMPTY_PACKED = AFI.undefined.pack_afi() + SAFI.undefined.pack_safi() + bytes([0, 0])
EMPTY_MPRNLRI = MPRNLRI(_EMPTY_PACKED, addpath=False)
