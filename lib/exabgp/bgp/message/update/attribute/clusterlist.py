# encoding: utf-8
"""
clusterlist.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip import IPv4

from exabgp.bgp.message.update.attribute.attribute import Attribute


# ===================================================================
#

class ClusterID (IPv4):
	def __init__ (self, ip):
		IPv4.__init__(self,ip)


class ClusterList (Attribute):
	ID = Attribute.CODE.CLUSTER_LIST
	FLAG = Attribute.Flag.OPTIONAL
	CACHING = True

	__slots__ = ['clusters','packed','_len']

	def __init__ (self, clusters, packed=None):
		self.clusters = clusters
		self.packed = self._attribute(packed if packed else ''.join([_.pack() for _ in clusters]))
		self._len = len(clusters)*4

	def pack (self, negotiated=None):
		return self.packed

	def __len__ (self):
		return self._len

	def __str__ (self):
		if self._len != 1:
			return '[ %s ]' % ' '.join([str(_) for _ in self.clusters])
		return '%s' % self.clusters[0]

	def json (self):
		return '[ %s ]' % ', '.join(['"%s"' % str(_) for _ in self.clusters])

	@classmethod
	def unpack (cls, data, negotiated):
		clusters = []
		while data:
			clusters.append(IPv4.unpack(data[:4]))
			data = data[4:]
		return cls(clusters)
