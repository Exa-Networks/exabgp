# encoding: utf-8
"""
clusterlist.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.util import concat_bytes_i

from exabgp.protocol.ip import IPv4

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

    __slots__ = ['clusters', 'packed', '_len']

    def __init__(self, clusters, packed=None):
        self.clusters = clusters
        self._packed = self._attribute(packed if packed else concat_bytes_i(_.pack() for _ in clusters))
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
            return '[ %s ]' % ' '.join([str(_) for _ in self.clusters])
        return '%s' % self.clusters[0]

    def json(self):
        return '[ %s ]' % ', '.join(['"%s"' % str(_) for _ in self.clusters])

    @classmethod
    def unpack(cls, data, negotiated):
        clusters = []
        while data:
            clusters.append(IPv4.unpack(data[:4]))
            data = data[4:]
        return cls(clusters)
