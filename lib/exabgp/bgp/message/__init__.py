# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack

# =================================================================== BGP States
#

class State (object):
	IDLE        = 0x01
	CONNECT     = 0x02
	ACTIVE      = 0x03
	OPENSENT    = 0x04
	OPENCONFIRM = 0x05
	ESTABLISHED = 0x06


# ==================================================================== Direction
#

from exabgp.util.enumeration import Enumeration

OUT = Enumeration ('announce','withdraw')
IN  = Enumeration ('announced','withdrawn')


# ================================================================== BGP Message
#

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

	class ID (int):
		__slots__ = []

		NOP           = 0x00  # .   0 - internal
		OPEN          = 0x01  # .   1
		UPDATE        = 0x02  # .   2
		NOTIFICATION  = 0x03  # .   3
		KEEPALIVE     = 0x04  # .   4
		ROUTE_REFRESH = 0x05  # .   5
		OPERATIONAL   = 0x06  # .   6  # Not IANA assigned yet
		#LIST          = 0x20  # .  32
		#HEADER        = 0x40  # .  64
		#GENERAL       = 0x80  # . 128
		#LOCALRIB      = 0x100  # . 256

		names = {
			NOP           : 'NOP',
			OPEN          : 'OPEN',
			UPDATE        : 'UPDATE',
			NOTIFICATION  : 'NOTIFICATION',
			KEEPALIVE     : 'KEEPALIVE',
			ROUTE_REFRESH : 'ROUTE_REFRESH',
			OPERATIONAL   : 'OPERATIONAL',
		}

		def __str__ (self):
			return self.names.get(self,'UNKNOWN MESSAGE %s' % hex(self))

		def __repr__ (self):
			return str(self)

		@classmethod
		def name (cls,message_id):
			return cls.names.get(message_id,'UNKNOWN MESSAGE %s' % hex(message_id))

	class Name:
		NOP           = 'NOP'
		OPEN          = 'OPEN'
		UPDATE        = 'UPDATE'
		NOTIFICATION  = 'NOTIFICATION'
		KEEPALIVE     = 'KEEPALIVE'
		ROUTE_REFRESH = 'ROUTE_REFRESH'
		OPERATIONAL   = 'OPERATIONAL'


	Length = {
		ID.OPEN          : lambda _ : _ >= 29,
		ID.UPDATE        : lambda _ : _ >= 23,
		ID.NOTIFICATION  : lambda _ : _ >= 21,
		ID.KEEPALIVE     : lambda _ : _ == 19,
		ID.ROUTE_REFRESH : lambda _ : _ == 23,
	}

	def __init__ (self):
		self._name = None

	@staticmethod
	def string (code):
		if code is None:
			return 'invalid'
		if code == Message.ID.OPEN:
			return 'open'
		if code == Message.ID.UPDATE:
			return 'update'
		if code == Message.ID.NOTIFICATION:
			return 'notification'
		if code == Message.ID.KEEPALIVE:
			return 'keepalive'
		if code == Message.ID.ROUTE_REFRESH:
			return 'route refresh'
		if code == Message.ID.OPERATIONAL:
			return 'operational'
		return 'unknown'

	def _message (self,message):
		message_len = pack('!H',19+len(message))
		return "%s%s%s%s" % (self.MARKER,message_len,self.TYPE,message)

	def message (self):
		raise RuntimeError('message not implemented in subclasses')

	@classmethod
	def register_message (cls,message=None):
		what = cls.TYPE if message is None else message
		if what in cls.registered_message:
			raise RuntimeError('only one class can be registered per message')
		cls.registered_message[ord(what)] = cls

	@classmethod
	def klass (cls,what):
		if what in cls.registered_message:
			return cls.registered_message[what]
		raise cls.klass_notify(2,4,'can not handle message %s' % what)

	@classmethod
	def unpack_message (cls,message,data,negotiated):
		if message in cls.registered_message:
			return cls.klass(message).unpack_message(data,negotiated)
		return cls.klass(message).unpack_message(data,negotiated)
