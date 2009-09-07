#!/usr/bin/env python
# encoding: utf-8
"""
message.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from data import *

# We do not implement the RFC State Machine so .. we do not care :D
class State (object):
	IDLE = 1
	CONNECT = 2
	ACTIVE = 3
	OPENSENT = 4
	OPENCONFIRM = 5
	ESTABLISHED = 6


class Message (object):
	TYPE = 0
	
	MARKER = chr(0xff)*16
	
	class Type:
		OPEN = 1,
		UPDATE = 2,
		NOTIFICATION = 4,
		KEEPALIVE = 8,
		ROUTE_REFRESH = 16,
		LIST = 32,
		HEADER = 64,
		GENERAL = 128,
		#LOCALRIB = 256,
	
	# XXX: the name is HORRIBLE, fix this !!
	def _prefix (self,data):
		return '%s%s' % (pack('!H',len(data)),data)
	
	def _message (self,message = ""):
		message_len = pack('!H',19+len(message))
		return "%s%s%s%s" % (self.MARKER,message_len,self.TYPE,message)


# This message is not part of the RFC but very practical to return that no data is waiting on the socket
class NOP (Message):
	TYPE = chr(0)

class Open (Message):
	TYPE = chr(1)

	def __init__ (self,asn,router_id,hold_time=HOLD_TIME,version=4):
		self.version = Version(version)
		self.asn = ASN(asn)
		self.hold_time = HoldTime(hold_time)
		self.router_id = RouterID(router_id)

	def message (self):
		return self._message("%s%s%s%s%s" % (self.version.pack(),self.asn.pack(),self.hold_time.pack(),self.router_id.pack(),chr(0)))

	def __str__ (self):
		return "OPEN version=%d asn=%d hold_time=%s router_id=%s" % (self.version, self.asn, self.hold_time, self.router_id)

class Update (Message):
	TYPE = chr(2)

	def __init__ (self,table):
		self.table = table
		self.last = 0

	def announce (self,local_asn,remote_asn):
		announce = []
		# table.changed always returns routes to remove before routes to add
		for action,route in self.table.changed(self.last):
			if action == '+':
				w = self._prefix(route.bgp())
				a = self._prefix(route.pack(local_asn,remote_asn))+route.bgp()
				announce.append(self._message(w + a))
			if action == '':
				self.last = route

		return ''.join(announce)

	def update (self,local_asn,remote_asn):
		announce = []
		withdraw = {}
		# table.changed always returns routes to remove before routes to add
		for action,route in self.table.changed(self.last):
			if action == '-':
				prefix = str(route)
				withdraw[prefix] = route.bgp()
			if action == '+':
				prefix = str(route)
				if withdraw.has_key(prefix):
					del withdraw[prefix]
				w = self._prefix(route.bgp())
				a = self._prefix(route.pack(local_asn,remote_asn))
				announce.append(self._message(w + a))
			if action == '':
				self.last = route
			
		if len(withdraw.keys()) == 0 and len(announce) == 0:
			return ''
		
		unfeasible = self._message(self._prefix(''.join([withdraw[prefix] for prefix in withdraw.keys()])) + self._prefix(''))
		return unfeasible + ''.join(announce)
	

class Failure (Exception):
	pass

# A Notification received from our peer.
# RFC 1771 Section 4.5 - but really I should refer to RFC 4271 Section 4.5 :)
class Notification (Message,Failure):
	TYPE = chr(3)
	
	_str_code = [
		"",
		"Message header error",
		"OPEN message error",
		"UPDATE message error", 
		"Hold timer expired",
		"State machine error",
		"Cease"
	]

	_str_subcode = {
		1 : {
			0 : "Unspecific.",
			1 : "Connection Not Synchronized.",
			2 : "Bad Message Length.",
			3 : "Bad Message Type.",
		},
		2 : {
			0 : "Unspecific.",
			1 : "Unsupported Version Number.",
			2 : "Bad Peer AS.",
			3 : "Bad BGP Identifier.",
			4 : "Unsupported Optional Parameter.",
			5 : "Authentication Notification (Deprecated).",
			6 : "Unacceptable Hold Time.",
		},
		3 : {
			0 : "Unspecific.",
			1 : "Malformed Attribute List.",
			2 : "Unrecognized Well-known Attribute.",
			3 : "Missing Well-known Attribute.",
			4 : "Attribute Flags Error.",
			5 : "Attribute Length Error.",
			6 : "Invalid ORIGIN Attribute.",
			7 : "AS Routing Loop.",
			8 : "Invalid NEXT_HOP Attribute.",
			9 : "Optional Attribute Error.",
			10 : "Invalid Network Field.",
			11 : "Malformed AS_PATH.",
		},
		4 : {
			0 : "Hold Timer Expired.",
		},
		5 : {
			0 : "Finite State Machine Error.",
		},
		6 : {
			0 : "Cease.",
			# RFC 4486
			1 : "Maximum Number of Prefixes Reached",
			2 : "Administrative Shutdown",
			3 : "Peer De-configured",
			4 : "Administrative Reset",
			5 : "Connection Rejected",
			6 : "Other Configuration Change",
			7 : "Connection Collision Resolution",
			8 : "Out of Resources",
		},
	}
	
	def __init__ (self,code,subcode,data=''):
		assert self._str_subcode.has_key(code)
		assert self._str_subcode[code].has_key(subcode)
		self.code = code
		self.subcode = subcode
		self.data = data
	
	def __str__ (self):
		return "%s: %s" % (self._str_code[self.code], self._str_subcode[self.code][self.subcode])

# A Notification we need to inform our peer of.
class SendNotification (Notification):
	def message (self):
		return self._message("%s%s%s" % (chr(self.code),chr(self.subcode),self.data))

class KeepAlive (Message):
	TYPE = chr(4)
	
	def message (self):
		return self._message()

