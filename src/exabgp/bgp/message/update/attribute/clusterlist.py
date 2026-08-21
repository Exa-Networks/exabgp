"""clusterlist.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.protocol.ip import IPv4

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.attribute import Attribute


# ===================================================================
#


class ClusterID(IPv4):
    def __init__(self, ip):
        IPv4.__init__(self, ip)


@Attribute.register()
class ClusterList(Attribute):
    ID = Attribute.CODE.CLUSTER_LIST
    FLAG = Attribute.Flag.OPTIONAL
    CACHING = True

    def __init__(self, clusters, packed=None):
        self.clusters = clusters
        self._packed = self._attribute(packed if packed else b''.join(_.pack() for _ in clusters))
        self._len = len(clusters) * 4

    def __eq__(self, other):
        return self.ID == other.ID and self.FLAG == other.FLAG and self.clusters == other.clusters

    def __ne__(self, other):
        return not self.__eq__(other)

    def pack(self, negotiated=None):
        return self._packed

    def __len__(self):
        return self._len

    def __repr__(self):
        if self._len != 1:
            return '[ {} ]'.format(' '.join([str(_) for _ in self.clusters]))
        return '{}'.format(self.clusters[0])

    def json(self):
        return '[ {} ]'.format(', '.join(['"{}"'.format(str(_)) for _ in self.clusters]))

    def as_dict(self):
        return [str(_) for _ in self.clusters]

    @classmethod
    def unpack(cls, data, direction, negotiated):
        # not `not data or ...`: an empty cluster list is zero clusters, which IS a
        # whole number of them, and 5.0.12 renders it. Refusing it drops a route on
        # upgrade. The same clause was wrong in BaseLS.check_multiple.
        if len(data) % 4:
            raise Notify(3, 5, 'invalid CLUSTER_LIST, %d bytes is not a whole number of clusters' % len(data))
        clusters = []
        while data:
            clusters.append(IPv4.unpack(data[:4]))
            data = data[4:]
        return cls(clusters)
