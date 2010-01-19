#!/usr/bin/env python
# encoding: utf-8
"""
attributes.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.utils import *
from bgp.message.update.attribute import AttributeID,Flag,PathAttribute

# =================================================================== Local Preference (5)

def new_LocalPreference (data):
	return LocalPreference(unpack('!L',data[:4])[0])

class LocalPreference (PathAttribute):
	ID = AttributeID.LOCAL_PREF 
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	def pack (self):
		return self._attribute(pack('!L',self.attribute))

	def __len__ (self):
		return 4
	
	def __str__ (self):
		return str(self.attribute)

