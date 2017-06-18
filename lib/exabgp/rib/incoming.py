# encoding: utf-8
"""
store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.rib.cache import Cache


class IncomingRIB (Cache):
	def __init__ (self, families):
		Cache.__init__(self,families)

	# back to square one, all the routes are removed
	def clear (self):
		self.clear_cache()

	def reset (self):
		pass
