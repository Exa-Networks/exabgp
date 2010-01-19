#!/usr/bin/env python
# encoding: utf-8
"""
aspath.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from struct import pack,unpack

from bgp.utils                import *
from bgp.message.update.attribute import Attribute,Flag

# =================================================================== ASPath (2)

def new_ASPath (data):
	stype = ord(data[0])
	slen = ord(data[1])
	sdata = data[2:2+(slen*2)]

	ASPS = ASPath(stype)
	for c in unpack('!'+('H'*slen),sdata):
		ASPS.add(c)
	return ASPS

# XXX: There can be more than once segment ...........
class ASPath (Attribute):
	AS_SET      = 0x01
	AS_SEQUENCE = 0x02

	ID = Attribute.AS_PATH
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	def __init__ (self,asptype=0x02,aspsegment = None):
		if aspsegment == None:
			asps = []
		else:
			asps = aspsegment
		Attribute.__init__(self,(asptype,asps))

	def add (self,asn):
		self.attribute[1].append(asn)

	def pack (self):
		return self._attribute(self._segment(self.attribute[0],self.attribute[1]))

	def __len__ (self):
		return 2 + (len(self.attribute[1])*2)

	def __str__ (self):
		if self.attribute[0] == 0x01: t = 'AS_SET'
		if self.attribute[0] == 0x02: t = 'AS_SEQUENCE'
		else: t = 'INVALID'

		if len(self) >  1: return '%s [ %s ]' % (t,' '.join([str(community) for community in self.attribute[1]]))
		if len(self) == 1: return '%s %s' % (t,str(self.attribute[1][0]))
		return t
