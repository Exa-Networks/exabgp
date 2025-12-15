"""Copyright (c) 2016 Job Snijders <job@ntt.net>
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util.types import Buffer
from typing import TYPE_CHECKING, Iterator, Sequence

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.large.community import LargeCommunity

# Large community size constant
LARGE_COMMUNITY_SIZE = (
    12  # Each large community is 12 bytes (4 bytes global admin + 4 bytes local data 1 + 4 bytes local data 2)
)


@Attribute.register()
class LargeCommunities(Attribute):
    """Large Communities attribute (code 32).

    Stores packed wire-format bytes. Each large community is 12 bytes.
    """

    ID = Attribute.CODE.LARGE_COMMUNITY
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL
    TREAT_AS_WITHDRAW = True

    def __init__(self, packed: Buffer = b'') -> None:
        """Initialize from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_large_communities() for semantic construction.

        Args:
            packed: Raw large communities bytes (concatenated 12-byte large communities)
        """
        self._packed: Buffer = packed

    @classmethod
    def from_packet(cls, data: Buffer) -> 'LargeCommunities':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw attribute value bytes from wire

        Returns:
            LargeCommunities instance

        Raises:
            Notify: If data length is not a multiple of 12
        """
        if len(data) % LARGE_COMMUNITY_SIZE != 0:
            raise Notify(3, 1, 'could not decode large community {}'.format(str([hex(_) for _ in data])))
        # Deduplicate while preserving order
        seen: set[bytes] = set()
        unique_packed = b''
        offset = 0
        while offset < len(data):
            chunk = data[offset : offset + LARGE_COMMUNITY_SIZE]
            if chunk not in seen:
                seen.add(chunk)
                unique_packed += chunk
            offset += LARGE_COMMUNITY_SIZE
        return cls(unique_packed)

    @classmethod
    def make_large_communities(cls, communities: Sequence[LargeCommunity]) -> 'LargeCommunities':
        """Create from list of LargeCommunity objects.

        Args:
            communities: Sequence of LargeCommunity objects

        Returns:
            LargeCommunities instance
        """
        # Sort and deduplicate
        sorted_communities = sorted(set(communities))
        packed = b''.join(c.pack_attribute(None) for c in sorted_communities)
        return cls(packed)

    def add(self, data: LargeCommunity) -> 'LargeCommunities':
        """Add a large community and return self (builder pattern).

        Note: This unpacks, adds, sorts, and repacks. For building many communities,
        consider collecting them first and using make_large_communities().
        """
        communities = list(self.communities)
        if data not in communities:
            communities.append(data)
            communities.sort()
        self._packed = b''.join(c.pack_attribute(None) for c in communities)
        return self

    @property
    def communities(self) -> list[LargeCommunity]:
        """Get list of LargeCommunity objects by unpacking from bytes."""
        result: list[LargeCommunity] = []
        data = self._packed
        while data:
            result.append(LargeCommunity(data[:LARGE_COMMUNITY_SIZE]))
            data = data[LARGE_COMMUNITY_SIZE:]
        return result

    def __len__(self) -> int:
        return len(self._packed)

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        if self._packed:
            return self._attribute(self._packed)
        return b''

    def __iter__(self) -> Iterator[LargeCommunity]:
        return iter(self.communities)

    def __repr__(self) -> str:
        communities = self.communities
        lc = len(communities)
        if lc > 1:
            return '[ {} ]'.format(' '.join(repr(community) for community in sorted(communities)))
        if lc == 1:
            return repr(communities[0])
        return ''

    def json(self) -> str:
        return '[ {} ]'.format(', '.join(community.json() for community in self.communities))

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> 'LargeCommunities':
        return cls.from_packet(data)
