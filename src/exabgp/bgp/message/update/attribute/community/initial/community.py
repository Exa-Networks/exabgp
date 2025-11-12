"""community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from struct import unpack
from typing import TYPE_CHECKING, Any, ClassVar, Dict

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated


# ==================================================================== Community
#


class Community:
    MAX: ClassVar[int] = 0xFFFFFFFF

    NO_EXPORT: ClassVar[bytes] = pack('!L', 0xFFFFFF01)
    NO_ADVERTISE: ClassVar[bytes] = pack('!L', 0xFFFFFF02)
    NO_EXPORT_SUBCONFED: ClassVar[bytes] = pack('!L', 0xFFFFFF03)
    NO_PEER: ClassVar[bytes] = pack('!L', 0xFFFFFF04)
    BLACKHOLE: ClassVar[bytes] = pack('!L', 0xFFFF029A)

    cache: ClassVar[Dict[bytes, Community]] = {}
    caching: ClassVar[bool] = True

    def __init__(self, community: bytes) -> None:
        self.community: bytes = community
        self._str: str
        if community == self.NO_EXPORT:
            self._str = 'no-export'
        elif community == self.NO_ADVERTISE:
            self._str = 'no-advertise'
        elif community == self.NO_EXPORT_SUBCONFED:
            self._str = 'no-export-subconfed'
        elif community == self.NO_PEER:
            self._str = 'no-peer'
        elif community == self.BLACKHOLE:
            self._str = 'blackhole'
        else:
            self._str = '%d:%d' % unpack('!HH', self.community)

    def __eq__(self, other: object) -> bool:
        return self.community == other.community  # type: ignore[attr-defined]

    def __ne__(self, other: object) -> bool:
        return self.community != other.community  # type: ignore[attr-defined]

    def __lt__(self, other: object) -> bool:
        return self.community < other.community  # type: ignore[attr-defined]

    def __le__(self, other: object) -> bool:
        return self.community <= other.community  # type: ignore[attr-defined]

    def __gt__(self, other: object) -> bool:
        return self.community > other.community  # type: ignore[attr-defined]

    def __ge__(self, other: object) -> bool:
        return self.community >= other.community  # type: ignore[attr-defined]

    def json(self) -> str:
        return '[ %d, %d ]' % unpack('!HH', self.community)

    def pack(self, negotiated: Negotiated = None) -> bytes:  # type: ignore[assignment]
        return self.community

    def __repr__(self) -> str:
        return self._str

    def __len__(self) -> int:
        return 4

    @classmethod
    def unpack(cls, community: bytes, direction: Any, negotiated: Negotiated) -> Community:
        return cls(community)

    @classmethod
    def cached(cls, community: bytes) -> Community:
        if not cls.caching:
            return cls(community)
        if community in cls.cache:
            return cls.cache[community]
        instance = cls(community)
        cls.cache[community] = instance
        return instance


# Always cache well-known communities, they will be used a lot
if not Community.cache:
    Community.cache[Community.NO_EXPORT] = Community(Community.NO_EXPORT)
    Community.cache[Community.NO_ADVERTISE] = Community(Community.NO_ADVERTISE)
    Community.cache[Community.NO_EXPORT_SUBCONFED] = Community(Community.NO_EXPORT_SUBCONFED)
    Community.cache[Community.NO_PEER] = Community(Community.NO_PEER)
    Community.cache[Community.BLACKHOLE] = Community(Community.BLACKHOLE)
