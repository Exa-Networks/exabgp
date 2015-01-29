# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack

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
	# This is redefined by the Notify class, Exception is never used
	klass_notify = Exception
	klass_unknown = Exception

	class CODE (int):
		__slots__ = []

		NOP           = 0x00  # .   0 - internal
		OPEN          = 0x01  # .   1
		UPDATE        = 0x02  # .   2
		NOTIFICATION  = 0x03  # .   3
		KEEPALIVE     = 0x04  # .   4
		ROUTE_REFRESH = 0x05  # .   5
		OPERATIONAL   = 0x06  # .   6  # Not IANA assigned yet

		names = {
			NOP:            'NOP',
			OPEN:           'OPEN',
			UPDATE:         'UPDATE',
			NOTIFICATION:   'NOTIFICATION',
			KEEPALIVE:      'KEEPALIVE',
			ROUTE_REFRESH:  'ROUTE_REFRESH',
			OPERATIONAL:    'OPERATIONAL',
		}

		def __str__ (self):
			return self.names.get(self,'unknown message %s' % hex(self))

		def __repr__ (self):
			return str(self)

		@staticmethod
		def name (message_id):
			return Message.CODE.names.get(message_id,'unknown message %s' % hex(message_id))

	Length = {
		CODE.OPEN:           lambda _:  _ >= 29,  # noqa
		CODE.UPDATE:         lambda _:  _ >= 23,  # noqa
		CODE.NOTIFICATION:   lambda _:  _ >= 21,  # noqa
		CODE.KEEPALIVE:      lambda _:  _ == 19,  # noqa
		CODE.ROUTE_REFRESH:  lambda _:  _ == 23,  # noqa
	}

	def __init__ (self):
		self._name = None

	@staticmethod
	def string (code):
		if code is None:
			return 'invalid'
		if code == Message.CODE.OPEN:
			return 'open'
		if code == Message.CODE.UPDATE:
			return 'update'
		if code == Message.CODE.NOTIFICATION:
			return 'notification'
		if code == Message.CODE.KEEPALIVE:
			return 'keepalive'
		if code == Message.CODE.ROUTE_REFRESH:
			return 'route refresh'
		if code == Message.CODE.OPERATIONAL:
			return 'operational'
		return 'unknown'

	def _message (self, message):
		message_len = pack('!H',19+len(message))
		return "%s%s%s%s" % (self.MARKER,message_len,self.TYPE,message)

	def message (self):
		raise NotImplementedError('message not implemented in subclasses')

	@staticmethod
	def register_message (klass, message=None):
		what = klass.TYPE if message is None else message
		if what in Message.registered_message:
			raise RuntimeError('only one class can be registered per message')
		Message.registered_message[ord(what)] = klass

	@classmethod
	def klass (cls, what):
		if what in cls.registered_message:
			return cls.registered_message[what]
		raise cls.klass_notify(2,4,'can not handle message %s' % what)

	@classmethod
	def unpack (cls, message, data, negotiated):
		if message in cls.registered_message:
			return cls.klass(message).unpack_message(data,negotiated)
		return cls.klass_unknown(message,data,negotiated)
