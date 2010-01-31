#!/usr/bin/env python
# encoding: utf-8
"""
attributes.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from struct import pack,unpack

from bgp.utils import *
from bgp.message.update.attribute import AttributeID,Flag,Attribute

# =================================================================== MED (4)

class MED (Attribute):
	ID = AttributeID.MED  
	FLAG = Flag.OPTIONAL
	MULTIPLE = False

	def __init__ (self,med):
		self.med = med

	def pack (self):
		return self._attribute(pack('!L',self.med))

	def __len__ (self):
		return 4

	def __str__ (self):
		return str(self.med)

