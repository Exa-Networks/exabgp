# encoding: utf-8
"""
protocol.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import os

from exabgp.rib.table import Table
from exabgp.rib.delta import Delta

from exabgp.reactor.network.outgoing import Outgoing
from exabgp.reactor.network.error import SizeError

from exabgp.bgp.message import Message
from exabgp.bgp.message.nop import NOP
from exabgp.bgp.message.unknown import Unknown
from exabgp.bgp.message.open import Open
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.eor import EOR
from exabgp.bgp.message.keepalive import KeepAlive
from exabgp.bgp.message.notification import Notification, Notify
from exabgp.bgp.message.refresh import RouteRefresh

from exabgp.reactor.api.processes import ProcessError

from exabgp.logger import Logger,FakeLogger,LazyFormat

# This is the number of chuncked message we are willing to buffer, not the number of routes
MAX_BACKLOG = 15000

_NOP = NOP()
_UPDATE = Update()
_UNKNOWN = Unknown()

class Protocol (object):
	decode = True

	def __init__ (self,peer):
		try:
			self.logger = Logger()
		except RuntimeError:
			self.logger = FakeLogger()
		self.peer = peer
		self.neighbor = peer.neighbor
		self.negotiated = Negotiated()
		self.delta = Delta(Table(peer))
		self.connection = None
		port = os.environ.get('exabgp.tcp.port','')
		self.port = int(port) if port.isdigit() else 179

		# XXX: FIXME: check the the -19 is correct (but it is harmless)
		# The message size is the whole BGP message _without_ headers
		self.message_size = Message.MAX_LEN-Message.HEADER_LEN

	# XXX: we use self.peer.neighbor.peer_address when we could use self.neighbor.peer_address

	def me (self,message):
		return "Peer %15s ASN %-7s %s" % (self.peer.neighbor.peer_address,self.peer.neighbor.peer_as,message)

	def accept (self,incoming):
		if not self.connection:
			self.connection = incoming

		if self.peer.neighbor.api.neighbor_changes:
			self.peer.reactor.processes.connected(self.peer.neighbor.peer_address)

	def connect (self):
		# allows to test the protocol code using modified StringIO with a extra 'pending' function
		if not self.connection:
			peer = self.neighbor.peer_address
			local = self.neighbor.local_address
			md5 = self.neighbor.md5
			ttl = self.neighbor.ttl
			self.connection = Outgoing(peer.afi,peer.ip,local.ip,self.port,md5,ttl)

			if self.peer.neighbor.api.neighbor_changes:
				self.peer.reactor.processes.connected(self.peer.neighbor.peer_address)

	def close (self,reason='unspecified'):
		if self.connection:
			# must be first otherwise we could have a loop caused by the raise in the below
			self.connection.close()
			self.connection = None

			try:
				if self.peer.neighbor.api.neighbor_changes:
					self.peer.reactor.processes.down(self.peer.neighbor.peer_address,reason)
			except ProcessError:
				self.logger.message(self.me('could not send notification of neighbor close to API'))


	def write (self,message):
		if self.neighbor.api.send_packets:
			self.peer.reactor.processes.send(self.peer.neighbor.peer_address,message[18],message[:19],message[19:])
		for boolean in self.connection.writer(message):
			yield boolean

	# Read from network .......................................................

	def read_message (self,keepalive_comment=''):
		try:
			for length,msg,header,body in self.connection.reader():
				if not length:
					yield _NOP
		except ValueError,e:
			code,subcode,string = str(e).split(' ',2)
			raise Notify(int(code),int(subcode),string)

		if self.neighbor.api.receive_packets:
			self.peer.reactor.processes.receive(self.peer.neighbor.peer_address,msg,header,body)

		if msg == Message.Type.UPDATE:
			self.logger.message(self.me('<< UPDATE'))

			if length == 30 and body.startswith(EOR.PREFIX):
				yield EOR().factory(body)

			if self.neighbor.api.receive_routes:
				update = Update().factory(self.negotiated,body)

				for route in update.routes:
					self.logger.routes(LazyFormat(self.me(''),str,route))

				self.peer.reactor.processes.routes(self.neighbor.peer_address,update.routes)
				yield update
			else:
				yield _UNKNOWN

		elif msg == Message.Type.KEEPALIVE:
			self.logger.message(self.me('<< KEEPALIVE%s' % keepalive_comment))
			yield KeepAlive()

		elif msg == Message.Type.NOTIFICATION:
			self.logger.message(self.me('<< NOTIFICATION'))
			yield Notification().factory(body)

		elif msg == Message.Type.ROUTE_REFRESH:
			self.logger.message(self.me('<< ROUTE-REFRESH'))
			yield RouteRefresh().factory(body)

		elif msg == Message.Type.OPEN:
			yield Open().factory(body)

		else:
			self.logger.message(self.me('<< NOP (unknow type %d)' % msg))
			yield Unknown().factory(msg)

	def validate_open (self):
		error = self.negotiated.validate(self.neighbor)
		if error is not None:
			raise Notify(*error)

	def read_open (self,ip):
		for received_open in self.read_message():
			if received_open.TYPE == NOP.TYPE:
				yield received_open
			else:
				break

		if received_open.TYPE != Open.TYPE:
			raise Notify(5,1,'The first packet recevied is not an open message (%s)' % received_open)

		self.logger.message(self.me('<< %s' % received_open))
		yield received_open

	def read_keepalive (self,comment=''):
		for message in self.read_message(comment):
			if message.TYPE == NOP.TYPE:
				yield message
			else:
				break

		if message.TYPE != KeepAlive.TYPE:
			raise Notify(5,2)

		yield message

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

		# we do not buffer open message in purpose
		for _ in self.write(sent_open.message()):
			yield _NOP

		self.logger.message(self.me('>> %s' % sent_open))
		yield sent_open

	def new_keepalive (self,comment=''):
		keepalive = KeepAlive()

		for _ in self.write(keepalive.message()):
			yield _NOP

		self.logger.message(self.me('>> KEEPALIVE%s' % comment))
		yield keepalive

	def new_notification (self,notification):
		for _ in self.write(notification.message()):
			yield _NOP
		self.logger.error(self.me('>> NOTIFICATION (%d,%d,"%s")' % (notification.code,notification.subcode,notification.data)))
		yield notification

	def new_update (self):
		# XXX: This should really be calculated once only
		for _ in self._announce('UPDATE',self.peer.proto.delta.updates(self.negotiated,self.neighbor.group_updates)):
			yield _NOP
		yield _UPDATE

	def new_eors (self):
		eor = EOR().new(self.negotiated.families)
		for _ in self._announce(str(eor),eor.updates(self.negotiated)):
			yield _NOP
		yield _UPDATE

	def _announce (self,name,generator):
		def chunked (generator,size):
			chunk = ''
			number = 0
			for data in generator:
				if len(data) > size:
					raise SizeError('Can not send BGP update larger than %d bytes on this connection.' % size)
				if len(chunk) + len(data) <= size:
					chunk += data
					number += 1
					continue
				yield number,chunk
				chunk = data
				number = 1
			if chunk:
				yield number,chunk

		for number,update in chunked(generator,self.message_size):
			for boolean in self.write(update):
				if boolean:
					self.logger.message(self.me('>> %d %s(s)' % (number,name)))
					yield number
				else:
					yield 0
