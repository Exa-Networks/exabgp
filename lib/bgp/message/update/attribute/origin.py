#!/usr/bin/env python
# encoding: utf-8
"""
attributes.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.utils import *
from bgp.message.update.attribute.parent import Attribute,Flag

# =================================================================== Origin (1)

def new_Origin (data):
	return Origin(ord(data[0]))

class Origin (Attribute):
	ID = Attribute.ORIGIN
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	IGP        = 0x00
	EGP        = 0x01
	INCOMPLETE = 0x02

	def pack (self):
		return self._attribute(chr(self.value))

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		if self.value == 0x00: return 'IGP'
		if self.value == 0x01: return 'EGP'
		if self.value == 0x02: return 'INCOMPLETE'
		return 'INVALID'
