# encoding: utf-8
"""
protocol.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import time
from struct import unpack

from exabgp.rib.table import Table
from exabgp.rib.delta import Delta

from exabgp.bgp.connection import Connection
from exabgp.bgp.message import Message,Failure
from exabgp.bgp.message.nop import NOP
from exabgp.bgp.message.open import Open
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.eor import EOR
from exabgp.bgp.message.keepalive import KeepAlive
from exabgp.bgp.message.notification import Notification, Notify
from exabgp.bgp.message.refresh import RouteRefresh

from exabgp.structure.processes import ProcessError

from exabgp.structure.log import Logger,LazyFormat

# This is the number of chuncked message we are willing to buffer, not the number of routes
MAX_BACKLOG = 15000

# README: Move all the old packet decoding in another file to clean up the includes here, as it is not used anyway

class Protocol (object):
	decode = True

	def __init__ (self,peer,connection=None):
		self.logger = Logger()
		self.peer = peer
		self.neighbor = peer.neighbor
		self.connection = connection
		self.negotiated = Negotiated()

		self.delta = Delta(Table(peer))
		self._messages = []
		self._frozen = 0
		# The message size is the whole BGP message _without_ headers
		self.message_size = 4096-19

	# XXX: we use self.peer.neighbor.peer_address when we could use self.neighbor.peer_address

	def me (self,message):
		return "Peer %15s ASN %-7s %s" % (self.peer.neighbor.peer_address,self.peer.neighbor.peer_as,message)

	def connect (self):
		# allows to test the protocol code using modified StringIO with a extra 'pending' function
		if not self.connection:
			peer = self.neighbor.peer_address
			local = self.neighbor.local_address
			md5 = self.neighbor.md5
			ttl = self.neighbor.ttl
			self.connection = Connection(peer,local,md5,ttl)

			if self.peer.neighbor.api.neighbor_changes:
				try:
					self.peer.supervisor.processes.connected(self.peer.neighbor.peer_address)
				except ProcessError:
					raise Failure('Could not send connected message(s) to helper program(s)')

	def close (self,reason='unspecified'):
		if self.connection:
			# must be first otherwise we could have a loop caused by the raise in the below
			self.connection.close()
			self.connection = None

			if self.peer.neighbor.api.neighbor_changes:
				try:
					self.peer.supervisor.processes.down(self.peer.neighbor.peer_address,reason)
				except ProcessError:
					raise Failure('Could not send down message(s) to helper program(s)')

	def write (self,message):
		if self.neighbor.api.send_packets:
			try:
				self.peer.supervisor.processes.send(self.peer.neighbor.peer_address,message[18],message[:19],message[19:])
			except ProcessError:
				raise Failure('Could not send update message(s) to helper program(s)')
		return self.connection.write(message)

	# Read from network .......................................................

	def read_message (self,keepalive_comment=''):
		# This call reset the time for the timeout in
		if not self.connection.pending(True):
			return NOP()

		length = 19
		header = ''
		while length:
			if self.connection.pending():
				delta = self.connection.read(length)
				header += delta
				length -= len(delta)

		if header[:16] != Message.MARKER:
			# We are speaking BGP - send us a valid Marker
			raise Notify(1,1,'The packet received does not contain a BGP marker')

		raw_length = header[16:18]
		msg_length = unpack('!H',raw_length)[0]
		msg = header[18]

		if (msg_length < 19 or msg_length > 4096):
			# BAD Message Length
			raise Notify(1,2)

		if (
			(msg == Open.TYPE and msg_length < 29) or
			(msg == Update.TYPE and msg_length < 23) or
			(msg == Notification.TYPE and msg_length < 21) or
			(msg == KeepAlive.TYPE and msg_length != 19) or
			(msg == RouteRefresh.TYPE and msg_length != 23)
		):
			# MUST send the faulty msg_length back
			raise Notify(1,2,'%d has an invalid message length of %d' %(str(msg),msg_length))

		length = msg_length - 19
		body = ''
		while length:
			if self.connection.pending():
				delta = self.connection.read(length)
				body += delta
				length -= len(delta)

		if self.neighbor.api.receive_packets:
			try:
				self.peer.supervisor.processes.receive(self.peer.neighbor.peer_address,msg,header,body)
			except ProcessError:
				raise Failure('Could not send update message(s) to helper program(s)')

		if msg == KeepAlive.TYPE:
			self.logger.message(self.me('<< KEEPALIVE%s' % keepalive_comment))
			return KeepAlive()

		elif msg == Update.TYPE:
			self.logger.message(self.me('<< UPDATE'))

			if msg_length == 30 and body.startswith(EOR.PREFIX):
				return EOR().factory(body)

			if self.neighbor.api.receive_routes:
				update = Update().factory(self.negotiated,body)

				for route in update.routes:
					self.logger.routes(LazyFormat(self.me(''),str,route))

				try:
					self.peer.supervisor.processes.routes(self.neighbor.peer_address,update.routes)
				except ProcessError:
					raise Failure('Could not send routes message(s) to helper program(s)')
				return update
			else:
				return NOP()

		elif msg == Notification.TYPE:
			self.logger.message(self.me('<< NOTIFICATION'))
			raise Notification().factory(body)

		elif msg == Open.TYPE:
			return Open().factory(body)


		if msg == RouteRefresh.TYPE:
			self.logger.message(self.me('<< ROUTE-REFRESH'))
			return RouteRefresh().factory(body)

		else:
			self.logger.message(self.me('<< NOP'))

		return NOP().factory(msg)


	def read_open (self,_open,ip):
		message = self.read_message()

		if message.TYPE == NOP.TYPE:
			return message

		if message.TYPE != Open.TYPE:
			raise Notify(5,1,'The first packet recevied is not an open message (%s)' % message)

		self.negotiated.received(message)

		if not self.negotiated.asn4:
			if self.neighbor.local_as.asn4():
				raise Notify(2,0,'peer does not speak ASN4, we are stuck')
			else:
				# we will use RFC 4893 to convey new ASN to the peer
				self.negotiated.asn4

		if self.negotiated.peer_as != self.neighbor.peer_as:
			raise Notify(2,2,'ASN in OPEN (%d) did not match ASN expected (%d)' % (message.asn,self.neighbor.peer_as))

		# RFC 6286 : http://tools.ietf.org/html/rfc6286
		#if message.router_id == RouterID('0.0.0.0'):
		#	message.router_id = RouterID(ip)
		if message.router_id == RouterID('0.0.0.0'):
			raise Notify(2,3,'0.0.0.0 is an invalid router_id according to RFC6286')

		if message.router_id == self.neighbor.router_id and message.asn == self.neighbor.local_as:
			raise Notify(2,3,'BGP Indendifier collision (%s) on IBGP according to RFC 6286' % message.router_id)

		if message.hold_time and message.hold_time < 3:
			raise Notify(2,6,'Hold Time is invalid (%d)' % message.hold_time)

		if self.negotiated.multisession not in (True,False):
			raise Notify(*self.negotiated.multisession)

		self.logger.message(self.me('<< %s' % message))
		return message

	def read_keepalive (self,comment=''):
		message = self.read_message(comment)
		if message.TYPE == NOP.TYPE:
			return message
		if message.TYPE != KeepAlive.TYPE:
			raise Notify(5,2)
		return message

	#
	# Sending message to peer
	#

	def new_open (self,restarted):
		sent_open = Open().new(
			4,
			self.neighbor.local_as,
			self.neighbor.router_id.ip,
			Capabilities().new(self.neighbor,restarted),
			self.neighbor.hold_time
		)

		self.negotiated.sent(sent_open)

		# we do not buffer open message in purpose
		if not self.write(sent_open.message()):
			raise Failure('Could not send open')
		self.logger.message(self.me('>> %s' % sent_open))
		return sent_open

	def new_keepalive (self,comment=''):
		k = KeepAlive()
		m = k.message()
		written = self.write(m)
		if not written:
			self.logger.message(self.me('|| buffer not yet empty, adding KEEPALIVE to it'))
			self._messages.append((1,'KEEPALIVE%s' % comment,m))
		else:
			self.logger.message(self.me('>> KEEPALIVE%s' % comment))
		return k

	def new_update (self):
		# XXX: This should really be calculated once only
		for number in self._announce('UPDATE',self.peer.bgp.delta.updates(self.negotiated,self.neighbor.group_updates)):
			yield number

	def new_eors (self):
		eor = EOR().new(self.negotiated.families)
		for answer in self._announce(str(eor),eor.updates(self.negotiated)):
				pass

	def new_notification (self,notification):
		return self.write(notification.message())

	#
	# Sending / Buffer handling
	#

	def clear_buffer (self):
		self.logger.message(self.me('clearing MESSAGE(s) buffer'))
		self._messages = []

	def buffered (self):
		return len(self._messages)

	def _backlog (self):
		# performance only to remove inference
		if self._messages:
			if not self._frozen:
				self._frozen = time.time()
			if self._frozen and self._frozen + self.negotiated.holdtime < time.time():
				raise Failure('peer %s not reading on his socket (or not fast at all) - killing session' % self.neighbor.peer_as)
			self.logger.message(self.me("unable to send route for %d second (maximum allowed %d)" % (time.time()-self._frozen,self.negotiated.holdtime)))
			nb_backlog = len(self._messages)
			if nb_backlog > MAX_BACKLOG:
				raise Failure('over %d chunked routes buffered for peer %s - killing session' % (MAX_BACKLOG,self.neighbor.peer_as))
			self.logger.message(self.me("self._messages of %d/%d chunked routes" % (nb_backlog,MAX_BACKLOG)))
		while self._messages:
			number,name,update = self._messages[0]
			if not self.write(update):
				self.logger.message(self.me("|| failed to send %d %s(s) from buffer" % (number,name)))
				break
			self._messages.pop(0)
			self._frozen = 0
			yield name,number

	def _announce (self,name,generator):
		def chunked (generator,size):
			chunk = ''
			number = 0
			for data in generator:
				if len(data) > size:
					raise Failure('Can not send BGP update larger than %d bytes on this connection.' % size)
				if len(chunk) + len(data) <= size:
					chunk += data
					number += 1
					continue
				yield number,chunk
				chunk = data
				number = 1
			if chunk:
				yield number,chunk

		if self._messages:
			for number,update in chunked(generator,self.message_size):
					self.logger.message(self.me('|| adding %d  %s(s) to existing buffer' % (number,name)))
					self._messages.append((number,name,update))
			for name,number in self._backlog():
				self.logger.message(self.me('>> %d buffered %s(s)' % (number,name)))
				yield number
		else:
			sending = True
			for number,update in chunked(generator,self.message_size):
				if sending:
					if self.write(update):
						self.logger.message(self.me('>> %d %s(s)' % (number,name)))
						yield number
					else:
						self.logger.message(self.me('|| could not send %d %s(s), buffering' % (number,name)))
						self._messages.append((number,name,update))
						sending = False
				else:
					self.logger.message(self.me('|| buffering the rest of the %s(s) (%d)' % (name,number)))
					self._messages.append((number,name,update))
					yield 0
