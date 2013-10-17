# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import time
#import traceback

from exabgp.bgp.timer import Timer
from exabgp.bgp.message import Message
from exabgp.bgp.message.open.capability.id import CapabilityID,REFRESH
from exabgp.bgp.message.nop import NOP
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.notification import Notification, Notify
from exabgp.reactor.protocol import Protocol
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.api.processes import ProcessError

from exabgp.rib.change import Change

from exabgp.configuration.environment import environment
from exabgp.logger import Logger,FakeLogger,LazyFormat

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

ACTION = Enumeration (
	'close',
	'later',
	'immediate',
	)

SEND = Enumeration (
	'done',
	'normal',
	'refresh',
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
			self.bind = True if environment.settings().tcp.bind else False
		except RuntimeError:
			self.logger = FakeLogger()
			self.once = True

		self.reactor = reactor
		self.neighbor = neighbor
		# The next restart neighbor definition
		self._neighbor = None

		# The peer should restart after a stop
		self._restart = True
		# The peer was restarted (to know what kind of open to send for graceful restart)
		self._restarted = FORCE_GRACEFUL
		self._reset_skip()

		# We want to send all the known routes
		self._resend_routes = SEND.done
		# We have new routes for the peers
		self._have_routes = True

		# We have been asked to teardown the session with this code
		self._teardown = None

		self._ = {'in':{},'out':{}}

		self._['in']['state'] = STATE.idle
		self._['out']['state'] = STATE.idle

		# value to reset 'generator' to
		self._['in']['enabled'] = False
		self._['out']['enabled'] = None if not self.neighbor.passive else False

		# the networking code
		self._['out']['proto'] = None
		self._['in']['proto'] = None

		# the networking code
		self._['out']['code'] = self._connect
		self._['in']['code'] = self._accept

		# the generator used by the main code
		# * False, the generator for this direction is down
		# * Generator, the code to run to connect or accept the connection
		# * None, the generator must be re-created
		self._['in']['generator'] = self._['in']['enabled']
		self._['out']['generator'] = self._['out']['enabled']

	def _reset (self,direction,message='',error=''):
		self._[direction]['state'] = STATE.idle

		if self._restart:
			if self._[direction]['proto']:
				self._[direction]['proto'].close('%s loop reset %s %s' % (direction,message,str(error)))
			self._[direction]['proto'] = None
			self._[direction]['generator'] = self._[direction]['enabled']
			self._teardown = None
			self._more_skip(direction)
			self.neighbor.rib.reset()

			# If we are restarting, and the neighbor definition is different, update the neighbor
			if self._neighbor:
				self.neighbor = self._neighbor
				self._neighbor = None
		else:
			self._[direction]['generator'] = False
			self._[direction]['proto'] = None

	def _stop (self,direction,message):
		self._[direction]['generator'] = False
		self._[direction]['proto'].close('%s loop stop %s' % (direction,message))
		self._[direction]['proto'] = None

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
		self._teardown = 3
		self._restart = False
		self._restarted = False
		self._reset_skip()

	def resend (self):
		self._resend_routes = SEND.normal
		self._reset_skip()

	def send_new (self,changes=None,update=None):
		if changes:
			self.neighbor.rib.outgoing.update(changes)
		self._have_routes = self.neighbor.flush if update is None else update

	def restart (self,restart_neighbor=None):
		# we want to tear down the session and re-establish it
		self._teardown = 3
		self._restart = True
		self._restarted = True
		self._resend_routes = SEND.normal
		self._neighbor = restart_neighbor
		self._reset_skip()

	def teardown (self,code,restart=True):
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
		# if the other side fails, we go back to idle
		if self._['in']['proto'] not in (True,False,None):
			self.logger.network('we already have a peer at this address')
			return False

		self._['in']['proto'] = Protocol(self).accept(connection)
		# Let's make sure we do some work with this connection
		self._['in']['generator'] = None
		self._['in']['state'] = STATE.connect
		return True

	def _accept (self):
		# we can do this as Protocol is a mutable object
		proto = self._['in']['proto']

		# send OPEN
		for message in proto.new_open(self._restarted):
			if ord(message.TYPE) == Message.Type.NOP:
				yield ACTION.immediate

		proto.negotiated.sent(message)

		self._['in']['state'] = STATE.opensent

		# Read OPEN
		wait = environment.settings().bgp.openwait
		opentimer = Timer(self._log('in'),wait,1,1,'waited for open too long, we do not like stuck in active')
		# Only yield if we have not the open, otherwise the reactor can run the other connection
		# which would be bad as we need to do the collission check without going to the other peer
		for message in proto.read_open(self.neighbor.peer_address.ip):
			opentimer.tick(message)
			if ord(message.TYPE) == Message.Type.NOP:
				yield ACTION.later

		self._['in']['state'] = STATE.openconfirm
		proto.negotiated.received(message)
		proto.validate_open()

		if self._['out']['state'] == STATE.openconfirm:
			self.logger.network('incoming connection finds the outgoing connection is in openconfirm')
			local_id = self.neighbor.router_id.packed
			remote_id = proto.negotiated.received_open.router_id.packed

			if local_id < remote_id:
				self.logger.network('closing the outgoing connection')
				self._stop('out','collision local id < remote id')
				yield ACTION.later
			else:
				self.logger.network('aborting the incoming connection')
				stop = Interrupted()
				stop.direction = 'in'
				raise stop

		# Send KEEPALIVE
		for message in self._['in']['proto'].new_keepalive('OPENCONFIRM'):
			yield ACTION.immediate

		# Start keeping keepalive timer
		self.timer = Timer(self._log('in'),proto.negotiated.holdtime,4,0)
		# Read KEEPALIVE
		for message in proto.read_keepalive('ESTABLISHED'):
			self.timer.tick(message)
			yield ACTION.later

		self._['in']['state'] = STATE.established
		# let the caller know that we were sucesfull
		yield ACTION.immediate


	def _connect (self):
		# try to establish the outgoing connection

		proto = Protocol(self)
		generator = proto.connect()

		connected = False
		try:
			while not connected:
				connected = generator.next()
				# we want to come back as soon as possible
				yield ACTION.immediate
		except StopIteration:
			# Connection failed
			if not connected:
				proto.close('connection to peer failed')
			# A connection arrived before we could establish !
			if not connected or self._['in']['proto']:
				stop = Interrupted()
				stop.direction = 'out'
				raise stop

		self._['out']['state'] = STATE.connect
		self._['out']['proto'] = proto

		# send OPEN
		# Only yield if we have not the open, otherwise the reactor can run the other connection
		# which would be bad as we need to set the state without going to the other peer
		for message in proto.new_open(self._restarted):
			if ord(message.TYPE) == Message.Type.NOP:
				yield ACTION.immediate

		proto.negotiated.sent(message)

		self._['out']['state'] = STATE.opensent

		# Read OPEN
		wait = environment.settings().bgp.openwait
		opentimer = Timer(self._log('out'),wait,1,1,'waited for open too long, we do not like stuck in active')
		for message in self._['out']['proto'].read_open(self.neighbor.peer_address.ip):
			opentimer.tick(message)
			# XXX: FIXME: change the whole code to use the ord and not the chr version
			# Only yield if we have not the open, otherwise the reactor can run the other connection
			# which would be bad as we need to do the collission check
			if ord(message.TYPE) == Message.Type.NOP:
				yield ACTION.later

		self._['out']['state'] = STATE.openconfirm
		proto.negotiated.received(message)
		proto.validate_open()

		if self._['in']['state'] == STATE.openconfirm:
			self.logger.network('outgoing connection finds the incoming connection is in openconfirm')
			local_id = self.neighbor.router_id.packed
			remote_id = proto.negotiated.received_open.router_id.packed

			if local_id < remote_id:
				self.logger.network('aborting the outgoing connection')
				stop = Interrupted()
				stop.direction = 'out'
				raise stop
			else:
				self.logger.network('closing the incoming connection')
				self._stop('in','collision local id < remote id')
				yield ACTION.later

		# Send KEEPALIVE
		for message in proto.new_keepalive('OPENCONFIRM'):
			yield ACTION.immediate

		# Start keeping keepalive timer
		self.timer = Timer(self._log('out'),self._['out']['proto'].negotiated.holdtime,4,0)
		# Read KEEPALIVE
		for message in self._['out']['proto'].read_keepalive('ESTABLISHED'):
			self.timer.tick(message)
			yield ACTION.immediate

		self._['out']['state'] = STATE.established
		# let the caller know that we were sucesfull
		yield ACTION.immediate

	def _main (self,direction):
		"yield True if we want to come back to it asap, None if nothing urgent, and False if stopped"

		if self._teardown:
			raise Notify(6,3)

		proto = self._[direction]['proto']

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

		send_eor = True
		new_routes = None
		self._resend_routes = SEND.normal
		send_families = []

		# Every last asm message should be re-announced on restart
		for family in self.neighbor.asm:
			if family in self.neighbor.families():
				self.neighbor.messages.appendleft(self.neighbor.asm[family])

		counter = Counter(self.logger,self._log(direction))
		need_keepalive = False
		keepalive = None
		operational = None
		refresh = None

		while not self._teardown:
			for message in proto.read_message():
				# Update timer
				self.timer.tick(message)

				# Give information on the number of routes seen
				counter.display()

				# Received update
				if message.TYPE == Update.TYPE:
					counter.increment(len(message.nlris))

					for nlri in message.nlris:
						self.neighbor.rib.incoming.insert_received(Change(nlri,message.attributes))
						self.logger.routes(LazyFormat(self.me(''),str,nlri))
				elif message.TYPE == RouteRefresh.TYPE:
					if message.reserved == RouteRefresh.request:
						self._resend_routes = SEND.refresh
						send_families.append((message.afi,message.safi))

				# SEND KEEPALIVES
				need_keepalive |= self.timer.keepalive()

				if need_keepalive and not keepalive:
					keepalive = proto.new_keepalive()
					need_keepalive = False

				if keepalive:
					try:
						keepalive.next()
					except StopIteration:
						keepalive = None

				# SEND OPERATIONAL
				if self.neighbor.operational:
					if not operational:
						new_operational = self.neighbor.messages.popleft() if self.neighbor.messages else None
						if new_operational:
							operational = proto.new_operational(new_operational,proto.negotiated)

					if operational:
						try:
							operational.next()
						except StopIteration:
							operational = None

				# SEND REFRESH
				if self.neighbor.route_refresh:
					if not refresh:
						new_refresh = self.neighbor.refresh.popleft() if self.neighbor.refresh else None
						if new_refresh:
							enhanced_negotiated = True if proto.negotiated.refresh == REFRESH.enhanced else False
							refresh = proto.new_refresh(new_refresh,enhanced_negotiated)

					if refresh:
						try:
							refresh.next()
						except StopIteration:
							refresh = None

				# Take the routes already sent to that peer and resend them
				if self._resend_routes != SEND.done:
					enhanced_refresh = True if self._resend_routes == SEND.refresh and proto.negotiated.refresh == REFRESH.enhanced else False
					self._resend_routes = SEND.done
					self.neighbor.rib.outgoing.resend(send_families,enhanced_refresh)
					self._have_routes = True
					send_families = []

				# Need to send update
				if self._have_routes and not new_routes:
					self._have_routes = False
					# XXX: in proto really. hum to think about ?
					new_routes = proto.new_update()

				if new_routes:
					try:
						count = 20
						while count:
							# This can raise a NetworkError
							new_routes.next()
							count -= 1
					except StopIteration:
						new_routes = None

				elif send_eor:
					send_eor = False
					for eor in proto.new_eors():
						yield ACTION.immediate
					self.logger.message(self.me('>> EOR(s)'))

				# Go to other Peers
				yield ACTION.immediate if new_routes or message.TYPE != NOP.TYPE or self.neighbor.messages else ACTION.later

				# read_message will loop until new message arrives with NOP
				if self._teardown:
					break

		# If graceful restart, silent shutdown
		if self.neighbor.graceful_restart and proto.negotiated.sent_open.capabilities.announced(CapabilityID.GRACEFUL_RESTART):
			self.logger.network('Closing the session without notification','error')
			proto.close('graceful restarted negotiated, closing without sending any notification')
			raise NetworkError('closing')

		# notify our peer of the shutdown
		raise Notify(6,self._teardown)

	def _run (self,direction):
		"yield True if we want the reactor to give us back the hand with the same peer loop, None if we do not have any more work to do"
		try:
			for action in self._[direction]['code']():
				yield action

			for action in self._main(direction):
				yield action

		# CONNECTION FAILURE
		except NetworkError, e:
			self._reset(direction,'closing connection')

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
						generator = self._[direction]['proto'].new_notification(n)
						try:
							maximum = 20
							while maximum:
								generator.next()
								maximum -= 1
								yield ACTION.immediate if maximum > 10 else ACTION.later
						except StopIteration:
							pass
					except (NetworkError,ProcessError):
						self.logger.network(self._output(direction,'NOTIFICATION NOT SENT'),'error')
						pass
					self._reset(direction,'notification sent (%d,%d)' % (n.code,n.subcode),n)
				else:
					self._reset(direction)
			return

		# THE PEER NOTIFIED US OF AN ERROR
		except Notification, n:
			self._reset(direction,'notification received (%d,%d)' % (n.code,n.subcode),n)
			return

		# RECEIVED a Message TYPE we did not expect
		except Message, m:
			self._reset(direction,'unexpected message received',m)
			return

		# PROBLEM WRITING TO OUR FORKED PROCESSES
		except ProcessError, e:
			self._reset(direction,'process problem',e)
			return

		# ....
		except Interrupted, i:
			self._reset(i.direction)
			return

		# UNHANDLED PROBLEMS
		except Exception, e:
			# Those messages can not be filtered in purpose
			self.logger.error(self.me('UNHANDLED PROBLEM, please report'),'reactor')
			self.logger.error(self.me(str(type(e))),'reactor')
			self.logger.error(self.me(str(e)),'reactor')
			self.logger.error(trace())

			self._reset(direction)
			return
	# loop

	def run (self):
		if self.reactor.processes.broken(self.neighbor.peer_address):
			# XXX: we should perhaps try to restart the process ??
			self.logger.processes('ExaBGP lost the helper process for this peer - stopping','error')
			self.stop()
			return True

		back = ACTION.later if self._restart else ACTION.close

		for direction in ['in','out']:
			opposite = 'out' if direction == 'in' else 'in'

			generator = self._[direction]['generator']
			if generator:
				try:
					# This generator only stops when it raises
					r = generator.next()

					if r is ACTION.immediate: status = 'immediate callback'
					elif r is ACTION.later:   status = 'when possible'
					elif r is ACTION.close:   status = 'stop'
					else: status = 'buggy'
					self.logger.network('%s loop %18s, state is %s' % (direction,status,self._[direction]['state']),'debug')

					if r == ACTION.immediate:
						back = ACTION.immediate
					elif r == ACTION.later:
						back == ACTION.later if back != ACTION.immediate else ACTION.immediate
				except StopIteration:
					# Trying to run a closed loop, no point continuing
					self._[direction]['generator'] = self._[direction]['enabled']

			elif generator is None:
				if self._[opposite]['state'] in [STATE.openconfirm,STATE.established]:
					self.logger.network('%s loop, stopping, other one is established' % direction,'debug')
					self._[direction]['generator'] = False
					continue
				if direction == 'out' and self._skip_time > time.time():
					self.logger.network('%s loop, skipping, not time yet' % direction,'debug')
					back = ACTION.later
					continue
				if self._restart:
					self.logger.network('%s loop, intialising' % direction,'debug')
					self._[direction]['generator'] = self._run(direction)
					back = ACTION.immediate

		return back
