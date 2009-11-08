#!/usr/bin/env python
# encoding: utf-8
"""
message.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
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

class Message (object):
	TYPE = 0 # Should be None ?

	MARKER = chr(0xff)*16

	class Type:
		OPEN          = 0x01, #   1
		UPDATE        = 0x02, #   2
		NOTIFICATION  = 0x04, #   4
		KEEPALIVE     = 0x08, #   8
		ROUTE_REFRESH = 0x10, #  16
		LIST          = 0x20, #  32
		HEADER        = 0x40, #  64
		GENERAL       = 0x80, # 128
		#LOCALRIB    = 0x100  # 256

	def _message (self,message = ""):
		message_len = pack('!H',19+len(message))
		return "%s%s%s%s" % (self.MARKER,message_len,self.TYPE,message)

class Failure (Exception):
	pass
