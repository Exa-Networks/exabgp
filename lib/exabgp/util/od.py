# encoding: utf-8
"""
od.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.util import ord_

def od (value):
	def spaced (value):
		even = None
		for v in value:
			if even is False:
				yield ' '
			yield '%02X' % ord_(v)
			even = not even
	return ''.join(spaced(value))
