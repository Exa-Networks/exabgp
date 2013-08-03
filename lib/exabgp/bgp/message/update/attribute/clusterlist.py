# encoding: utf-8
"""
clusterlist.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI,SAFI
from exabgp.protocol.ip.inet import Inet
from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag,Attribute

# ===================================================================

class ClusterID (Inet):
	def __init__ (self,cluster_id):
		Inet.__init__(self,AFI.ipv4,SAFI.unicast_multicast,cluster_id)


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
		# XXX: are we doing the work for nothing ?
		self.packed = self._attribute(''.join([_.pack() for _ in self.clusters]))

	def pack (self,asn4=None):
		return self.packed

	def __len__ (self):
		return self._len

	def __str__ (self):
		if self._len != 1:
			return '[ %s ]' % ' '.join([str(_) for _ in self.clusters])
		return '%s' % self.clusters[0]

	def json (self):
		return '[ %s ]' % ', '.join(['"%s"' % str(_) for _ in self.clusters])
