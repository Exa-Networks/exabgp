# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

from struct import pack


# =================================================================== BGP States

class State (object):
	IDLE        = 0x01
	CONNECT     = 0x02
	ACTIVE      = 0x03
	OPENSENT    = 0x04
	OPENCONFIRM = 0x05
	ESTABLISHED = 0x06


# ==================================================================== Direction

from exabgp.util.enumeration import Enumeration

OUT = Enumeration ('announce','withdraw')
IN  = Enumeration ('announced','withdrawn')


# ================================================================== BGP Message


# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                                                               |
# +                                                               +
# |                                                               |
# +                                                               +
# |                           Marker                              |
# +                                                               +
# |                                                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |          Length               |      Type     |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

class Message (Exception):
	# we need to define TYPE inside __init__ of the subclasses
	# otherwise we can not dynamically create different UnknownMessage
	# TYPE = None

	MARKER = chr(0xff)*16
	HEADER_LEN = 19
	MAX_LEN = 4096

	registered_message = {}
	klass_notify = None

	class Type:
		NOP           = 0x00  # .   0 - internal
		OPEN          = 0x01  # .   1
		UPDATE        = 0x02  # .   2
		NOTIFICATION  = 0x03  # .   3
		KEEPALIVE     = 0x04  # .   4
		ROUTE_REFRESH = 0x05  # .   5
		OPERATIONAL   = 0x06  # .   6
		#LIST          = 0x20  # .  32
		#HEADER        = 0x40  # .  64
		#GENERAL       = 0x80  # . 128
		#LOCALRIB      = 0x100  # . 256

	Length = {
		Type.OPEN          : lambda _ : _ >= 29,
		Type.UPDATE        : lambda _ : _ >= 23,
		Type.NOTIFICATION  : lambda _ : _ >= 21,
		Type.KEEPALIVE     : lambda _ : _ == 19,
		Type.ROUTE_REFRESH : lambda _ : _ == 23,
	}

	def __init__ (self):
		self._name = None

	@staticmethod
	def string (code):
		if code is None:
			return 'invalid'
		if code == Message.Type.OPEN:
			return 'open'
		if code == Message.Type.UPDATE:
			return 'update'
		if code == Message.Type.NOTIFICATION:
			return 'notification'
		if code == Message.Type.KEEPALIVE:
			return 'keepalive'
		if code == Message.Type.ROUTE_REFRESH:
			return 'route refresh'
		if code == Message.Type.OPERATIONAL:
			return 'operational'
		return 'unknown'

	def name (self,code):
		if not self._name:
			if code is None:
				self._name = 'UNKNOWN (invalid code)'
			elif code == self.Type.OPEN:
				self._name = 'OPEN'
			elif code == self.Type.UPDATE:
				self._name = 'UPDATE'
			elif code == self.Type.NOTIFICATION:
				self._name = 'NOTIFICATION'
			elif code == self.Type.KEEPALIVE:
				self._name = 'KEEPALIVE'
			elif code == self.Type.ROUTE_REFRESH:
				self._name = 'ROUTE_REFRESH'
			elif code == self.Type.OPERATIONAL:
				self._name = 'OPERATIONAL'
			# if code & self.Type.LIST:
			# 	self._str = 'LIST'
			# if code & self.Type.HEADER:
			# 	self._str = 'HEADER'
			# if code & self.Type.GENERAL:
			# 	self._str = 'GENERAL'
			else:
				self._name = 'UNKNOWN (%d)' % code

		return self._name

	def _message (self,message):
		message_len = pack('!H',19+len(message))
		return "%s%s%s%s" % (self.MARKER,message_len,self.TYPE,message)

	def message (self):
		raise RuntimeError('message not implemented in subclasses')

	@classmethod
	def register_message (cls,message=None):
		what = cls.TYPE if message is None else message
		if what in cls.registered_message:
			raise RuntimeError('only one class can be registered per capability')
		cls.registered_message[what] = cls

	@classmethod
	def klass (cls,what):
		if what in cls.registered_capability:
			return cls.registered_message[what]
		raise cls.klass_notify(2,4,'can not handle capability %s' % what)

	@classmethod
	def unpack_message (cls,message,data,negotiated):
		if message in cls.register_message:
			return cls.klass(message).unpack_message(data,negotiated)
		return cls.klass(message).unpack_message(data,negotiated)
