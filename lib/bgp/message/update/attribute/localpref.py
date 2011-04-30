#!/usr/bin/env python
# encoding: utf-8
"""
attributes.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2011 Exa Networks. All rights reserved.
"""

from struct import pack

from bgp.message.update.attribute import AttributeID,Flag,Attribute

# =================================================================== Local Preference (5)

class LocalPreference (Attribute):
	ID = AttributeID.LOCAL_PREF 
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	def __init__ (self,localpref):
		self.localpref = localpref

	def pack (self):
		return self._attribute(pack('!L',self.localpref))

	def __len__ (self):
		return 4
	
	def __str__ (self):
		return str(self.localpref)

	def __repr__ (self):
		return str(self)
