"""empty.py

Empty NLRI for attributes-only UPDATE messages.

Created for API command round-trip testing (empty UPDATE with just attributes).
Copyright (c) 2024 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.family import AFI, SAFI
from exabgp.util.types import Buffer


class Empty(NLRI):
    """Empty NLRI for attributes-only UPDATE messages.

    This NLRI type represents "no routes" and is used to generate
    UPDATE messages that contain only path attributes (no NLRI).

    Such messages are valid per RFC 4271 but don't announce or withdraw
    any routes - they're primarily useful for testing.
    """

    __slots__ = ()

    # Class attribute to identify Empty NLRI instances
    EMPTY_NLRI = True

    def __init__(self, afi: AFI = AFI.ipv4, safi: SAFI = SAFI.unicast) -> None:
        """Create an Empty NLRI.

        Args:
            afi: Address Family Identifier (default: ipv4)
            safi: Subsequent Address Family Identifier (default: unicast)
        """
        super().__init__(afi, safi, PathInfo.DISABLED)
        self._packed = b''

    def pack_nlri(self, negotiated: 'Negotiated') -> Buffer:
        """Pack to empty bytes (no NLRI)."""
        return b''

    def json(self, compact: bool = False) -> str:
        """JSON representation (empty object)."""
        return '{}'

    def __str__(self) -> str:
        return 'empty'

    def __repr__(self) -> str:
        return 'Empty()'

    def __copy__(self) -> 'Empty':
        new = object.__new__(Empty)
        self._copy_nlri_slots(new)
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'Empty':
        new = object.__new__(Empty)
        self._deepcopy_nlri_slots(new, memo)
        return new

    def feedback(self, action: Action) -> str:
        return 'empty'
