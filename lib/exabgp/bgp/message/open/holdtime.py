# encoding: utf-8
"""
holdtime.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack

# =================================================================== HoldTime


class HoldTime (int):
	MAX = 0xFFFF

	def pack (self):
		return pack('!H',self)

	def keepalive (self):
		return int(self/3)

	def __len__ (self):
		return 2
