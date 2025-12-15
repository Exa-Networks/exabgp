"""mprnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack
from typing import TYPE_CHECKING, Iterator

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update.collection import RoutedNLRI

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability import Negotiated
from exabgp.bgp.message.update.attribute import Attribute, NextHop
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.protocol.ip import IP

# ==================================================== MP Reachable NLRI (14)
#


@Attribute.register()
class MPRNLRI(Attribute, Family):
    """Wire-format MP_REACH_NLRI attribute container.

    Stores raw wire bytes and yields NLRIs lazily via __iter__.
    For semantic operations (building/packing), use MPNLRICollection.
    """

    FLAG = Attribute.Flag.OPTIONAL
    ID = Attribute.CODE.MP_REACH_NLRI
    NO_DUPLICATE = True

    def __init__(self, packed: Buffer, addpath: bool) -> None:
        """Create MPRNLRI from wire-format bytes.

        Args:
            packed: Wire-format payload (after attribute header)
            addpath: Whether AddPath is enabled for this AFI/SAFI
        """
        self._packed = packed
        self._addpath = addpath
        # Initialize Family from packed data
        _afi = unpack('!H', packed[:2])[0]
        _safi = packed[2]
        Family.__init__(self, AFI.from_int(_afi), SAFI.from_int(_safi))

    @property
    def packed(self) -> bytes:
        """Raw wire-format bytes."""
        return bytes(self._packed)

    def _parse_nexthop_and_nlris(self) -> tuple[bytes | None, Iterator[NLRI]]:
        """Parse wire format, returning (nexthop_bytes, nlri_iterator).

        Internal method that separates nexthop parsing from NLRI parsing.
        """
        data = self._packed

        # -- Reading AFI/SAFI (already done in __init__ for Family)
        offset = 3

        # -- Reading length of next-hop
        len_nh = data[offset]
        offset += 1

        if (self.afi, self.safi) not in Family.size:
            raise Notify(3, 0, 'unsupported {} {}'.format(self.afi, self.safi))

        length, rd = Family.size[(self.afi, self.safi)]

        size = len_nh - rd

        # Parse nexthops
        nhs = data[offset + rd : offset + rd + size]
        nexthops = [nhs[pos : pos + 16] for pos in range(0, len(nhs), 16)]
        nexthop_bytes = nexthops[0] if nexthops else None

        offset += len_nh

        # Skip reserved byte
        offset += 1

        # Reading the NLRIs
        nlri_data = data[offset:]

        def nlri_generator() -> Iterator[NLRI]:
            nonlocal nlri_data
            while nlri_data:
                nlri_result, left_result = NLRI.unpack_nlri(
                    self.afi, self.safi, nlri_data, Action.ANNOUNCE, self._addpath, Negotiated.UNSET
                )

                if nlri_result is not NLRI.INVALID:
                    yield nlri_result

                if left_result == nlri_data:
                    raise RuntimeError('sub-calls should consume data')

                nlri_data = left_result

        return nexthop_bytes, nlri_generator()

    def __iter__(self) -> Iterator[NLRI]:
        """Yield NLRIs from wire format.

        Generator that yields NLRIs one by one, parsing lazily.
        Note: Does NOT set nlri.nexthop - use iter_routed() for RoutedNLRI.
        """
        _, nlri_iter = self._parse_nexthop_and_nlris()
        yield from nlri_iter

    def iter_routed(self) -> Iterator['RoutedNLRI']:
        """Yield RoutedNLRI from wire format.

        Generator that yields RoutedNLRI (nlri + nexthop) one by one.
        This is the preferred method for getting announces with nexthop.
        """
        from exabgp.bgp.message.update.collection import RoutedNLRI

        nexthop_bytes, nlri_iter = self._parse_nexthop_and_nlris()
        nexthop = NextHop.unpack_attribute(nexthop_bytes, Negotiated.UNSET) if nexthop_bytes else IP.NoNextHop
        for nlri in nlri_iter:
            yield RoutedNLRI(nlri, nexthop)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MPRNLRI):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __len__(self) -> int:
        # Return 0 to indicate unknown length - use list(mprnlri) to iterate
        return 0

    def __repr__(self) -> str:
        return 'MP_REACH_NLRI for %s %s' % (self.afi, self.safi)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> MPRNLRI:
        """Unpack MPRNLRI from wire format.

        Validates the data and creates an MPRNLRI instance storing the wire bytes.
        NLRIs are parsed lazily when iterating over the instance.
        """
        # MP_REACH_NLRI minimum: AFI(2) + SAFI(1) + NH_len(1) + reserved(1) = 5 bytes
        if len(data) < 5:
            raise Notify(3, 9, f'MP_REACH_NLRI too short: need at least 5 bytes, got {len(data)}')

        # -- Reading AFI/SAFI for validation
        _afi, _safi = unpack('!HB', data[:3])
        afi, safi = AFI.from_int(_afi), SAFI.from_int(_safi)
        offset = 3

        # we do not want to accept unknown families
        if negotiated and (afi, safi) not in negotiated.families:
            raise Notify(3, 0, 'presented a non-negotiated family {}/{}'.format(afi, safi))

        # -- Reading length of next-hop
        len_nh = data[offset]
        offset += 1

        # Validate we have enough data for next-hop + reserved byte
        if len(data) < offset + len_nh + 1:
            raise Notify(3, 9, f'MP_REACH_NLRI truncated: need {offset + len_nh + 1} bytes, got {len(data)}')

        if (afi, safi) not in Family.size:
            raise Notify(3, 0, 'unsupported {} {}'.format(afi, safi))

        length, rd = Family.size[(afi, safi)]

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

        # check the RD is well zero
        if rd and sum([int(_) for _ in data[offset : offset + 8]]) != 0:
            raise Notify(3, 0, "MP_REACH_NLRI next-hop's route-distinguisher must be zero")

        offset += len_nh

        # Skip a reserved bit as someone had to bug us !
        reserved = data[offset]
        offset += 1

        if reserved != 0:
            raise Notify(3, 0, 'the reserved bit of MP_REACH_NLRI is not zero')

        # Verify there's NLRI data
        if offset >= len(data):
            raise Notify(3, 0, 'No data to decode in an MPREACHNLRI but it is not an EOR %d/%d' % (afi, safi))

        # Get addpath flag for lazy NLRI parsing
        addpath = negotiated.required(afi, safi)

        # Store wire bytes and addpath flag - NLRIs parsed lazily
        return cls(data, addpath)


# Create empty MPRNLRI with minimal packed structure
# AFI(2) + SAFI(1) + NH_LEN(1)=0 + RESERVED(1)=0 = 5 bytes minimum
_EMPTY_PACKED = AFI.undefined.pack_afi() + SAFI.undefined.pack_safi() + bytes([0, 0])
EMPTY_MPRNLRI = MPRNLRI(_EMPTY_PACKED, addpath=False)
