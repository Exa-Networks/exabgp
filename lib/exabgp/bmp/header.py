# encoding: utf-8
"""
message.py

Created by Thomas Mangin on 2013-02-26.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import unpack
from exabgp.bmp.peer import Peer
from exabgp.bmp.message import Message


class Header (object):
	def __init__ (self, data):
		self.version = ord(data[0])
		self.message = Message(ord(data[1]))
		self.peer = Peer(data)

		self.time_sec = unpack('!L',data[36:40])[0]
		self.time_micro_sec = unpack('!L',data[40:44])[0]

	def validate (self):
		if self.version != 1:
			return False
		if not self.message.validate():
			return False
		if not self.peer.validate():
			return False
		return True

	def json (self):
		return "{}"
