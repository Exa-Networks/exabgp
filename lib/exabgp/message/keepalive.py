# encoding: utf-8
"""
keepalive.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

from exabgp.message import Message

# =================================================================== KeepAlive

class KeepAlive (Message):
	TYPE = chr(0x04)

	def message (self):
		return self._message()

	def __str__ (self):
		return "KEEPALIVE"

