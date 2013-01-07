# encoding: utf-8
"""
graceful.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import pack

# =================================================================== Graceful (Restart)
# RFC 4727

class Graceful (dict):
	TIME_MASK     = 0x0FFF
	FLAG_MASK     = 0xF000

	# 0x8 is binary 1000
	RESTART_STATE = 0x08
	FORWARDING_STATE = 0x80

	def __init__ (self,restart_flag,restart_time,protos):
		dict.__init__(self)
		self.restart_flag = restart_flag
		self.restart_time = restart_time & Graceful.TIME_MASK
		for afi,safi,family_flag in protos:
			self[(afi,safi)] = family_flag & Graceful.FORWARDING_STATE

	def extract (self):
		restart  = pack('!H',((self.restart_flag << 12) | (self.restart_time & Graceful.TIME_MASK)))
		families = [(afi.pack(),safi.pack(),chr(self[(afi,safi)])) for (afi,safi) in self.keys()]
		sfamilies = ''.join(["%s%s%s" % (pafi,psafi,family) for (pafi,psafi,family) in families])
		return ["%s%s" % (restart,sfamilies)]

	def __str__ (self):
		families = [(str(afi),str(safi),hex(self[(afi,safi)])) for (afi,safi) in self.keys()]
		sfamilies = ' '.join(["%s/%s=%s" % (afi,safi,family) for (afi,safi,family) in families])
		return "Graceful Restart Flags %s Time %d %s" % (hex(self.restart_flag),self.restart_time,sfamilies)

	def families (self):
		return self.keys()
