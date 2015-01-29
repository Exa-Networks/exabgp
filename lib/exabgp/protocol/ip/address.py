# encoding: utf-8
"""
address.py

Created by Thomas Mangin on 2012-07-16.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI


# ====================================================================== Address
#

class Address (object):
	__slots__ = ['afi','safi']

	def __init__ (self, afi, safi):
		self.afi = AFI(afi)
		self.safi = SAFI(safi)

	def family (self):
		return (self.afi,self.safi)

	def address (self):
		return "%s %s" % (str(self.afi),str(self.safi))

	def __str__ (self):
		return self.address()
