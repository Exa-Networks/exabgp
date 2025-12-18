"""community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# ============================================================== Communities (8)
# https://www.iana.org/assignments/bgp-extended-communities

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, Sequence

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    pass

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.initial.community import Community

# Community size constant
COMMUNITY_SIZE = 4  # Each standard community is 4 bytes (2 bytes ASN + 2 bytes value)


@Attribute.register()
class Communities(Attribute):
    """Communities attribute (code 8).

    Stores packed wire-format bytes. Each community is 4 bytes.
    """

    ID = Attribute.CODE.COMMUNITY
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL

    def __init__(self, packed: Buffer = b'') -> None:
        """Initialize from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_communities() for semantic construction.

        Args:
            packed: Raw communities bytes (concatenated 4-byte communities)
        """
        self._packed: Buffer = packed

    @classmethod
    def from_packet(cls, data: Buffer) -> 'Communities':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw attribute value bytes from wire

        Returns:
            Communities instance

        Raises:
            Notify: If data length is not a multiple of 4
        """
        if len(data) % COMMUNITY_SIZE != 0:
            raise Notify(3, 1, 'could not decode community {}'.format(str([hex(_) for _ in data])))
        return cls(data)

    @classmethod
    def make_communities(cls, communities: Sequence[Community]) -> 'Communities':
        """Create from list of Community objects.

        Args:
            communities: Sequence of Community objects

        Returns:
            Communities instance
        """
        # Sort communities and pack
        sorted_communities = sorted(communities)
        packed = b''.join(c.pack_attribute(Negotiated.UNSET) for c in sorted_communities)
        return cls(packed)

    def add(self, data: Community) -> 'Communities':
        """Add a community and return self (builder pattern).

        Note: This unpacks, adds, sorts, and repacks. For building many communities,
        consider collecting them first and using make_communities().
        """
        communities = list(self.communities)
        communities.append(data)
        communities.sort()
        self._packed = b''.join(c.pack_attribute(Negotiated.UNSET) for c in communities)
        return self

    @property
    def communities(self) -> list[Community]:
        """Get list of Community objects by unpacking from bytes."""
        result: list[Community] = []
        data = self._packed
        while data:
            result.append(Community(data[:COMMUNITY_SIZE]))
            data = data[COMMUNITY_SIZE:]
        return result

    def __len__(self) -> int:
        return len(self._packed)

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        if self._packed:
            return self._attribute(self._packed)
        return b''

    def __iter__(self) -> Iterator[Community]:
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
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Attribute:
        return cls.from_packet(data)
