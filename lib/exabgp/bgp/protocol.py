# encoding: utf-8
"""
protocol.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

import time
from struct import unpack

from exabgp.rib.table import Table
from exabgp.rib.delta import Delta

from exabgp.bgp.connection import Connection
from exabgp.bgp.message import Message,Failure
from exabgp.bgp.message.nop import NOP
from exabgp.bgp.message.open import Open
from exabgp.bgp.message.open.asn import AS_TRANS
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.open.capability.id import CapabilityID
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.eor import EOR
from exabgp.bgp.message.keepalive import KeepAlive
from exabgp.bgp.message.notification import Notification, Notify

from exabgp.structure.processes import ProcessError

from exabgp.structure.log import Logger
logger = Logger()

# This is the number of chuncked message we are willing to buffer, not the number of routes
MAX_BACKLOG = 15000


# README: Move all the old packet decoding in another file to clean up the includes here, as it is not used anyway

class Protocol (object):
	decode = True

	def __init__ (self,peer,connection=None):
		self.peer = peer
		self.neighbor = peer.neighbor
		self.connection = connection
		# for which afi/safi pair should we encode path information (addpath)
		self.use_path = None

		self._delta = Delta(Table(peer))
		self._asn4 = False
		self._messages = []
		self._frozen = 0
		# The message size is the whole BGP message _without_ headers
		self.message_size = 4096-19

		# The holdtime / families negocicated between the two peers
		self.hold_time = None
		self.families = []

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

			if self.peer.neighbor.peer_updates:
				message = 'neighbor %s connected\n' % self.peer.neighbor.peer_address
				try:
					proc = self.peer.supervisor.processes
					for name in proc.notify(self.neighbor.peer_address):
						proc.write(name,message)
				except ProcessError:
					raise Failure('Could not send message(s) to helper program(s) : %s' % message)

	def check_keepalive (self):
		left = int (self.connection.last_read  + self.hold_time - time.time())
		if left <= 0:
			raise Notify(4,0)
		return left

	def close (self,reason='unspecified'):
		#self._delta.last = 0
		if self.connection:
			# must be first otherwise we could have a loop caused by the raise in the below
			self.connection.close()
			self.connection = None

			if self.peer.neighbor.peer_updates:
				message = 'neighbor %s down - %s\n' % (self.peer.neighbor.peer_address,reason)
				try:
					proc = self.peer.supervisor.processes
					for name in proc.notify(self.neighbor.peer_address):
						proc.write(name,message)
				except ProcessError:
					raise Failure('Could not send message(s) to helper program(s) : %s' % message)

	# Read from network .......................................................

	def read_message (self):
		# This call reset the time for the timeout in
		if not self.connection.pending(True):
			return NOP('')

		length = 19
		data = ''
		while length:
			if self.connection.pending():
				delta = self.connection.read(length)
				data += delta
				length -= len(delta)
				# The socket is closed
				if not data:
					raise Failure('The TCP connection is closed')

		if data[:16] != Message.MARKER:
			# We are speaking BGP - send us a valid Marker
			raise Notify(1,1,'The packet received does not contain a BGP marker')

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
		data = ''
		while length:
			if self.connection.pending():
				delta = self.connection.read(length)
				data += delta
				length -= len(delta)
				# The socket is closed
				if not data:
					raise Failure('The TCP connection is closed')

		if msg == Notification.TYPE:
			raise Notification(ord(data[0]),ord(data[1]))

		if msg == KeepAlive.TYPE:
			return KeepAlive()

		if msg == Open.TYPE:
			return Open().factory(data)

		if msg == Update.TYPE:
			if self.neighbor.parse_routes:
				update = Update().factory(self._asn4,self.neighbor.families(),self.use_path,data)
				if update.routes:
					return update

		return NOP(data)

	def read_open (self,_open,ip):
		message = self.read_message()

		if message.TYPE == NOP.TYPE:
			return message

		if message.TYPE != Open.TYPE:
			raise Notify(5,1,'The first packet recevied is not an open message (%s)' % message)

		if _open.asn.asn4() and not message.capabilities.announced(CapabilityID.FOUR_BYTES_ASN):
			raise Notify(2,0,'We have an ASN4 and you do not speak it. bye.')

		self._asn4 = message.capabilities.announced(CapabilityID.FOUR_BYTES_ASN)

		if message.asn == AS_TRANS:
			peer_as = message.capabilities[CapabilityID.FOUR_BYTES_ASN]
		else:
			peer_as = message.asn

		if peer_as != self.neighbor.peer_as:
			raise Notify(2,2,'ASN in OPEN (%d) did not match ASN expected (%d)' % (message.asn,self.neighbor.peer_as))

		# RFC 6286 : http://tools.ietf.org/html/rfc6286
		#if message.router_id == RouterID('0.0.0.0'):
		#	message.router_id = RouterID(ip)
		if message.router_id == RouterID('0.0.0.0'):
			raise Notify(2,3,'0.0.0.0 is an invalid router_id according to RFC6286')
		if message.router_id == self.neighbor.router_id and message.asn == self.neighbor.local_as:
			raise Notify(2,3,'BGP Indendifier collision (%s) on IBGP according to RFC 6286' % message.router_id)

		if message.hold_time < 3:
			raise Notify(2,6,'Hold Time is invalid (%d)' % message.hold_time)
		if message.hold_time >= 3:
			self.hold_time = HoldTime(min(self.neighbor.hold_time,message.hold_time))

		if message.capabilities.announced(CapabilityID.MULTIPROTOCOL_EXTENSIONS) \
		and _open.capabilities.announced(CapabilityID.MULTIPROTOCOL_EXTENSIONS):
			for family in message.capabilities[CapabilityID.MULTIPROTOCOL_EXTENSIONS]:
				if family in _open.capabilities[CapabilityID.MULTIPROTOCOL_EXTENSIONS]:
					self.families.append(family)

		# XXX: Does not work as the capa is not yet defined
		if message.capabilities.announced(CapabilityID.EXTENDED_MESSAGE):
			# untested !
			if self.peer.bgp.message_size:
				self.message_size = self.peer.bgp.message_size - 19

# README: This limit what we are announcing may cause some issue if you add new family and SIGHUP
# README: So it is commented until I make my mind to add it or not (as Juniper complain about mismatch capabilities)
#		# Those are the capacity we need to announce those routes
#		for family in _open.capabilities[CapabilityID.MULTIPROTOCOL_EXTENSIONS]:
#			# if the peer does not support them, tear down the session
#			if family not in message.capabilities[CapabilityID.MULTIPROTOCOL_EXTENSIONS]:
#				afi,safi = family
#				raise Notify(2,0,'Peers does not speak %s %s' % (afi,safi))

		logger.message(self.me('<< %s' % message))
		return message

	def read_keepalive (self):
		message = self.read_message()
		if message.TYPE == NOP.TYPE:
			return message
		if message.TYPE != KeepAlive.TYPE:
			raise Notify(5,2)
		logger.message(self.me('<< KEEPALIVE (ESTABLISHED)'))
		return message

	# Sending message to peer .................................................

	# we do not buffer those message in purpose

	def new_open (self,restarted,asn4):
		if asn4:
			asn = self.neighbor.local_as
		else:
			asn = AS_TRANS

		o = Open().new(4,asn,self.neighbor.router_id.ip,Capabilities().default(self.neighbor,restarted),self.neighbor.hold_time)

		if not self.connection.write(o.message()):
			raise Failure('Could not send open')
		logger.message(self.me('>> %s' % o))
		return o

	def new_keepalive (self,force=None):
		left = int(self.connection.last_write + self.hold_time.keepalive() - time.time())
		k = KeepAlive()
		m = k.message()
		if force:
			written = self.connection.write(k.message())
			if not written:
				logger.message(self.me('|| buffer not yet empty, adding KEEPALIVE to it'))
				self._messages.append((1,'KEEPALIVE',m))
			else:
				self._frozen = 0
				if force == True:
					logger.message(self.me('>> KEEPALIVE (OPENCONFIRM)'))
				elif force == False:
					logger.message(self.me('>> KEEPALIVE (no more UPDATE and no EOR)'))
			return left,k
		if left <= 0:
			written = self.connection.write(k.message())
			if not written:
				logger.message(self.me('|| could not send KEEPALIVE, buffering'))
				self._messages.append((1,'KEEPALIVE',m))
			else:
				logger.message(self.me('>> KEEPALIVE'))
				self._frozen = 0
			return left,k
		return left,None

	def new_notification (self,notification):
		return self.connection.write(notification.message())

	def clear_buffer (self):
		logger.message(self.me('clearing MESSAGE(s) buffer'))
		self._messages = []

	def buffered (self):
		return len(self._messages)

	def _backlog (self):
		# performance only to remove inference
		if self._messages:
			if not self._frozen:
				self._frozen = time.time()
			if self._frozen and self._frozen + (self.hold_time) < time.time():
				raise Failure('peer %s not reading on socket - killing session' % self.neighbor.peer_as)
			logger.message(self.me("unable to send route for %d second (maximum allowed %d)" % (time.time()-self._frozen,self.hold_time)))
			nb_backlog = len(self._messages)
			if nb_backlog > MAX_BACKLOG:
				raise Failure('over %d chunked routes buffered for peer %s - killing session' % (MAX_BACKLOG,self.neighbor.peer_as))
			logger.message(self.me("self._messages of %d/%d chunked routes" % (nb_backlog,MAX_BACKLOG)))
		while self._messages:
			number,name,update = self._messages[0]
			if not self.connection.write(update):
				logger.message(self.me("|| failed to send %d %s(s) from buffer" % (number,name)))
				break
			self._messages.pop(0)
			self._frozen = 0
			yield number

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
					logger.message(self.me('|| adding %d  %s(s) to existing buffer' % (number,name)))
					self._messages.append((number,name,update))
			for number in self._backlog():
				logger.message(self.me('>> %d buffered %s(s)' % (number,name)))
				yield number
		else:
			sending = True
			for number,update in chunked(generator,self.message_size):
				if sending:
					if self.connection.write(update):
						logger.message(self.me('>> %d %s(s)' % (number,name)))
						yield number
					else:
						logger.message(self.me('|| could not send %d %s(s), buffering' % (number,name)))
						self._messages.append((number,name,update))
						sending = False
				else:
					logger.message(self.me('|| buffering the rest of the %s(s) (%d)' % (name,number)))
					self._messages.append((number,name,update))
					yield 0

	def new_update (self):
		# XXX: This should really be calculated once only
		asn4 = not not self.peer.open.capabilities.announced(CapabilityID.FOUR_BYTES_ASN)
		for number in self._announce('UPDATE',self._delta.updates(asn4,self.neighbor.local_as,self.neighbor.peer_as,self.neighbor.group_updates,self.use_path,self.message_size)):
			yield number

	def new_eors (self,families):
		eor = EOR()
		eors = eor.eors(families)
		for answer in self._announce('EOR %s' % ', '.join(['%s %s' % (str(afi),str(safi)) for (afi,safi) in families]),eors):
			pass

