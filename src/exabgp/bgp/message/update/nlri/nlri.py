"""nlri.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, ClassVar, Dict, List, Tuple, Type, TypeVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.protocol.ip import IP

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family
from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify

from exabgp.logger import log
from exabgp.logger import lazynlri

T = TypeVar('T', bound='NLRI')


class NLRI(Family):
    EOR: ClassVar[bool] = False

    registered_nlri: ClassVar[Dict[str, Type[NLRI]]] = dict()
    registered_families: ClassVar[List[Tuple[AFI, SAFI]]] = [(AFI.ipv4, SAFI.multicast)]

    action: int
    nexthop: 'IP'

    # Singleton invalid NLRI (initialized after class definition)
    INVALID: ClassVar['NLRI']

    @classmethod
    def _create_invalid(cls) -> 'NLRI':
        """Create the invalid NLRI singleton. Called once at module load.

        Used for "treat as withdraw" semantics when parsing fails.
        """
        # Bypass normal __init__
        instance = object.__new__(cls)
        instance.afi = AFI.undefined
        instance.safi = SAFI.undefined
        instance.action = Action.UNSET
        return instance

    def __init__(self, afi: AFI, safi: SAFI, action: int = Action.UNSET) -> None:
        Family.__init__(self, afi, safi)
        self.action = action

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

    def index(self) -> bytes:
        return Family.index(self) + self.pack_nlri()  # type: ignore[call-arg]

    def pack_nlri(self, negotiated: Negotiated) -> bytes:
        raise Exception('unimplemented in NLRI children class')

    @classmethod
    def register(cls, afi: int, safi: int, force: bool = False) -> Callable[[Type[NLRI]], Type[NLRI]]:
        def register_nlri(klass: Type[NLRI]) -> Type[NLRI]:
            new: Tuple[AFI, SAFI] = (AFI.create(afi), SAFI.create(safi))
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
    def known_families() -> List[Tuple[AFI, SAFI]]:
        # we do not want to take the risk of the caller modifying the list by accident
        # it can not be a generator
        return list(NLRI.registered_families)

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: bytes, action: Action, addpath: Any, negotiated: Negotiated
    ) -> Tuple[NLRI, bytes]:
        a: AFI
        s: SAFI
        a, s = AFI.create(afi), SAFI.create(safi)
        log.debug(lazynlri(a, s, addpath, data), 'parser')

        key: str = '{}/{}'.format(a, s)
        if key in cls.registered_nlri:
            return cls.registered_nlri[key].unpack_nlri(a, s, data, action, addpath, negotiated)
        raise Notify(3, 0, 'trying to decode unknown family {}/{}'.format(a, s))


# Initialize the invalid NLRI singleton
NLRI.INVALID = NLRI._create_invalid()
