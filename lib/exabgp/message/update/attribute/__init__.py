# encoding: utf-8
"""
attribute/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

from struct import pack

from exabgp.message.update.attribute.flag import Flag
from exabgp.message.update.attribute.id import AttributeID

# =================================================================== Attribute

class Attribute (object):
	ID   = 0x00
	FLAG = 0x00

	def _attribute (self,value):
		flag = self.FLAG
		if flag & Flag.OPTIONAL and not value:
			return ''
		length = len(value)
		if length > 0xFF:
			flag |= Flag.EXTENDED_LENGTH
		if flag & Flag.EXTENDED_LENGTH:
			len_value = pack('!H',length)
		else:
			len_value = chr(length)
		return "%s%s%s%s" % (chr(flag),chr(self.ID),len_value,value)

	def __eq__ (self,other):
		return self.ID == other.ID

