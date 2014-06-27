# encoding: utf-8
"""
nlri.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip.address import Address

class NLRI (Address):

	def index (self):
		return '%s%s%s' % (self.afi,self.safi,self.pack())

	# remove this when code restructure is finished
	def pack (self):
		raise Exception('unimplemented')
