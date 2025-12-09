"""nlri.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Type, TypeVar

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.protocol.ip import IP
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.logger import lazynlri, log
from exabgp.protocol.family import AFI, SAFI, Family

T = TypeVar('T', bound='NLRI')

# Sentinel for unparsed NLRI cache (distinguishes "not parsed" from "parsed empty")
# Use `is _UNPARSED` / `is not _UNPARSED` for comparison
_UNPARSED: list['NLRI'] = []


class NLRI(Family):
    """Base class for all NLRI types.

    Single-family types (VPLS, RTC, EVPN): Define afi/safi as class attributes,
    which shadow the inherited slots and make them read-only.

    Multi-family types (INET, Flow): Use inherited slots for instance storage.
    """

    # Slots for NLRI base class (subclasses add their own slots)
    # afi/safi inherited from Family.__slots__
    __slots__ = ('action', 'nexthop', 'addpath', '_packed')

    EOR: ClassVar[bool] = False

    registered_nlri: ClassVar[dict[str, Type[NLRI]]] = dict()
    registered_families: ClassVar[list[tuple[AFI, SAFI]]] = [(AFI.ipv4, SAFI.multicast)]

    action: Action
    nexthop: 'IP'
    addpath: 'PathInfo'
    _packed: Buffer  # Wire format bytes (subclass-specific interpretation)

    # Singleton invalid NLRI (initialized after class definition)
    INVALID: ClassVar['NLRI']
    # Singleton empty NLRI for cleared references (initialized after class definition)
    EMPTY: ClassVar['NLRI']

    @classmethod
    def _create_singleton(cls, name: str) -> 'NLRI':
        """Create a singleton NLRI (INVALID or EMPTY). Called once at module load."""
        instance = object.__new__(cls)
        instance.afi = AFI.undefined
        instance.safi = SAFI.undefined
        instance.action = Action.UNSET
        instance.addpath = PathInfo.DISABLED
        instance._packed = b''
        return instance

    def __init__(
        self, afi: AFI, safi: SAFI, action: Action = Action.UNSET, addpath: PathInfo = PathInfo.DISABLED
    ) -> None:
        """Initialize NLRI base class.

        Args:
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier
            action: UNSET by default - MUST be set to ANNOUNCE or WITHDRAW after creation.
                    Code checking action should raise an error if it encounters UNSET.
            addpath: Path identifier for ADD-PATH (RFC 7911), DISABLED by default
        """
        Family.__init__(self, afi, safi)
        self.action = action
        self.nexthop = IP.NoNextHop  # Default nexthop - set by subclasses if needed
        self.addpath = addpath
        self._packed = b''  # Subclasses set actual wire data

    def _copy_nlri_slots(self, new: 'NLRI') -> None:
        """Copy NLRI base class slots to new instance."""
        # Family.__slots__ = ('afi', 'safi')
        # Single-family types have read-only class-level afi/safi - skip those
        try:
            new.afi = self.afi
        except AttributeError:
            pass  # Read-only class attribute
        try:
            new.safi = self.safi
        except AttributeError:
            pass  # Read-only class attribute
        # NLRI.__slots__ = ('action', 'nexthop', 'addpath', '_packed')
        new.action = self.action
        new.nexthop = self.nexthop
        new.addpath = self.addpath
        new._packed = self._packed

    def _deepcopy_nlri_slots(self, new: 'NLRI', memo: dict[Any, Any]) -> None:
        """Deep copy NLRI base class slots to new instance."""
        # Family.__slots__ = ('afi', 'safi') - singletons, no deepcopy needed
        # Single-family types have read-only class-level afi/safi - skip those
        try:
            new.afi = self.afi
        except AttributeError:
            pass  # Read-only class attribute
        try:
            new.safi = self.safi
        except AttributeError:
            pass  # Read-only class attribute
        # NLRI.__slots__ = ('action', 'nexthop', 'addpath', '_packed')
        new.action = self.action  # int - immutable
        new.nexthop = deepcopy(self.nexthop, memo)
        new.addpath = self.addpath  # PathInfo - typically shared singleton
        new._packed = self._packed  # bytes - immutable

    def __copy__(self) -> 'NLRI':
        """Preserve singleton identity for INVALID and EMPTY."""
        if self is NLRI.INVALID or self is NLRI.EMPTY:
            return self
        # Subclasses should override and call _copy_nlri_slots
        raise NotImplementedError(f'{type(self).__name__} must implement __copy__')

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'NLRI':
        """Preserve singleton identity for INVALID and EMPTY."""
        if self is NLRI.INVALID or self is NLRI.EMPTY:
            return self
        # Subclasses should override and call _deepcopy_nlri_slots
        raise NotImplementedError(f'{type(self).__name__} must implement __deepcopy__')

    def __hash__(self) -> int:
        return hash('{}:{}:{}'.format(self.afi, self.safi, self.pack_nlri(Negotiated.UNSET).hex()))

    def __eq__(self, other: Any) -> bool:
        return bool(self.index() == other.index())

    def __ne__(self, other: Any) -> bool:
        return bool(self.index() != other.index())

    # does not really make sense but allows to get the NLRI in a
    # deterministic order when generating update (Good for testing)

    def __lt__(self, other: Any) -> bool:
        return bool(self.index() < other.index())

    def __le__(self, other: Any) -> bool:
        return bool(self == other or self.index() < other.index())

    def __gt__(self, other: Any) -> bool:
        return bool(self.index() > other.index())

    def __ge__(self, other: Any) -> bool:
        return bool(self == other or self.index() > other.index())

    def feedback(self, action: Action) -> str:
        raise RuntimeError('feedback is not implemented')

    def add(self, data: Any) -> bool:
        """Add data to NLRI. Only implemented by Flow NLRI."""
        raise NotImplementedError('add() only implemented by Flow NLRI')

    def index(self) -> bytes:
        return bytes(Family.index(self)) + self.pack_nlri(Negotiated.UNSET)

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        raise Exception('unimplemented in NLRI children class')

    def json(self, compact: bool = False) -> str:
        """Serialize NLRI to JSON format. Must be implemented by subclasses."""
        raise NotImplementedError('json() must be implemented by NLRI subclasses')

    def v4_json(self, compact: bool = False) -> str:
        """Serialize NLRI to JSON format for API v4 backward compatibility.

        By default, returns the same as json(). Override in subclasses that need
        to include deprecated fields (like nexthop) for v4 compatibility.
        """
        return self.json(compact=compact)

    @classmethod
    def register(cls, afi: int, safi: int, force: bool = False) -> Callable[[Type[NLRI]], Type[NLRI]]:
        def register_nlri(klass: Type[NLRI]) -> Type[NLRI]:
            new: tuple[AFI, SAFI] = (AFI.from_int(afi), SAFI.from_int(safi))
            if new in cls.registered_nlri:
                if force:
                    # python has a bug and does not allow %ld/%ld (pypy does)
                    cls.registered_nlri['{}/{}'.format(*new)] = klass
                else:
                    raise RuntimeError('Tried to register {}/{} twice'.format(*new))
            else:
                # python has a bug and does not allow %ld/%ld (pypy does)
                cls.registered_nlri['{}/{}'.format(*new)] = klass
                cls.registered_families.append(new)
            return klass

        return register_nlri

    @staticmethod
    def known_families() -> list[tuple[AFI, SAFI]]:
        # we do not want to take the risk of the caller modifying the list by accident
        # it can not be a generator
        return list(NLRI.registered_families)

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[NLRI, Buffer]:
        a: AFI
        s: SAFI
        a, s = AFI.from_int(afi), SAFI.from_int(safi)
        log.debug(lazynlri(a, s, addpath, bytes(data)), 'parser')

        key: str = '{}/{}'.format(a, s)
        if key in cls.registered_nlri:
            return cls.registered_nlri[key].unpack_nlri(a, s, data, action, addpath, negotiated)
        raise Notify(3, 0, 'trying to decode unknown family {}/{}'.format(a, s))


# Initialize the NLRI singletons
NLRI.INVALID = NLRI._create_singleton('INVALID')
NLRI.EMPTY = NLRI._create_singleton('EMPTY')
