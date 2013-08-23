# encoding: utf-8
"""
protocol.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import os

from exabgp.reactor.network.outgoing import Outgoing
from exabgp.reactor.network.error import NotifyError

from exabgp.bgp.message import Message
from exabgp.bgp.message.nop import NOP
from exabgp.bgp.message.unknown import UnknownMessageFactory
from exabgp.bgp.message.open import Open,OpenFactory
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import Update,messages
from exabgp.bgp.message.update.eor import EOR,EORFactory
from exabgp.bgp.message.keepalive import KeepAlive
from exabgp.bgp.message.notification import NotificationFactory, Notify
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update.factory import UpdateFactory

from exabgp.reactor.api.processes import ProcessError
from exabgp.rib.change import Change

from exabgp.logger import Logger,FakeLogger,LazyFormat

# This is the number of chuncked message we are willing to buffer, not the number of routes
MAX_BACKLOG = 15000

_NOP = NOP()
_UPDATE = Update([],'')

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
		self.connection = incoming

		if self.peer.neighbor.api.neighbor_changes:
			self.peer.reactor.processes.connected(self.peer.neighbor.peer_address)

		# very important - as we use this function on __init__
		return self

	def connect (self):
		# allows to test the protocol code using modified StringIO with a extra 'pending' function
		if not self.connection:
			peer = self.neighbor.peer_address
			local = self.neighbor.local_address
			md5 = self.neighbor.md5
			ttl = self.neighbor.ttl
			self.connection = Outgoing(peer.afi,peer.ip,local.ip,self.port,md5,ttl)

			connected = False
			try:
				generator = self.connection.establish()
				while True:
					connected = generator.next()
					if not connected:
						yield False
						continue
					if self.peer.neighbor.api.neighbor_changes:
						self.peer.reactor.processes.connected(self.peer.neighbor.peer_address)
					yield True
					return
			except StopIteration:
				# close called by the caller
				# self.close('could not connect to remote end')
				yield False
				return

	def close (self,reason='protocol closed, reason unspecified'):
		self.logger.network(self.me(reason))
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

	def read_message (self,comment=''):
		try:
			for length,msg,header,body in self.connection.reader():
				if not length:
					yield _NOP
		except NotifyError,n:
			raise Notify(n.code,n.subcode,str(n))

		if self.neighbor.api.receive_packets:
			self.peer.reactor.processes.receive(self.peer.neighbor.peer_address,msg,header,body)

		if msg == Message.Type.UPDATE:
			self.logger.message(self.me('<< UPDATE'))

			if length == 30 and body.startswith(EOR.PREFIX):
				update = EORFactory(body)
			elif self.neighbor.api.receive_routes:
				update = UpdateFactory(self.negotiated,body)
			else:
				yield _UPDATE
				return

			# XXX: FIXME: really this should be in the Peer loop :-)
			for nlri in update.nlris:
				self.neighbor.rib.incoming.insert_received(Change(nlri,update.attributes))
				self.logger.routes(LazyFormat(self.me(''),str,nlri))

			self.peer.reactor.processes.update(self.neighbor.peer_address,update)
			yield update

		elif msg == Message.Type.KEEPALIVE:
			self.logger.message(self.me('<< KEEPALIVE%s' % (' (%s)' % comment if comment else '')))
			yield KeepAlive()

		elif msg == Message.Type.NOTIFICATION:
			self.logger.message(self.me('<< NOTIFICATION'))
			yield NotificationFactory(body)

		elif msg == Message.Type.ROUTE_REFRESH:
			self.logger.message(self.me('<< ROUTE-REFRESH'))
			# not doing anything with the Data we do not handle route refresh
			yield RouteRefresh()

		elif msg == Message.Type.OPEN:
			yield OpenFactory(body)

		else:
			self.logger.message(self.me('<< NOP (unknow type %d)' % msg))
			yield UnknownMessageFactory(msg)

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
		sent_open = Open(
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

		self.logger.message(self.me('>> KEEPALIVE%s' % (' (%s)' % comment if comment else '')))

		yield keepalive

	def new_notification (self,notification):
		for _ in self.write(notification.message()):
			yield _NOP
		self.logger.message(self.me('>> NOTIFICATION (%d,%d,"%s")' % (notification.code,notification.subcode,notification.data)))
		yield notification

	def new_update (self):
		number = 0
		for update in self.neighbor.rib.outgoing.updates(self.neighbor.group_updates):
			for message in messages(update,self.negotiated):
				number += 1
				for boolean in self.write(message):
					# boolean is a transient network error we already announced
					yield _NOP
		if number:
			self.logger.message(self.me('>> %d UPDATE(s)' % number))
		yield _UPDATE

	def new_eors (self):
		# Send EOR to let our peer know he can perform a RIB update
		if self.negotiated.families:
			for afi,safi in self.negotiated.families:
				eor = EOR(afi,safi).message()
				for _ in self.write(eor):
					yield _NOP
				yield _UPDATE
		else:
			# If we are not sending an EOR, send a keepalive as soon as when finished
			# So the other routers knows that we have no (more) routes to send ...
			# (is that behaviour documented somewhere ??)
			for eor in self.new_keepalive('EOR'):
				yield _NOP
			yield _UPDATE
