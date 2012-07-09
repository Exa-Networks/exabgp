# encoding: utf-8
"""
clusterlist.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

from exabgp.structure.ip import IPv4
from exabgp.message.update.attribute import AttributeID,Flag,Attribute

# =================================================================== 

class ClusterID (IPv4):
	def __init__ (self,cluster_id):
		self.packed(cluster_id)

	def __repr__ (self):
		return str(self)


class ClusterList (Attribute):
	ID = AttributeID.CLUSTER_LIST
	FLAG = Flag.OPTIONAL
	MULTIPLE = False

	def __init__ (self,cluster_ids):
		self.clusters = []
		while cluster_ids:
			self.clusters.append(ClusterID(cluster_ids[:4]))
			cluster_ids = cluster_ids[4:]
		self._len = len(self.clusters)*4

	def pack (self):
		return ''.join([_.pack() for _ in self.clusters])

	def __len__ (self):
		return self._len

	def __str__ (self):
		if self._len != 1:
			return '[ %s ]' % ' '.join([str(_) for _ in self.clusters])
		return '%s' % self.clusters[0]

	def __repr__ (self):
		return str(self)

