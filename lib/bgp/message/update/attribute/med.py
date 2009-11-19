#!/usr/bin/env python
# encoding: utf-8
"""
attributes.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from struct import pack,unpack

from bgp.utils import *
from bgp.message.update.attribute.parent import Attribute,Flag

# =================================================================== MED (4)

def new_MED (data):
	return MED(unpack('!L',data[:4])[0])

class MED (Attribute):
	ID = Attribute.MULTI_EXIT_DISC  
	FLAG = Flag.OPTIONAL
	MULTIPLE = False

	def pack (self):
		return self._attribute(pack('!L',self.value))

	def __len__ (self):
		return 4

	def __str__ (self):
		return str(self.value)

