# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

import sys
import time
import traceback

from exabgp.message              import Failure
from exabgp.message.nop          import NOP
from exabgp.message.open         import Open,Capabilities
from exabgp.message.update       import Update
from exabgp.message.keepalive    import KeepAlive
from exabgp.message.notification import Notification, Notify, NotConnected
from exabgp.network.protocol     import Protocol
from exabgp.processes            import ProcessError

from exabgp.log import Logger,LazyFormat
logger = Logger()

# As we can not know if this is our first start or not, this flag is used to
# always make the program act like it was recovering from a failure
# If set to FALSE, no EOR and OPEN Flags set for Restart will be set in the
# OPEN Graceful Restart Capability
FORCE_GRACEFUL = True

# Present a File like interface to socket.socket

class Peer (object):
	# debug hold/keepalive timers
	debug_trace = True			# debug traceback on unexpected exception
	update_time = 3

	def __init__ (self,neighbor,supervisor):
		self.supervisor = supervisor
		self.neighbor = neighbor
		# The next restart neighbor definition
		self._neighbor = None
		self.bgp = None
		# We may have new update to transmit to our peers, so we need to check
		self._updates = False

		self._loop = None
		self.open = None

		# The peer message should be processed
		self._running = False
		# The peer should restart after a stop
		self._restart = True
		# The peer was restarted (to know what kind of open to send for graceful restart)
		self._restarted = FORCE_GRACEFUL
		self._reset_skip()

		self._asn4 = True

		# The routes we have parsed from our neighbour
		self._received_routes = []

		self._route_parsed = 0L
		self._now = time.time()
		self._next_info = self._now + self.update_time

	def _reset_skip (self):
		# We are currently not skipping connection attempts
		self._skip_time = 0
		# when we can not connect to a peer how many time (in loop) should we back-off
		self._next_skip = 0

	def _more_skip (self):
		self._skip_time = time.time() + self._next_skip
		self._next_skip = int(1+ self._next_skip*1.2)
		if self._next_skip > 60:
			self._next_skip = 60

	def me (self,message):
		return "Peer %15s ASN %-7s %s" % (self.neighbor.peer_address,self.neighbor.peer_as,message)

	def stop (self):
		self._running = False
		self._restart = False
		self._restarted = False
		self._reset_skip()

	def reload (self,routes):
		self._updates = True
		self.neighbor.set_routes(routes)
		self._reset_skip()

	def restart (self,restart_neighbor=None):
		# we want to tear down the session and re-establish it
		self._running = False
		self._restart = True
		self._restarted = True
		self._route_parsed = 0L
		self._neighbor = restart_neighbor
		self._reset_skip()

	def run (self):
		if self._loop:
			try:
				if self._skip_time > time.time():
					return None
				else:
					return self._loop.next()
			except StopIteration:
				self._loop = None
		elif self._restart:
			# If we are restarting, and the neighbor definition is different, update the neighbor
			if self._neighbor:
				self.neighbor = self._neighbor
				self._neighbor = None
			self._running = True
			self._loop = self._run()
		else:
			self.bgp.close()
			self.supervisor.unschedule(self)

	def _run (self,max_wait_open=10.0):
		try:
			if self.supervisor.processes.broken(self.neighbor.peer_address):
				# XXX: we should perhaps try to restart the process ??
				raise Failure('ExaBGP lost the helper process for this peer - peer down')

			self.bgp = Protocol(self)
			self.bgp.connect()

			self._reset_skip()

			_open = self.bgp.new_open(self._restarted,self._asn4)
			logger.message(self.me('>> %s' % _open))
			yield None

			start = time.time()
			while True:
				self.open = self.bgp.read_open(_open,self.neighbor.peer_address.ip)
				if time.time() - start > max_wait_open:
					logger.message(self.me('Waited for an OPEN for too long - killing the session'))
					raise Notify(1,1,'The client took over %s seconds to send the OPEN, closing' % str(max_wait_open))
				# OPEN or NOP
				if self.open.TYPE == NOP.TYPE:
					yield None
					continue
				# This test is already done in read_open
				#if self.open.TYPE != Open.TYPE:
				#	raise Notify(5,1,'We are expecting an OPEN message')
				logger.message(self.me('<< %s' % self.open))
				if not self.open.capabilities.announced(Capabilities.FOUR_BYTES_ASN) and _open.asn.asn4():
					self._asn4 = False
					raise Notify(2,0,'peer does not speak ASN4 - restarting in compatibility mode')
				if _open.capabilities.announced(Capabilities.MULTISESSION_BGP):
					if not self.open.capabilities.announced(Capabilities.MULTISESSION_BGP):
						raise Notify(2,7,'peer does not support MULTISESSION')
					local_sessionid = set(_open.capabilities[Capabilities.MULTISESSION_BGP])
					remote_sessionid = self.open.capabilities[Capabilities.MULTISESSION_BGP]
					# Empty capability is the same as MultiProtocol (which is what we send)
					if not remote_sessionid:
						remote_sessionid.append(Capabilities.MULTIPROTOCOL_EXTENSIONS)
					remote_sessionid = set(remote_sessionid)
					# As we only send one MP per session, if the matching fails, we have nothing in common
					if local_sessionid.intersection(remote_sessionid) != local_sessionid:
						raise Notify(2,8,'peer did not reply with the sessionid we sent')
					# We can not collide due to the way we generate the configuration
				yield None
				break

			message = self.bgp.new_keepalive(force=True)
			logger.message(self.me('>> KEEPALIVE (OPENCONFIRM)'))
			yield True

			while True:
				message = self.bgp.read_keepalive()
				# KEEPALIVE or NOP
				if message.TYPE == KeepAlive.TYPE:
					logger.message(self.me('<< KEEPALIVE (ESTABLISHED)'))
					break
				yield None

			try:
				for name in self.supervisor.processes.notify(self.neighbor.peer_address):
					self.supervisor.processes.write(name,'neighbor %s up\n' % self.neighbor.peer_address)
			except ProcessError:
				# Can not find any better error code that 6,0 !
				raise Notify(6,0,'ExaBGP Internal error, sorry.')

			count = 0
			for count in self.bgp.new_announce():
				yield True
			self._updates = self.bgp.buffered()
			if count:
				logger.message(self.me('>> %d UPDATE(s)' % count))

			eor = False
			if self.neighbor.graceful_restart and \
				self.open.capabilities.announced(Capabilities.MULTIPROTOCOL_EXTENSIONS) and \
				self.open.capabilities.announced(Capabilities.GRACEFUL_RESTART):

				families = []
				for family in self.open.capabilities[Capabilities.GRACEFUL_RESTART].families():
					if family in self.neighbor.families():
						families.append(family)
				self.bgp.new_eors(families)
				if families:
					eor = True
					logger.message(self.me('>> EOR %s' % ', '.join(['%s %s' % (str(afi),str(safi)) for (afi,safi) in families])))

			if not eor:
				# If we are not sending an EOR, send a keepalive as soon as when finished
				# So the other routers knows that we have no (more) routes to send ...
				# (is that behaviour documented somewhere ??)
				c,k = self.bgp.new_keepalive(True)
				if k: logger.message(self.me('>> KEEPALIVE (no more UPDATE and no EOR)'))

			seen_update = False
			while self._running:
				self._now = time.time()
				if self._now > self._next_info:
					self._next_info = self._now + self.update_time
					display_update = True
				else:
					display_update = False

				c,k = self.bgp.new_keepalive()
				if k: logger.message(self.me('>> KEEPALIVE'))

				if display_update:
					logger.timers(self.me('Sending Timer %d second(s) left' % c))

				message = self.bgp.read_message()
				# let's read if we have keepalive before doing the timer check
				c = self.bgp.check_keepalive()

				if display_update:
					logger.timers(self.me('Receive Timer %d second(s) left' % c))

				if message.TYPE == KeepAlive.TYPE:
					logger.message(self.me('<< KEEPALIVE'))
				elif message.TYPE == Update.TYPE:
					seen_update = True
					self._received_routes.extend(message.routes)
					if message.routes:
						logger.message(self.me('<< UPDATE'))
						self._route_parsed += len(message.routes)
						if self._route_parsed:
							for route in message.routes:
								logger.routes(LazyFormat(self.me(''),str,route))
					else:
						logger.message(self.me('<< UPDATE (not parsed)'))
				elif message.TYPE not in (NOP.TYPE,):
					 logger.message(self.me('<< %d' % ord(message.TYPE)))

				if seen_update and display_update:
					logger.supervisor(self.me('processed %d routes' % self._route_parsed))
					seen_update = False

				if self._updates:
					count = 0
					for count in self.bgp.new_update():
						yield True
					logger.message(self.me('>> UPDATE (%d)' % count))
					self._updates = self.bgp.buffered()

				yield None

			if self.neighbor.graceful_restart and self.open.capabilities.announced(Capabilities.GRACEFUL_RESTART):
				logger.warning('Closing the connection without notification')
				self.bgp.close()
				return

			# User closing the connection
			raise Notify(6,3)
		except NotConnected, e:
			logger.warning('we can not connect to the peer %s' % str(e))
			self._more_skip()
			try:
				self.bgp.close()
			except Failure:
				pass
			return
		except Notify,e:
			logger.warning(self.me('Sending Notification (%d,%d) [%s] %s' % (e.code,e.subcode,str(e),e.data)))
			try:
				self.bgp.new_notification(e)
			except Failure:
				pass
			try:
				self.bgp.close()
			except Failure:
				pass
			return
		except Notification, e:
			logger.warning(self.me('Received Notification (%d,%d) from peer %s' % (e.code,e.subcode,str(e))))
			try:
				self.bgp.close()
			except Failure:
				pass
			return
		except Failure, e:
			logger.warning(self.me(str(e)),'connection')
			self._more_skip()
			try:
				self.bgp.close()
			except Failure:
				pass
			return
		except Exception, e:
			logger.warning(self.me('UNHANDLED EXCEPTION'))
			self._more_skip()
			if self.debug_trace:
				# should really go to syslog
				traceback.print_exc(file=sys.stdout)
				raise
			else:
				logger.warning(self.me(str(e)))
			if self.bgp: self.bgp.close()
			return

	def received_routes (self):
		if self._received_routes:
			while self._received_routes:
				route = self._received_routes.pop(0)
				yield str(route)
		else:
			raise StopIteration()

