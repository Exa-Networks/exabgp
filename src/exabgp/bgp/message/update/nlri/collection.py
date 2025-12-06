"""collection.py

Wire-format NLRI container classes following the packed-bytes-first pattern.

Created for separation of wire format from semantic representation.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
    from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.open.capability.negotiated import OpenContext
from exabgp.bgp.message.update.nlri.nlri import NLRI, _UNPARSED
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP


class NLRICollection:
    """Wire-format NLRI container for IPv4 announce/withdraw sections.

    Dual-mode:
    - Wire mode: __init__(packed, context, action) - stores bytes, lazy parsing
    - Semantic mode: make_collection(context, nlris, action) - stores NLRI list

    This class follows the packed-bytes-first pattern where wire format
    is the canonical representation and semantic values are derived lazily.
    """

    _MODE_PACKED = 1  # Created from wire bytes (unpack path)
    _MODE_NLRIS = 2  # Created from NLRI list (semantic path)

    def __init__(self, packed: bytes, context: OpenContext, action: Action = Action.ANNOUNCE) -> None:
        """Create NLRICollection from wire-format bytes.

        Args:
            packed: Raw NLRI section bytes from UPDATE message.
                    Format: sequence of [mask(1) + prefix_bytes...]
            context: OpenContext with AFI/SAFI and parsing options (addpath, etc.)
            action: Whether these are announcements or withdrawals.
        """
        self._packed = packed
        self._context = context
        self._action = action
        self._mode = self._MODE_PACKED
        self._nlris_cache: list[NLRI] = _UNPARSED

    @classmethod
    def make_collection(cls, context: OpenContext, nlris: list[NLRI], action: Action) -> 'NLRICollection':
        """Create NLRICollection from semantic data (NLRI list).

        Args:
            context: OpenContext with AFI/SAFI and negotiated parameters.
            nlris: List of NLRI objects to include.
            action: Whether these are announcements or withdrawals.

        Returns:
            NLRICollection instance in semantic mode.
        """
        # Create instance with empty packed data
        instance = cls(b'', context, action)
        # Switch to semantic mode
        instance._mode = cls._MODE_NLRIS
        instance._nlris_cache = nlris
        return instance

    @property
    def packed(self) -> bytes:
        """Raw NLRI bytes.

        In wire mode: returns the stored wire bytes.
        In semantic mode: packs the NLRI list to wire format.
        """
        if self._mode == self._MODE_PACKED:
            return self._packed

        # Semantic mode: pack NLRIs to wire format
        if self._nlris_cache is _UNPARSED:
            return b''

        # Pack each NLRI using its _pack_nlri_simple method (no addpath)
        # AddPath handling would be done at UPDATE message level
        packed = b''
        for nlri in self._nlris_cache:
            packed += nlri._pack_nlri_simple()
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
        """Parse NLRIs from wire format using stored context."""
        nlris: list[NLRI] = []
        data = self._packed

        # Handle empty data
        if not data:
            return nlris

        # Parse NLRIs using the factory
        from exabgp.bgp.message.open.capability.negotiated import Negotiated

        while data:
            nlri, data = NLRI.unpack_nlri(
                self._context.afi,
                self._context.safi,
                data,
                self._action,
                self._context.addpath,
                Negotiated.UNSET,
            )
            if nlri is not NLRI.INVALID:
                nlris.append(nlri)

        return nlris

    def __len__(self) -> int:
        """Return number of NLRIs in collection."""
        return len(self.nlris)

    def __repr__(self) -> str:
        return f'NLRICollection({self._context.afi}/{self._context.safi}, {len(self)} NLRIs)'


class MPNLRICollection:
    """Wire-format MP_REACH/MP_UNREACH NLRI container.

    Dual-mode:
    - Wire mode: __init__(packed, context, is_reach) - stores bytes, lazy parsing
    - Semantic mode: from_reach(mprnlri) / from_unreach(mpurnlri)

    This class follows the packed-bytes-first pattern where wire format
    is the canonical representation and semantic values are derived lazily.
    """

    _MODE_PACKED = 1  # Created from wire bytes (unpack path)
    _MODE_SEMANTIC = 2  # Created from MPRNLRI/MPURNLRI (semantic path)

    def __init__(self, packed: bytes, context: OpenContext, is_reach: bool = True) -> None:
        """Create MPNLRICollection from wire-format bytes.

        Args:
            packed: Wire-format payload for MP_REACH or MP_UNREACH attribute.
                    MP_REACH format: AFI(2) + SAFI(1) + NH_len(1) + NH + reserved(1) + NLRI
                    MP_UNREACH format: AFI(2) + SAFI(1) + NLRI
            context: OpenContext with AFI/SAFI and parsing options.
            is_reach: True for MP_REACH_NLRI, False for MP_UNREACH_NLRI.
        """
        self._packed = packed
        self._context = context
        self._is_reach = is_reach
        self._mode = self._MODE_PACKED
        self._nlris_cache: list[NLRI] = _UNPARSED
        self._mp_attr: 'MPRNLRI | MPURNLRI | None' = None

        # Parse AFI/SAFI from wire header
        if len(packed) >= 3:
            _afi = unpack('!H', packed[:2])[0]
            _safi = packed[2]
            self._afi = AFI.from_int(_afi)
            self._safi = SAFI.from_int(_safi)
        else:
            self._afi = context.afi
            self._safi = context.safi

    @classmethod
    def from_reach(cls, mprnlri: 'MPRNLRI') -> 'MPNLRICollection':
        """Create MPNLRICollection from MPRNLRI attribute.

        Args:
            mprnlri: Parsed MPRNLRI attribute object.

        Returns:
            MPNLRICollection in semantic mode.
        """
        context = mprnlri._context
        instance = cls(mprnlri._packed, context, is_reach=True)
        instance._mode = cls._MODE_SEMANTIC
        instance._mp_attr = mprnlri
        instance._afi = mprnlri.afi
        instance._safi = mprnlri.safi
        return instance

    @classmethod
    def from_unreach(cls, mpurnlri: 'MPURNLRI') -> 'MPNLRICollection':
        """Create MPNLRICollection from MPURNLRI attribute.

        Args:
            mpurnlri: Parsed MPURNLRI attribute object.

        Returns:
            MPNLRICollection in semantic mode.
        """
        context = mpurnlri._context
        instance = cls(mpurnlri._packed, context, is_reach=False)
        instance._mode = cls._MODE_SEMANTIC
        instance._mp_attr = mpurnlri
        instance._afi = mpurnlri.afi
        instance._safi = mpurnlri.safi
        return instance

    @property
    def packed(self) -> bytes:
        """Raw MP attribute payload bytes."""
        return self._packed

    @property
    def nlris(self) -> list[NLRI]:
        """Get the list of NLRIs, parsing from wire format if needed."""
        if self._nlris_cache is not _UNPARSED:
            return self._nlris_cache

        # Semantic mode: delegate to MP attribute
        if self._mode == self._MODE_SEMANTIC and self._mp_attr is not None:
            self._nlris_cache = self._mp_attr.nlris
            return self._nlris_cache

        # Wire mode: parse from packed bytes
        if self._mode == self._MODE_PACKED:
            self._nlris_cache = self._parse_nlris()
            return self._nlris_cache

        return []

    def _parse_nlris(self) -> list[NLRI]:
        """Parse NLRIs from wire format.

        Delegates to MPRNLRI or MPURNLRI unpack for proper parsing.
        """
        from exabgp.bgp.message.open.capability.negotiated import Negotiated
        from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
        from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI

        if not self._packed:
            return []

        # Use the appropriate MP attribute parser
        if self._is_reach:
            mp = MPRNLRI.unpack_attribute(self._packed, Negotiated.UNSET)
            self._mp_attr = mp
            return mp.nlris
        else:
            mp = MPURNLRI.unpack_attribute(self._packed, Negotiated.UNSET)
            self._mp_attr = mp
            return mp.nlris

    @property
    def afi(self) -> AFI:
        """Address Family Identifier from MP attribute header."""
        return self._afi

    @property
    def safi(self) -> SAFI:
        """Subsequent Address Family Identifier from MP attribute header."""
        return self._safi

    @property
    def nexthop(self) -> IP | None:
        """Next-hop IP address (only for MP_REACH)."""
        if not self._is_reach:
            return None

        # Get nexthop from first NLRI if available
        nlris = self.nlris
        if nlris and hasattr(nlris[0], 'nexthop'):
            nh = nlris[0].nexthop
            if nh is not IP.NoNextHop:
                return nh
        return None

    def __len__(self) -> int:
        """Return number of NLRIs in collection."""
        return len(self.nlris)

    def __repr__(self) -> str:
        reach_type = 'REACH' if self._is_reach else 'UNREACH'
        return f'MPNLRICollection({reach_type}, {self._afi}/{self._safi}, {len(self)} NLRIs)'
