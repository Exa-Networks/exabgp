#!/usr/bin/env python
# encoding: utf-8
"""
protocol.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import time
import socket
from struct import pack,unpack

from bgp.rib.table import Table
from bgp.rib.delta import Delta

from bgp.utils                import *
from bgp.message.parent       import Message,Failure
from bgp.message.nop          import new_NOP
from bgp.message.open         import new_Open,Open,Parameter,Capabilities,RouterID
from bgp.message.update       import new_Update,Update,EOR
from bgp.message.keepalive    import new_KeepAlive,KeepAlive
from bgp.message.notification import Notification, Notify, NotConnected
from bgp.network.connection   import Connection

class Protocol (object):
	trace = False
	decode = True
	strict = False

	def __init__ (self,neighbor,connection=None):
		self.log = Log(neighbor.peer_address,neighbor.peer_as)
		self.neighbor = neighbor
		self.connection = connection
		self._table = Table()
		self._table.update(self.neighbor.routes)
		self._delta = Delta(self._table)

	def connect (self):
		# allows to test the protocol code using modified StringIO with a extra 'pending' function
		if not self.connection:
			peer = self.neighbor.peer_address
			local = self.neighbor.local_address
			asn = self.neighbor.peer_as
			self.connection = Connection(peer,local)

	def check_keepalive (self):
		left = int (self.connection.last_read  + self.neighbor.hold_time - time.time())
		if left <= 0:
			raise Notify(4,0)
		return left

	def close (self):
		#self._delta.last = 0
		if self.connection:
			self.connection.close()
			self.connection = None


	# Read from network .......................................................

	def read_message (self):
		if not self.connection.pending():
			return new_NOP('')

		data = self.connection.read(19)

		# It seems that select tells us there is data even when there isn't
		if not data:
			raise NotConnected(self.neighbor.peer_address)

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
		data = self.connection.read(length)

		if len(data) != length:
			raise SendNotificaiton(ord(msg),0)

		self.log.outIf(self.trace and msg == Update.TYPE,"UPDATE RECV: %s " % hexa(data))

		if msg == Notification.TYPE:
			raise Notification(ord(data[0]),ord(data[1]))

		if msg == KeepAlive.TYPE:
			return new_KeepAlive(data)

		if msg == Open.TYPE:
			return new_Open(data)

		if msg == Update.TYPE:
			return new_Update(data)

		if self.strict:
			raise Notify(1,3,msg)

		return new_NOP(data)

	def read_open (self,ip):
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

		if message.router_id == '0.0.0.0':
			message.router_id = RouterID(ip)

		return message

	def read_keepalive (self):
		message = self.read_message()
		if message.TYPE != KeepAlive.TYPE:
			raise Notify(5,0)
		return message

	# Sending message to peer .................................................

	def new_open (self,graceful,restarted):
		o = Open(4,self.neighbor.local_as,self.neighbor.router_id.ip(),Capabilities().default(graceful,restarted),self.neighbor.hold_time)
		self.connection.write(o.message())
		return o

	def new_announce (self):
		m = self._delta.announce(self.neighbor.local_as,self.neighbor.peer_as)
		updates = ''.join(m)
		self.log.outIf(self.trace,"UPDATE (update)   SENT: %s" % hexa(updates[19:]))
		if m:
			self.connection.write(updates)
			return m
		return []

	def new_eors (self,families):
		eor = EOR()
		eors = eor.eors(families)
		self.log.outIf(self.trace,"UPDATE (eors) SENT: %s" % hexa(eors[19:]))
		self.connection.write(eors)
		return eor.announced()

	def new_update (self):
		m = self._delta.update(self.neighbor.local_as,self.neighbor.peer_as)
		updates = ''.join(m)
		self.log.outIf(self.trace,"UPDATE (update)   SENT: %s" % hexa(updates[19:]))
		if m:
			self.connection.write(updates)
			return m
		return []

	def new_keepalive (self,force=False):
		left = int(self.connection.last_write + self.neighbor.hold_time.keepalive() - time.time())
		if force or left <= 0:
			k = KeepAlive()
			self.connection.write(k.message())
			return left,k
		return left,None

	def new_notification (self,notification):
		return self.connection.write(notification.message())


