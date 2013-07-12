# encoding: utf-8
"""
__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

from struct import pack,unpack

# We do not implement the RFC State Machine so .. we do not care :D
class State (object):
	IDLE        = 0x01
	CONNECT     = 0x02
	ACTIVE      = 0x03
	OPENSENT    = 0x04
	OPENCONFIRM = 0x05
	ESTABLISHED = 0x06


# XXX: the name is HORRIBLE, fix this !!
def defix (data):
	l = unpack('!H',data[0:2])[0]
	return l,data[2:l+2],data[l+2:]

# XXX: the name is HORRIBLE, fix this !!
def prefix (data):
	return '%s%s' % (pack('!H',len(data)),data)

class Message (Exception):
	TYPE = None
	HEADER_LEN = 19
	MARKER = chr(0xff)*16

	class Type:
		OPEN          = 0x01  # .   1
		UPDATE        = 0x02  # .   2
		NOTIFICATION  = 0x03  # .   3
		KEEPALIVE     = 0x04  # .   4
		ROUTE_REFRESH = 0x05  # .   5
		#LIST          = 0x20  # .  32
		#HEADER        = 0x40  # .  64
		#GENERAL       = 0x80  # . 128
		#LOCALRIB      = 0x100  # . 256

	Length = {
		Type.OPEN          : (int.__gt__,29),
		Type.UPDATE        : (int.__gt__,23),
		Type.NOTIFICATION  : (int.__gt__,21),
		Type.KEEPALIVE     : (int.__eq__,19),
		Type.ROUTE_REFRESH : (int.__eq__,23),
	}

	def __init__ (self):
		self._str = None

	def name (self,code):
		if code is None:
			return 'UNKNOWN (invalid code)'

		if code == self.Type.OPEN:
			return 'OPEN'
		elif code == self.Type.UPDATE:
			return 'UPDATE'
		elif code == self.Type.NOTIFICATION:
			return 'NOTIFICATION'
		elif code == self.Type.KEEPALIVE:
			return 'KEEPALIVE'
		elif code == self.Type.ROUTE_REFRESH:
			return 'ROUTE_REFRESH'
		# if code & self.Type.LIST:
		# 	self._str = 'LIST'
		# if code & self.Type.HEADER:
		# 	self._str = 'HEADER'
		# if code & self.Type.GENERAL:
		# 	self._str = 'GENERAL'
		return 'UNKNOWN (%d)' % code

	def _message (self,message=""):
		message_len = pack('!H',19+len(message))
		return "%s%s%s%s" % (self.MARKER,message_len,self.TYPE,message)

	def __str__ (self):
		if not self._str:
			self._str = self.name(ord(self.TYPE))
		return self._str

class Failure (Exception):
	pass
