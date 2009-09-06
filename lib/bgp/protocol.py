#!/usr/bin/env python
# encoding: utf-8
"""
protocol.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import time
from struct import pack,unpack
from bgp.table import Table
from bgp.message import Message, Open, Update, Failure,Notification, SendNotification, KeepAlive
from bgp.network import Network
from bgp.display import Display



class Protocol (Display):
	follow = True
	
	def __init__ (self,neighbor,network=None):
		Display.__init__(self,neighbor.peer_address,neighbor.peer_as)
		self.neighbor = neighbor
		self.network = network
		self._table = Table()
		self._update = Update(self._table)
		self._table.update(self.neighbor.routes)

	def connect (self):
		# allows to test the protocol code using modified StringIO with a extra 'pending' function
		if not self.network:
			peer = self.neighbor.peer_address
			local = self.neighbor.local_address
			asn = self.neighbor.peer_as
			self.network = Network(peer,local,asn)
	
	def _read_header (self):
		# Read it as a block as it is better for the timer code
		data = self.network.read(19)
		
		marker = data[:16]
		if marker != Message.MARKER:
			# We are speaking BGP - send us a valid Marker
			raise SendNotification(1,1)
		
		raw_length = data[16:18]
		length = unpack('!H',raw_length)[0]
		if ( length < 19 or length > 4096):
			# BAD Message Length
			raise SendNotification(1,2)
		
		msg = data[18]
		if (
			(msg == Open.TYPE and length < 29) or
			(msg == Update.TYPE and length < 23) or
			(msg == Notification.TYPE and length < 21) or
			(msg == KeepAlive.TYPE and length != 19)
		):
			# MUST send the faulty length back
			raise SendNotification(1,2,raw_length)
			#(msg == RouteRefresh.TYPE and length != 23)
		
		return msg,length-19
	
	def read_open (self):
		msg,l = self._read_header()
		data = self.network.read(l)
		
		if msg == Notification.TYPE:
			# You did not like our open .. grrr who has an ASN mismatch (most likely) :p ..
			raise Notification(ord(data[0]),ord(data[1]))
		
		if msg != Open.TYPE:
			# We are speaking BGP - send us an OPEN ..
			raise SendNotification(1,1,chr(msg))
		
		version = ord(data[0])
		if version != 4:
			# Only version 4 is supported nowdays..
			raise SendNotification(2,1,data[0])
		
		asn = unpack('!H',data[1:3])[0]
		if asn != self.neighbor.peer_as:
			# ASN sent did not match ASN expected
			raise SendNotification(2,2,data[1:3])
		
		hold_time = unpack('!H',data[3:5])[0]
		if hold_time == 0:
			# Hold Time of zero not accepted
			raise SendNotification(2,6,data[3:5])
		self.neighbor.hold_time.update(hold_time)
		
		router_id = unpack('!L',data[5:9])[0]

# XXX: Refuse connections with unknown options - not recommended. :) 
#		option_len = ord(data[9])
#		if option_len:
#			# We do not support any Optional Parameter
#			raise SendNotification(2,4)
		
		o = Open(asn,router_id,hold_time,version)
		
		return o

	def read_message (self):
		if not self.network.pending():
			return chr(0),''
		
		msg,l = self._read_header()
		data = self.network.read(l)
		
		if msg == Notification.TYPE:
			# The other side wants to close
			raise Notification(ord(data[0]),ord(data[1]))
		
		if msg not in [KeepAlive.TYPE,Update.TYPE,Notification.TYPE]:
			# We are speaking BGP - greet us with OPEN when we meet only
			# We do not speak any extension like Route Refresh, so do not use it
			raise SendNotification(1,3,chr(msg))
		self.logIf(msg == Update.TYPE,"UPDATE RECV: %s " % [hex(ord(c)) for c in data])
		return msg, data
	
	def read_keepalive (self):
		msg,data = self.read_message()
		if msg != KeepAlive.TYPE:
			raise SendNotification(5,0)
		return msg,data
	
	def new_open (self):
		o = Open(self.neighbor.local_as,self.neighbor.router_id,self.neighbor.hold_time)
		self.network.write(o.message())
		return o
	
	def new_announce (self):
		m = self._update.announce(self.neighbor.local_as,self.neighbor.peer_as)
		self.log("UPDATE (announce) SENT: %s" % [hex(ord(c)) for c in m][19:])
		self.network.write(m)
		return self._update if m else None
	
	def new_update (self):
		m = self._update.update(self.neighbor.local_as,self.neighbor.peer_as)
		self.log("UPDATE (update)   SENT: %s" % [hex(ord(c)) for c in m][19:])
		if m: self.network.write(m)
		return self._update if m else None
	
	def new_keepalive (self,force=False):
		left = int(self.network.last_write + self.neighbor.hold_time.keepalive() - time.time())
		if force or left <= 0:
			k = KeepAlive()
			self.network.write(k.message())
			return left,k
		return left,None
	
	def new_notification (self,notification):
		return self.network.write(notification.message())
	
	def check_keepalive (self):
		left = int (self.network.last_read  + self.neighbor.hold_time - time.time())
		if left <= 0:
			raise SendNotification(4,0)
		return left
	
	def close (self):
		self._update.last = 0
		if self.network:
			self.network.close()
			self.network = None
