# encoding: utf-8
"""
originatorid.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

from exabgp.structure.ip import Inet,afi_packed
from exabgp.message.update.attribute import AttributeID,Flag,Attribute

# =================================================================== OriginatorID (3)

class OriginatorID (Attribute,Inet):
	ID = AttributeID.ORIGINATOR_ID
	FLAG = Flag.OPTIONAL
	MULTIPLE = False

	# Take an IP as value
	def __init__ (self,afi,raw):
		Inet.__init__(self,afi,raw)

	def pack (self):
		return self._attribute(Inet.pack(self))

	def __str__ (self):
		return Inet.__str__(self)

	def __repr__ (self):
		return str(self)

def OriginatorIDIP (ip):
	return OriginatorID(*afi_packed(ip))
