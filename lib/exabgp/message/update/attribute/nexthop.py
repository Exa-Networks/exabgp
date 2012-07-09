# encoding: utf-8
"""
nexthop.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

from exabgp.structure.ip import Inet,packed_afi
from exabgp.message.update.attribute import AttributeID,Flag,Attribute

# =================================================================== NextHop (3)

class NextHop (Attribute,Inet):
	ID = AttributeID.NEXT_HOP
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	# Take an IP as value
	def __init__ (self,packed,afi):
		Inet.__init__(self,packed,afi)

	def pack (self):
		return self._attribute(Inet.pack(self))

	def __str__ (self):
		return Inet.__str__(self)

	def __repr__ (self):
		return str(self)

def NextHopIP (ip):
	return NextHop(*packed_afi(ip))
