# encoding: utf-8
"""
label.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

from struct import pack

#from exabgp.message.update.attribute import AttributeID,Flag,Attribute

# =================================================================== Community

class Label (object):
	def __init__ (self,label):
		self.label = label

	def pack (self):
		return pack('!L',self.label)

	def __str__ (self):
		return "NOT DONE"

	def __len__ (self):
		return 4

	def __cmp__ (self,other):
		if not isinstance(other,self.__class__):
			return -1
		if self.label != other.label:
			return -1
		return 0
