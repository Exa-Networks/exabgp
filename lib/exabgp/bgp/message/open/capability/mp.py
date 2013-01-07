# encoding: utf-8
"""
mp.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import pack

# =================================================================== MultiProtocol

class MultiProtocol (list):
	def __str__ (self):
		return 'Multiprotocol(' + ','.join(["%s %s" % (str(afi),str(safi)) for (afi,safi) in self]) + ')'

	def extract (self):
		rs = []
		for v in self:
			rs.append(pack('!H',v[0]) + pack('!H',v[1]))
		return rs
