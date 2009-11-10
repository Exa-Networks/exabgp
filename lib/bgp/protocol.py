#!/usr/bin/env python
# encoding: utf-8
"""
protocol.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import math
import time
import socket
from struct import pack,unpack

from bgp.rib.table import Table
from bgp.rib.delta import Delta

from bgp.structure.message    import Message,Failure
from bgp.message.nop          import new_NOP
from bgp.message.open         import new_Open,Open,Parameter,Capabilities
from bgp.message.update       import new_Updates,Update
from bgp.message.keepalive    import new_KeepAlive,KeepAlive
from bgp.message.notification import Notification, Notify

from bgp.network import Network
from bgp.display import Display

class Protocol (Display):
	trace = False
	decode = True
	strict = False

	def __init__ (self,neighbor,network=None):
		Display.__init__(self,neighbor.peer_address,neighbor.peer_as)
		self.neighbor = neighbor
		self.network = network
		self._table = Table()
		self._table.update(self.neighbor.routes)
		self._delta = Delta(self._table)

	def connect (self):
		# allows to test the protocol code using modified StringIO with a extra 'pending' function
		if not self.network:
			peer = self.neighbor.peer_address
			local = self.neighbor.local_address
			asn = self.neighbor.peer_as
			self.network = Network(peer,local)

	def check_keepalive (self):
		left = int (self.network.last_read  + self.neighbor.hold_time - time.time())
		if left <= 0:
			raise Notify(4,0)
		return left

	def close (self):
		#self._delta.last = 0
		if self.network:
			self.network.close()
			self.network = None


	# Read from network .......................................................

	def read_message (self):
		if not self.network.pending():
			return new_NOP('')

		data = self.network.read(19)
		if data[:16] != Message.MARKER:
			# We are speaking BGP - send us a valid Marker
			raise Notify(1,1)

		raw_length = data[16:18]
		length = unpack('!H',raw_length)[0]
		msg = data[18]

		if ( length < 19 or length > 4096):
			# BAD Message Length
			raise Notify(1,2)

		if (
			(msg == Open.TYPE and length < 29) or
			(msg == Update.TYPE and length < 23) or
			(msg == Notification.TYPE and length < 21) or
			(msg == KeepAlive.TYPE and length != 19)
		):
			# MUST send the faulty length back
			raise Notify(1,2,raw_length)
			#(msg == RouteRefresh.TYPE and length != 23)

		length -= 19
		data = self.network.read(length)

		if len(data) != length:
			raise SendNotificaiton(ord(msg),0)

		self.logIf(self.trace and msg == Update.TYPE,"UPDATE RECV: %s " % [hex(ord(c)) for c in data])

		if msg == Notification.TYPE:
			raise Notification(ord(data[0]),ord(data[1]))

		if msg == KeepAlive.TYPE:
			return new_KeepAlive(data)

		if msg == Open.TYPE:
			return new_Open(data)

		if msg == Update.TYPE:
			return new_Updates(data)

		if self.strict:
			raise Notify(1,3,msg)

		return new_NOP(data)

	def read_open (self):
		message = self.read_message()
		if message.TYPE not in [Open.TYPE,]:
			raise Notify(1,1,msg)

		if message.asn != self.neighbor.peer_as:
			# ASN sent did not match ASN expected
			raise Notify(2,2,data[1:3])

		if message.hold_time == 0:
			# Hold Time of zero not accepted
			raise Notify(2,6,data[3:5])
		if message.hold_time >= 3:
			self.neighbor.hold_time = min(self.neighbor.hold_time,message.hold_time)

		return message

	def read_keepalive (self):
		message = self.read_message()
		if message.TYPE != KeepAlive.TYPE:
			raise Notify(5,0)
		return message

	# Sending message to peer .................................................

	def new_open (self):
		o = Open(4,self.neighbor.local_as,self.neighbor.router_id,Capabilities().default(),self.neighbor.hold_time)
		self.network.write(o.message())
		return o

	def new_announce (self):
		m = self._delta.announce(self.neighbor.local_as,self.neighbor.peer_as)
		updates = ''.join(m)
		self.logIf(self.trace,"UPDATE (update)   SENT: %s" % [hex(ord(c)) for c in updates][19:])
		if m: self.network.write(updates)
		return m if m else []

	def new_update (self):
		m = self._delta.update(self.neighbor.local_as,self.neighbor.peer_as)
		updates = ''.join(m)
		self.logIf(self.trace,"UPDATE (update)   SENT: %s" % [hex(ord(c)) for c in updates][19:])
		if m: self.network.write(updates)
		return m if m else []

	def new_keepalive (self,force=False):
		left = int(self.network.last_write + self.neighbor.hold_time.keepalive() - time.time())
		if force or left <= 0:
			k = KeepAlive()
			self.network.write(k.message())
			return left,k
		return left,None

	def new_notification (self,notification):
		return self.network.write(notification.message())


