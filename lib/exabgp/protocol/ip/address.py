# encoding: utf-8
"""
address.py

Created by Thomas Mangin on 2012-07-16.
Copyright (c) 2012 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI,SAFI

## =================================================================== Address

class Address (object):
	def __init__ (self,afi,safi):
		self.afi = AFI(afi)
		self.safi = SAFI(safi)

	def __str__ (self):
		return "%s %s" % (str(self.afi),str(self.safi))
