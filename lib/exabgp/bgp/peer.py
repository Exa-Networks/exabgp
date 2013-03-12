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
from exabgp.bgp.message import Failure
from exabgp.bgp.message.nop import NOP
from exabgp.bgp.message.open.capability.id import CapabilityID
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.keepalive import KeepAlive
from exabgp.bgp.message.notification import Notification, Notify
#from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.protocol import Protocol
from exabgp.bgp.connection import NotConnected
from exabgp.structure.processes import ProcessError

from exabgp.structure.environment import environment
from exabgp.structure.log import Logger

# reporting the number of routes we saw
class RouteCounter (object):
	def __init__ (self,me,interval=3):
		self.logger = Logger()

		self.me = me
		self.interval = interval
		self.last_update = time.time()
		self.count = 0
		self.last_count = 0

	def display (self):
		left = int(self.last_update  + self.interval - time.time())
		if left <=0:
			self.last_update = time.time()
			if self.count > self.last_count:
				self.last_count = self.count
				self.logger.supervisor(self.me('processed %d routes' % self.count))

	def increment (self,count):
		self.count += count

# As we can not know if this is our first start or not, this flag is used to
# always make the program act like it was recovering from a failure
# If set to FALSE, no EOR and OPEN Flags set for Restart will be set in the
# OPEN Graceful Restart Capability
FORCE_GRACEFUL = True

# Present a File like interface to socket.socket

class Peer (object):
	def __init__ (self,neighbor,supervisor):
		self.logger = Logger()
		self.supervisor = supervisor
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

		# We want to clear the buffer of unsent routes
		self._clear_routes_buffer = None

		# We have routes following a reload (or we just started)
		self._have_routes = True

		# We only to try to connect via TCP once
		self.once = environment.settings().tcp.once

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
		self.neighbor.set_routes(routes)
		self._have_routes = True
		self._clear_routes_buffer = True
		self._reset_skip()

	def restart (self,restart_neighbor=None):
		# we want to tear down the session and re-establish it
		self._running = False
		self._restart = True
		self._restarted = True
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
			self.bgp.close('safety shutdown before unregistering peer, session should already be closed, report if seen in anywhere')
			self.supervisor.unschedule(self)

	def _run (self):
		try:
			if self.supervisor.processes.broken(self.neighbor.peer_address):
				# XXX: we should perhaps try to restart the process ??
				self.logger.error('ExaBGP lost the helper process for this peer - stopping','process')
				self._running = False

			self.bgp = Protocol(self)
			self.bgp.connect()

			self._reset_skip()

			# The reload() function is called before we get it and it will set this value we do not want on startup
			self._clear_routes_buffer = False

			#
			# SEND OPEN
			#

			_open = self.bgp.new_open(self._restarted)
			yield None

			#
			# READ OPEN
			#

			# XXX: put that timer timer in the configuration
			opentimer = Timer(self.me,10.0,1,1,'waited for open too long')
			opn = NOP()

			while opn.TYPE == NOP.TYPE:
				opn = self.bgp.read_open(_open,self.neighbor.peer_address.ip)
				opentimer.tick()
				if not self._running:
					return
				yield None

			#
			# Start keeping keepalive timer
			#

			timer = Timer(self.me,self.bgp.negotiated.holdtime,4,0)

			#
			# READ KEEPALIVE
			#

			while True:
				message = self.bgp.read_keepalive(' (OPENCONFIRM)')
				timer.tick(message)
				# KEEPALIVE or NOP
				if message.TYPE == KeepAlive.TYPE:
					break
				if not self._running:
					return
				yield None

			#
			# SEND KEEPALIVE
			#

			message = self.bgp.new_keepalive(' (ESTABLISHED)')
			yield True


			#
			# ANNOUNCE TO THE PROCESS BGP IS UP
			#

			self.logger.network('Connected to peer %s' % self.neighbor.name())
			if self.neighbor.api.neighbor_changes:
				try:
					self.supervisor.processes.up(self.neighbor.peer_address)
				except ProcessError:
					# Can not find any better error code than 6,0 !
					# XXX: We can not restart the program so this will come back again and again - FIX
					# XXX: In the main loop we do exit on this kind of error
					raise Notify(6,0,'ExaBGP Internal error, sorry.')


			#
			# SENDING OUR ROUTING TABLE
			#

			# Dict with for each AFI/SAFI pair if we should announce ADDPATH Path Identifier

			for count in self.bgp.new_update():
				yield True

			if self.bgp.negotiated.families:
				self.bgp.new_eors()
			else:
				# If we are not sending an EOR, send a keepalive as soon as when finished
				# So the other routers knows that we have no (more) routes to send ...
				# (is that behaviour documented somewhere ??)
				c,k = self.bgp.new_keepalive('KEEPALIVE (EOR)')

			#
			# MAIN UPDATE LOOP
			#

			counter = RouteCounter(self.me)

			while self._running:
				#
				# SEND KEEPALIVES
				#

				if timer.keepalive():
					self.bgp.new_keepalive()

				#
				# READ MESSAGE
				#

				message = self.bgp.read_message()
				timer.tick(message)

				#
				# UPDATE
				#

				if message.TYPE == Update.TYPE:
					counter.increment(len(message.routes))

				#
				# GIVE INFORMATION ON THE NUMBER OF ROUTES SEEN
				#

				counter.display()

				#
				# IF WE RELOADED, CLEAR THE BUFFER WE MAY HAVE QUEUED AND NOT YET SENT
				#

				if self._clear_routes_buffer:
					self._clear_routes_buffer = False
					self.bgp.clear_buffer()

				#
				# GIVE INFORMATION ON THE NB OF BUFFERED ROUTES
				#

				nb_pending = self.bgp.buffered()
				if nb_pending:
					self.logger.supervisor(self.me('BUFFERED MESSAGES  (%d)' % nb_pending))
					count = 0

				#
				# SEND UPDATES (NEW OR BUFFERED)
				#

				# If we have reloaded, reset the RIB information

				if self._have_routes:
					self._have_routes = False
					self.logger.supervisor(self.me('checking for new routes to send'))

					for count in self.bgp.new_update():
						yield True

				# emptying the buffer of routes

				elif self.bgp.buffered():
					for count in self.bgp.new_update():
						yield True

				#
				# Go to other Peers
				#

				yield None

			#
			# IF GRACEFUL RESTART, SILENT SHUTDOWN
			#

			if self.neighbor.graceful_restart and opn.capabilities.announced(CapabilityID.GRACEFUL_RESTART):
				self.logger.error('Closing the connection without notification','supervisor')
				self.bgp.close('graceful restarted negotiated, closing without sending any notification')
				return

			#
			# NOTIFYING OUR PEER OF THE SHUTDOWN
			#

			raise Notify(6,3)

		#
		# CONNECTION FAILURE, UPDATING TIMERS FOR BACK-OFF
		#

		except NotConnected, e:
			self.logger.network('we can not connect to the peer, reason : %s' % str(e).lower())
			self._more_skip()
			self.bgp.clear_buffer()
			try:
				self.bgp.close('could not connect to the peer')
			except Failure:
				pass

			# we tried to connect once, it failed, we stop
			if self.once:
				self.logger.network('only one attempt to connect is allowed, stoping the peer')
				self.stop()

			return

		#
		# NOTIFY THE PEER OF AN ERROR
		#

		except Notify,e:
			self.logger.error(self.me('>> NOTIFICATION (%d,%d) to peer [%s] %s' % (e.code,e.subcode,str(e),e.data)),'supervisor')
			self.bgp.clear_buffer()
			try:
				self.bgp.new_notification(e)
			except Failure:
				self.logger.error(self.me('NOTIFICATION NOT SENT','supervisor'))
				pass
			try:
				self.bgp.close('notification sent (%d,%d) [%s] %s' % (e.code,e.subcode,str(e),e.data))
			except Failure:
				self.logger.error(self.me('issue cleaning session','supervisor'))
			return

		#
		# THE PEER NOTIFIED US OF AN ERROR
		#

		except Notification, e:
			self.logger.error(self.me('Received Notification (%d,%d) %s' % (e.code,e.subcode,str(e))),'supervisor')
			self.bgp.clear_buffer()
			try:
				self.bgp.close('notification received (%d,%d) %s' % (e.code,e.subcode,str(e)))
			except Failure:
				pass
			return

		#
		# OTHER FAILURES
		#

		except Failure, e:
			self.logger.error(self.me(str(e)),'supervisor')
			self._more_skip()
			self.bgp.clear_buffer()
			try:
				self.bgp.close('failure %s' % str(e))
			except Failure:
				pass
			return

		#
		# UNHANDLED PROBLEMS
		#

		except Exception, e:
			self.logger.error(self.me('UNHANDLED EXCEPTION'),'supervisor')
			self._more_skip()
			self.bgp.clear_buffer()
			# XXX: we need to read this from the env.
			if True:
				traceback.print_exc(file=sys.stdout)
				raise
			else:
				self.logger.error(self.me(str(e)),'supervisor')
			if self.bgp: self.bgp.close('internal problem %s' % str(e))
			return
