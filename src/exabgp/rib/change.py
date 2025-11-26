"""change.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from exabgp.bgp.message.update.nlri.nlri import NLRI
    from exabgp.bgp.message.update.attribute.attributes import Attributes
    from exabgp.protocol.family import AFI, SAFI


class Change:
    nlri: NLRI
    attributes: Attributes
    _Change__index: bytes

    @staticmethod
    def family_prefix(family: Tuple[AFI, SAFI]) -> bytes:
        return b'%02x%02x' % family

    def __init__(self, nlri: NLRI, attributes: Attributes) -> None:
        self.nlri = nlri
        self.attributes = attributes
        # Index is computed lazily on first .index() call, not at __init__ time.
        # This is intentional: at construction time the NLRI may not be fully populated
        # (e.g., nexthop not yet set), which would cause api-attributes.sequence to fail.
        # The lazy evaluation ensures the index is computed only when all NLRI fields are set.
        self.__index = b''

    def index(self) -> bytes:
        if not self.__index:
            self.__index = b'%02x%02x' % self.nlri.family().afi_safi() + self.nlri.index()
        return self.__index

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Change):
            return False
        return self.nlri == other.nlri and self.attributes == other.attributes

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, Change):
            return True
        return self.nlri != other.nlri or self.attributes != other.attributes

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing Change for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing Change for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing Change for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing Change for ordering does not make sense')

    def extensive(self) -> str:
        # If you change this you must change as well extensive in Update
        return f'{self.nlri!s}{self.attributes!s}'

    def __repr__(self) -> str:
        return self.extensive()

    def feedback(self) -> str:
        if self.nlri is not None:
            return self.nlri.feedback(self.nlri.action)  # type: ignore[func-returns-value,no-any-return]
        return 'no check implemented for the family {} {}'.format(*self.nlri.family().afi_safi())
