# encoding: utf-8
"""
pmsi_tunnel.py

Created by Orange.
Copyright (c) 2014-2014, Orange. All rights reserved.
"""

import socket
from struct import pack

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag

from exabgp.bgp.message.update.nlri.mpls import LabelStackEntry, NO_LABEL


tunnel_types_to_class = dict()
def register (myclass):
	tunnel_types_to_class[myclass.subtype] = myclass


# http://tools.ietf.org/html/rfc6514#section-5
#
#  +---------------------------------+
#  |  Flags (1 octet)                |
#  +---------------------------------+
#  |  Tunnel Type (1 octets)         |
#  +---------------------------------+
#  |  MPLS Label (3 octets)          |
#  +---------------------------------+
#  |  Tunnel Identifier (variable)   |
#  +---------------------------------+

class PMSI (Attribute):
	ID = AttributeID.PMSI_TUNNEL
	FLAG = Flag.OPTIONAL
	MULTIPLE = False

	def __init__ (self,subtype,label=NO_LABEL,flags=0,packedTunnelId=None):
		if not isinstance(label,LabelStackEntry):
			raise Exception("label should be of LabelStackEntry type (is: %s)" % type(label))

		if label == None:
			label = NO_LABEL

		if label.bottomOfStack:
			raise Exception("label.bottomOfStack should not be set")

		self.subtype = subtype
		self.label = label
		self.pmsi_flags = flags
		self.packedTunnelId = packedTunnelId

	def pack(self):
		if self.packedTunnelId is None:
			self._computePackedTunnelId()
		return self._attribute(pack('!BB', self.pmsi_flags, self.subtype) + self.label.pack() + self.packedTunnelId)

	def __len__ (self):
		if self.packedTunnelId is None:
			self._computePackedTunnelId()
		return 4+len(self.packedTunnelId)

	def __str__ (self):
		if self.subtype in tunnel_types_to_class:
			type_string = tunnel_types_to_class[self.subtype].nickname
			return "pmsi:%s:%s:[%s]" % (type_string,str(self.pmsi_flags) or '',self.label or "-")
		else:
			type_string = "%d" % self.subtype
			return "pmsi:%s:%s:[%s]:%s" % (type_string,str(self.pmsi_flags) or '',self.label or "-","xxx")
			#TODO: add hex dump of packedValue

	def __repr__ (self):
		return str(self)

	def _computePackedTunnelId(self):
		raise Exception("Abstract class, cannot compute packedTunnelId")

	def __cmp__(self,o):
		if not isinstance(o,self.__class__):
			return -1
		if self.subtype != o.subtype:
			return -1
		if self.label != o.label:
			return -1
		if self.pmsi_flags != o.pmsi_flags:
			return -1
		if self.packedTunnelId != o.packedTunnelId:
			return -1
		return 0

	@staticmethod
	def unpack(data):
		#flags
		flags = ord(data[0])
		data=data[1:]

		#subtype
		subtype = ord(data[0])
		data=data[1:]

		#label
		label = LabelStackEntry.unpack(data[:3])
		data=data[3:]

		if subtype in tunnel_types_to_class:
			return tunnel_types_to_class[subtype].unpack(label,flags,data)
		else:
			return PMSI(subtype,label,flags,data)



class PMSIIngressReplication(PMSI):

	subtype = 6
	nickname = "IngressReplication"

	def __init__(self,ip,label=NO_LABEL,flags=0):
		self.ip = ip

		PMSI.__init__(self, self.subtype, label, flags)

	def __str__ (self):
		desc = "[%s]" % self.ip
		return PMSI.__str__(self) + ":" + desc

	def _computePackedTunnelId(self):
		self.packedTunnelId = socket.inet_pton(socket.AF_INET,self.ip)

	@staticmethod
	def unpack(label,flags,data):
		ip = socket.inet_ntop(socket.AF_INET,data[:4])
		return PMSIIngressReplication(ip,label,flags)

register(PMSIIngressReplication)
