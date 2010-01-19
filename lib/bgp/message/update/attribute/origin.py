#!/usr/bin/env python
# encoding: utf-8
"""
attributes.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.utils import *
from bgp.message.update.attribute import AttributeID,Flag,Attribute

# =================================================================== Origin (1)

def new_Origin (data):
	return Origin(ord(data[0]))

def to_Origin (data):
	data = data.lower()
	if data == 'igp':
		return Origin(0x00)
	if data == 'egp':
		return Origin(0x01)
	if data == 'incomplete':
		return Origin(0x02)
	raise ValueError('invalid origin')

class Origin (Attribute):
	ID = AttributeID.ORIGIN
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	IGP        = 0x00
	EGP        = 0x01
	INCOMPLETE = 0x02

	def pack (self):
		return self._attribute(chr(self.attribute))

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		if self.attribute == 0x00: return 'IGP'
		if self.attribute == 0x01: return 'EGP'
		if self.attribute == 0x02: return 'INCOMPLETE'
		return 'INVALID'
