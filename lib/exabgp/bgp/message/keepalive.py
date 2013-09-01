# encoding: utf-8
"""
keepalive.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message import Message

# =================================================================== KeepAlive

class KeepAlive (Message):
	TYPE = chr(Message.Type.KEEPALIVE)

	def __str__ (self):
		return "KEEPALIVE"
