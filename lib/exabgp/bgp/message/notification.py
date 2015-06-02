# encoding: utf-8
"""
notification.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import string

from exabgp.bgp.message.message import Message


def hexstring (value):
	def spaced (value):
		for v in value:
			yield '%02X' % ord(v)
	return '0x' + ''.join(spaced(value))


# ================================================================== Notification
# A Notification received from our peer.
# RFC 4271 Section 4.5

# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | Error code    | Error subcode |   Data (variable)             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

@Message.register
class Notification (Message):
	ID = Message.CODE.NOTIFICATION
	TYPE = chr(Message.CODE.NOTIFICATION)

	_str_code = {
		1: "Message header error",
		2: "OPEN message error",
		3: "UPDATE message error",
		4: "Hold timer expired",
		5: "State machine error",
		6: "Cease"
	}

	_str_subcode = {
		(1,0): "Unspecific",
		(1,1): "Connection Not Synchronized",
		(1,2): "Bad Message Length",
		(1,3): "Bad Message Type",

		(2,0): "Unspecific",
		(2,1): "Unsupported Version Number",
		(2,2): "Bad Peer AS",
		(2,3): "Bad BGP Identifier",
		(2,4): "Unsupported Optional Parameter",
		(2,5): "Authentication Notification (Deprecated)",
		(2,6): "Unacceptable Hold Time",
		# RFC 5492
		(2,7): "Unsupported Capability",

		# draft-ietf-idr-bgp-multisession-06
		(2,8):  "Grouping Conflict",
		(2,9):  "Grouping Required",
		(2,10): "Capability Value Mismatch",

		(3,0): "Unspecific",
		(3,1): "Malformed Attribute List",
		(3,2): "Unrecognized Well-known Attribute",
		(3,3): "Missing Well-known Attribute",
		(3,4): "Attribute Flags Error",
		(3,5): "Attribute Length Error",
		(3,6): "Invalid ORIGIN Attribute",
		(3,7): "AS Routing Loop",
		(3,8): "Invalid NEXT_HOP Attribute",
		(3,9): "Optional Attribute Error",
		(3,10): "Invalid Network Field",
		(3,11): "Malformed AS_PATH",

		(4,0): "Unspecific",

		(5,0): "Unspecific",
		# RFC 6608
		(5,1): "Receive Unexpected Message in OpenSent State",
		(5,2): "Receive Unexpected Message in OpenConfirm State",
		(5,3): "Receive Unexpected Message in Established State",

		(6,0): "Unspecific",
		# RFC 4486
		(6,1): "Maximum Number of Prefixes Reached",
		(6,2): "Administrative Shutdown",
		(6,3): "Peer De-configured",
		(6,4): "Administrative Reset",
		(6,5): "Connection Rejected",
		(6,6): "Other Configuration Change",
		(6,7): "Connection Collision Resolution",
		(6,8): "Out of Resources",
		# draft-keyur-bgp-enhanced-route-refresh-00
		(7,1): "Invalid Message Length",
		(7,2): "Malformed Message Subtype",
	}

	def __init__ (self, code, subcode, data=''):
		self.code = code
		self.subcode = subcode
		self.data = data if not len([_ for _ in data if _ not in string.printable]) else hexstring(data)

	def __str__ (self):
		return "%s / %s%s" % (
			self._str_code.get(self.code,'unknown error'),
			self._str_subcode.get((self.code,self.subcode),'unknow reason'),
			'%s' % (' / %s' % self.data if self.data else '')
		)

	@classmethod
	def unpack_message (cls, data, negotiated=None):
		return cls(ord(data[0]),ord(data[1]),data[2:])


# =================================================================== Notify
# A Notification we need to inform our peer of.

@Message.notify
class Notify (Notification):
	def __init__ (self, code, subcode, data=None):
		if data is None:
			data = self._str_subcode.get((code,subcode),'unknown notification type')
		Notification.__init__(self,code,subcode,data)

	def message (self,negotiated=None):
		return self._message("%s%s%s" % (
			chr(self.code),
			chr(self.subcode),
			self.data
		))
