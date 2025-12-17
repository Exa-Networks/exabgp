"""Extended community collection attributes (RFC 4360, RFC 5701).

Extended communities are 8-byte values used for VPN route targets,
traffic engineering, and FlowSpec actions. IPv6 extended communities
are 20 bytes.

Key classes:
    ExtendedCommunitiesBase: Abstract base for community collections
    ExtendedCommunities: IPv4 extended community attribute
    ExtendedCommunitiesIPv6: IPv6 extended community attribute

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Iterator, Sequence

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.extended.community import (
    ExtendedCommunity,
    ExtendedCommunityBase,
    ExtendedCommunityIPv6,
)

# Extended Community size constants (RFC 4360, RFC 5701)
EXTENDED_COMMUNITY_SIZE = 8  # Standard extended community size
EXTENDED_COMMUNITY_IPV6_SIZE = 20  # IPv6 extended community size


# ===================================================== ExtendedCommunitiesBase
# Abstract base class for extended community attributes


class ExtendedCommunitiesBase(Attribute, ABC):
    """Abstract base class for extended community attributes.

    Defines the common interface for ExtendedCommunities (code 16) and
    ExtendedCommunitiesIPv6 (code 25).
    """

    _packed: Buffer

    @property
    @abstractmethod
    def communities(self) -> list[Any]:
        """Get list of community objects by unpacking from bytes."""
        ...

    @abstractmethod
    def add(self, data: Any) -> 'ExtendedCommunitiesBase':
        """Add a community and return self (builder pattern)."""
        ...


# ===================================================== ExtendedCommunities (16)
# https://www.iana.org/assignments/bgp-extended-communities


@Attribute.register()
class ExtendedCommunities(ExtendedCommunitiesBase):
    """Extended Communities attribute (code 16).

    Stores packed wire-format bytes. Each extended community is 8 bytes.
    """

    ID = Attribute.CODE.EXTENDED_COMMUNITY
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL

    def __init__(self, packed: Buffer = b'') -> None:
        """Initialize from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_extended_communities() for semantic construction.

        Args:
            packed: Raw extended communities bytes (concatenated 8-byte extended communities)
        """
        self._packed: Buffer = packed

    @classmethod
    def from_packet(cls, data: Buffer) -> 'ExtendedCommunities':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw attribute value bytes from wire

        Returns:
            ExtendedCommunities instance

        Raises:
            Notify: If data length is not a multiple of 8
        """
        if len(data) % EXTENDED_COMMUNITY_SIZE != 0:
            raise Notify(3, 1, 'could not decode extended community {}'.format(str([hex(_) for _ in data])))
        return cls(data)

    @classmethod
    def make_extended_communities(cls, communities: Sequence[ExtendedCommunityBase]) -> 'ExtendedCommunities':
        """Create from list of ExtendedCommunity objects.

        Args:
            communities: Sequence of ExtendedCommunityBase objects

        Returns:
            ExtendedCommunities instance
        """
        sorted_communities = sorted(communities)
        packed = b''.join(c.pack_attribute(None) for c in sorted_communities)
        return cls(packed)

    def add(self, data: ExtendedCommunityBase) -> 'ExtendedCommunities':
        """Add an extended community and return self (builder pattern).

        Note: This unpacks, adds, sorts, and repacks.
        """
        communities = list(self.communities)
        communities.append(data)
        communities.sort()
        self._packed = b''.join(c.pack_attribute(None) for c in communities)
        return self

    @property
    def communities(self) -> list[ExtendedCommunityBase]:
        """Get list of ExtendedCommunity objects by unpacking from bytes."""
        result: list[ExtendedCommunityBase] = []
        data = self._packed
        while data:
            result.append(ExtendedCommunity.unpack_attribute(data[:EXTENDED_COMMUNITY_SIZE], None))
            data = data[EXTENDED_COMMUNITY_SIZE:]
        return result

    def __len__(self) -> int:
        return len(self._packed)

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        if self._packed:
            return self._attribute(self._packed)
        return b''

    def __iter__(self) -> Iterator[ExtendedCommunityBase]:
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


# ===================================================== ExtendedCommunitiesIPv6 (25)
# RFC 5701


@Attribute.register()
class ExtendedCommunitiesIPv6(ExtendedCommunitiesBase):
    """IPv6 Extended Communities attribute (code 25).

    Stores packed wire-format bytes. Each IPv6 extended community is 20 bytes.
    """

    ID = Attribute.CODE.IPV6_EXTENDED_COMMUNITY
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL

    def __init__(self, packed: Buffer = b'') -> None:
        """Initialize from packed wire-format bytes."""
        self._packed: Buffer = packed

    @classmethod
    def from_packet(cls, data: Buffer) -> 'ExtendedCommunitiesIPv6':
        """Validate and create from wire-format bytes."""
        if len(data) % EXTENDED_COMMUNITY_IPV6_SIZE != 0:
            raise Notify(3, 1, 'could not decode ipv6 extended community {}'.format(str([hex(_) for _ in data])))
        return cls(data)

    @classmethod
    def make_extended_communities_ipv6(cls, communities: Sequence[ExtendedCommunityIPv6]) -> 'ExtendedCommunitiesIPv6':
        """Create from list of ExtendedCommunityIPv6 objects."""
        sorted_communities = sorted(communities)
        packed = b''.join(c.pack_attribute(None) for c in sorted_communities)
        return cls(packed)

    def add(self, data: ExtendedCommunityIPv6) -> 'ExtendedCommunitiesIPv6':
        """Add an IPv6 extended community and return self (builder pattern)."""
        communities = list(self.communities)
        communities.append(data)
        communities.sort()
        self._packed = b''.join(c.pack_attribute(None) for c in communities)
        return self

    @property
    def communities(self) -> list[ExtendedCommunityIPv6]:
        """Get list of ExtendedCommunityIPv6 objects by unpacking from bytes."""
        result: list[ExtendedCommunityIPv6] = []
        data = self._packed
        while data:
            community = ExtendedCommunityIPv6.unpack_attribute(data[:EXTENDED_COMMUNITY_IPV6_SIZE], None)
            result.append(community)
            data = data[EXTENDED_COMMUNITY_IPV6_SIZE:]
        return result

    def __len__(self) -> int:
        return len(self._packed)

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        if self._packed:
            return self._attribute(self._packed)
        return b''

    def __iter__(self) -> Iterator[ExtendedCommunityIPv6]:
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
