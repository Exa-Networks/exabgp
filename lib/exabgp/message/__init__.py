# encoding: utf-8
"""
__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2010-2012 Exa Networks. All rights reserved.
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


# README: the name is HORRIBLE, fix this !!
def defix (data):
	l = unpack('!H',data[0:2])[0]
	return l,data[2:l+2],data[l+2:]

# README: the name is HORRIBLE, fix this !!
def prefix (data):
	return '%s%s' % (pack('!H',len(data)),data)

class Message (Exception):
	TYPE = None

	MARKER = chr(0xff)*16

	class Type:
		OPEN          = 0x01  #   1
		UPDATE        = 0x02  #   2
		NOTIFICATION  = 0x04  #   4
		KEEPALIVE     = 0x08  #   8
		ROUTE_REFRESH = 0x10  #  16
		LIST          = 0x20  #  32
		HEADER        = 0x40  #  64
		GENERAL       = 0x80  # 128
		#LOCALRIB    = 0x100  # 256

	def __init__ (self):
		if self.TYPE is None:
			self._str = 'UNKNOWN (invalid code)'
			return

		code = ord(self.TYPE)
		result = []

		if code & self.Type.OPEN:
			result.append('OPEN')
		if code & self.Type.UPDATE:
			result.append('UPDATE')
		if code & self.Type.NOTIFICATION:
			result.append('NOTIFICATION')
		if code & self.Type.KEEPALIVE:
			result.append('KEEPALIVE')
		if code & self.Type.ROUTE_REFRESH:
			result.append('ROUTE_REFRESH')
		if code & self.Type.LIST:
			result.append('LIST')
		if code & self.Type.HEADER:
			result.append('HEADER')
		if code & self.Type.GENERAL:
			result.append('GENERAL')

		if result:
			self._str = ' '.join(result)
		else:
			self._str = 'UNKNOWN (%d)' % code

	def _message (self,message = ""):
		message_len = pack('!H',19+len(message))
		return "%s%s%s%s" % (self.MARKER,message_len,self.TYPE,message)

	def __str__ (self):
		return self._str

class Failure (Exception):
	pass
