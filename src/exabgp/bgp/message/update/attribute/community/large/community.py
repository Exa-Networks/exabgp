"""Support for RFC 8092

Copyright (c) 2016 Job Snijders <job@ntt.net>
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Dict

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
        return self.large_community == other.large_community  # type: ignore[attr-defined]

    def __ne__(self, other: object) -> bool:
        return self.large_community != other.large_community  # type: ignore[attr-defined]

    def __lt__(self, other: object) -> bool:
        return self.large_community < other.large_community  # type: ignore[attr-defined]

    def __le__(self, other: object) -> bool:
        return self.large_community <= other.large_community  # type: ignore[attr-defined]

    def __gt__(self, other: object) -> bool:
        return self.large_community > other.large_community  # type: ignore[attr-defined]

    def __ge__(self, other: object) -> bool:
        return self.large_community >= other.large_community  # type: ignore[attr-defined]

    def json(self) -> str:
        return '[ %d, %d , %d ]' % unpack('!LLL', self.large_community)

    def pack(self, negotiated: Negotiated = None) -> bytes:  # type: ignore[assignment]
        return self.large_community

    def __repr__(self) -> str:
        return self._str

    def __len__(self) -> int:
        return 12

    @classmethod
    def unpack(cls, large_community: bytes, direction: Any, negotiated: Negotiated) -> LargeCommunity:
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
