# encoding: utf-8
"""
path.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.qualifier import PathInfo
from exabgp.bgp.message.update.nlri.qualifier import Labels

# ====================================================== MPLS
# RFC 3107

@NLRI.register(AFI.ipv4,SAFI.nlri_mpls)
@NLRI.register(AFI.ipv6,SAFI.nlri_mpls)
class Labelled (INET):
	__slots__ = ['labels']

	def __init__ (self, afi, safi, action):
		INET.__init__(self, afi, safi, action)
		self.labels = Labels.NOLABEL

	def __len__ (self):
		return INET.__len__(self) + len(self.labels)

	def __eq__ (self, other):
		return \
			INET.__eq__(self, other) and \
			self.labels == other.labels

	@classmethod
	def has_label (cls):
		return True

	def prefix (self):
		return "%s%s" % (INET.prefix(self),str(self.labels))

	def pack (self, negotiated=None):
		addpath = self.path_info.pack() if negotiated and negotiated.addpath.send(self.afi,self.safi) else ''
		mask = chr(len(self.labels)*8 + self.cidr.mask)
		return addpath + mask + self.labels.pack() + self.cidr.pack_ip()

	def index (self, negotiated=None):
		addpath = 'no-pi' if self.path_info is PathInfo.NOPATH else self.path_info.pack()
		mask = chr(self.cidr.mask)
		return addpath + mask + self.cidr.pack_ip()

	def _internal (self, announced=True):
		r = INET._internal(self,announced)
		if announced and self.labels:
			r.append(self.labels.json())
		return r

	# @classmethod
	# def _labels (cls, data, action):
	# 	mask = ord(data[0])
	# 	data = data[1:]
	# 	labels = []
	# 	while data and mask >= 8:
	# 		label = int(unpack('!L',chr(0) + data[:3])[0])
	# 		data = data[3:]
	# 		mask -= 24  	# 3 bytes
	# 		# The last 4 bits are the bottom of Stack
	# 		# The last bit is set for the last label
	# 		labels.append(label >> 4)
	# 		# This is a route withdrawal
	# 		if label == 0x800000 and action == IN.WITHDRAWN:
	# 			break
	# 		# This is a next-hop
	# 		if label == 0x000000:
	# 			break
	# 		if label & 1:
	# 			break
	# 	return mask, Labels(labels), data
	#
	# @classmethod
	# def unpack_label (cls, afi, safi, data, action, addpath):
	# 	pathinfo, data = cls._pathinfo(data,addpath)
	# 	mask, labels, data = cls._labels(data,action)
	# 	nlri, data = cls.unpack_cidr(afi,safi,mask,data,action)
	# 	nlri.path_info = pathinfo
	# 	nlri.labels = labels
	# 	return nlri,data
	#
	# @classmethod
	# def unpack_nlri (cls, afi, safi, data, addpath):
	# 	return cls.unpack_label(afi,safi,data,addpath)
