# encoding: utf-8
"""
originatorid.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

from exabgp.message.update.attribute import AttributeID,Flag,Attribute

# =================================================================== NextHop (3)

class OriginatorID (Attribute):
	ID = AttributeID.ORIGINATOR_ID
	FLAG = Flag.OPTIONAL
	MULTIPLE = False

	# Take an IP as value
	def __init__ (self,originator_id):
		# Must be an Inet
		self.originator_id = originator_id

	def pack (self):
		return self._attribute(self.originator_id.pack())

	def __len__ (self):
		return len(self.originator_id.pack())

	def __str__ (self):
		return str(self.originator_id)

	def __repr__ (self):
		return str(self)
