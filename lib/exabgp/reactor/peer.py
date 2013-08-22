# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import sys
import time
#import traceback

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
from exabgp.util.trace import trace

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
class CollisionIn (Exception): pass
class CollisionOut (Exception): pass

# Present a File like interface to socket.socket

class Peer (object):
	def __init__ (self,neighbor,reactor):
		try:
			self.logger = Logger()
			# We only to try to connect via TCP once
			self.once = environment.settings().tcp.once
			self.bind = True if environment.settings().tcp.bind else False
		except RuntimeError:
			self.logger = FakeLogger()
			self.once = True

		self.reactor = reactor
		self.neighbor = neighbor
		# The next restart neighbor definition
		self._neighbor = None

		# The peer message should be processed
		self._running = True
		# The peer should restart after a stop
		self._restart = True
		# The peer was restarted (to know what kind of open to send for graceful restart)
		self._restarted = FORCE_GRACEFUL
		self._reset_skip()

		# We want to send all the known routes
		self._resend_routes = True
		# We have new routes for the peers
		self._have_routes = True

		# We have been asked to teardown the session with this code
		self._teardown = None

		# the protocol in use when the session is established
		self.proto = None

		# BGP state information
		self._state = STATE.idle


		self._ = {'in':{},'out':{}}

		# value to reset 'loop' to
		self._['in']['enabled'] = False
		self._['out']['enabled'] = None if not self.neighbor.passive else False

		# the networking code
		self._['out']['proto'] = None
		self._['in']['proto'] = None

		# the networking code
		self._['out']['code'] = self._connect
		self._['in']['code'] = self._accept

		self._init()

	# setup

	def _init (self):
		# the BGP session state
		self._state = STATE.idle

		# the generator used by the main code
		# * False, the generator for this direction is down
		# * Generator, the code to run to connect or accept the connection
		# * None, the generator must be re-created
		self._['in']['loop'] = self._['in']['enabled']
		self._['out']['loop'] = self._['out']['enabled']

	def _reset (self,message,error):
		if self._['out']['proto']:
			self._['out']['proto'].close('%s %s' % (message,str(error)))
		self._['out']['proto'] = None

		if self._['in']['proto']:
			self._['in']['proto'].close('%s %s' % (message,str(error)))
		self._['in']['proto'] = None

	# connection delay

	def _reset_skip (self):
		# We are currently not skipping connection attempts
		self._skip_time = time.time()
		# when we can not connect to a peer how many time (in loop) should we back-off
		self._next_skip = 0

	def _more_skip (self,direction):
		if direction != 'out':
			return
		self._skip_time = time.time() + self._next_skip
		self._next_skip = int(1+ self._next_skip*1.2)
		if self._next_skip > 60:
			self._next_skip = 60

	# logging

	def me (self,message):
		return "peer %s ASN %-7s %s" % (self.neighbor.peer_address,self.neighbor.peer_as,message)

	def _output (self,direction,message):
		return "%s %s" % (self._[direction]['proto'].connection.name(),self.me(message))

	def _log (self,direction):
		def inner (message):
			return self._output(direction,message)
		return inner

	# control

	def stop (self):
		self._running = False
		self._restart = False
		self._restarted = False
		self._reset_skip()

	def resend (self):
		self._resend_routes = True
		self._reset_skip()

	def send_new (self):
		self._have_routes = True

	def restart (self,restart_neighbor=None):
		# we want to tear down the session and re-establish it
		self._running = False
		self._restart = True
		self._restarted = True
		self._resend_routes = True
		self._neighbor = restart_neighbor
		self._reset_skip()

	def teardown (self,code,restart=True):
		self._running = False
		self._restart = restart
		self._teardown = code
		self._reset_skip()

	# sockets we must monitor

	def sockets (self):
		ios = []
		for direction in ['in','out']:
			proto = self._[direction]['proto']
			if proto and proto.connection and proto.connection.io:
				ios.append(proto.connection.io)
		return ios

	def incoming (self,connection):
		# Let's be clear BGP state machine definition is a mess !
		# By not sending the OPEN we are avoiding the brainfucked collision

		if self._state != STATE.idle:
			return False

		self._['in']['proto'] = Protocol(self).accept(connection)
		if self._['in']['loop'] not in [False, None, True]:
			self.logger.network('WARNING, show never happen protocol is a generator on accepted incoming connection !')
			self.logger.network(str(self._['in']['loop']))
			self.logger.network(str(self._state))

		# Let's make sure we do some work with this connection
		self._['in']['loop'] = None
		self._state = STATE.connect
		return True

	def _accept (self):
		"yield True if we want to come back to it asap, None if nothing urgent, and False if stopped"

		# we can do this as Protocol is a mutable object
		proto = self._['in']['proto']

		# send OPEN
		# Only yield if we have not the open, otherwise the reactor can run the other connection
		# which would be bad as we need to set the state without going to the other peer
		for message in proto.new_open(self._restarted):
			if ord(message.TYPE) == Message.Type.NOP:
				yield True

		self._state = STATE.opensent
		proto.negotiated.sent(message)

		# Send KEEPALIVE
		for message in self._['in']['proto'].new_keepalive('ESTABLISHED'):
			yield True

		# Read OPEN
		wait = environment.settings().bgp.openwait
		opentimer = Timer(self._log('in'),wait,1,1,'waited for open too long, we do not like stuck in active')
		# Only yield if we have not the open, otherwise the reactor can run the other connection
		# which would be bad as we need to do the collission check without going to the other peer
		for message in proto.read_open(self.neighbor.peer_address.ip):
			opentimer.tick(message)
			if ord(message.TYPE) == Message.Type.NOP:
				yield None

		self._state = STATE.openconfirm
		proto.negotiated.received(message)
		proto.validate_open()

		# Start keeping keepalive timer
		self.timer = Timer(self._log('in'),proto.negotiated.holdtime,4,0)
		# Read KEEPALIVE
		for message in proto.read_keepalive('OPENCONFIRM'):
			self.timer.tick(message)
			yield None

		self._state = STATE.established
		# let the caller know that we were sucesfull
		yield True


	def _connect (self):
		"yield True if we want to come back to it asap, None if nothing urgent, and False if stopped"

		# Let's be clear BGP state machine definition is a mess !
		# By not sending the OPEN we are avoiding the brainfucked collision

		# if self._state != STATE.idle:
		# 	yield False
		# 	return

		# 	local_id = self.neighbor.router_id.packed
		# 	remote_id = self.proto.negotiated.received_open.router_id.packed

		# 	if local_id < remote_id:
		# 		# close already exist
		# 		self._['out']['proto'].close('collision local id < remote id')
		# 		self._['out']['proto'] = None
		# 		yield False
		# 		return
		# 	else:
		# 		# close new connection
		# 		self._['in']['proto'].close('collision local id < remote id')
		# 		self._['in']['proto'] = None
		# 		yield False
		# 		return

		# try to establish the outgoing connection

		proto = Protocol(self)
		generator = proto.connect()

		connected = False
		try:
			while not connected:
				connected = generator.next()
				# we want to come back as soon as possible
				yield True
		except StopIteration:
			# we want to come back when we can
			if not connected:
				yield None
				return

		# Connection arrived before we could establish !
		if self._state != STATE.idle:
			yield False
			return

		self._state = STATE.connect
		self._['out']['proto'] = proto
		self._reset_skip()

		# send OPEN
		# Only yield if we have not the open, otherwise the reactor can run the other connection
		# which would be bad as we need to set the state without going to the other peer
		for message in proto.new_open(self._restarted):
			if ord(message.TYPE) == Message.Type.NOP:
				yield True

		self._state = STATE.opensent
		proto.negotiated.sent(message)

		# Send KEEPALIVE
		for message in proto.new_keepalive('ESTABLISHED'):
			yield True

		# Read OPEN
		wait = environment.settings().bgp.openwait
		opentimer = Timer(self._log('out'),wait,1,1,'waited for open too long, we do not like stuck in active')
		for message in self._['out']['proto'].read_open(self.neighbor.peer_address.ip):
			opentimer.tick(message)
			# XXX: FIXME: change the whole code to use the ord and not the chr version
			# Only yield if we have not the open, otherwise the reactor can run the other connection
			# which would be bad as we need to do the collission check
			if ord(message.TYPE) == Message.Type.NOP:
				yield None

		self._state = STATE.openconfirm
		self._['out']['proto'].negotiated.received(message)
		self._['out']['proto'].validate_open()

		# Start keeping keepalive timer
		self.timer = Timer(self._log('out'),self._['out']['proto'].negotiated.holdtime,4,0)
		# Read KEEPALIVE
		for message in self._['out']['proto'].read_keepalive('OPENCONFIRM'):
			self.timer.tick(message)
			yield None

		self._state = STATE.established
		# let the caller know that we were sucesfull
		yield True

	def _main (self,direction):
		"yield True if we want to come back to it asap, None if nothing urgent, and False if stopped"

		self.proto = self._[direction]['proto']

		# Announce to the process BGP is up
		self.logger.network('Connected to peer %s (%s)' % (self.neighbor.name(),direction))
		if self.neighbor.api.neighbor_changes:
			try:
				self.reactor.processes.up(self.neighbor.peer_address)
			except ProcessError:
				# Can not find any better error code than 6,0 !
				# XXX: We can not restart the program so this will come back again and again - FIX
				# XXX: In the main loop we do exit on this kind of error
				raise Notify(6,0,'ExaBGP Internal error, sorry.')

		send_eor = False
		new_routes = None

		counter = Counter(self.logger,self._log(direction))

		self._resend_routes = True

		while self._running:
			for message in self.proto.read_message():
				# Received update
				if message.TYPE == Update.TYPE:
					counter.increment(len(message.nlris))

				self.timer.tick(message)

				# SEND KEEPALIVES
				if self.timer.keepalive():
					for message in self.proto.new_keepalive():
						yield True

				# Give information on the number of routes seen
				counter.display()

				# Take the routes already sent to that peer and resend them
				if self._resend_routes:
					self._resend_routes = False
					self.neighbor.rib.outgoing.resend_known()
					self._have_routes = True

				# Need to send update
				if self._have_routes and not new_routes:
					self._have_routes = False
					# XXX: in proto really. hum to think about ?
					new_routes = self.proto.new_update()

				if new_routes:
					try:
						count = 20
						while count:
							# This can raise a NetworkError
							new_routes.next()
							count -= 1
					except StopIteration:
						new_routes = None
						send_eor = True

				elif send_eor:
					send_eor = False
					for eor in self.proto.new_eors():
						if not self._running:
							yield False
							return
						yield True
					self.logger.message(self.me('>> EOR(s)'))

				# Go to other Peers
				yield True if new_routes or message.TYPE != NOP.TYPE else None

				# read_message will loop until new message arrives with NOP
				if not self._running:
					break

		# If graceful restart, silent shutdown
		if self.neighbor.graceful_restart and self.proto.negotiated.sent_open.capabilities.announced(CapabilityID.GRACEFUL_RESTART):
			self.logger.network('Closing the session without notification','error')
			self.proto.close('graceful restarted negotiated, closing without sending any notification')
			raise NetworkError('closing')

		# notify our peer of the shutdown
		if self._teardown:
			code, self._teardown = self._teardown, None
			raise Notify(6,code)
		raise Notify(6,3)

	def _run (self,direction):
		"yield True if we want the reactor to give us back the hand with the same peer loop, None if we do not have any more work to do"

		try:
			for event in self._[direction]['code']():
				yield event

			# False it means that we finished the reactor
			# True means that we finished nicely
			# None means that we were interrupted ??
			if event is not True:
				self._more_skip(direction)
				raise Interrupted('can not %s connection' % 'establish' if direction == 'out' else 'accept')

			for event in self._main(direction):
				yield event

		# CONNECTION FAILURE
		except NetworkError, e:
			self._init()
			self._reset('closing connection','')

			# UPDATING TIMERS FOR BACK-OFF as we most likely failed to connect
			self._more_skip(direction)

			# we tried to connect once, it failed, we stop
			if self.once:
				self.logger.network('only one attempt to connect is allowed, stoping the peer')
				self.stop()
			return

		# NOTIFY THE PEER OF AN ERROR
		except Notify, n:
			for direction in ['in','out']:
				if self._[direction]['proto']:
					try:
						self._[direction]['proto'].new_notification(n)
					except (NetworkError,ProcessError):
						self.logger.network(self._output(direction,'NOTIFICATION NOT SENT','error'))
						pass
			self._init()
			self._reset('notification sent (%d,%d)' % (n.code,n.subcode),n)
			return

		# THE PEER NOTIFIED US OF AN ERROR
		except Notification, n:
			self.logger.reactor(self.me('received Notification (%d,%d) %s' % (n.code,n.subcode,str(n))),'warning')
			self._init()
			self._reset('notification received (%d,%d)' % (n.code,n.subcode),n)
			return

		# RECEIVED a Message TYPE we did not expect
		except Message, m:
			self.logger.network(self.me('received unexpected message %s' % m.name(),'error'))
			self._init()
			self._reset('unexpected message received',m)
			return

		# PROBLEM WRITING TO OUR FORKED PROCESSES
		except ProcessError, e:
			self.logger.reactor(self.me(str(e)),'error')
			self._init()
			self._reset('process problem',e)
			return

		# ....
		except Interrupted, e:
			self.logger.reactor(self.me(str(e)),'info')
			self._init()
			self._reset('',e)
			return

		# UNHANDLED PROBLEMS
		except Exception, e:
			# Those messages can not be filtered in purpose
			self.logger.error(self.me('UNHANDLED PROBLEM, please report'),'reactor')
			self.logger.error(self.me(str(type(e))),'reactor')
			self.logger.error(self.me(str(e)),'reactor')
			self.logger.error(trace())

			self._init()
			self._reset('',e)
			return

	# loop

	def run (self):
		if self.reactor.processes.broken(self.neighbor.peer_address):
			# XXX: we should perhaps try to restart the process ??
			self.logger.process('ExaBGP lost the helper process for this peer - stopping','error')
			self._running = False

		elif self._running:
			back = None

			for direction in ['in','out']:
				loop = self._[direction]['loop']

				if loop:
					try:
						r = loop.next()
						if r is True:
							back = True
						elif r is False:
							# two False, exiting
							if back is False:
								return False
							back = False
					except StopIteration:
						# should we restart when finished
						# the other side is established : no
						# incoming connection: no,  as it is event driven by new socket
						# outgoing connection: yes, if the peer close we re-init

						if self._state == STATE.established:
							self._[direction]['loop'] = False
						else:
							self._[direction]['loop'] = self._[direction]['enabled']

				elif loop is None:
					if self._state == STATE.established:
						loop = False
						continue
					if direction == 'out' and self._skip_time > time.time():
						continue
					self._[direction]['loop'] = self._run(direction)

					back = True

			return back

		# not running
		elif self._restart:
			# If we are restarting, and the neighbor definition is different, update the neighbor
			if self._neighbor:
				self.neighbor = self._neighbor
				self._neighbor = None

			self._running = True
			return True

		# not running, and not restarting
		else:
			return False
