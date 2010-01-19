#!/usr/bin/env python
# encoding: utf-8
"""
attribute/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.utils import *
from bgp.message.update.attribute.flag import Flag
from bgp.message.update.attribute.id import AttributeID

# =================================================================== Attribute

class PathAttribute (object):
	ID   = 0x00
	FLAG = 0x00

	def __init__ (self,value=None):
		self.attribute = value

	def _attribute (self,value):
		flag = self.FLAG
		if flag & Flag.OPTIONAL and not value:
			return ''
		length = len(value)
		if length > 0xFF:
			flag &= Flag.EXTENDED_LENGTH
		if flag & Flag.EXTENDED_LENGTH:
			len_value = pack('!H',length)[0]
		else:
			len_value = chr(length)
		return "%s%s%s%s" % (chr(flag),chr(self.ID),len_value,value)

	def _segment (self,seg_type,values):
		if len(values)>255:
			return self._segment(values[:256]) + self._segment(values[256:])
		return "%s%s%s" % (chr(seg_type),chr(len(values)),''.join([v.pack() for v in values]))

	def __cmp__ (self,other):
		if type(self) == type(other):
			return cmp(self.ID,other.ID)
		return cmp(self.ID,other)

