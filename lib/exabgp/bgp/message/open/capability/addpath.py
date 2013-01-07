# encoding: utf-8
"""
addpath.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import pack

# =================================================================== AddPath

class AddPath (dict):
	string = {
		0 : 'disabled',
		1 : 'receive',
		2 : 'send',
		3 : 'send/receive',
	}

	def __init__ (self,families=[],send_receive=0):
		for afi,safi in families:
			self.add_path(afi,safi,send_receive)

	def add_path (self,afi,safi,send_receive):
		self[(afi,safi)] = send_receive

	def __str__ (self):
		return 'AddPath(' + ','.join(["%s %s %s" % (self.string[self[aafi]],xafi,xsafi) for (aafi,xafi,xsafi) in [((afi,safi),str(afi),str(safi)) for (afi,safi) in self]]) + ')'

	def extract (self):
		rs = []
		for v in self:
			if self[v]:
				rs.append(v[0].pack() +v[1].pack() + pack('!B',self[v]))
		return rs
