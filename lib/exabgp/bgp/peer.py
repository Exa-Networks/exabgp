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

from exabgp.configuration.environment import environment

from exabgp.util.enumeration import Enumeration

STATE = Enumeration (
	'idle',
	'active',
	'connect',
	'opensent',
	'openconfirm',
	'established',
)

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

		self._out_proto = None
		self._in_proto = None

		self._in_loop = None
		self._out_loop = None

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
		self._accepted = False

		# the BGP session state
		self._in_state = STATE.idle
		self._out_state = STATE.idle

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

	def ios (self):
		ios = []
		if self._out_proto:
			ios.append(self._out_proto.connection.io)
		if self._in_proto:
			ios.append(self._in_proto.connection.io)
		return ios

	def run (self):
		if self._in_loop or self._out_loop:
			if self._skip_time > time.time():
				return None

			if self._in_loop:
				try:
					rin = self._in_loop.next()
				except StopIteration:
					rin = None
					self._in_loop = None
			else:
				rin = None


			if self._out_loop:
				try:
					rout = self._out_loop.next()
				except StopIteration:
					rout = None
					self._out_loop = None
			else:
				rout = None

			if True in [rin,rout]:
				return True
			return None

		elif self._restart:
			# If we are restarting, and the neighbor definition is different, update the neighbor
			if self._neighbor:
				self.neighbor = self._neighbor
				self._neighbor = None
			self._running = True
			self._in_loop = self._run('in')
			self._out_loop = self._run('out')

		else:
			if self._out_proto: self._out_proto.close('safety shutdown before unregistering peer, session should already be closed, report if seen in anywhere')
			if self._in_proto: self._in_proto.close('safety shutdown before unregistering peer, session should already be closed, report if seen in anywhere')
			self.reactor.unschedule(self)

	def incoming (self,incoming):
		if self._out_state != STATE.established:
			self._accepted = True
			self._out_proto = Protocol(self)
			self._out_proto.accept(incoming)
			self._in_loop = None
		else:
			incoming.notification(2,0,'connection already established')
			incoming.close()

	def _accept (self):
		"yield True if we want to come back to it asap, None if nothing urgent, and False if stopped"

		# waiting for a connection
		while self._running and not self._accepted:
			#print '\nWAITING ACCEPT\n'
			yield None

		if not self._accepted:
			yield False
			return

		# Read OPEN
		wait = environment.settings().bgp.openwait
		opentimer = Timer(self.me,wait,1,1,'waited for open too long, we do not like stuck in active')

		for message in self._out_proto.read_open(self.neighbor.peer_address.ip):
			# XXX: FIXME: this should return data and we should raise here
			opentimer.tick(message)
			if not self._running:
				yield False
				return
			# XXX: FIXME: change the whole code to use the ord and not the chr version
			if ord(message.TYPE) not in [Message.Type.NOP,Message.Type.OPEN]:
				raise message
			yield None

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

		self._in_proto.negotiated.received(message)

		# send OPEN
		for message in self._out_proto.new_open(self._restarted):
			if not self._running:
				yield False
				return
			yield True

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

		self._in_proto.negotiated.sent(message)
		self._in_proto.validate_open()

		# Send KEEPALIVE
		for message in self._out_proto.new_keepalive(' (ESTABLISHED)'):
			if not self._running:
				yield False
				return
			yield True

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

		self._state = STATE.openconfirm

		# Start keeping keepalive timer
		self.timer = Timer(self.me,self._out_proto.negotiated.holdtime,4,0)

		# Read KEEPALIVE
		for message in self._out_proto.read_keepalive(' (OPENCONFIRM)'):
			self.timer.tick(message)
			if not self._running:
				yield False
				return
			if ord(message.TYPE) not in [Message.Type.NOP,Message.Type.KEEPALIVE]:
				raise message
			yield None

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

		self._out_state = STATE.established


	def _connect (self):
		self._state = STATE.active

		if self.reactor.processes.broken(self.neighbor.peer_address):
			# XXX: we should perhaps try to restart the process ??
			self.logger.error('ExaBGP lost the helper process for this peer - stopping','process')
			self._running = False

		self._out_proto = Protocol(self)
		self._out_proto.connect()
		self._reset_skip()
		self._out_state = STATE.connect

		# send OPEN
		for message in self._out_proto.new_open(self._restarted):
			yield True

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

		self._out_proto.negotiated.sent(message)
		self._out_state = STATE.opensent

		# Read OPEN
		wait = environment.settings().bgp.openwait
		opentimer = Timer(self.me,wait,1,1,'waited for open too long, we do not like stuck in active')

		for message in self._out_proto.read_open(self.neighbor.peer_address.ip):
			opentimer.tick(message)
			if not self._running:
				break
			# XXX: FIXME: change the whole code to use the ord and not the chr version
			if ord(message.TYPE) not in [Message.Type.NOP,Message.Type.OPEN]:
				raise message
			yield None

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

		self._out_proto.negotiated.received(message)
		self._out_proto.validate_open()

		self._state = STATE.openconfirm

		# Start keeping keepalive timer
		self.timer = Timer(self.me,self._out_proto.negotiated.holdtime,4,0)

		# Read KEEPALIVE
		for message in self._out_proto.read_keepalive(' (OPENCONFIRM)'):
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
		for message in self._out_proto.new_keepalive(' (ESTABLISHED)'):
			yield True

		# the generator was interrupted
		if ord(message.TYPE) == Message.Type.NOP:
			raise Interrupted()

		self._out_state = STATE.established



	def _connected (self):
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

		first_loop = True

		new_routes = None
		counter = Counter(self.logger,self.me)

		while self._running:
			for message in self.proto.read_message():
				# Received update
				if message.TYPE == Update.TYPE:
					counter.increment(len(message.routes))

				self.timer.tick(message)

				# SEND KEEPALIVES
				if self.timer.keepalive():
					for message in self.proto.new_keepalive():
						yield True

					# the generator was interrupted
					if ord(message.TYPE) == Message.Type.NOP:
						raise Interrupted()

				# Give information on the number of routes seen
				counter.display()

				# Need to send update
				if self._have_routes and not new_routes:
					self._have_routes = False
					new_routes = self.proto.new_update()

				if new_routes:
					try:
						new_routes.next()
					except StopIteration:
						new_routes = None

						if first_loop:
							first_loop = False
							# Send EOR to let our peer know he can perform a RIB update
							if self.proto.negotiated.families:
								for eor in self.proto.new_eors():
									if not self._running:
										yield False
										return
									yield True
							else:
								# If we are not sending an EOR, send a keepalive as soon as when finished
								# So the other routers knows that we have no (more) routes to send ...
								# (is that behaviour documented somewhere ??)
								for eor in self.proto.new_keepalive('KEEPALIVE (EOR)'):
									if not self._running:
										yield False
										return
									yield True

							# the generator was interrupted
							if ord(eor.TYPE) == Message.Type.NOP:
								raise Interrupted()

				# Go to other Peers
				yield True if new_routes or message.TYPE != NOP.TYPE else None

				# read_message will loop until new message arrives with NOP
				if not self._running:
					break

		# If graceful restart, silent shutdown
		if self.neighbor.graceful_restart and self.proto.open_sent.capabilities.announced(CapabilityID.GRACEFUL_RESTART):
			self.logger.error('Closing the self.proto without notification','network')
			self.proto.close('graceful restarted negotiated, closing without sending any notification')
			return

		# notify our peer of the shutdown
		if self._teardown:
			code, self._teardown = self._teardown, None
			raise Notify(6,code)
		raise Notify(6,3)

	def _run (self,direction):
		"yield True if we want the reactor to give us back the hand with the same peer loop, None if we do not have any more work to do"

		try:
			if direction == 'in':
				for event in self._accept():
					yield event
				self.proto = self._in_proto
			elif direction == 'out':
				if self.neighbor.passive:
					raise StopIteration('this ends trying to connect')
				else:
					for event in self._connect():
						yield event
				self.proto = self._out_proto
			else:
				raise RuntimeError('The programmer done a mistake, please report this issue')

			# if False, it mean the session initiation failed
			if not event:
				return

			for event in self._connected():
				yield event

		# CONNECTION FAILURE
		except NetworkError, e:
			self._in_state = STATE.idle
			self._out_state = STATE.idle
			self._in_loop = None
			self._out_loop = None
			self._accepted = False

			# UPDATING TIMERS FOR BACK-OFF as we most likely failed to connect
			self._more_skip()

			if self._in_proto: self._in_proto.close()
			self._in_proto = None

			if self._out_proto: self._out_proto.close()
			self._out_proto = None

			self.logger.network('can not write to the peer, reason : %s' % str(e))
			if self._out_proto:
				self._out_proto.close('could not connect to the peer')

			# we tried to connect once, it failed, we stop
			if self.once:
				self.logger.network('only one attempt to connect is allowed, stoping the peer')
				self.stop()
			return

		# NOTIFY THE PEER OF AN ERROR
		except Notify, n:
			self._in_state = STATE.idle
			self._out_state = STATE.idle
			self._in_loop = None
			self._out_loop = None
			self._accepted = False

			if self._out_proto:
				try:
					self._out_proto.new_notification(n)
				except (NetworkError,ProcessError):
					self.logger.error(self.me('NOTIFICATION NOT SENT','network'))
					pass
				self._out_proto.close('notification sent (%d,%d) [%s] %s' % (n.code,n.subcode,str(n),n.data))
			self._out_proto = None

			if self._in_proto:
				try:
					self._in_proto.new_notification(n)
				except (NetworkError,ProcessError):
					self.logger.error(self.me('NOTIFICATION NOT SENT','network'))
					pass
				self._in_proto.close('notification sent (%d,%d) [%s] %s' % (n.code,n.subcode,str(n),n.data))
			self._in_proto = None

			return

		# THE PEER NOTIFIED US OF AN ERROR
		except Notification, n:
			self._in_state = STATE.idle
			self._out_state = STATE.idle
			self._in_loop = None
			self._out_loop = None
			self._accepted = False

			self.logger.error(self.me('Received Notification (%d,%d) %s' % (n.code,n.subcode,str(n))),'reactor')

			if self._out_proto:
				self._out_proto.close('notification received (%d,%d) %s' % (n.code,n.subcode,str(n)))
			self._out_proto = None

			if self._in_proto:
				self._in_proto.close('notification received (%d,%d) %s' % (n.code,n.subcode,str(n)))
			self._in_proto = None

			return

		# RECEIVED a Message TYPE we did not expect
		except Message, m:
			self._in_state = STATE.idle
			self._out_state = STATE.idle
			self._in_loop = None
			self._out_loop = None
			self._accepted = False

			self.logger.error(self.me('Received unexpected message %s' % m.name(),'network'))

			if self._out_proto:
				self._out_proto.close('unexpected message received')
			self._out_proto = None

			if self._in_proto:
				self._in_proto.close('unexpected message received')
			self._in_proto = None

			return

		# PROBLEM WRITING TO OUR FORKED PROCESSES
		except ProcessError, e:
			self._in_state = STATE.idle
			self._out_state = STATE.idle
			self._in_loop = None
			self._out_loop = None
			self._accepted = False

			self.logger.error(self.me(str(e)),'reactor')

			if self._out_proto:
				self._out_proto.close('failure %s' % str(e))
			self._out_proto = None

			if self._in_proto:
				self._in_proto.close('failure %s' % str(e))
			self._in_proto = None

			return

		# MOST LIKELY ^C DURING A LOOP
		except Interrupted, e:
			self._in_state = STATE.idle
			self._out_state = STATE.idle
			self._in_loop = None
			self._out_loop = None
			self._accepted = False

			self.logger.error(self.me(str(e)),'reactor')

			if self._out_proto:
				self._out_proto.close('interruped %s' % str(e))
			self._out_proto = None

			if self._in_proto:
				self._in_proto.close('interruped %s' % str(e))
			self._in_proto = None

			return

		# UNHANDLED PROBLEMS
		except Exception, e:
			self._in_state = STATE.idle
			self._out_state = STATE.idle
			self._in_loop = None
			self._out_loop = None
			self._accepted = False

			self.logger.error(self.me('UNHANDLED EXCEPTION'),'reactor')

			self.logger.error(self.me(str(e)),'reactor')

			if self._out_proto:
				self._out_proto.close('unhandled problem, please report to developers %s' % str(e))
			self._out_proto = None

			if self._in_proto:
				self._in_proto.close('unhandled problem, please report to developers %s' % str(e))
			self._in_proto = None

			try:
				traceback.print_exc(file=sys.stderr)
			except:
				pass

			return
