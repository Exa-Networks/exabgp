#!/usr/bin/env python
# encoding: utf-8
"""
aspath.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from struct import pack,unpack

from bgp.utils                import *
from bgp.message.update.attribute import AttributeID,Flag,Attribute

# =================================================================== ASPath (2)

# XXX: There can be more than once segment ...........
class ASPath (Attribute):
	AS_SET      = 0x01
	AS_SEQUENCE = 0x02

	ID = AttributeID.AS_PATH
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	def __init__ (self,asptype=0x02,aspsegment = None):
		self.asptype = asptype
		if aspsegment == None:
			self.aspsegment = []
		else:
			self.aspsegment = aspsegment

	def add (self,asn):
		self.aspsegment.append(asn)

	def pack (self):
		return self._attribute(self._segment(self.asptype,self.aspsegment))

	def __len__ (self):
		return 2 + (len(self.aspsegment)*2)

	def __str__ (self):
		if self.asptype == 0x01: t = 'AS_SET'
		if self.asptype == 0x02: t = 'AS_SEQUENCE'
		else: t = 'INVALID'

		if len(self) >  1: return '%s [ %s ]' % (t,' '.join([str(community) for community in self.aspsegment]))
		if len(self) == 1: return '%s %s' % (t,str(self.aspsegment[0]))
		return t
