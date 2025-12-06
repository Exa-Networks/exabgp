"""mpurnlri.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from collections.abc import Buffer
from struct import unpack
from typing import Generator

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability import Negotiated
from exabgp.bgp.message.open.capability.negotiated import OpenContext
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.nlri import NLRI, _UNPARSED
from exabgp.protocol.family import AFI, SAFI, Family

# ================================================================= MP Unreachable NLRI (15)


@Attribute.register()
class MPURNLRI(Attribute, Family):
    FLAG = Attribute.Flag.OPTIONAL
    ID = Attribute.CODE.MP_UNREACH_NLRI
    NO_DUPLICATE = True

    # Mode indicators
    _MODE_PACKED = 1  # Created from wire bytes (unpack path)
    _MODE_NLRIS = 2  # Created from NLRI list (semantic path)

    def __init__(self, packed: bytes, context: OpenContext) -> None:
        """Create MPURNLRI from wire-format bytes.

        Args:
            packed: Wire-format payload (after attribute header)
            context: Parsing context for NLRI decoding
        """
        self._packed = packed
        self._context = context
        self._mode = self._MODE_PACKED
        self._nlris_cache: list[NLRI] = _UNPARSED
        # Initialize Family from packed data
        _afi = unpack('!H', packed[:2])[0]
        _safi = packed[2]
        Family.__init__(self, AFI.from_int(_afi), SAFI.from_int(_safi))

    @classmethod
    def make_mpurnlri(cls, context: OpenContext, nlris: list[NLRI]) -> 'MPURNLRI':
        """Create MPURNLRI from semantic data (NLRI list).

        Args:
            context: Parsing context containing AFI/SAFI and negotiated parameters
            nlris: List of NLRI objects to include

        Returns:
            MPURNLRI instance in semantic mode
        """
        # Create minimal packed header just for Family init
        # Full packing happens in packed_attributes()
        header = context.afi.pack_afi() + context.safi.pack_safi()
        instance = cls(header, context)
        # Switch to semantic mode
        instance._mode = cls._MODE_NLRIS
        instance._nlris_cache = nlris
        return instance

    @property
    def nlris(self) -> list[NLRI]:
        """Get the list of NLRIs, parsing from wire format if needed."""
        if self._nlris_cache is not _UNPARSED:
            return self._nlris_cache

        if self._mode == self._MODE_PACKED:
            self._nlris_cache = self._parse_nlris()
            return self._nlris_cache

        return []

    def _parse_nlris(self) -> list[NLRI]:
        """Parse NLRIs from wire format using stored context."""
        nlris: list[NLRI] = []

        # Skip AFI/SAFI (already parsed in __init__)
        nlri_data = self._packed[3:]

        while nlri_data:
            nlri_result, data_result = NLRI.unpack_nlri(
                self.afi, self.safi, nlri_data, Action.WITHDRAW, self._context.addpath, Negotiated.UNSET
            )
            if nlri_result is not NLRI.INVALID:
                nlris.append(nlri_result)
            nlri_data = data_result

        return nlris

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

        packed_nlris: list[bytes] = []
        for nlri in self.nlris:
            if nlri.family().afi_safi() != self.family().afi_safi():  # nlri is not part of specified family
                continue
            packed_nlris.append(nlri.pack_nlri(negotiated))

        payload = self.afi.pack_afi() + self.safi.pack_safi()
        header_length = len(payload)
        for packed in packed_nlris:
            if self._len(payload + packed) > maximum:
                if len(payload) == header_length or len(payload) > maximum:
                    raise Notify(6, 0, 'attributes size is so large we can not even pack on MPURNLRI')
                yield self._attribute(payload)
                payload = self.afi.pack_afi() + self.safi.pack_safi() + packed
                continue
            payload = payload + packed
        if len(payload) == header_length or len(payload) > maximum:
            raise Notify(6, 0, 'attributes size is so large we can not even pack on MPURNLRI')
        yield self._attribute(payload)

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        return b''.join(self.packed_attributes(negotiated))

    def __len__(self) -> int:
        raise RuntimeError('we can not give you the size of an MPURNLRI - was it with our witout addpath ?')

    def __repr__(self) -> str:
        return 'MP_UNREACH_NLRI for %s %s with %d NLRI(s)' % (self.afi, self.safi, len(self.nlris))

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> MPURNLRI:
        """Unpack MPURNLRI from wire format.

        Validates the data and creates an MPURNLRI instance storing the wire bytes.
        NLRIs are parsed lazily when accessed via the nlris property.
        """
        data_bytes = bytes(data)
        # MP_UNREACH_NLRI minimum: AFI(2) + SAFI(1) = 3 bytes
        if len(data_bytes) < 3:
            raise Notify(3, 9, f'MP_UNREACH_NLRI too short: need at least 3 bytes, got {len(data_bytes)}')

        # -- Reading AFI/SAFI for validation
        _afi, _safi = unpack('!HB', data_bytes[:3])
        afi, safi = AFI.from_int(_afi), SAFI.from_int(_safi)

        if negotiated and (afi, safi) not in negotiated.families:
            raise Notify(3, 0, 'presented a non-negotiated family {} {}'.format(afi, safi))

        # Create context for lazy NLRI parsing
        context = negotiated.nlri_context(afi, safi)

        # Store wire bytes and context - NLRIs parsed lazily
        return cls(data_bytes, context)


# Create empty MPURNLRI using factory method with default context
_EMPTY_CONTEXT = OpenContext.make_open_context(
    afi=AFI.undefined,
    safi=SAFI.undefined,
    addpath=False,
    asn4=False,
    msg_size=4096,
)
EMPTY_MPURNLRI = MPURNLRI.make_mpurnlri(_EMPTY_CONTEXT, [])
