"""route.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection
    from exabgp.bgp.message.update.nlri.nlri import NLRI
    from exabgp.protocol.family import AFI, SAFI

from exabgp.bgp.message import Action
from exabgp.protocol.ip import IP


class Route:
    """A Route is an NLRI with attributes and operation context.

    Route is IMMUTABLE after creation. Use with_action() or with_nexthop()
    to create modified copies.

    The action field indicates whether this route is being announced or withdrawn.
    This is operation context, not part of the NLRI identity - the same NLRI can
    be announced and later withdrawn.

    During the transition period, action/nexthop fall back to nlri values if not set.
    Eventually, action and nexthop will only be stored in Route, not in NLRI.
    """

    __slots__ = ('nlri', 'attributes', '_action', '_nexthop', '_Route__index')

    nlri: NLRI
    attributes: AttributeCollection
    _action: Action
    _nexthop: IP
    _Route__index: bytes

    @staticmethod
    def family_prefix(family: tuple[AFI, SAFI]) -> bytes:
        return b'%02x%02x' % family

    def __init__(
        self,
        nlri: NLRI,
        attributes: AttributeCollection,
        action: Action = Action.UNSET,
        nexthop: IP = IP.NoNextHop,
    ) -> None:
        self.nlri = nlri
        self.attributes = attributes
        self._action = action
        self._nexthop = nexthop
        # Index is computed lazily on first .index() call, not at __init__ time.
        # This is intentional: at construction time the NLRI may not be fully populated
        # (e.g., nexthop not yet set), which would cause api-attributes.sequence to fail.
        # The lazy evaluation ensures the index is computed only when all NLRI fields are set.
        self.__index = b''

    @property
    def action(self) -> Action:
        """Get the route action (ANNOUNCE/WITHDRAW).

        During transition: returns self._action if set, else falls back to nlri.action.
        Eventually: will only return self._action.
        """
        if self._action != Action.UNSET:
            return self._action
        # Fallback to nlri.action during transition period
        return self.nlri.action

    @property
    def nexthop(self) -> IP:
        """Get the route nexthop.

        During transition: returns self._nexthop if set, else falls back to nlri.nexthop.
        Eventually: will only return self._nexthop.
        """
        if self._nexthop is not IP.NoNextHop:
            return self._nexthop
        # Fallback to nlri.nexthop during transition period
        return self.nlri.nexthop

    def with_action(self, action: Action) -> 'Route':
        """Return a new Route with a different action.

        Route is immutable, so this creates a new instance.
        Uses self.nexthop (with fallback) to preserve nexthop during transition.
        """
        return Route(self.nlri, self.attributes, action=action, nexthop=self.nexthop)

    def with_nexthop(self, nexthop: IP) -> 'Route':
        """Return a new Route with a different nexthop.

        Route is immutable, so this creates a new instance.
        Uses self.action (with fallback) to preserve action during transition.
        Also syncs to nlri.nexthop during transition for code that reads from there.
        """
        # Sync to nlri.nexthop during transition - UpdateCollection reads from there
        self.nlri.nexthop = nexthop
        return Route(self.nlri, self.attributes, action=self.action, nexthop=nexthop)

    def index(self) -> bytes:
        if not self.__index:
            self.__index = b'%02x%02x' % self.nlri.family().afi_safi() + self.nlri.index()
        return self.__index

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Route):
            return False
        return self.nlri == other.nlri and self.attributes == other.attributes

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, Route):
            return True
        return self.nlri != other.nlri or self.attributes != other.attributes

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing Route for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing Route for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing Route for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing Route for ordering does not make sense')

    def extensive(self) -> str:
        # If you change this you must change as well extensive in Update
        return f'{self.nlri!s}{self.attributes!s}'

    def __repr__(self) -> str:
        return self.extensive()

    def feedback(self) -> str:
        if self.nlri is not None:
            return self.nlri.feedback(self.action)  # Use route.action, not nlri.action
        return 'no check implemented for the family {} {}'.format(*self.nlri.family().afi_safi())
