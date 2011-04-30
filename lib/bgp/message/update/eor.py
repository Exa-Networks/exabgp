#!/usr/bin/env python
# encoding: utf-8
"""
eor.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010-2011 Exa Networks. All rights reserved.
"""

from bgp.structure.address import Address,AFI,SAFI
from bgp.message.update import Update
from bgp.message.update.attributes import Attributes

# =================================================================== End-Of-Record

class Empty (object):
	def pack (self):
		return ''
	def __len__ (self):
		return 0

class EmptyRoute (Address,Attributes):
	autocomplete = False

	def __init__ (self,afi,safi):
		Address.__init__(self,afi,safi)
		Attributes.__init__(self)
		self.nlri = Empty()

class EOR (object):
	def __init__ (self):
		self._announced = []

	def eors (self,families):
		self._announced = []
		r = ''
		for afi,safi in families:
			if afi == AFI.ipv4 and safi in [SAFI.unicast, SAFI.multicast]:
				r += self.ipv4()
			else:
				r += self.mp(afi,safi)
			self._announced.append((afi,safi))
		return r

	def ipv4 (self):
		return Update([EmptyRoute(AFI.ipv4,SAFI.unicast),]).withdraw()

	def mp (self,afi,safi):
		return Update([EmptyRoute(afi,safi),]).withdraw()

	def announced (self):
		return self._announced
