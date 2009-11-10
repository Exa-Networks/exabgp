#!/usr/bin/env python
# encoding: utf-8
"""
notification.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.message.parent import *

# =================================================================== Notification
# A Notification received from our peer.
# RFC 4271 Section 4.5

class Notification (Message,Failure):
	TYPE = chr(0x03)

	_str_code = {
		1 : "Message header error",
		2 : "OPEN message error",
		3 : "UPDATE message error", 
		4 : "Hold timer expired",
		5 : "State machine error",
		6 : "Cease"
	}

	_str_subcode = {
		(1,0) : "Unspecific.",
		(1,1) : "Connection Not Synchronized.",
		(1,2) : "Bad Message Length.",
		(1,3) : "Bad Message Type.",

		(2,0) : "Unspecific.",
		(2,1) : "Unsupported Version Number.",
		(2,2) : "Bad Peer AS.",
		(2,3) : "Bad BGP Identifier.",
		(2,4) : "Unsupported Optional Parameter.",
		(2,5) : "Authentication Notification (Deprecated).",
		(2,6) : "Unacceptable Hold Time.",
		# RFC 5492
		(2,7) : "Unsupported Capability",

		(3,0) : "Unspecific.",
		(3,1) : "Malformed Attribute List.",
		(3,2) : "Unrecognized Well-known Attribute.",
		(3,3) : "Missing Well-known Attribute.",
		(3,4) : "Attribute Flags Error.",
		(3,5) : "Attribute Length Error.",
		(3,6) : "Invalid ORIGIN Attribute.",
		(3,7) : "AS Routing Loop.",
		(3,8) : "Invalid NEXT_HOP Attribute.",
		(3,9) : "Optional Attribute Error.",
		(3,10) : "Invalid Network Field.",
		(3,11) : "Malformed AS_PATH.",

		(4,0) : "Unspecific.",

		(5,0) : "Unspecific.",

		(6,0) : "Unspecific.",
		# RFC 4486
		(6,1) : "Maximum Number of Prefixes Reached",
		(6,2) : "Administrative Shutdown",
		(6,3) : "Peer De-configured",
		(6,4) : "Administrative Reset",
		(6,5) : "Connection Rejected",
		(6,6) : "Other Configuration Change",
		(6,7) : "Connection Collision Resolution",
		(6,8) : "Out of Resources",
	}

	def __init__ (self,code,subcode,data=''):
		self.code = code
		self.subcode = subcode
		self.data = data

	def __str__ (self):
		return "%s: %s" % (self._str_code.get(self.code,'unknown error'), self._str_subcode.get((self.code,self.subcode),'unknow reason'))

# =================================================================== Notify
# A Notification we need to inform our peer of.

class Notify (Notification):
	def message (self):
		return self._message("%s%s%s" % (chr(self.code),chr(self.subcode),self.data))
