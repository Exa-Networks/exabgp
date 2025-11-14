"""Support for RFC 8092

Copyright (c) 2016 Job Snijders <job@ntt.net>
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Dict

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute import Attribute

from struct import unpack


class LargeCommunity(Attribute):
    MAX: ClassVar[int] = 0xFFFFFFFFFFFFFFFFFFFFFFFF

    cache: ClassVar[Dict[bytes, LargeCommunity]] = {}
    caching: ClassVar[bool] = True

    def __init__(self, large_community: bytes) -> None:
        self.large_community: bytes = large_community
        self._str: str = '%d:%d:%d' % unpack('!LLL', self.large_community)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LargeCommunity):
            return False
        return self.large_community == other.large_community

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, LargeCommunity):
            return True
        return self.large_community != other.large_community

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, LargeCommunity):
            return NotImplemented
        return self.large_community < other.large_community

    def __le__(self, other: object) -> bool:
        if not isinstance(other, LargeCommunity):
            return NotImplemented
        return self.large_community <= other.large_community

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, LargeCommunity):
            return NotImplemented
        return self.large_community > other.large_community

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, LargeCommunity):
            return NotImplemented
        return self.large_community >= other.large_community

    def json(self) -> str:
        return '[ %d, %d , %d ]' % unpack('!LLL', self.large_community)

    def pack(self, negotiated: Negotiated = None) -> bytes:  # type: ignore[assignment]
        return self.large_community

    def __repr__(self) -> str:
        return self._str

    def __len__(self) -> int:
        return 12

    @classmethod
    def unpack_attribute(cls, large_community: bytes, negotiated: Negotiated) -> LargeCommunity:
        return cls(large_community)

    @classmethod
    def cached(cls, large_community: bytes) -> LargeCommunity:
        if not cls.caching:
            return cls(large_community)
        if large_community in cls.cache:
            return cls.cache[large_community]
        instance = cls(large_community)
        cls.cache[large_community] = instance
        return instance
