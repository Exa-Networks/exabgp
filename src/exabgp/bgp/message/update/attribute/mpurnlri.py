"""mpurnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack
from typing import Iterator

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability import Negotiated
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI
from exabgp.util.types import Buffer

# ================================================================= MP Unreachable NLRI (15)


@Attribute.register()
class MPURNLRI(Attribute):
    """Wire-format MP_UNREACH_NLRI attribute container.

    Stores raw wire bytes and yields NLRIs lazily via __iter__.
    For semantic operations (building/packing), use MPNLRICollection.
    """

    FLAG = Attribute.Flag.OPTIONAL
    ID = Attribute.CODE.MP_UNREACH_NLRI
    NO_DUPLICATE = True

    def __init__(self, packed: Buffer, addpath: bool) -> None:
        """Create MPURNLRI from wire-format bytes.

        Args:
            packed: Wire-format payload (after attribute header)
            addpath: Whether AddPath is enabled for this AFI/SAFI
        """
        self._packed = packed
        self._addpath = addpath

    @property
    def afi(self) -> AFI:
        """Address Family Identifier."""
        return AFI.from_int(unpack('!H', self._packed[:2])[0])

    @property
    def safi(self) -> SAFI:
        """Subsequent Address Family Identifier."""
        return SAFI.from_int(self._packed[2])

    @property
    def packed(self) -> bytes:
        """Raw wire-format bytes."""
        return bytes(self._packed)

    def __iter__(self) -> Iterator[NLRI]:
        """Yield NLRIs from wire format.

        Generator that yields NLRIs one by one, parsing lazily.
        """
        # Skip AFI/SAFI header
        nlri_data = self._packed[3:]

        while nlri_data:
            nlri_result, data_result = NLRI.unpack_nlri(
                self.afi, self.safi, nlri_data, Action.WITHDRAW, self._addpath, Negotiated.UNSET
            )
            if nlri_result is not NLRI.INVALID:
                yield nlri_result

            if data_result == nlri_data:
                raise RuntimeError('sub-calls should consume data')

            nlri_data = data_result

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MPURNLRI):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __len__(self) -> int:
        # Return 0 to indicate unknown length - use list(mpurnlri) to iterate
        return 0

    def __repr__(self) -> str:
        return 'MP_UNREACH_NLRI for %s %s' % (self.afi, self.safi)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Attribute:
        """Unpack MPURNLRI from wire format.

        Validates the data and creates an MPURNLRI instance storing the wire bytes.
        NLRIs are parsed lazily when iterating over the instance.
        """
        # MP_UNREACH_NLRI minimum: AFI(2) + SAFI(1) = 3 bytes
        if len(data) < 3:
            raise Notify(3, 9, f'MP_UNREACH_NLRI too short: need at least 3 bytes, got {len(data)}')

        # -- Reading AFI/SAFI for validation
        _afi, _safi = unpack('!HB', data[:3])
        afi, safi = AFI.from_int(_afi), SAFI.from_int(_safi)

        if negotiated and (afi, safi) not in negotiated.families:
            raise Notify(3, 0, 'presented a non-negotiated family {} {}'.format(afi, safi))

        # Get addpath flag for lazy NLRI parsing
        addpath = negotiated.required(afi, safi)

        # Store wire bytes and addpath flag - NLRIs parsed lazily
        return cls(data, addpath)


# Create empty MPURNLRI with minimal packed structure
# AFI(2) + SAFI(1) = 3 bytes minimum
_EMPTY_PACKED = AFI.undefined.pack_afi() + SAFI.undefined.pack_safi()
EMPTY_MPURNLRI = MPURNLRI(_EMPTY_PACKED, addpath=False)
