# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import time
# import traceback

from exabgp.bgp.timer import ReceiveTimer
from exabgp.bgp.timer import SendTimer
from exabgp.bgp.message import Message
from exabgp.bgp.message import STATE
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability import REFRESH
from exabgp.bgp.message.nop import NOP
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.notification import Notification
from exabgp.bgp.message.notification import Notify
from exabgp.reactor.protocol import Protocol
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.api.processes import ProcessError

from exabgp.rib.change import Change

from exabgp.configuration.environment import environment
from exabgp.logger import Logger
from exabgp.logger import FakeLogger
from exabgp.logger import LazyFormat

from exabgp.util.trace import trace

from exabgp.util.panic import no_panic
from exabgp.util.panic import footer


class ACTION (object):
	CLOSE = 0x01
	LATER = 0x02
	NOW   = 0x03


class SEND (object):
	DONE    = 0x01
	NORMAL  = 0x02
	REFRESH = 0x04


# As we can not know if this is our first start or not, this flag is used to
# always make the program act like it was recovering from a failure
# If set to FALSE, no EOR and OPEN Flags set for Restart will be set in the
# OPEN Graceful Restart Capability
FORCE_GRACEFUL = True


class Interrupted (Exception):
	pass


# =========================================================================== KA
#

class KA (object):
	def __init__ (self, log, proto):
		self._generator = self._keepalive(proto)
		self.send_timer = SendTimer(log,proto.negotiated.holdtime)

	def _keepalive (self, proto):
		need_ka   = False
		generator = None

		while True:
			# SEND KEEPALIVES
			need_ka |= self.send_timer.need_ka()

			if need_ka:
				if not generator:
					generator = proto.new_keepalive()
					need_ka = False

			if not generator:
				yield False
				continue

			try:
				# try to close the generator and raise a StopIteration in one call
				generator.next()
				generator.next()
				# still running
				yield True
			except NetworkError:
				raise Notify(4,0,'problem with network while trying to send keepalive')
			except StopIteration:
				generator = None
				yield False

	def __call__ (self):
		#  True  if we need or are trying
		#  False if we do not need to send one
		try:
			return self._generator.next()
		except StopIteration:
			raise Notify(4,0,'could not send keepalive')


# Present a File like interface to socket.socket

class Peer (object):
	def __init__ (self, neighbor, reactor):
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

		# We want to remove routes which are not in the configuration anymote afte a signal to reload
		self._reconfigure = True
		# We want to send all the known routes
		self._resend_routes = SEND.DONE
		# We have new routes for the peers
		self._have_routes = True

		# We have been asked to teardown the session with this code
		self._teardown = None

		self._ = {'in':{},'out':{}}

		self._['in']['state'] = STATE.IDLE
		self._['out']['state'] = STATE.IDLE

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

	def _reset (self, direction, message='',error=''):
		self._[direction]['state'] = STATE.IDLE

		if self._restart:
			if self._[direction]['proto']:
				self._[direction]['proto'].close('%s loop, peer reset, message [%s] error[%s]' % (direction,message,str(error)))
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

	def _stop (self, direction, message):
		self._[direction]['generator'] = False
		self._[direction]['proto'].close('%s loop, stop, message [%s]' % (direction,message))
		self._[direction]['proto'] = None

	# connection delay

	def _reset_skip (self):
		# We are currently not skipping connection attempts
		self._skip_time = time.time()
		# when we can not connect to a peer how many time (in loop) should we back-off
		self._next_skip = 0

	def _more_skip (self, direction):
		if direction != 'out':
			return
		self._skip_time = time.time() + self._next_skip
		self._next_skip = int(1 + self._next_skip * 1.2)
		if self._next_skip > 60:
			self._next_skip = 60

	# logging

	def me (self, message):
		return "peer %s ASN %-7s %s" % (self.neighbor.peer_address,self.neighbor.peer_as,message)

	# control

	def stop (self):
		self._teardown = 3
		self._restart = False
		self._restarted = False
		self._reset_skip()
		self.neighbor.rib.uncache()

	def resend (self):
		self._resend_routes = SEND.NORMAL
		self._reset_skip()

	def send_new (self, changes=None,update=None):
		if changes:
			self.neighbor.rib.outgoing.replace(changes)
		self._have_routes = self.neighbor.flush if update is None else update

	def reestablish (self, restart_neighbor=None):
		# we want to tear down the session and re-establish it
		self._teardown = 3
		self._restart = True
		self._restarted = True
		self._resend_routes = SEND.NORMAL
		self._neighbor = restart_neighbor
		self._reset_skip()

	def reconfigure (self, restart_neighbor=None):
		# we want to update the route which were in the configuration file
		self._reconfigure = True
		self._neighbor = restart_neighbor
		self._resend_routes = SEND.NORMAL
		self._neighbor = restart_neighbor

	def teardown (self, code, restart=True):
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

	def incoming (self, connection):
		# if the other side fails, we go back to idle
		if self._['in']['proto'] not in (True,False,None):
			self.logger.network('we already have a peer at this address')
			return False

		self._['in']['proto'] = Protocol(self).accept(connection)
		# Let's make sure we do some work with this connection
		self._['in']['generator'] = None
		self._['in']['state'] = STATE.CONNECT
		return True

	def established (self):
		return self._['in']['state'] == STATE.ESTABLISHED or self._['out']['state'] == STATE.ESTABLISHED

	def detailed_link_status (self):
		state_tbl = {
			STATE.IDLE : "Idle",
			STATE.ACTIVE : "Active",
			STATE.CONNECT : "Connect",
			STATE.OPENSENT : "OpenSent",
			STATE.OPENCONFIRM : "OpenConfirm",
			STATE.ESTABLISHED : "Established" }
		return state_tbl[max(self._["in"]["state"], self._["out"]["state"])]

	def negotiated_families(self):
		if self._['out']['proto']:
			families = ["%s/%s" % (x[0], x[1]) for x in self._['out']['proto'].negotiated.families]
		else:
			families = ["%s/%s" % (x[0], x[1]) for x in self.neighbor.families()]

		if len(families) > 1:
			return "[ %s ]" % " ".join(families)
		elif len(families) == 1:
			return families[0]

		return ''

	def _accept (self):
		# we can do this as Protocol is a mutable object
		proto = self._['in']['proto']

		# send OPEN
		message = Message.CODE.NOP
		for message in proto.new_open(self._restarted):
			if ord(message.TYPE) == Message.CODE.NOP:
				yield ACTION.NOW

		proto.negotiated.sent(message)

		self._['in']['state'] = STATE.OPENSENT

		# Read OPEN
		wait = environment.settings().bgp.openwait
		opentimer = ReceiveTimer(self.me,wait,1,1,'waited for open too long, we do not like stuck in active')
		# Only yield if we have not the open, otherwise the reactor can run the other connection
		# which would be bad as we need to do the collission check without going to the other peer
		for message in proto.read_open(self.neighbor.peer_address.ip):
			opentimer.check_ka(message)
			if ord(message.TYPE) == Message.CODE.NOP:
				yield ACTION.LATER

		self._['in']['state'] = STATE.OPENCONFIRM
		proto.negotiated.received(message)
		proto.validate_open()

		if self._['out']['state'] == STATE.OPENCONFIRM:
			self.logger.network('incoming connection finds the outgoing connection is in openconfirm')
			local_id = self.neighbor.router_id.packed
			remote_id = proto.negotiated.received_open.router_id.packed

			if local_id < remote_id:
				self.logger.network('closing the outgoing connection')
				self._stop('out','collision local id < remote id')
				yield ACTION.LATER
			else:
				self.logger.network('aborting the incoming connection')
				stop = Interrupted()
				stop.direction = 'in'
				raise stop

		# Send KEEPALIVE
		for message in self._['in']['proto'].new_keepalive('OPENCONFIRM'):
			yield ACTION.NOW

		# Start keeping keepalive timer
		self.recv_timer = ReceiveTimer(self.me,proto.negotiated.holdtime,4,0)
		# Read KEEPALIVE
		for message in proto.read_keepalive():
			self.recv_timer.check_ka(message)
			yield ACTION.NOW

		self._['in']['state'] = STATE.ESTABLISHED
		# let the caller know that we were sucesfull
		yield ACTION.NOW

	def _connect (self):
		# try to establish the outgoing connection

		proto = Protocol(self)
		generator = proto.connect()

		connected = False
		try:
			while not connected:
				if self._teardown:
					raise StopIteration()
				connected = generator.next()
				# we want to come back as soon as possible
				yield ACTION.LATER
		except StopIteration:
			# Connection failed
			if not connected:
				proto.close('connection to peer failed',self._['in']['state'] != STATE.ESTABLISHED)
			# A connection arrived before we could establish !
			if not connected or self._['in']['proto']:
				stop = Interrupted()
				stop.direction = 'out'
				yield ACTION.NOW
				raise stop

		self._['out']['state'] = STATE.CONNECT
		self._['out']['proto'] = proto

		# send OPEN
		# Only yield if we have not the open, otherwise the reactor can run the other connection
		# which would be bad as we need to set the state without going to the other peer
		message = Message.CODE.NOP
		for message in proto.new_open(self._restarted):
			if ord(message.TYPE) == Message.CODE.NOP:
				yield ACTION.NOW

		proto.negotiated.sent(message)

		self._['out']['state'] = STATE.OPENSENT

		# Read OPEN
		wait = environment.settings().bgp.openwait
		opentimer = ReceiveTimer(self.me,wait,1,1,'waited for open too long, we do not like stuck in active')
		for message in self._['out']['proto'].read_open(self.neighbor.peer_address.ip):
			opentimer.check_ka(message)
			# XXX: FIXME: change the whole code to use the ord and not the chr version
			# Only yield if we have not the open, otherwise the reactor can run the other connection
			# which would be bad as we need to do the collission check
			if ord(message.TYPE) == Message.CODE.NOP:
				yield ACTION.LATER

		self._['out']['state'] = STATE.OPENCONFIRM
		proto.negotiated.received(message)
		proto.validate_open()

		if self._['in']['state'] == STATE.OPENCONFIRM:
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
				yield ACTION.LATER

		# Send KEEPALIVE
		for message in proto.new_keepalive('OPENCONFIRM'):
			yield ACTION.NOW

		# Start keeping keepalive timer
		self.recv_timer = ReceiveTimer(self.me,proto.negotiated.holdtime,4,0)
		# Read KEEPALIVE
		for message in self._['out']['proto'].read_keepalive():
			self.recv_timer.check_ka(message)
			yield ACTION.NOW

		self._['out']['state'] = STATE.ESTABLISHED
		# let the caller know that we were sucesfull
		yield ACTION.NOW

	def _main (self, direction):
		"""yield True if we want to come back to it asap, None if nothing urgent, and False if stopped"""
		if self._teardown:
			raise Notify(6,3)

		proto = self._[direction]['proto']

		# Announce to the process BGP is up
		self.logger.network('Connected to peer %s (%s)' % (self.neighbor.name(),direction))
		if self.neighbor.api['neighbor-changes']:
			try:
				self.reactor.processes.up(self)
			except ProcessError:
				# Can not find any better error code than 6,0 !
				# XXX: We can not restart the program so this will come back again and again - FIX
				# XXX: In the main loop we do exit on this kind of error
				raise Notify(6,0,'ExaBGP Internal error, sorry.')

		send_eor = not self.neighbor.manual_eor
		new_routes = None
		self._resend_routes = SEND.NORMAL
		send_families = []

		# Every last asm message should be re-announced on restart
		for family in self.neighbor.asm:
			if family in self.neighbor.families():
				self.neighbor.messages.appendleft(self.neighbor.asm[family])

		operational = None
		refresh = None
		command_eor = None
		number = 0
		refresh_enhanced = True if proto.negotiated.refresh == REFRESH.ENHANCED else False

		self.send_ka = KA(self.me,proto)

		while not self._teardown:
			for message in proto.read_message():
				self.recv_timer.check_ka(message)

				if self.send_ka() is not False:
					# we need and will send a keepalive
					while self.send_ka() is None:
						yield ACTION.NOW

				# Received update
				if message.TYPE == Update.TYPE:
					number += 1

					self.logger.routes(LazyFormat(self.me('<< UPDATE (%d)' % number),message.attributes,lambda _: "%s%s" % (' attributes' if _ else '',_)))

					for nlri in message.nlris:
						self.neighbor.rib.incoming.insert_received(Change(nlri,message.attributes))
						self.logger.routes(LazyFormat(self.me('<< UPDATE (%d) nlri ' % number),nlri,str))

				elif message.TYPE == RouteRefresh.TYPE:
					if message.reserved == RouteRefresh.request:
						self._resend_routes = SEND.REFRESH
						send_families.append((message.afi,message.safi))

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
							refresh = proto.new_refresh(new_refresh)

					if refresh:
						try:
							refresh.next()
						except StopIteration:
							refresh = None

				# Take the routes already sent to that peer and resend them
				if self._reconfigure:
					self._reconfigure = False

					# we are here following a configuration change
					if self._neighbor:
						# see what changed in the configuration
						self.neighbor.rib.outgoing.replace(self._neighbor.backup_changes,self._neighbor.changes)
						# do not keep the previous routes in memory as they are not useful anymore
						self._neighbor.backup_changes = []

					self._have_routes = True

				# Take the routes already sent to that peer and resend them
				if self._resend_routes != SEND.DONE:
					enhanced = True if refresh_enhanced and self._resend_routes == SEND.REFRESH else False
					self._resend_routes = SEND.DONE
					self.neighbor.rib.outgoing.resend(send_families,enhanced)
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
					for _ in proto.new_eors():
						yield ACTION.NOW
					self.logger.message(self.me('>> EOR(s)'))

				# SEND MANUAL KEEPALIVE (only if we have no more routes to send)
				elif not command_eor and self.neighbor.eor:
						new_eor = self.neighbor.eor.popleft()
						command_eor = proto.new_eors(new_eor.afi,new_eor.safi)

				if command_eor:
					try:
						command_eor.next()
					except StopIteration:
						command_eor = None

				if new_routes or message.TYPE != NOP.TYPE:
					yield ACTION.NOW
				elif self.neighbor.messages or operational:
					yield ACTION.NOW
				elif self.neighbor.eor or command_eor:
					yield ACTION.NOW
				else:
					yield ACTION.LATER

				# read_message will loop until new message arrives with NOP
				if self._teardown:
					break

		# If graceful restart, silent shutdown
		if self.neighbor.graceful_restart and proto.negotiated.sent_open.capabilities.announced(Capability.CODE.GRACEFUL_RESTART):
			self.logger.network('Closing the session without notification','error')
			proto.close('graceful restarted negotiated, closing without sending any notification')
			raise NetworkError('closing')

		# notify our peer of the shutdown
		raise Notify(6,self._teardown)

	def _run (self, direction):
		"""yield True if we want the reactor to give us back the hand with the same peer loop, None if we do not have any more work to do"""
		try:
			for action in self._[direction]['code']():
				yield action

			for action in self._main(direction):
				yield action

		# CONNECTION FAILURE
		except NetworkError,network:
			self._reset(direction,'closing connection',network)

			# we tried to connect once, it failed, we stop
			if self.once:
				self.logger.network('only one attempt to connect is allowed, stopping the peer')
				self.stop()
			return

		# NOTIFY THE PEER OF AN ERROR
		except Notify,notify:
			for direction in ['in','out']:
				if self._[direction]['proto']:
					try:
						generator = self._[direction]['proto'].new_notification(notify)
						try:
							maximum = 20
							while maximum:
								generator.next()
								maximum -= 1
								yield ACTION.NOW if maximum > 10 else ACTION.LATER
						except StopIteration:
							pass
					except (NetworkError,ProcessError):
						self.logger.network(self.me('NOTIFICATION NOT SENT'),'error')
					self._reset(direction,'notification sent (%d,%d)' % (notify.code,notify.subcode),notify)
				else:
					self._reset(direction)
			return

		# THE PEER NOTIFIED US OF AN ERROR
		except Notification,notification:
			self._reset(direction,'notification received (%d,%d)' % (notification.code,notification.subcode),notification)

			# we tried to connect once, it failed, we stop
			if self.once:
				self.logger.network('only one attempt to connect is allowed, stopping the peer')
				self.stop()
			return

		# RECEIVED a Message TYPE we did not expect
		except Message,message:
			self._reset(direction,'unexpected message received',message)
			return

		# PROBLEM WRITING TO OUR FORKED PROCESSES
		except ProcessError, process:
			self._reset(direction,'process problem',process)
			return

		# ....
		except Interrupted,interrupt:
			self._reset(interrupt.direction)
			return

		# UNHANDLED PROBLEMS
		except Exception,exc:
			# Those messages can not be filtered in purpose
			self.logger.raw('\n'.join([
				no_panic,
				self.me(''),
				'',
				str(type(exc)),
				str(exc),
				trace(),
				footer
			]))
			self._reset(direction)
			return
	# loop

	def run (self):
		back = ACTION.LATER if self._restart else ACTION.CLOSE

		for direction in ['in','out']:
			opposite = 'out' if direction == 'in' else 'in'

			generator = self._[direction]['generator']
			if generator:
				try:
					# This generator only stops when it raises
					r = generator.next()

					# if r is ACTION.NOW: status = 'immediately'
					# elif r is ACTION.LATER:   status = 'next second'
					# elif r is ACTION.CLOSE:   status = 'stop'
					# else: status = 'buggy'
					# self.logger.network('%s loop %11s, state is %s' % (direction,status,self._[direction]['state']),'debug')

					if r == ACTION.NOW:
						back = ACTION.NOW
					elif r == ACTION.LATER:
						back = ACTION.LATER if back != ACTION.NOW else ACTION.NOW
				except StopIteration:
					# Trying to run a closed loop, no point continuing
					self._[direction]['generator'] = self._[direction]['enabled']

			elif generator is None:
				if self._[opposite]['state'] in [STATE.OPENCONFIRM,STATE.ESTABLISHED]:
					self.logger.network('%s loop, stopping, other one is established' % direction,'debug')
					self._[direction]['generator'] = False
					continue
				if direction == 'out' and self._skip_time > time.time():
					self.logger.network('%s loop, skipping, not time yet' % direction,'debug')
					back = ACTION.LATER
					continue
				if self._restart:
					self.logger.network('%s loop, intialising' % direction,'debug')
					self._[direction]['generator'] = self._run(direction)
					back = ACTION.LATER  # make sure we go through a clean loop

		return back
