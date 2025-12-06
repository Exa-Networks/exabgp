"""nlri.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Type, TypeVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.protocol.ip import IP

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family
from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo

from exabgp.logger import log
from exabgp.logger import lazynlri

T = TypeVar('T', bound='NLRI')


class NLRI(Family):
    """Base class for all NLRI types.

    Subclasses can define class-level AFI/SAFI via _class_afi/_class_safi ClassVars
    and corresponding @property accessors. Family.__init__ will detect these and
    skip instance attribute assignment.

    Single-family types: Set _class_afi and _class_safi, define afi/safi properties
    Multi-family types: Leave _class_afi as None, use instance afi attribute
    """

    EOR: ClassVar[bool] = False

    registered_nlri: ClassVar[dict[str, Type[NLRI]]] = dict()
    registered_families: ClassVar[list[tuple[AFI, SAFI]]] = [(AFI.ipv4, SAFI.multicast)]

    # Inherited from Family, redeclared for documentation:
    # _class_afi: ClassVar[AFI | None] = None  # Set by single-family subclasses
    # _class_safi: ClassVar[SAFI | None] = None  # Set by single-family subclasses

    action: int
    nexthop: 'IP'
    addpath: 'PathInfo'
    _packed: bytes  # Wire format bytes (subclass-specific interpretation)

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

    def __init__(self, afi: AFI, safi: SAFI, action: int = Action.UNSET, addpath: PathInfo = PathInfo.DISABLED) -> None:
        Family.__init__(self, afi, safi)
        self.action = action
        self.addpath = addpath
        self._packed = b''  # Subclasses set actual wire data

    def __copy__(self) -> 'NLRI':
        """Preserve singleton identity for INVALID and EMPTY."""
        if self is NLRI.INVALID or self is NLRI.EMPTY:
            return self
        # Regular NLRI: create a shallow copy
        new = self.__class__.__new__(self.__class__)
        new.__dict__.update(self.__dict__)
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'NLRI':
        """Preserve singleton identity for INVALID and EMPTY."""
        if self is NLRI.INVALID or self is NLRI.EMPTY:
            return self
        # Regular NLRI: create a deep copy
        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        for k, v in self.__dict__.items():
            setattr(new, k, deepcopy(v, memo))
        return new

    def __hash__(self) -> int:
        return hash('{}:{}:{}'.format(self.afi, self.safi, self.pack_nlri().hex()))  # type: ignore[call-arg]

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

    def feedback(self, action: int) -> None:
        raise RuntimeError('feedback is not implemented')

    def assign(self, name: str, value: Any) -> None:
        setattr(self, name, value)

    def add(self, data: Any) -> bool:
        """Add data to NLRI. Only implemented by Flow NLRI."""
        raise NotImplementedError('add() only implemented by Flow NLRI')

    def index(self) -> bytes:
        return Family.index(self) + self.pack_nlri()  # type: ignore[call-arg]

    def pack_nlri(self, negotiated: Negotiated) -> bytes:
        raise Exception('unimplemented in NLRI children class')

    def json(self, compact: bool = False) -> str:
        """Serialize NLRI to JSON format. Must be implemented by subclasses."""
        raise NotImplementedError('json() must be implemented by NLRI subclasses')

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
        cls, afi: AFI, safi: SAFI, data: bytes, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[NLRI, bytes]:
        a: AFI
        s: SAFI
        a, s = AFI.from_int(afi), SAFI.from_int(safi)
        log.debug(lazynlri(a, s, addpath, data), 'parser')

        key: str = '{}/{}'.format(a, s)
        if key in cls.registered_nlri:
            return cls.registered_nlri[key].unpack_nlri(a, s, data, action, addpath, negotiated)
        raise Notify(3, 0, 'trying to decode unknown family {}/{}'.format(a, s))


# Initialize the NLRI singletons
NLRI.INVALID = NLRI._create_singleton('INVALID')
NLRI.EMPTY = NLRI._create_singleton('EMPTY')
