"""collection.py

Wire-format NLRI container classes following the packed-bytes-first pattern.

Created for separation of wire format from semantic representation.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update.attribute.attribute import Attribute
    from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
    from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
    from exabgp.bgp.message.update.collection import RoutedNLRI

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.update.attribute.nexthop import NextHop
from exabgp.bgp.message.update.nlri.nlri import _UNPARSED, NLRI
from exabgp.protocol.family import AFI, SAFI
from exabgp.util.types import Buffer


class NLRICollection:
    """Wire-format NLRI container for IPv4 announce/withdraw sections.

    Dual-mode:
    - Wire mode: __init__(packed, afi, safi, addpath, action) - stores bytes, lazy parsing
    - Semantic mode: make_collection(afi, safi, nlris, action) - stores NLRI list

    This class follows the packed-bytes-first pattern where wire format
    is the canonical representation and semantic values are derived lazily.
    """

    _MODE_PACKED = 1  # Created from wire bytes (unpack path)
    _MODE_NLRIS = 2  # Created from NLRI list (semantic path)

    def __init__(self, packed: Buffer, afi: AFI, safi: SAFI, addpath: bool, action: Action = Action.UNSET) -> None:
        """Create NLRICollection from wire-format bytes.

        Args:
            packed: Raw NLRI section bytes from UPDATE message.
                    Format: sequence of [mask(1) + prefix_bytes...]
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier
            addpath: Whether AddPath is enabled for this AFI/SAFI
            action: Whether these are announcements or withdrawals.
        """
        self._packed = packed
        self._afi = afi
        self._safi = safi
        self._addpath = addpath
        self._action = action
        self._mode = self._MODE_PACKED
        self._nlris_cache: list[NLRI] = _UNPARSED

    @classmethod
    def make_collection(cls, afi: AFI, safi: SAFI, nlris: list[NLRI], action: Action) -> 'NLRICollection':
        """Create NLRICollection from semantic data (NLRI list).

        Args:
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier
            nlris: List of NLRI objects to include.
            action: Whether these are announcements or withdrawals.

        Returns:
            NLRICollection instance in semantic mode.
        """
        # Create instance with empty packed data (addpath=False for semantic mode)
        instance = cls(b'', afi, safi, addpath=False, action=action)
        # Switch to semantic mode
        instance._mode = cls._MODE_NLRIS
        instance._nlris_cache: list[NLRI] = nlris
        return instance

    @property
    def packed(self) -> Buffer:
        """Raw NLRI bytes.

        In wire mode: returns the stored wire bytes.
        In semantic mode: packs the NLRI list to wire format.
        """
        if self._mode == self._MODE_PACKED:
            return self._packed

        # Semantic mode: pack NLRIs to wire format
        if self._nlris_cache is _UNPARSED:
            return b''

        # Pack each NLRI using its _packed attribute (no addpath)
        # AddPath handling would be done at UPDATE message level
        packed = b''
        for nlri in self._nlris_cache:
            packed += nlri._packed
        return packed

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
        """Parse NLRIs from wire format using stored AFI/SAFI/addpath."""
        nlris: list[NLRI] = []
        data = self._packed

        # Handle empty data
        if not data:
            return nlris

        # Parse NLRIs using the factory
        from exabgp.bgp.message.open.capability.negotiated import Negotiated

        while data:
            nlri, data = NLRI.unpack_nlri(
                self._afi,
                self._safi,
                data,
                self._action,
                self._addpath,
                Negotiated.UNSET,
            )
            if nlri is not NLRI.INVALID:
                nlris.append(nlri)

        return nlris

    def __len__(self) -> int:
        """Return number of NLRIs in collection."""
        return len(self.nlris)

    def __repr__(self) -> str:
        return f'NLRICollection({self._afi}/{self._safi}, {len(self)} NLRIs)'


class MPNLRICollection:
    """Unified semantic container for MP_REACH/MP_UNREACH NLRIs.

    Stores NLRIs and attributes dict. Generates MPRNLRI or MPURNLRI
    wire format based on action (reach vs unreach).

    Two modes:
    - Bare NLRI mode: __init__(nlris, attributes, afi, safi)
      Used for MP_UNREACH (withdraws) where no nexthop is needed.
    - RoutedNLRI mode: from_routed(routed_nlris, attributes, afi, safi)
      Used for MP_REACH (announces) where nexthop comes from RoutedNLRI.
    """

    # Attribute flags and IDs for wire format generation
    _FLAG_OPTIONAL = 0x80
    _CODE_MP_REACH_NLRI = 14
    _CODE_MP_UNREACH_NLRI = 15

    def __init__(
        self,
        nlris: list[NLRI],
        attributes: 'dict[int, Attribute]',
        afi: AFI,
        safi: SAFI,
    ) -> None:
        """Create MPNLRICollection from bare NLRIs (for unreach/withdraws).

        Args:
            nlris: List of NLRI objects (without nexthop).
            attributes: Dict of attributes indexed by Attribute.CODE (int).
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier
        """
        self._nlris = nlris
        self._routed_nlris: 'list[RoutedNLRI]' = []  # Empty for bare NLRI mode
        self._attributes = attributes
        self._afi = afi
        self._safi = safi

    @classmethod
    def from_routed(
        cls,
        routed_nlris: 'list[RoutedNLRI]',
        attributes: 'dict[int, Attribute]',
        afi: AFI,
        safi: SAFI,
    ) -> 'MPNLRICollection':
        """Create MPNLRICollection from RoutedNLRIs (for reach/announces).

        Args:
            routed_nlris: List of RoutedNLRI (nlri + nexthop).
            attributes: Dict of attributes indexed by Attribute.CODE (int).
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier

        Returns:
            MPNLRICollection configured for reach mode with nexthops.
        """
        instance = cls([], attributes, afi, safi)
        instance._routed_nlris = routed_nlris
        # Also populate _nlris for compatibility (e.g., __len__)
        instance._nlris = [routed.nlri for routed in routed_nlris]
        return instance

    @classmethod
    def from_wire(
        cls,
        mprnlri: 'MPRNLRI | None',
        mpurnlri: 'MPURNLRI | None',
        attributes: 'dict[int, Attribute]',
        afi: AFI,
        safi: SAFI,
    ) -> 'MPNLRICollection':
        """Create from wire containers (reach and/or unreach).

        Args:
            mprnlri: MPRNLRI wire container (or None).
            mpurnlri: MPURNLRI wire container (or None).
            attributes: Dict of attributes indexed by Attribute.CODE.
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier

        Returns:
            MPNLRICollection with NLRIs from both containers.
        """
        nlris: list[NLRI] = []
        if mprnlri is not None:
            # Use list() to iterate without calling __len__
            nlris.extend(list(mprnlri))
        if mpurnlri is not None:
            nlris.extend(list(mpurnlri))
        return cls(nlris, attributes, afi, safi)

    @property
    def nlris(self) -> list[NLRI]:
        """Get NLRIs in this collection."""
        return self._nlris

    @property
    def attributes(self) -> 'dict[int, Attribute]':
        """Get attributes dict indexed by Attribute.CODE."""
        return self._attributes

    @property
    def afi(self) -> AFI:
        """Address Family Identifier."""
        return self._afi

    @property
    def safi(self) -> SAFI:
        """Subsequent Address Family Identifier."""
        return self._safi

    def _attribute_header(self, code: int, length: int) -> bytes:
        """Build attribute header (flag + code + length)."""
        flag = self._FLAG_OPTIONAL
        if length > 255:
            # Extended length
            flag |= 0x10
            return bytes([flag, code]) + pack('!H', length)
        return bytes([flag, code, length])

    def _attr_len(self, payload_len: int) -> int:
        """Calculate total attribute length including header."""
        return payload_len + (4 if payload_len > 255 else 3)

    def packed_reach_attributes(
        self,
        negotiated: 'Negotiated',
        maximum: int = 4096,
    ) -> 'Generator[bytes, None, None]':
        """Generate MP_REACH_NLRI wire-format attributes.

        Groups NLRIs by nexthop, handles fragmentation.

        Args:
            negotiated: BGP session parameters.
            maximum: Maximum bytes per attribute (default 4096).

        Yields:
            Wire-format attribute bytes (with flags/type/length header).
        """
        from exabgp.protocol.family import Family

        # Filter NLRIs for this family and group by nexthop
        mpnlri: dict[bytes, list[bytes]] = {}
        family_key = (self._afi, self._safi)

        # Use _routed_nlris to get nexthop from RoutedNLRI container
        for routed in self._routed_nlris:
            nlri = routed.nlri
            nlri_nexthop = routed.nexthop
            if nlri.family().afi_safi() != family_key:
                continue

            # Encode nexthop
            if nlri_nexthop is NextHop.UNSET:
                nexthop = b''
            else:
                _, rd_size = Family.size.get(family_key, (0, 0))
                nh_rd = bytes([0]) * rd_size if rd_size else b''
                try:
                    nexthop = nh_rd + nlri_nexthop.pack_ip()
                except TypeError:
                    # Fallback for invalid nexthop
                    nexthop = bytes([0]) * 4

            mpnlri.setdefault(nexthop, []).append(nlri.pack_nlri(negotiated))

        # Generate attributes for each nexthop group
        afi_bytes = self._afi.pack_afi()
        safi_bytes = self._safi.pack_safi()

        for nexthop, packed_nlris in mpnlri.items():
            # Build header: AFI(2) + SAFI(1) + NH_len(1) + NH + reserved(1)
            header = afi_bytes + safi_bytes + bytes([len(nexthop)]) + nexthop + bytes([0])
            header_length = len(header)
            payload = header

            for packed_nlri in packed_nlris:
                # Check if adding this NLRI would exceed maximum
                if self._attr_len(len(payload) + len(packed_nlri)) > maximum:
                    if len(payload) == header_length:
                        raise RuntimeError('NLRI too large for attribute size limit')
                    # Yield current payload and start new one
                    yield self._attribute_header(self._CODE_MP_REACH_NLRI, len(payload)) + payload
                    payload = header + packed_nlri
                else:
                    payload = payload + packed_nlri

            # Yield final payload for this nexthop
            if len(payload) > header_length:
                yield self._attribute_header(self._CODE_MP_REACH_NLRI, len(payload)) + payload

    def packed_unreach_attributes(
        self,
        negotiated: 'Negotiated',
        maximum: int = 4096,
    ) -> 'Generator[bytes, None, None]':
        """Generate MP_UNREACH_NLRI wire-format attributes.

        Handles fragmentation only (no nexthop grouping).

        Args:
            negotiated: BGP session parameters.
            maximum: Maximum bytes per attribute (default 4096).

        Yields:
            Wire-format attribute bytes (with flags/type/length header).
        """
        # Filter and pack NLRIs for this family
        family_key = (self._afi, self._safi)
        packed_nlris: list[bytes] = []

        for nlri in self._nlris:
            if nlri.family().afi_safi() != family_key:
                continue
            packed_nlris.append(nlri.pack_nlri(negotiated))

        if not packed_nlris:
            return

        # Build header: AFI(2) + SAFI(1)
        header = self._afi.pack_afi() + self._safi.pack_safi()
        header_length = len(header)
        payload = header

        for packed_nlri in packed_nlris:
            # Check if adding this NLRI would exceed maximum
            if self._attr_len(len(payload) + len(packed_nlri)) > maximum:
                if len(payload) == header_length:
                    raise RuntimeError('NLRI too large for attribute size limit')
                # Yield current payload and start new one
                yield self._attribute_header(self._CODE_MP_UNREACH_NLRI, len(payload)) + payload
                payload = header + packed_nlri
            else:
                payload = payload + packed_nlri

        # Yield final payload
        if len(payload) > header_length:
            yield self._attribute_header(self._CODE_MP_UNREACH_NLRI, len(payload)) + payload

    def __len__(self) -> int:
        """Return number of NLRIs in collection."""
        return len(self._nlris)

    def __repr__(self) -> str:
        return f'MPNLRICollection({self._afi}/{self._safi}, {len(self)} NLRIs)'
