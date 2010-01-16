#!/usr/bin/env python
# encoding: utf-8
"""
attribute/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.utils import *
from bgp.message.update.attribute.flag import Flag

# =================================================================== Attribute

class Attribute (object):
	ID   = 0x00
	FLAG = 0x00

	# This should move within the classes and not be here
	# RFC 4271
	ORIGIN             = 0x01
	AS_PATH            = 0x02
	NEXT_HOP           = 0x03
	MULTI_EXIT_DISC    = 0x04
	LOCAL_PREFERENCE   = 0x05
	ATOMIC_AGGREGATE   = 0x06
	AGGREGATOR         = 0x07
	# RFC 1997
	COMMUNITY          = 0x08
	# RFC 4360
	EXTENDED_COMMUNITY = 0x10
	# RFC 4760
	MP_REACH_NLRI      = 0x0e # 14
	MP_UNREACH_NLRI    = 0x0f # 15

	def __init__ (self,value):
		self.value = value

	def __str__ (self):
		# This should move within the classes and not be here
		if self.value == 0x01: return "ORIGIN"
		if self.value == 0x02: return "AS_PATH"
		if self.value == 0x03: return "NEXT_HOP"
		if self.value == 0x04: return "MULTI_EXIT_DISC"
		if self.value == 0x05: return "LOCAL_PREFERENCE"
		if self.value == 0x06: return "ATOMIC_AGGREGATE"
		if self.value == 0x07: return "AGGREGATOR"
		if self.value == 0x08: return "COMMUNITY"
		if self.value == 0x0e: return "MP_REACH_NLRI"
		if self.value == 0x0f: return "MP_UNREACH_NLRI"
		return 'UNKNOWN ATTRIBUTE (%s)' % hex(self.value)

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
			return cmp(self.value,other.value)
		return cmp(self.value,other)

