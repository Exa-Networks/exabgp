#!/usr/bin/env python
# encoding: utf-8
"""
eor.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from bgp.structure.address import AFI,SAFI
from bgp.message.update import Update
from bgp.message.update.attribute.mpurnlri import MPURNLRI
from bgp.message.update.attributes import Attributes

# =================================================================== End-Of-Record

class Empty (object):
	def pack (self):
		return ''
	def __len__ (self):
		return 0

class EmptyRoute (Empty):
	nlri = Empty()

class EOR (object):
	def __init__ (self):
		self._announced = []

	def eors (self,families):
		self._announced = []
		r = ''
		for afi,safi in families:
			if safi != SAFI.unicast:
				continue
			if afi == AFI.ipv4:
				r += self.ipv4()
			else:
				r += self.mp(afi,safi)
			self._announced.append((afi,safi))
		return r

	def ipv4 (self):
		#attributes = EORAttributes()
		attributes = Attributes()
		attributes.autocomplete = False
		return Update([],[],attributes).announce(0,0)

	def mp (self,afi,safi):
		attributes = Attributes()
		attributes.autocomplete = False
		attributes.add(MPURNLRI(afi,safi,EmptyRoute()))
		return Update([],[],attributes).announce(0,0)

	def announced (self):
		return self._announced
