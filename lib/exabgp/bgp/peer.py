# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import sys
import time
import traceback

from exabgp.bgp.timer import Timer
from exabgp.bgp.message import Message
from exabgp.bgp.message.open.capability.id import CapabilityID
from exabgp.bgp.message.nop import NOP
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.notification import Notification, Notify
#from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.reactor.protocol import Protocol
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.api.processes import ProcessError

from exabgp.configuration.environment import environment
from exabgp.logger import Logger,FakeLogger

from exabgp.util.counter import Counter

# As we can not know if this is our first start or not, this flag is used to
# always make the program act like it was recovering from a failure
# If set to FALSE, no EOR and OPEN Flags set for Restart will be set in the
# OPEN Graceful Restart Capability
FORCE_GRACEFUL = True

class Interrupted (Exception): pass

# Present a File like interface to socket.socket

class Peer (object):
	def __init__ (self,neighbor,reactor):
		try:
			self.logger = Logger()
			# We only to try to connect via TCP once
			self.once = environment.settings().tcp.once
		except RuntimeError:
			self.logger = FakeLogger()
			self.once = True

		self.reactor = reactor
		self.neighbor = neighbor
		# The next restart neighbor definition
		self._neighbor = None
		self.bgp = None

		self._loop = None

		# The peer message should be processed
		self._running = False
		# The peer should restart after a stop
		self._restart = True
		# The peer was restarted (to know what kind of open to send for graceful restart)
		self._restarted = FORCE_GRACEFUL
		self._reset_skip()

		# We have routes following a reload (or we just started)
		self._have_routes = True

		# We have been asked to teardown the session with this code
		self._teardown = None

		# A peer connected to us and we need to associate the socket to us
		self._peered = False

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

	def reload (self,neighbor):
		self.neighbor = neighbor
		self._have_routes = True
		self._reset_skip()

	def restart (self,restart_neighbor=None):
		# we want to tear down the session and re-establish it
		self._running = False
		self._restart = True
		self._restarted = True
		self._neighbor = restart_neighbor
		self._reset_skip()

	def teardown (self,code,restart=True):
		self._running = False
		self._restart = restart
		self._teardown = code
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
			self.bgp.close('safety shutdown before unregistering peer, session should already be closed, report if seen in anywhere')
			self.reactor.unschedule(self)

	def incoming (self,incoming):
		self._peered = True
		self.bgp = Protocol(self)
		self.bgp.accept(incoming)

	def _accept (self):
		# waiting for a connection
		while self._running and not self._peered:
			yield None

		# Read OPEN
		# XXX: FIXME: put that timer timer in the configuration
		opentimer = Timer(self.me,10.0,1,1,'waited for open too long')

		for message in self.bgp.read_open(self.neighbor.peer_address.ip):
			opentimer.tick()
			if not self._running:
				break
			# XXX: FIXME: change the whole code to use the ord and not the chr version
			if ord(message.TYPE) not in [Message.Type.NOP,Message.Type.OPEN]:
				raise message
			yield None

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

		# send OPEN
		for _open in self.bgp.new_open(self._restarted):
			yield True

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

		self.bgp.negotiate()

		# Start keeping keepalive timer
		self.timer = Timer(self.me,self.bgp.negotiated.holdtime,4,0)

		# Send KEEPALIVE
		for message in self.bgp.new_keepalive(' (ESTABLISHED)'):
			yield True

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

		# Read KEEPALIVE
		for message in self.bgp.read_keepalive(' (OPENCONFIRM)'):
			self.timer.tick(message)
			if not self._running:
				break
			if ord(message.TYPE) not in [Message.Type.NOP,Message.Type.KEEPALIVE]:
				raise message
			yield None

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

		# Announce to the process BGP is up
		self.logger.network('Connected to peer %s' % self.neighbor.name())
		if self.neighbor.api.neighbor_changes:
			try:
				self.reactor.processes.up(self.neighbor.peer_address)
			except ProcessError:
				# Can not find any better error code than 6,0 !
				# XXX: We can not restart the program so this will come back again and again - FIX
				# XXX: In the main loop we do exit on this kind of error
				raise Notify(6,0,'ExaBGP Internal error, sorry.')


		# Sending our routing table
		# Dict with for each AFI/SAFI pair if we should announce ADDPATH Path Identifier
		for message in self.bgp.new_update():
			yield True

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

		# Send EOR to let our peer know he can perform a RIB update
		if self.bgp.negotiated.families:
			for message in self.bgp.new_eors():
				yield True
		else:
			# If we are not sending an EOR, send a keepalive as soon as when finished
			# So the other routers knows that we have no (more) routes to send ...
			# (is that behaviour documented somewhere ??)
			for message in self.bgp.new_keepalive('KEEPALIVE (EOR)'):
				yield True

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

	def _connect (self):
		if self.reactor.processes.broken(self.neighbor.peer_address):
			# XXX: we should perhaps try to restart the process ??
			self.logger.error('ExaBGP lost the helper process for this peer - stopping','process')
			self._running = False

		self.bgp = Protocol(self)
		self.bgp.connect()

		self._reset_skip()

		# send OPEN
		for _open in self.bgp.new_open(self._restarted):
			yield True

		# Read OPEN
		# XXX: FIXME: put that timer timer in the configuration
		opentimer = Timer(self.me,10.0,1,1,'waited for open too long')

		for message in self.bgp.read_open(self.neighbor.peer_address.ip):
			opentimer.tick()
			if not self._running:
				break
			# XXX: FIXME: change the whole code to use the ord and not the chr version
			if ord(message.TYPE) not in [Message.Type.NOP,Message.Type.OPEN]:
				raise message
			yield None

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

		self.bgp.negotiate()

		# Start keeping keepalive timer
		self.timer = Timer(self.me,self.bgp.negotiated.holdtime,4,0)

		# Read KEEPALIVE
		for message in self.bgp.read_keepalive(' (OPENCONFIRM)'):
			self.timer.tick(message)
			if not self._running:
				break
			if ord(message.TYPE) not in [Message.Type.NOP,Message.Type.KEEPALIVE]:
				raise message
			yield None

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

		# Send KEEPALIVE
		for message in self.bgp.new_keepalive(' (ESTABLISHED)'):
			yield True

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

		# Announce to the process BGP is up
		self.logger.network('Connected to peer %s' % self.neighbor.name())
		if self.neighbor.api.neighbor_changes:
			try:
				self.reactor.processes.up(self.neighbor.peer_address)
			except ProcessError:
				# Can not find any better error code than 6,0 !
				# XXX: We can not restart the program so this will come back again and again - FIX
				# XXX: In the main loop we do exit on this kind of error
				raise Notify(6,0,'ExaBGP Internal error, sorry.')


		# Sending our routing table
		# Dict with for each AFI/SAFI pair if we should announce ADDPATH Path Identifier
		for message in self.bgp.new_update():
			yield True

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

		# Send EOR to let our peer know he can perform a RIB update
		if self.bgp.negotiated.families:
			for message in self.bgp.new_eors():
				yield True
		else:
			# If we are not sending an EOR, send a keepalive as soon as when finished
			# So the other routers knows that we have no (more) routes to send ...
			# (is that behaviour documented somewhere ??)
			for message in self.bgp.new_keepalive('KEEPALIVE (EOR)'):
				yield True

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

	def _connected (self):
		new_routes = None
		counter = Counter(self.logger,self.me)

		while self._running:
			for message in self.bgp.read_message():
				# SEND KEEPALIVES
				self.timer.tick(message)
				if self.timer.keepalive():
					self.bgp.new_keepalive()

				# Received update
				if message.TYPE == Update.TYPE:
					counter.increment(len(message.routes))

				# Give information on the number of routes seen
				counter.display()

				# Need to send update
				if self._have_routes and not new_routes:
					self._have_routes = False
					new_routes = self.bgp.new_update()

				if new_routes:
					try:
						new_routes.next()
					except StopIteration:
						new_routes = None

				# Go to other Peers
				yield True if new_routes or message.TYPE != NOP.TYPE else None

				# read_message will loop until new message arrives with NOP
				if not self._running:
					break

		# If graceful restart, silent shutdown
		if self.neighbor.graceful_restart and self.bgp.open_sent.capabilities.announced(CapabilityID.GRACEFUL_RESTART):
			self.logger.error('Closing the connection without notification','network')
			self.bgp.close('graceful restarted negotiated, closing without sending any notification')
			return

		# notify our peer of the shutdown
		if self._teardown:
			code, self._teardown = self._teardown, None
			raise Notify(6,code)
		raise Notify(6,3)

	def _run (self):
		"yield True if we want the reactor to give us back the hand with the same peer loop, None if we do not have any more work to do"

		try:
			if self.neighbor.passive:
				for event in self._accept():
					yield event
			else:
				for event in self._connect():
					yield event

			for event in self._connected():
				yield event

		# CONNECTION FAILURE, UPDATING TIMERS FOR BACK-OFF
		except NetworkError, e:
			self._loop = None
			self._peered = False
			self.logger.network('can not write to the peer, reason : %s' % str(e))
			self._more_skip()
			self.bgp.close('could not connect to the peer')

			# we tried to connect once, it failed, we stop
			if self.once:
				self.logger.network('only one attempt to connect is allowed, stoping the peer')
				self.stop()
			return

		# NOTIFY THE PEER OF AN ERROR
		except Notify,e:
			self._loop = None
			self._peered = False
			try:
				self.bgp.new_notification(e)
			except (NetworkError,ProcessError):
				self.logger.error(self.me('NOTIFICATION NOT SENT','network'))
				pass
			self.bgp.close('notification sent (%d,%d) [%s] %s' % (e.code,e.subcode,str(e),e.data))
			return

		# THE PEER NOTIFIED US OF AN ERROR
		except Notification, e:
			self._loop = None
			self._peered = False
			self.logger.error(self.me('Received Notification (%d,%d) %s' % (e.code,e.subcode,str(e))),'reactor')
			self.bgp.close('notification received (%d,%d) %s' % (e.code,e.subcode,str(e)))
			return

		# RECEIVED a Message TYPE we did not expect
		except Message, e:
			# XXX: FIXME: return better information about the message in question
			self._loop = None
			self._peered = False
			self.logger.error(self.me('Received unexpected message','network'))
			self.bgp.close('unexpected message received')
			return

		# PROBLEM WRITING TO OUR FORKED PROCESSES
		except ProcessError, e:
			self._loop = None
			self._peered = False
			self.logger.error(self.me(str(e)),'reactor')
			self._more_skip()
			self.bgp.close('failure %s' % str(e))
			return

		# MOST LIKELY ^C DURING A LOOP
		except Interruped, e:
			self._loop = None
			self._peered = False
			self.logger.error(self.me(str(e)),'reactor')
			self._more_skip()
			self.bgp.close('interruped %s' % str(e))
			return

		# UNHANDLED PROBLEMS
		except Exception, e:
			self._loop = None
			self._peered = False
			self.logger.error(self.me('UNHANDLED EXCEPTION'),'reactor')
			self._more_skip()
			# XXX: we need to read this from the env.
			if True:
				traceback.print_exc(file=sys.stdout)
				raise
			else:
				self.logger.error(self.me(str(e)),'reactor')
			if self.bgp: self.bgp.close('internal problem %s' % str(e))
			return
