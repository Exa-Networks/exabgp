"""clusterlist.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.protocol.ip import IPv4

from exabgp.bgp.message.update.attribute.attribute import Attribute


# ===================================================================
#


class ClusterID(IPv4):
    def __init__(self, ip: str) -> None:
        IPv4.__init__(self, ip)


@Attribute.register()
class ClusterList(Attribute):
    ID = Attribute.CODE.CLUSTER_LIST
    FLAG = Attribute.Flag.OPTIONAL
    CACHING = True

    def __init__(self, clusters: List[IPv4], packed: Optional[bytes] = None) -> None:
        self.clusters: List[IPv4] = clusters
        self._packed: bytes = self._attribute(packed if packed else b''.join(_.pack() for _ in clusters))
        self._len: int = len(clusters) * 4

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ClusterList):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self.clusters == other.clusters

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def pack_attribute(self, negotiated: Negotiated = None) -> bytes:  # type: ignore[assignment]
        return self._packed

    def __len__(self) -> int:
        return self._len

    def __repr__(self) -> str:
        if self._len != 1:
            return '[ {} ]'.format(' '.join([str(_) for _ in self.clusters]))
        return '{}'.format(self.clusters[0])

    def json(self) -> str:
        return '[ {} ]'.format(', '.join(['"{}"'.format(str(_)) for _ in self.clusters]))

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> ClusterList:
        clusters: List[IPv4] = []
        while data:
            clusters.append(IPv4.unpack_ipv4(data[:4]))
            data = data[4:]
        return cls(clusters)
