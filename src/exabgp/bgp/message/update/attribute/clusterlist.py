"""clusterlist.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Sequence

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.protocol.ip import IPv4

# ===================================================================
#


class ClusterID(IPv4):
    pass


@Attribute.register()
class ClusterList(Attribute):
    """Cluster List attribute (code 10).

    Stores packed wire-format bytes. Each cluster ID is a 4-byte IPv4 address.
    """

    ID: ClassVar[int] = Attribute.CODE.CLUSTER_LIST
    FLAG: ClassVar[int] = Attribute.Flag.OPTIONAL
    CACHING: ClassVar[bool] = True

    def __init__(self, packed: Buffer) -> None:
        """Initialize from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_clusterlist() for semantic construction.

        Args:
            packed: Raw cluster list bytes (concatenated 4-byte IPv4 addresses)
        """
        self._packed: Buffer = packed

    @classmethod
    def from_packet(cls, data: Buffer) -> 'ClusterList':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw attribute value bytes from wire

        Returns:
            ClusterList instance

        Raises:
            ValueError: If data length is not a multiple of 4
        """
        if len(data) % 4 != 0:
            raise ValueError(f'ClusterList must be a multiple of 4 bytes, got {len(data)}')
        return cls(data)

    @classmethod
    def make_clusterlist(cls, clusters: Sequence[IPv4]) -> 'ClusterList':
        """Create from list of cluster IDs.

        Args:
            clusters: Sequence of IPv4 cluster IDs

        Returns:
            ClusterList instance
        """
        packed = b''.join(c.pack_ip() for c in clusters)
        return cls(packed)

    @property
    def clusters(self) -> list[IPv4]:
        """Get list of cluster IDs by unpacking from bytes."""
        result: list[IPv4] = []
        data = self._packed
        while data:
            result.append(IPv4.unpack_ipv4(data[:4]))
            data = data[4:]
        return result

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ClusterList):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __len__(self) -> int:
        return len(self._packed)

    def __repr__(self) -> str:
        clusters = self.clusters
        if len(clusters) != 1:
            return '[ {} ]'.format(' '.join([str(_) for _ in clusters]))
        return '{}'.format(clusters[0])

    def json(self) -> str:
        return '[ {} ]'.format(', '.join(['"{}"'.format(str(_)) for _ in self.clusters]))

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        return self._attribute(self._packed)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Attribute:
        return cls.from_packet(data)
