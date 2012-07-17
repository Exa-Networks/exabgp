# encoding: utf-8
"""
eor.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010-2012 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip.address import Address,AFI,SAFI
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.attribute.attributes import Attributes

# =================================================================== End-Of-Record

class Empty (Address):
	def __init__ (self,afi,safi):
		Address.__init__(self,AFI(afi),SAFI(safi))

	def pack (self,ignore_path_info_encoding=True):
		return ''
	def __len__ (self):
		return 0

class EmptyRoute (object):
	autocomplete = False

	def __init__ (self,afi,safi):
		self.attributes = Attributes()
		self.nlri = Empty(afi,safi)

class EOR (object):
	def __init__ (self):
		self._announced = []

	def eors (self,families):
		self._announced = []
		r = []
		for afi,safi in families:
			r.append(self.mp(afi,safi))
			self._announced.append((afi,safi))
		return r

	def mp (self,afi,safi):
		return Update().new([EmptyRoute(afi,safi),]).withdraw()

	def announced (self):
		return self._announced
