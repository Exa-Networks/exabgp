"""nlri.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, ClassVar, Dict, List, Tuple, Type

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family
from exabgp.protocol.family import _AFI
from exabgp.protocol.family import _SAFI
from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify

from exabgp.logger import log
from exabgp.logger import lazynlri


class NLRI(Family):
    EOR: ClassVar[bool] = False

    registered_nlri: ClassVar[Dict[str, Type[NLRI]]] = dict()
    registered_families: ClassVar[List[Tuple[_AFI, _SAFI]]] = [(AFI.ipv4, SAFI.multicast)]

    action: int

    def __init__(self, afi: _AFI, safi: _SAFI, action: int = Action.UNSET) -> None:
        Family.__init__(self, afi, safi)
        self.action = action

    def __hash__(self) -> int:
        return hash('{}:{}:{}'.format(self.afi, self.safi, self.pack_nlri()))  # type: ignore[str-bytes-safe]

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
        return Family.index(self) + self.pack_nlri()

    # remove this when code restructure is finished
    def pack(self, negotiated: Negotiated = None) -> bytes:  # type: ignore[assignment]
        return self.pack_nlri(negotiated)

    def pack_nlri(self, negotiated: Negotiated = None) -> bytes:  # type: ignore[assignment]
        raise Exception('unimplemented in NLRI children class')

    @classmethod
    def register(cls, afi: int, safi: int, force: bool = False) -> Callable[[Type[NLRI]], Type[NLRI]]:
        def register_nlri(klass: Type[NLRI]) -> Type[NLRI]:
            new: Tuple[_AFI, _SAFI] = (AFI.create(afi), SAFI.create(safi))
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
    def known_families() -> List[Tuple[_AFI, _SAFI]]:
        # we do not want to take the risk of the caller modifying the list by accident
        # it can not be a generator
        return list(NLRI.registered_families)

    @classmethod
    def unpack_nlri(cls, afi: int, safi: int, data: bytes, action: int, addpath: bool) -> NLRI:
        a: _AFI
        s: _SAFI
        a, s = AFI.create(afi), SAFI.create(safi)
        log.debug(lazynlri(a, s, addpath, data), 'parser')

        key: str = '{}/{}'.format(a, s)
        if key in cls.registered_nlri:
            return cls.registered_nlri[key].unpack_nlri(a, s, data, action, addpath)
        raise Notify(3, 0, 'trying to decode unknown family {}/{}'.format(a, s))
