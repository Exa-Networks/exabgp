#!/usr/bin/env python
# encoding: utf-8
"""
labels.py

based on communities.py Created by Thomas Mangin on 2009-11-05.
Modified by Diego Garcia del Rio on 2010-01-05
Copyright (c) 2009-2011 Exa Networks. All rights reserved.
"""

from struct import pack

from bgp.message.update.attribute import AttributeID,Flag,Attribute

# =================================================================== Community

class Label (object):
	def __init__ (self,label):
		self.label = label
	
	def pack (self):
		return pack('!L',self.label)

	def __str__ (self):
		return "NO DONE"

	def __len__ (self):
		return 4

	def __eq__ (self,other):
		return self.label == other.label

