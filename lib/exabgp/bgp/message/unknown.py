# encoding: utf-8
"""
unknown.py

Created by Thomas Mangin on 2013-07-20.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.message import Message

# ================================================================= UnknownMessage
#


class UnknownMessage (Message):
	# Make sure we have a value, which is not defined in any RFC !

	def __init__ (self, code, data=b''):
		self.ID = code
		self.TYPE = chr(code)
		self.data = data

	def message (self,negotiated=None):
		return self._message(self.data)

	def __str__ (self):
		return "UNKNOWN"

	@classmethod
	def unpack_message (cls, data):  # pylint: disable=W0613
		raise RuntimeError('should not have been used')

UnknownMessage.klass_unknown = UnknownMessage
