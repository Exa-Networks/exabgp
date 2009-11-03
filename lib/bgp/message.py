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
	IDLE        = 0x01
	CONNECT     = 0x02
	ACTIVE      = 0x03
	OPENSENT    = 0x04
	OPENCONFIRM = 0x05
	ESTABLISHED = 0x06


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
	
	# XXX: the name is HORRIBLE, fix this !!
	def _prefix (self,data):
		return '%s%s' % (pack('!H',len(data)),data)
	
	def _message (self,message = ""):
		message_len = pack('!H',19+len(message))
		return "%s%s%s%s" % (self.MARKER,message_len,self.TYPE,message)


# This message is not part of the RFC but very practical to return that no data is waiting on the socket
class NOP (Message):
	TYPE = chr(0x00)

class Open (Message):
	TYPE = chr(0x01)

	def __init__ (self,version,asn,router_id,capabilities,hold_time=HOLD_TIME):
		self.version = Version(version)
		self.asn = ASN(asn)
		self.hold_time = HoldTime(hold_time)
		self.router_id = RouterID(router_id)
		self.capabilities = capabilities

	def message (self):
		return self._message("%s%s%s%s%s" % (self.version.pack(),self.asn.pack(),self.hold_time.pack(),self.router_id.pack(),chr(0)))

	def __str__ (self):
		return "OPEN version=%d asn=%d hold_time=%s router_id=%s capabilities=[%s]" % (self.version, self.asn, self.hold_time, self.router_id,self.capabilities)

class Update (Message):
	TYPE = chr(0x02)

	def __init__ (self,table):
		self.table = table
		self.last = 0

	def announce (self,local_asn,remote_asn):
		return self.update(local_asn,remote_asn,False)

	def update (self,local_asn,remote_asn,remove=True):
		message = ''
		withdraw4 = {}
		announce4 = []
		mp_route6 = []
		# table.changed always returns routes to remove before routes to add
		for action,route in self.table.changed(self.last):
			if action == '':
				self.last = route
				continue
			if route.ip.version == 6:
				# XXX: We should keep track of what we have already sent to only remove routes if we have sent them
				if remove:
					mp_route6.append(self._message(self._prefix('') + self._prefix(route.pack(local_asn,remote_asn,'-'))))
				if action == '+':
					mp_route6.append(self._message(self._prefix('') + self._prefix(route.pack(local_asn,remote_asn,'+'))))
				continue
			if route.ip.version == 4:
				if action == '-' and remove:
					prefix = str(route)
					withdraw4[prefix] = route.bgp()
					continue
				if action == '+':
					prefix = str(route)
					if withdraw4.has_key(prefix):
						del withdraw4[prefix]
					announce4.append(self._message(self._prefix(route.bgp()) + self._prefix(route.pack(local_asn,remote_asn)) + route.bgp()))
					continue
			
		if len(withdraw4.keys()) or len(announce4):
			# XXX: We should keep track of what we have already sent to only remove routes if we have sent them
			remove4 = self._message(self._prefix(''.join([withdraw4[prefix] for prefix in withdraw4.keys()])) + self._prefix(''))
			adding4 = ''.join(announce4)
			message += remove4 + adding4
		
		if len(mp_route6):
			message += ''.join(mp_route6)
		
		return message
	
	def __str__ (self):
		return "UPDATE"

class Failure (Exception):
	pass

# A Notification received from our peer.
# RFC 1771 Section 4.5 - but really I should refer to RFC 4271 Section 4.5 :)
class Notification (Message,Failure):
	TYPE = chr(0x03)
	
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
			# RFC 5492
			7 : "Unsupported Capability",
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
	TYPE = chr(0x04)
	
	def message (self):
		return self._message()

